import * as vscode from 'vscode';
import * as path from 'path';
import * as os from 'os';
import * as fs from 'fs';
import * as http from 'http';
import * as cp from 'child_process';
import * as hive from './hive';
import * as library from './library';
import { LiveSession } from './live';

export let loadedLibrary: library.Library | undefined;
export let libraryProvider: LibraryViewProvider | undefined;
export let modelsProvider: ModelsViewProvider | undefined;

let selection: hive.Selection | undefined;
const verdicts = new Map<string, hive.Verdict>();
let status: vscode.StatusBarItem;

export const activity = new hive.ActivityBuffer();
export let lastTrackResult: hive.TrackResult | undefined;
export let lastNeeds: hive.Need[] = [];
let lastNotificationTime = 0;
const excludedNowSkills = new Set<string>();

let extContext: vscode.ExtensionContext | undefined;
let sessionStats: hive.SessionStats = hive.defaultSessionStats();
let baselineSelection: hive.Selection | undefined;
let currentInclude: string[] = [];
let currentExclude: string[] = [];
let currentDiff: { added: string[]; removed: string[] } | undefined;

function getEditorSelection(): string | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return undefined;
  const text = editor.document.getText(editor.selection).trim();
  return text.length > 0 && text.length <= 300 ? text : undefined;
}

function config() {
  const c = vscode.workspace.getConfiguration('sfpHive');
  return {
    opts: { sfpPath: c.get<string>('sfpPath') || undefined, python: c.get<string>('python') || undefined },
    max: c.get<number>('maxSkills', 4),
    copy: c.get<boolean>('copyPromptAfterChoosing', true),
    tool: c.get<string>('installTool', 'antigravity'),
    follow: c.get<boolean>('follow', true),
    followCommands: c.get<boolean>('followCommands', true),
    autoAttach: c.get<boolean>('autoAttach', true),
    autoAttachDelayMs: c.get<number>('autoAttachDelayMs', 200),
    autoRefreshSeconds: c.get<number>('autoRefreshSeconds', 5),
    autoSkills: c.get<boolean>('autoSkills', true),
    autoSkillsFile: c.get<string>('autoSkillsFile', '.agents/rules/sfp-active-skills.md'),
  };
}

function sfpRoot(): string | undefined {
  const root = hive.findSfpRoot(config().opts);
  if (!root) {
    void vscode.window
      .showErrorMessage('SFP Hive could not find your SFP checkout. Install SFP, or set sfpHive.sfpPath.', 'Open settings')
      .then((pick) => pick && vscode.commands.executeCommand('workbench.action.openSettings', 'sfpHive.sfpPath'));
  }
  return root;
}

function project(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

export let lastDoctorResult: hive.DoctorResult | undefined;

// ---- automatic skills: keep the agent's rule file in step with what the hive chose
let autoSeenSelection: unknown;
let autoSeenTrack: unknown;
let autoSource: 'task' | 'activity' | undefined;
let autoLastText = '';
export let autoSkillsInfo: { enabled: boolean; file?: string; count: number; updated?: number; source?: string } = { enabled: false, count: 0 };

function historyFile(): string {
  return path.join(process.env.SFP_DATA_DIR || path.join(os.homedir(), '.sfp'), 'skill_history.jsonl');
}

/** Keep a local record of what the agent was given, for which prompt or phase (in the data folder, never shared). */
function recordHistory(active: hive.ActiveSkills) {
  try {
    const f = historyFile();
    fs.mkdirSync(path.dirname(f), { recursive: true });
    fs.appendFileSync(f, JSON.stringify(hive.historyEntry(active)) + '\n', 'utf8');
  } catch { /* history is a convenience; never block the agent on it */ }
}

export function loadHistory(limit = 20): hive.HistoryEntry[] {
  try {
    return hive.readHistory(fs.readFileSync(historyFile(), 'utf8'), limit);
  } catch {
    return [];
  }
}

/** Write the rule file if what the agent should have has changed. The newest of the two decides: a task you chose, or the
 * phase the hive follows. Returns the file written, if any. */
export function writeActiveSkills(): string | undefined {
  const cfg = config();
  const root = sfpRoot();
  const ws = project();
  autoSkillsInfo = { ...autoSkillsInfo, enabled: cfg.autoSkills };
  if (!cfg.autoSkills || !root || !ws) return undefined;
  if (selection !== autoSeenSelection) { autoSeenSelection = selection; if (selection) autoSource = 'task'; }
  if (lastTrackResult !== autoSeenTrack) { autoSeenTrack = lastTrackResult; if (lastTrackResult?.skills?.length) autoSource = 'activity'; }
  let active: hive.ActiveSkills | undefined;
  if (autoSource === 'task' && selection) {
    active = { source: 'task', task: selection.task, skills: selection.stack,
      bundles: selection.bundle ? [{ name: selection.bundle.name, skills: selection.stack.map((x) => x.name) }] : [] };
  } else if (autoSource === 'activity' && lastTrackResult) {
    const t = lastTrackResult;
    active = { source: 'activity', phase: t.phase, confidence: t.confidence, skills: t.skills || [], bundles: (t.bundles || []).map((b) => ({ name: b.name, skills: b.skills })) };
  }
  if (!active) return undefined;
  const text = hive.activeSkillsRule(active, root);
  const body = text.replace(/^Updated .*$/m, '');                  // the time alone is not a change
  const file = path.resolve(ws, cfg.autoSkillsFile);
  if (!file.startsWith(path.resolve(ws) + path.sep)) return undefined;   // never outside the workspace
  if (body === autoLastText) return undefined;
  try {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, text, 'utf8');
    autoLastText = body;
    const names = new Set([...active.skills.map((s) => s.name), ...(active.bundles || []).flatMap((b) => b.skills)]);
    autoSkillsInfo = { enabled: true, file: path.relative(ws, file), count: names.size, updated: Date.now(), source: active.source };
    recordHistory(active);
    return file;
  } catch {
    return undefined;
  }
}

export function isFirstRun(): boolean {
  try {
    const p = path.join(process.env.SFP_DATA_DIR || path.join(os.homedir(), '.sfp'), 'decisions.jsonl');
    if (!fs.existsSync(p)) return true;
    const content = fs.readFileSync(p, 'utf8').trim();
    return content.length === 0;
  } catch {
    return true;
  }
}

function showStatus() {
  if (lastDoctorResult && lastDoctorResult.status === 'fail') {
    const firstFail = lastDoctorResult.checks.find((c) => c.status === 'fail');
    status.text = `$(warning) Hive: ${firstFail?.name || 'Connection issue'}`;
    status.tooltip = firstFail ? `${firstFail.name}: ${firstFail.detail}` : 'SFP Hive connection check failed';
    return;
  }
  const bundleName = selection?.bundle?.name || (selection?.task?.startsWith('Bundle: ') ? selection.task.slice(8) : undefined);
  if (bundleName) {
    status.text = `$(organization) Hive: ${bundleName}`;
    status.tooltip = `Bundle: ${bundleName}`;
  } else if (selection) {
    status.text = `$(organization) Hive: ${selection.stack.length}`;
    status.tooltip = `Chosen for: ${selection.task}`;
  } else {
    status.text = '$(organization) Hive';
    status.tooltip = 'Choose skills for a task';
  }
}

export async function checkNeeds(task: string): Promise<hive.Need[]> {
  const root = sfpRoot();
  if (!root || !task.trim()) return [];
  try {
    const py = hive.pythonCommand(config().opts);
    // Fast first: matching the task takes about 100 ms. Checking programs and keys (--check) takes up to a second, so it
    // only runs when the task needs something, and the cards appear before it finishes.
    const quick = hive.parseNeeds(await hive.run(py, hive.needsArgs(root, task.trim(), project(), false)));
    lastNeeds = quick;
    studioProvider?.updateNeeds(quick);
    if (!quick.length) return quick;
    const checked = hive.parseNeeds(await hive.run(py, hive.needsArgs(root, task.trim(), project(), true)));
    lastNeeds = checked;
    studioProvider?.updateNeeds(checked);
    return checked;
  } catch {
    return [];
  }
}

export async function runDoctor(interactive = false): Promise<hive.DoctorResult> {
  const root = hive.findSfpRoot(config().opts);
  if (!root) {
    const res: hive.DoctorResult = {
      status: 'fail',
      checks: [
        {
          name: 'SFP checkout',
          status: 'fail',
          detail: 'Could not find your SFP checkout',
          fix: 'Open settings and set sfpHive.sfpPath',
        },
      ],
    };
    lastDoctorResult = res;
    showStatus();
    studioProvider?._view?.webview.postMessage({ type: 'doctorResult', result: res });
    modelsProvider?._view?.webview.postMessage({ type: 'doctorResult', result: res });
    if (interactive) {
      studioProvider?.showTab('insights');
      studioProvider?.focus();
    }
    return res;
  }

  try {
    const cfg = config();
    const out = await hive.run(
      hive.pythonCommand(cfg.opts),
      hive.doctorArgs(root, project(), routerPort),
      15000
    );
    const res = hive.parseDoctor(out);
    lastDoctorResult = res;
    showStatus();
    studioProvider?._view?.webview.postMessage({ type: 'doctorResult', result: res });
    modelsProvider?._view?.webview.postMessage({ type: 'doctorResult', result: res });
    if (interactive) {
      studioProvider?.showTab('insights');
      studioProvider?.focus();
    }
    return res;
  } catch (err: any) {
    try {
      const match = (err.message || '').match(/\{[\s\S]*"checks"[\s\S]*\}/);
      if (match) {
        const res = hive.parseDoctor(match[0]);
        lastDoctorResult = res;
        showStatus();
        studioProvider?._view?.webview.postMessage({ type: 'doctorResult', result: res });
        modelsProvider?._view?.webview.postMessage({ type: 'doctorResult', result: res });
        if (interactive) {
          studioProvider?.showTab('insights');
          studioProvider?.focus();
        }
        return res;
      }
    } catch {}

    const res: hive.DoctorResult = {
      status: 'fail',
      checks: [
        {
          name: 'Doctor execution',
          status: 'fail',
          detail: err.message || 'Failed to run doctor command',
          fix: 'Check Python installation and permissions',
        },
      ],
    };
    lastDoctorResult = res;
    showStatus();
    studioProvider?._view?.webview.postMessage({ type: 'doctorResult', result: res });
    modelsProvider?._view?.webview.postMessage({ type: 'doctorResult', result: res });
    if (interactive) {
      studioProvider?.showTab('insights');
      studioProvider?.focus();
    }
    return res;
  }
}

export async function flushActivity(): Promise<hive.TrackResult | undefined> {
  const root = sfpRoot();
  if (!root) return;
  const cfg = config();
  if (!cfg.follow) return;
  const events = activity.take();
  if (!events.length) return;
  try {
    const out = await hive.run(
      hive.pythonCommand(cfg.opts),
      hive.trackArgs(root, project(), cfg.max),
      15000,
      JSON.stringify(events)
    );
    const result = hive.parseTrack(out);
    lastTrackResult = result;
    studioProvider?.updateTrackResult(result);
    if (result.phase) {
      updateRightStatus(result.phase[0].toUpperCase() + result.phase.slice(1), result.skills?.length);
    }
    const now = Date.now();
    if (hive.shouldNotifyPhaseChange(lastNotificationTime, now, result.changed, result.confidence)) {
      lastNotificationTime = now;
      void vscode.window.showInformationMessage(
        `SFP Hive: Phase moved to ${result.phase} (${Math.round(result.confidence * 100)}% confidence).`,
        'Use these skills'
      ).then((action) => {
        if (action === 'Use these skills') {
          if (result.skills && result.skills.length) {
            selection = {
              task: `Phase: ${result.phase}`,
              stack: result.skills,
              layers: {
                base: result.skills.filter((s) => s.layer === 'base').map((s) => s.name),
                check: result.skills.filter((s) => s.layer === 'check').map((s) => s.name),
                finish: result.skills.filter((s) => s.layer === 'finish').map((s) => s.name),
              },
              tokens: result.skills.reduce((acc, s) => acc + (s.tokens || 0), 0),
              next: (result.next || []).map((n) => ({ name: n.phase, probability: n.probability })),
            };
            studioProvider?.syncState();
            if (cfg.copy) {
              void vscode.env.clipboard.writeText(hive.buildPrompt(selection, root));
            }
          }
          studioProvider?.showTab('now');
        }
      });
    }
    return result;
  } catch {
    // quiet fail or transient error
  }
}

async function choose(preset?: string, steer?: hive.Steer) {
  const root = sfpRoot();
  if (!root) return;
  const task = preset ?? getEditorSelection() ?? (await vscode.window.showInputBox({ prompt: 'What are you about to do?', placeHolder: 'add an accessible signup form', ignoreFocusOut: true }));
  if (!task || !task.trim()) return;
  activity.add({ kind: 'prompt', text: task.trim() });
  const cfg = config();
  const effectiveSteer: hive.Steer = { explain: true, ...(steer || { include: currentInclude, exclude: currentExclude }) };

  await vscode.window.withProgress({ location: vscode.ProgressLocation.Window, title: 'SFP Hive: choosing skills' }, async () => {
    try {
      const out = await hive.run(hive.pythonCommand(cfg.opts), hive.selectArgs(root, task.trim(), project(), cfg.max, effectiveSteer));
      const newSel = hive.parseSelection(out);

      if (!steer) {
        // Fresh choose
        baselineSelection = newSel;
        currentDiff = undefined;
        currentInclude = [];
        currentExclude = [];
        sessionStats = hive.updateSessionStats(sessionStats, { type: 'decision', chosenCount: newSel.stack.length });
        void extContext?.workspaceState?.update('sfpHive.sessionStats', sessionStats);
      } else if (baselineSelection) {
        currentDiff = hive.selectionDiff(baselineSelection, newSel);
      }

      selection = newSel;
      void checkNeeds(task.trim());
      verdicts.clear();
      await vscode.commands.executeCommand('setContext', 'sfpHive.hasSelection', selection.stack.length > 0);
      showStatus();
      updateRightStatus();
      studioProvider?.syncState();
      await vscode.commands.executeCommand('workbench.view.extension.sfpHive');
      if (!selection.stack.length) {
        void vscode.window.showInformationMessage('The hive found no skill that fits that task.');
      } else if (cfg.copy && !steer) {
        await vscode.env.clipboard.writeText(hive.buildPrompt(selection, root));
        void vscode.window.showInformationMessage(`Chose ${selection.stack.length} skills. The prompt is copied: paste it into the agent panel.`);
      }
    } catch (e) {
      void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
    }
  });
}

async function sendFeedback(verdict: hive.Verdict, names: string[]) {
  const root = sfpRoot();
  if (!root || !names.length) return;
  const decision = selection?.decision;
  if (!decision) {
    void vscode.window.showWarningMessage('Feedback is off: SFP_NO_USAGE_LOG is set, so the hive logs nothing and learns nothing.');
    return;
  }
  try {
    await hive.run(hive.pythonCommand(config().opts), hive.feedbackArgs(root, decision, verdict, names, selection?.task));
    names.forEach((n) => verdict !== 'missing' && verdicts.set(n, verdict));
    sessionStats = hive.updateSessionStats(sessionStats, { type: 'feedback', verdict: verdict === 'helped' ? 'helped' : 'unhelpful' });
    void extContext?.workspaceState?.update('sfpHive.sessionStats', sessionStats);
    studioProvider?.syncState();
    void vscode.window.setStatusBarMessage(`SFP Hive: noted ${verdict}: ${names.join(', ')}`, 4000);
  } catch (e) {
    void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
  }
}

function skillOf(arg: unknown): hive.Skill | undefined {
  if (typeof arg === 'string') {
    return (
      selection?.stack.find((s) => s.name === arg) ||
      lastTrackResult?.skills?.find((s) => s.name === arg) ||
      { name: arg, phase: '', tokens: 0 }
    );
  }
  if (arg && typeof arg === 'object') {
    if ('skill' in arg && (arg as any).skill) return (arg as any).skill;
    if ('name' in arg) return arg as hive.Skill;
  }
  return undefined;
}

function terminal(args: (root: string) => string[]) {
  const root = sfpRoot();
  if (!root) return;
  const t = vscode.window.createTerminal({ name: 'SFP', cwd: project() ?? root });
  t.show();
  t.sendText([hive.quote(hive.pythonCommand(config().opts)), ...args(root).map(hive.quote)].join(' '));
}

let loadedClusters: hive.Cluster[] = [];

async function fetchClusters(): Promise<hive.Cluster[]> {
  const root = sfpRoot();
  if (!root) return [];
  try {
    const out = await hive.run(hive.pythonCommand(config().opts), hive.clustersArgs(root));
    loadedClusters = hive.parseClusters(out);
    return loadedClusters;
  } catch {
    return loadedClusters;
  }
}

async function clusterAddWorkflow(preselectedSkill?: string) {
  const root = sfpRoot();
  if (!root) return;
  const name = await vscode.window.showInputBox({
    prompt: 'Name your new skill cluster',
    placeHolder: 'e.g., My Go Stack',
    ignoreFocusOut: true,
  });
  if (!name || !name.trim()) return;

  const description = (await vscode.window.showInputBox({
    prompt: 'Description for this cluster (optional)',
    placeHolder: 'e.g., Everyday skills for Go microservices',
    ignoreFocusOut: true,
  })) || '';

  const allSkills = hive.catalogNames(root);
  let picked: string[] = [];
  if (preselectedSkill) {
    picked = [preselectedSkill];
    const others = await vscode.window.showQuickPick(
      allSkills.filter((s) => s !== preselectedSkill),
      {
        canPickMany: true,
        placeHolder: `Add more skills to "${name.trim()}" (already includes ${preselectedSkill})`,
      }
    );
    if (others && others.length) picked.push(...others);
  } else {
    const picks = await vscode.window.showQuickPick(allSkills, {
      canPickMany: true,
      placeHolder: `Pick skills for "${name.trim()}"`,
    });
    if (!picks || !picks.length) return;
    picked = picks;
  }

  try {
    await hive.run(
      hive.pythonCommand(config().opts),
      hive.clusterAddArgs(root, name.trim(), picked, description.trim())
    );
    await fetchClusters();
    studioProvider?.syncState();
    void vscode.window.showInformationMessage(`Created cluster "${name.trim()}" with ${picked.length} skills.`);
  } catch (e) {
    void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
  }
}

async function clusterRemoveWorkflow(clusterName?: string) {
  const root = sfpRoot();
  if (!root) return;
  let target = clusterName;
  if (!target) {
    const userClusts = loadedClusters.filter((c) => c.mine);
    if (!userClusts.length) {
      void vscode.window.showInformationMessage('You have no custom clusters to remove.');
      return;
    }
    target = await vscode.window.showQuickPick(userClusts.map((c) => c.name), {
      placeHolder: 'Select a custom cluster to remove',
    });
  }
  if (!target) return;

  const confirm = await vscode.window.showWarningMessage(
    `Remove cluster "${target}"?`,
    { modal: true },
    'Remove'
  );
  if (confirm !== 'Remove') return;

  try {
    await hive.run(hive.pythonCommand(config().opts), hive.clusterRemoveArgs(root, target));
    await fetchClusters();
    studioProvider?.syncState();
    void vscode.window.showInformationMessage(`Removed cluster "${target}".`);
  } catch (e) {
    void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
  }
}

async function addSkillToMyClusterWorkflow(skill: string) {
  const root = sfpRoot();
  if (!root || !skill) return;
  const userClusts = loadedClusters.filter((c) => c.mine);
  const CREATE_NEW = '$(plus) Create new cluster...';
  const items = [CREATE_NEW, ...userClusts.map((c) => c.name)];
  const pick = await vscode.window.showQuickPick(items, {
    placeHolder: `Add "${skill}" to which cluster?`,
  });
  if (!pick) return;
  if (pick === CREATE_NEW) {
    await clusterAddWorkflow(skill);
    return;
  }
  const target = userClusts.find((c) => c.name === pick);
  if (!target) return;
  const skills = Array.from(new Set([...target.skills.map((s) => s.name), skill]));
  try {
    await hive.run(
      hive.pythonCommand(config().opts),
      hive.clusterAddArgs(root, target.name, skills, target.description)
    );
    await fetchClusters();
    studioProvider?.syncState();
    void vscode.window.showInformationMessage(`Added "${skill}" to "${target.name}".`);
  } catch (e) {
    void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
  }
}

async function pinSkillWorkflow(skillName: string) {
  if (!currentInclude.includes(skillName)) {
    currentInclude.push(skillName);
  }
  currentExclude = currentExclude.filter((s) => s !== skillName);
  await choose(selection?.task, { include: currentInclude, exclude: currentExclude, explain: true });
  studioProvider?.showTab('choose');
  void vscode.window.showInformationMessage(`Pinned "${skillName}" to current task.`);
}

async function applyBundleWorkflow(bundleId: string) {
  const root = sfpRoot();
  if (!root) return;
  if (!loadedLibrary) await libraryProvider?.loadLibrary();
  const bundle = loadedLibrary?.bundles.find((b) => b.id === bundleId);
  if (!bundle) return;
  const cfg = config();
  try {
    const task = `Bundle: ${bundle.name}`;
    const out = await hive.run(
      hive.pythonCommand(cfg.opts),
      hive.selectArgs(root, task, project(), cfg.max, { bundle: bundle.id })
    );
    const sel = hive.parseSelection(out);
    sel.task = task;
    (sel as any).bundleName = bundle.name;
    selection = sel;
    baselineSelection = sel;
    currentInclude = sel.stack.map((s) => s.name);
    currentExclude = [];
    currentDiff = undefined;
    sessionStats = hive.updateSessionStats(sessionStats, { type: 'decision', chosenCount: sel.stack.length });
    void extContext?.workspaceState?.update('sfpHive.sessionStats', sessionStats);
    showStatus();
    studioProvider?.syncState();
    studioProvider?.showTab('choose');
    if (cfg.copy) {
      await vscode.env.clipboard.writeText(hive.buildPrompt(sel, root));
    }
    void vscode.window.showInformationMessage(`Applied bundle "${bundle.name}". Skills pinned in Choose.`);
  } catch (e) {
    void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
  }
}

async function copyPromptWorkflow(bundleId: string) {
  const root = sfpRoot();
  if (!root) return;
  if (!loadedLibrary) await libraryProvider?.loadLibrary();
  const bundle = loadedLibrary?.bundles.find((b) => b.id === bundleId);
  if (!bundle) return;
  const cfg = config();
  try {
    const out = await hive.run(
      hive.pythonCommand(cfg.opts),
      hive.selectArgs(root, `Bundle: ${bundle.name}`, project(), cfg.max, { bundle: bundle.id })
    );
    const sel = hive.parseSelection(out);
    await vscode.env.clipboard.writeText(hive.buildPrompt(sel, root));
    void vscode.window.showInformationMessage(`Prompt copied for bundle "${bundle.name}".`);
  } catch (e) {
    void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
  }
}

/** "Add a skill from Git": convert a repository into a skill, install it for the chosen tool, and offer to open it. */
async function addSkillFromGitWorkflow(initial?: string) {
  const root = sfpRoot();
  if (!root) {
    void vscode.window.showWarningMessage('SFP checkout not found. Set sfpHive.sfpPath.');
    return;
  }
  const source = initial ?? await vscode.window.showInputBox({
    title: 'Add a skill from Git',
    prompt: 'A repository URL, owner/repo, or a folder on this computer',
    placeHolder: 'https://github.com/owner/repo',
    ignoreFocusOut: true,
    validateInput: (v) => (v.trim() && !hive.looksLikeRepo(v) ? 'Enter a URL, owner/repo, or a folder path.' : undefined),
  });
  if (!source || !source.trim()) return;
  const cfg = config();
  try {
    const result = await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: `Creating a skill from ${source.trim()}…` },
      async () => {
        let out = '';
        try {
          out = await hive.run(hive.pythonCommand(cfg.opts), hive.repoToSkillArgs(root, source, [cfg.tool]), 180000);
        } catch (e) {
          out = (e as Error).message;                       // the script prints its JSON error, which hive.run wraps in the message
          const m = out.match(/\{[\s\S]*\}/);
          if (m) out = m[0];
        }
        return hive.parseRepoSkill(out);
      }
    );
    const where = Object.keys(result.installed).length ? ` and installed it for ${Object.keys(result.installed).join(', ')}` : '';
    const pick = await vscode.window.showInformationMessage(`Created the skill "${result.skill_name}" (${result.category})${where}.`, 'Open SKILL.md');
    if (pick === 'Open SKILL.md') {
      await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(result.skill_path), { preview: true });
    }
  } catch (e) {
    void vscode.window.showErrorMessage(`Could not create a skill from that repository. ${(e as Error).message.slice(0, 300)}`);
  }
}

async function newBundleWorkflow(initialSkill?: string) {
  const root = sfpRoot();
  if (!root) return;
  if (!loadedLibrary) await libraryProvider?.loadLibrary();
  if (!loadedLibrary) return;

  const name = await vscode.window.showInputBox({
    prompt: 'Bundle name (e.g. ship-a-feature)',
    placeHolder: 'e.g., ship-a-feature',
    ignoreFocusOut: true,
    validateInput: (v) => (!v.trim() ? 'Name is required' : null),
  });
  if (!name || !name.trim()) return;

  const purposes = loadedLibrary.purposes.map((p) => ({ label: p.name, description: p.id, detail: p.description }));
  const pickedPurpose = await vscode.window.showQuickPick(purposes, {
    placeHolder: 'Select primary purpose for this bundle',
    ignoreFocusOut: true,
  });
  if (!pickedPurpose) return;

  const goal = (await vscode.window.showInputBox({
    prompt: 'Bundle goal (what does it achieve?)',
    placeHolder: 'e.g., Build and test end-to-end',
    ignoreFocusOut: true,
  })) || '';

  const allSkills = Object.keys(loadedLibrary.skills).sort().map((s) => ({
    label: s,
    picked: initialSkill === s,
    description: loadedLibrary?.skills[s]?.d,
  }));
  const pickedSkills = await vscode.window.showQuickPick(allSkills, {
    placeHolder: 'Select skills for this bundle (multi-select)',
    canPickMany: true,
    ignoreFocusOut: true,
  });
  if (!pickedSkills || !pickedSkills.length) return;

  const cfg = config();
  try {
    const skillNames = pickedSkills.map((p) => p.label);
    await hive.run(
      hive.pythonCommand(cfg.opts),
      hive.bundleAddArgs(root, name.trim(), skillNames, goal.trim(), pickedPurpose.description)
    );
    await libraryProvider?.loadLibrary();
    void vscode.window.showInformationMessage(`Bundle "${name.trim()}" created.`);
  } catch (e) {
    void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
  }
}

async function addToBundleWorkflow(skillName: string) {
  const root = sfpRoot();
  if (!root) return;
  if (!loadedLibrary) await libraryProvider?.loadLibrary();
  if (!loadedLibrary) return;

  const myBundles = loadedLibrary.bundles.filter((b) => b.mine);
  const CREATE_NEW = '$(add) New bundle...';
  const items: (vscode.QuickPickItem & { bundleId?: string; action?: string })[] = [
    { label: CREATE_NEW, action: 'new' },
    ...myBundles.map((b) => ({
      label: b.name,
      description: `${b.skills.length} skills`,
      detail: b.goal,
      bundleId: b.id,
    })),
  ];
  const pick = await vscode.window.showQuickPick(items, {
    placeHolder: `Add "${skillName}" to which bundle?`,
    ignoreFocusOut: true,
  });
  if (!pick) return;
  if (pick.action === 'new') {
    await newBundleWorkflow(skillName);
    return;
  }
  const bundle = myBundles.find((b) => b.id === pick.bundleId);
  if (!bundle) return;
  if (bundle.skills.includes(skillName)) {
    void vscode.window.showInformationMessage(`Skill "${skillName}" is already in bundle "${bundle.name}".`);
    return;
  }
  const updatedSkills = [...bundle.skills, skillName];
  const cfg = config();
  try {
    await hive.run(
      hive.pythonCommand(cfg.opts),
      hive.bundleAddArgs(root, bundle.name, updatedSkills, bundle.goal, bundle.purpose, bundle.when)
    );
    await libraryProvider?.loadLibrary();
    void vscode.window.showInformationMessage(`Added "${skillName}" to bundle "${bundle.name}".`);
  } catch (e) {
    void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
  }
}

async function editBundleWorkflow(bundleId: string) {
  const root = sfpRoot();
  if (!root) return;
  if (!loadedLibrary) await libraryProvider?.loadLibrary();
  if (!loadedLibrary) return;
  const bundle = loadedLibrary.bundles.find((b) => b.id === bundleId && b.mine);
  if (!bundle) return;

  const goal = await vscode.window.showInputBox({
    prompt: `Goal for "${bundle.name}"`,
    value: bundle.goal,
    ignoreFocusOut: true,
  });
  if (goal === undefined) return;

  const allSkills = Object.keys(loadedLibrary.skills).sort().map((s) => ({
    label: s,
    picked: bundle.skills.includes(s),
    description: loadedLibrary?.skills[s]?.d,
  }));
  const pickedSkills = await vscode.window.showQuickPick(allSkills, {
    placeHolder: `Skills for "${bundle.name}" (in order)`,
    canPickMany: true,
    ignoreFocusOut: true,
  });
  if (!pickedSkills) return;

  const cfg = config();
  try {
    const skillNames = pickedSkills.map((p) => p.label);
    await hive.run(
      hive.pythonCommand(cfg.opts),
      hive.bundleAddArgs(root, bundle.name, skillNames, goal.trim(), bundle.purpose, bundle.when)
    );
    await libraryProvider?.loadLibrary();
    void vscode.window.showInformationMessage(`Bundle "${bundle.name}" updated.`);
  } catch (e) {
    void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
  }
}

async function deleteBundleWorkflow(bundleId: string) {
  const root = sfpRoot();
  if (!root) return;
  if (!loadedLibrary) await libraryProvider?.loadLibrary();
  const bundle = loadedLibrary?.bundles.find((b) => b.id === bundleId && b.mine);
  if (!bundle) return;

  const confirm = await vscode.window.showWarningMessage(
    `Delete bundle "${bundle.name}"?`,
    { modal: true },
    'Delete'
  );
  if (confirm !== 'Delete') return;

  const cfg = config();
  try {
    await hive.run(hive.pythonCommand(cfg.opts), hive.bundleRemoveArgs(root, bundle.name));
    await libraryProvider?.loadLibrary();
    void vscode.window.showInformationMessage(`Bundle "${bundle.name}" deleted.`);
  } catch (e) {
    void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
  }
}

let rightStatus: vscode.StatusBarItem;
let studioProvider: StudioViewProvider | undefined;

function updateRightStatus(phaseName?: string, skillCount?: number) {
  if (!rightStatus) return;
  const count = skillCount ?? (selection ? selection.stack.length : 0);
  const phase = phaseName ? `${phaseName} · ` : '';
  rightStatus.text = count > 0 ? `$(organization) ${phase}${count}` : `$(organization) Hive`;
  rightStatus.tooltip = selection ? `SFP Hive: ${selection.task} (click to open Now)` : 'SFP Hive: Follow the agent (click to open Now)';
}

export class StudioViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'sfpHive.stack';
  public _view?: vscode.WebviewView;
  public liveSession?: LiveSession;
  public lastLiveResult?: hive.LiveResult;
  public isCollapsed = false;
  private _libQuery = '';
  private _libMode: library.GroupMode = 'family';

  constructor(private readonly extensionPath: string) {
    if (extContext) {
      this.isCollapsed = extContext.workspaceState?.get<boolean>('sfpHive.stackCollapsed', false) ?? false;
    }
  }

  public focus(): void {
    this._view?.show?.(true);
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this.sent.clear();
    this.librarySent = false;
    this._view = webviewView;
    const cfg = config();
    const askLive = async (draft: string, state: hive.LiveState | undefined, change: hive.LiveChange) => {
      const root = sfpRoot();
      if (!root) throw new Error('SFP checkout not found');
      const py = hive.pythonCommand(config().opts);
      const args = hive.liveArgs(root, draft, state, project(), config().max, change);
      const out = await hive.run(py, args);
      if (change.commit && draft.trim()) {
        void checkNeeds(draft.trim());
      }
      return hive.parseLive(out);
    };

    this.liveSession = new LiveSession(
      {
        ask: askLive,
        show: (result) => {
          this.lastLiveResult = result;
          webviewView.webview.postMessage({ type: 'liveResult', result });
        },
        fail: (_err) => {
          // Keep current state without flashing errors while typing
        },
      },
      cfg.autoAttachDelayMs
    );

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.file(path.join(this.extensionPath, 'media'))],
    };
    webviewView.webview.html = this.getHtml(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (message) => {
      switch (message.command) {
        case 'ready':
          this.syncState();
          break;
        case 'toggleCollapse':
          this.isCollapsed = typeof message.collapsed === 'boolean' ? message.collapsed : !this.isCollapsed;
          if (extContext) {
            void extContext.workspaceState?.update('sfpHive.stackCollapsed', this.isCollapsed);
          }
          break;
        case 'liveType':
          if (config().autoAttach && this.liveSession) {
            this.liveSession.type(message.draft ?? '');
          }
          break;
        case 'liveChange':
          if (this.liveSession) {
            await this.liveSession.steer(message.draft ?? '', message.change ?? {});
          }
          break;
        case 'choose':
          if (message.task) {
            if (this.liveSession) {
              await this.liveSession.send(message.task);
            }
            await choose(message.task);
          }
          break;
        case 'feedback':
          if (message.skill && message.verdict) {
            await sendFeedback(message.verdict, [message.skill]);
          }
          break;
        case 'removeSkill':
          if (message.skill) {
            excludedNowSkills.add(message.skill);
            await sendFeedback('unhelpful', [message.skill]);
            if (lastTrackResult?.phase) {
              const root = sfpRoot();
              if (root) {
                try {
                  const cfg = config();
                  const out = await hive.run(
                    hive.pythonCommand(cfg.opts),
                    hive.selectArgs(root, lastTrackResult.phase, project(), cfg.max, {
                      exclude: Array.from(excludedNowSkills),
                    })
                  );
                  const sel = hive.parseSelection(out);
                  lastTrackResult.skills = sel.stack;
                  this.updateTrackResult(lastTrackResult);
                } catch {
                  // keep existing
                }
              }
            }
          }
          break;
        case 'toggleAutoSkills':
          await vscode.commands.executeCommand('sfpHive.toggleAutoSkills');
          break;
        case 'toggleFollow':
          await vscode.workspace.getConfiguration('sfpHive').update('follow', Boolean(message.value), vscode.ConfigurationTarget.Global);
          break;
        case 'refresh':
          await flushActivity();
          this.syncState();
          break;
        case 'openSkill':
          const root = sfpRoot();
          if (root && message.skill) {
            const skill = (selection?.stack || lastTrackResult?.skills)?.find((s) => s.name === message.skill);
            const file = skill ? hive.skillFile(root, skill) : undefined;
            if (file) {
              await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(file), { preview: true });
            }
          }
          break;
        case 'rechoose':
          if (message.include) currentInclude = message.include;
          if (message.exclude) currentExclude = message.exclude;
          await choose(message.task || selection?.task, {
            include: currentInclude,
            exclude: currentExclude,
            explain: true,
          });
          break;
        case 'applyStack':
          if (selection) {
            const root = sfpRoot();
            if (root) {
              await vscode.env.clipboard.writeText(hive.buildPrompt(selection, root));
              void vscode.window.showInformationMessage('Prompt copied. Paste it into the agent panel.');
            }
            if (message.sendFeedback && baselineSelection) {
              const feedbacks = hive.interventionFeedback(baselineSelection, {
                include: currentInclude,
                exclude: currentExclude,
              });
              for (const fb of feedbacks) {
                await sendFeedback(fb.verdict, fb.skills);
              }
            }
            sessionStats = hive.updateSessionStats(sessionStats, {
              type: 'intervention',
              beforeCount: baselineSelection?.stack.length || 0,
              keptCount: Math.max(0, (baselineSelection?.stack.length || 0) - currentExclude.length),
              addedCount: currentInclude.length,
            });
            void extContext?.workspaceState?.update('sfpHive.sessionStats', sessionStats);
            this.syncState();
          }
          break;
        case 'getClusters':
          await fetchClusters();
          this.syncState();
          break;
        case 'newCluster':
          await clusterAddWorkflow();
          break;
        case 'removeCluster':
          if (message.name) await clusterRemoveWorkflow(message.name);
          break;
        case 'pinSkill':
          if (message.skill) {
            if (!currentInclude.includes(message.skill)) currentInclude.push(message.skill);
            currentExclude = currentExclude.filter((s) => s !== message.skill);
            await choose(selection?.task, { include: currentInclude, exclude: currentExclude, explain: true });
            this.showTab('choose');
            void vscode.window.showInformationMessage(`Pinned "${message.skill}" to current task.`);
          }
          break;
        case 'addToMyCluster':
          if (message.skill) await addSkillToMyClusterWorkflow(message.skill);
          break;
        case 'copyPrompt':
          await vscode.commands.executeCommand('sfpHive.copyPrompt');
          break;
        case 'train':
          await vscode.commands.executeCommand('sfpHive.train');
          break;
        case 'openChoose': {
          const t = message.task || selection?.task;
          if (t) {
            void checkNeeds(t);
          }
          break;
        }
        case 'copyNeedAction':
          if (message.action) {
            const raw = message.action;
            const cmd = raw.includes(': ') ? raw.split(': ').slice(1).join(': ').trim() : raw.trim();
            await vscode.env.clipboard.writeText(cmd);
            void vscode.window.showInformationMessage('Action command copied to clipboard.');
          }
          break;
        case 'runNeedAction':
          if (message.action) {
            const raw = message.action;
            const cmd = raw.includes(': ') ? raw.split(': ').slice(1).join(': ').trim() : raw.trim();
            const pick = await vscode.window.showInformationMessage(`Run "${cmd}" in terminal?`, 'Run', 'Cancel');
            if (pick === 'Run') {
              const term = vscode.window.createTerminal('SFP Need');
              term.show();
              term.sendText(cmd, false);
            }
          }
          break;
        case 'focusModels':
          await vscode.commands.executeCommand('sfpHive.focusModels');
          break;
        case 'libRefresh':
          await this.loadLibrary();
          break;
        case 'copyBundlePrompt':
          if (message.bundleId) {
            await copyPromptWorkflow(message.bundleId);
          }
          break;
        case 'libReady':
          if (!loadedLibrary) {
            await this.loadLibrary();
          } else {
            this.syncLibraryState();
          }
          break;
        case 'search':
          this._libQuery = message.query || '';
          this._libMode = message.mode || this._libMode;
          this.performLibrarySearch(this._libQuery, this._libMode);
          break;
        case 'switchMode':
          this._libMode = message.mode || 'family';
          this.performLibrarySearch(this._libQuery, this._libMode);
          break;
        case 'openDetail':
          if (message.skill) {
            await showSkillDetail(String(message.skill));
          }
          break;
        case 'addToBundle':
          if (message.skill) {
            await addToBundleWorkflow(message.skill);
          }
          break;
        case 'applyBundle':
          if (message.bundleId) {
            await applyBundleWorkflow(message.bundleId);
          }
          break;
        case 'newBundle':
          await newBundleWorkflow();
          break;
        case 'addFromGit':
          await addSkillFromGitWorkflow();
          break;
        case 'editBundle':
          if (message.bundleId) {
            await editBundleWorkflow(message.bundleId);
          }
          break;
        case 'deleteBundle':
          if (message.bundleId) {
            await deleteBundleWorkflow(message.bundleId);
          }
          break;
        case 'openSettings':
          void vscode.commands.executeCommand('workbench.action.openSettings', 'sfpHive.sfpPath');
          break;
        case 'notThisBundle':
          if (message.skills && Array.isArray(message.skills)) {
            for (const s of message.skills) {
              if (!currentExclude.includes(s)) currentExclude.push(s);
              currentInclude = currentInclude.filter((x) => x !== s);
            }
            if (this.liveSession) {
              this.liveSession.steer('', { remove: message.skills });
            }
            await choose(selection?.task, { include: currentInclude, exclude: currentExclude, explain: true });
          }
          break;
        case 'attachBundle':
          if (message.bundleId) {
            await applyBundleWorkflow(message.bundleId);
          }
          break;
        case 'fillExample':
          await choose('make the signup form accessible');
          break;
        case 'runDoctor':
          await runDoctor(true);
          break;
        case 'copyFix':
          if (message.fix) {
            await vscode.env.clipboard.writeText(message.fix);
            void vscode.window.showInformationMessage('Fix command copied to clipboard.');
          }
          break;
      }
    });
  }

  public async loadLibrary(): Promise<void> {
    const root = sfpRoot();
    if (!root) {
      this.postLibraryError('SFP checkout not found. Check sfpHive.sfpPath setting.');
      return;
    }
    const cfg = config();
    try {
      const out = await hive.run(hive.pythonCommand(cfg.opts), hive.libraryArgs(root));
      loadedLibrary = hive.parseLibrary(out);
      this.syncLibraryState();
    } catch (e) {
      this.postLibraryError((e as Error).message);
    }
  }

  private librarySent = false;
  private libraryObject: unknown;

  public syncLibraryState(): void {
    if (!this._view || !loadedLibrary) return;
    if (this.librarySent && this.libraryObject === loadedLibrary) return;   // the webview already has this payload
    this.librarySent = true;
    this.libraryObject = loadedLibrary;
    const hits = this._libQuery.trim() ? library.searchLibrary(loadedLibrary, this._libQuery.trim()) : undefined;
    const groups = library.groupBy(loadedLibrary, this._libMode, hits);
    const summary = library.summary(loadedLibrary);

    this._view.webview.postMessage({
      type: 'update',
      mode: this._libMode,
      query: this._libQuery,
      groups,
      summary,
      counts: loadedLibrary.counts,
      skills: loadedLibrary.skills,
      families: loadedLibrary.families,
      purposes: loadedLibrary.purposes,
      clusters: loadedLibrary.clusters,
      bundles: loadedLibrary.bundles,
      error: null,
    });
  }

  public performLibrarySearch(query: string, mode: library.GroupMode): void {
    if (!this._view || !loadedLibrary) return;
    const trimmed = query.trim();
    const hits = trimmed ? library.searchLibrary(loadedLibrary, trimmed) : undefined;
    const groups = library.groupBy(loadedLibrary, mode, hits);

    this._view.webview.postMessage({
      type: 'searchResults',
      query,
      mode,
      hits: hits ?? null,
      groups,
      matchCount: hits ? hits.length : loadedLibrary.counts.skills,
      totalCount: loadedLibrary.counts.skills,
    });
  }

  public postLibraryError(msg: string): void {
    if (!this._view) return;
    this._view.webview.postMessage({
      type: 'error',
      message: msg,
    });
  }

  public lastNeeds: hive.Need[] = [];

  public updateNeeds(needs: hive.Need[]) {
    this.lastNeeds = needs;
    this._view?.webview.postMessage({ type: 'updateNeeds', needs });
  }

  public showTab(tab: 'now' | 'choose' | 'insights' | 'library' | string) {
    if (this._view) {
      this._view.show?.(true);
      this._view.webview.postMessage({ type: 'switchTab', tab });
      if (tab === 'library') {
        if (!loadedLibrary) {
          void this.loadLibrary();
        } else {
          this.syncLibraryState();
        }
      }
    }
  }

  public updateTrackResult(_track: hive.TrackResult) {
    // The page draws the Now tab from the full state message (it has no handler for a bare track message), so a new
    // track result is sent that way. `lastTrackResult` was set by the caller just before this.
    this.syncState();
  }

  private sent = new Map<string, unknown>();

  /** The value if the webview has not seen this exact one yet, otherwise undefined (the webview keeps what it has). */
  private fresh<T>(key: string, value: T): T | undefined {
    const same = this.sent.has(key) && (this.sent.get(key) === value || (Array.isArray(value) && Array.isArray(this.sent.get(key)) && JSON.stringify(this.sent.get(key)) === JSON.stringify(value)));
    if (same) return undefined;
    this.sent.set(key, value);
    return value;
  }

  public syncState() {
    writeActiveSkills();
    if (!this._view) return;
    const root = sfpRoot();
    this._view.webview.postMessage({
      type: 'updateState',
      payload: {
        task: selection?.task ?? '',
        skills: selection?.stack ?? [],
        selection,
        baselineSelection,
        diff: baselineSelection && selection ? hive.selectionDiff(baselineSelection, selection) : currentDiff,
        include: currentInclude,
        exclude: currentExclude,
        // These two are large and rarely change: send them once per webview, then only when they do.
        catalog: this.fresh('catalog', root ? hive.catalogNames(root) : []),
        clusters: this.fresh('clusters', loadedClusters),
        sessionStats,
        editorSelection: getEditorSelection(),
        decision: selection?.decision,
        track: lastTrackResult,
        follow: config().follow,
        live: this.lastLiveResult,
        collapsed: this.isCollapsed,
        needs: this.lastNeeds,
        autoSkills: autoSkillsInfo,
        history: loadHistory(15),
      },
    });
  }

  private getHtml(webview: vscode.Webview): string {
    const nonce = getNonce();
    const styleUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'studio.css')));
    const libraryStyleUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'library.css')));
    const iconsUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'icons.js')));
    const scriptUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'studio.js')));
    const libraryScriptUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'library.js')));
    const iconUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'hive.svg')));
    const root = sfpRoot();
    const catalogCount = root ? hive.catalogNames(root).length : 819;

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}'; img-src ${webview.cspSource} data:;">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SFP Hive Studio</title>
  <link rel="stylesheet" href="${styleUri}">
  <link rel="stylesheet" href="${libraryStyleUri}">
</head>
<body>
  <div class="studio-header ${this.isCollapsed ? 'collapsed' : ''}" id="studio-header">
    <div class="studio-title-bar" id="studio-title-bar" role="button" tabindex="0" aria-expanded="${!this.isCollapsed}" aria-label="Toggle SFP Hive view">
      <div class="studio-brand">
        <button class="btn-icon collapse-chevron-btn" id="studio-collapse-btn" aria-label="Toggle view" tabindex="-1">
          <svg class="collapse-chevron" viewBox="0 0 16 16"><path fill="currentColor" d="M11 8l-5 5-.7-.7L9.6 8 5.3 3.7 6 3z"/></svg>
        </button>
        <img class="icon" src="${iconUri}" alt="Hive">
        <span>SFP Hive</span>
      </div>
      <div class="studio-badge" id="studio-status-badge">Ready</div>
    </div>
    <div class="tab-bar ${this.isCollapsed ? 'hidden' : ''}" id="studio-tab-bar" role="tablist" aria-label="SFP Hive Studio Navigation">
      <button class="tab-btn active" data-tab="now" role="tab" aria-selected="true" aria-controls="tab-now" id="btn-tab-now" tabindex="0">
        <svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M1 8.5h3.2l1.6-4.5 3.4 9 2.1-5.5H15v-1h-4.2l-1.6 4.2-3.4-9-2.1 6.8H1v1z"/></svg>
        <span>Now</span>
      </button>
      <button class="tab-btn" data-tab="choose" role="tab" aria-selected="false" aria-controls="tab-choose" id="btn-tab-choose" tabindex="-1">
        <svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M11.5 7a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0zm-.8 3.9l3.6 3.6.7-.7-3.6-3.6a5.5 5.5 0 1 0-.7.7z"/></svg>
        <span>Choose</span>
      </button>
      <button class="tab-btn" data-tab="library" role="tab" aria-selected="false" aria-controls="tab-library" id="btn-tab-library" tabindex="-1">
        <svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M14 2H2v12h12V2zM3 3h10v10H3V3z"/><path fill="currentColor" d="M5 5h6v1H5zm0 3h6v1H5zm0 3h4v1H5z"/></svg>
        <span>Library</span>
      </button>
      <button class="tab-btn" data-tab="insights" role="tab" aria-selected="false" aria-controls="tab-insights" id="btn-tab-insights" tabindex="-1">
        <svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M1 14h14v1H1v-1zm2-2h2V7H3v5zm4 0h2V3H7v9zm4 0h2V5h-2v7z"/></svg>
        <span>Insights</span>
      </button>
    </div>
  </div>

  <div class="studio-body ${this.isCollapsed ? 'hidden' : ''}" id="studio-body">

  <!-- Tab 1: Now -->
  <div class="tab-content active" id="tab-now" role="tabpanel" aria-labelledby="btn-tab-now">
    <div class="section">
      <div class="toggle-row">
        <label class="toggle-label" for="follow-toggle">
          <span>Follow the agent</span>
        </label>
        <label class="toggle-switch">
          <input type="checkbox" id="follow-toggle" checked aria-label="Toggle following agent activity">
          <span class="toggle-slider"></span>
        </label>
      </div>
    </div>

    <div class="section">
      <div class="section-title">
        <span>Current phase</span>
        <button class="btn-icon" data-action="refresh" aria-label="Refresh Phase" title="Refresh">
          <svg viewBox="0 0 16 16"><path fill="currentColor" d="M13.6 2.4A7 7 0 1 0 15 8h-1.5a5.5 5.5 0 1 1-1.1-4.4L10 6h5V1l-1.4 1.4z"/></svg>
        </button>
      </div>
      <div class="card" id="now-phase-card">
        <div class="card-header">
          <span class="card-title" id="now-phase-name">Idle</span>
          <span class="studio-badge" id="now-confidence-badge">Confidence 0%</span>
        </div>
        <div class="progress-container">
          <div class="progress-track"><div class="progress-fill" id="now-confidence-fill"></div></div>
        </div>
        <div class="stacked-phase-bar" id="now-stacked-shares" title="Share of recent activity by phase"></div>
        <div class="card-meta">
          <span id="now-phase-detail">Awaiting workspace activity</span>
          <span id="now-decision-id" class="decision-id"></span>
        </div>
      </div>
    </div>

    <div class="section hidden" id="now-next-section">
      <div class="section-title">Likely next</div>
      <div class="chip-bar" id="now-next-chips"></div>
    </div>

    <div class="auto-skills-line" data-auto-line></div>

    <div class="section hidden" id="now-bundles-section">
      <div class="section-title">
        <span>Loaded bundles</span>
        <span class="decision-id" id="now-bundles-count"></span>
      </div>
      <div id="now-bundles-list" class="skills-list"></div>
    </div>

    <div class="section">
      <div class="section-title">
        <span>Skills for this phase</span>
        <button class="btn btn-secondary hidden" data-action="copyPrompt" id="now-copy-btn">Copy prompt</button>
      </div>
      <div class="state-box hidden" id="now-loading-state">
        <svg class="spin-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1.5a6.5 6.5 0 1 0 6.5 6.5h-1.5A5 5 0 1 1 8 3v-1.5z"/></svg>
        <span>Monitoring workspace activity…</span>
      </div>
      <div class="state-box" id="now-empty-state">
        <svg viewBox="0 0 16 16"><path fill="currentColor" d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 13a6 6 0 1 1 0-12 6 6 0 0 1 0 12zm-.5-9h1v2h-1V5zm0 3h1v4h-1V8z"/></svg>
        <span>No activity detected yet. Edit a file, run a test or start a task, and the matching skills and bundles will load here.</span>
      </div>
      <div class="state-box error-state hidden" id="now-error-state">
        <svg viewBox="0 0 16 16"><path fill="currentColor" d="M8.865 1.52c-.418-.723-1.312-.723-1.73 0L.14 13.56c-.418.723.03 1.64.865 1.64h14c.836 0 1.283-.917.865-1.64L8.865 1.52zM8 4a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 8 4zm0 8.5a1 1 0 1 1 0-2 1 1 0 0 1 0 2z"/></svg>
        <span>Could not track workspace activity. Check Python settings in sfpHive.python.</span>
      </div>
      <div id="now-skills-list" class="skills-list hidden"></div>
    </div>

    <div class="section hidden" id="now-upcoming-section">
      <div class="section-title">Next phase</div>
      <div id="now-upcoming-skills" class="skills-list"></div>
    </div>

    <div class="section hidden" id="now-changes-section">
      <div class="section-title">Recent phase changes</div>
      <div id="now-changes-list" class="changes-list"></div>
    </div>
  </div>

  <!-- Tab 2: Choose -->
  <div class="tab-content" id="tab-choose" role="tabpanel" aria-labelledby="btn-tab-choose">
    <div class="auto-skills-line" data-auto-line></div>
    <div class="choose-welcome ${isFirstRun() ? '' : 'hidden'}" id="choose-welcome">
      <div class="welcome-title">Describe a task, see the skills, send it.</div>
      <div class="welcome-desc">The hive chooses skills based on your project files, task words, and past feedback.</div>
      <button class="btn btn-secondary btn-small" data-action="fillExample" id="btn-fill-example">Try an example</button>
    </div>
    <div class="choose-bundle-banner hidden" id="choose-bundle-banner"></div>
    <div class="section">
      <div class="section-title">Task Prompt</div>
      <div class="flex-row">
        <input type="text" id="choose-task-input" class="input-text" placeholder="What are you about to do?" aria-label="Task prompt input">
        <button class="btn" data-action="choose" aria-label="Choose skills for task">Choose</button>
      </div>
      <div id="choose-live-container" class="live-chips-container hidden">
        <div id="choose-live-chips" class="live-chips-bar"></div>
        <div id="choose-live-waiting" class="live-waiting-label hidden">waiting for more words...</div>
        <div id="choose-live-removed" class="live-removed-bar hidden"></div>
        <div id="choose-live-needs" class="live-needs-container hidden"></div>
      </div>
    </div>
    <div class="section hidden" id="choose-needs-section">
      <div class="section-title">Task Needs</div>
      <div id="choose-needs-list" class="needs-list"></div>
    </div>
    <div class="section hidden" id="choose-steer-section">
      <div class="steer-actions">
        <button class="btn" data-action="rechoose" id="choose-rechoose-btn">Re-choose with changes</button>
        <button class="btn btn-secondary" data-action="applyStack" id="choose-apply-btn">Apply</button>
        <label class="steer-feedback-label">
          <input type="checkbox" id="choose-feedback-checkbox" checked>
          <span>Send feedback on changes</span>
        </label>
      </div>
      <div id="choose-diff-summary" class="diff-summary hidden"></div>
    </div>
    <div class="section">
      <div class="section-title">
        <span>Skill Stack</span>
        <span id="choose-decision-id" class="decision-id"></span>
      </div>
      <div class="state-box hidden" id="choose-loading-state">
        <svg class="spin-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1.5a6.5 6.5 0 1 0 6.5 6.5h-1.5A5 5 0 1 1 8 3v-1.5z"/></svg>
        <span>Choosing skills for your task...</span>
      </div>
      <div class="state-box" id="choose-empty-state">
        <svg viewBox="0 0 16 16"><path fill="currentColor" d="M11.5 7a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0zm-.8 3.9l3.6 3.6.7-.7-3.6-3.6a5.5 5.5 0 1 0-.7.7z"/></svg>
        <span>Type a task above or select text in the editor to inspect skills.</span>
      </div>
      <div class="state-box error-state hidden" id="choose-error-state">
        <svg viewBox="0 0 16 16"><path fill="currentColor" d="M8.865 1.52c-.418-.723-1.312-.723-1.73 0L.14 13.56c-.418.723.03 1.64.865 1.64h14c.836 0 1.283-.917.865-1.64L8.865 1.52zM8 4a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 8 4zm0 8.5a1 1 0 1 1 0-2 1 1 0 0 1 0 2z"/></svg>
        <span>Failed to choose skills. Check that the SFP checkout exists in sfpHive.sfpPath.</span>
      </div>
      <div id="choose-stack-list" class="skills-list hidden"></div>
      <div id="choose-preload-list" class="skills-list preload-section hidden"></div>
    </div>
    <div class="section relative hidden" id="choose-add-section">
      <div class="section-title">Add any skill from catalog</div>
      <div class="flex-row relative">
        <input type="text" id="choose-catalog-search" class="input-text" placeholder="Type a skill name..." aria-label="Search catalog skills">
        <button class="btn btn-secondary" data-action="addCatalogSkill">Add</button>
      </div>
      <div id="choose-catalog-results" class="catalog-dropdown hidden"></div>
    </div>
    <div class="section hidden" id="choose-considered-section">
      <div class="section-title">Considered but not taken</div>
      <div class="overflow-x-auto">
        <table class="considered-table" id="choose-considered-table">
          <thead>
            <tr>
              <th>Skill</th>
              <th>Reason</th>
              <th>Signals</th>
              <th>Backers</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="choose-considered-body"></tbody>
        </table>
      </div>
    </div>
    <div class="section" id="choose-session-section">
      <div class="section-title">Session Stats</div>
      <div class="session-stats-grid" id="choose-session-stats">
        <div class="session-stat-card">
          <span class="session-stat-value" id="stat-decisions">0</span>
          <span class="card-subtitle">Decisions</span>
        </div>
        <div class="session-stat-card">
          <span class="session-stat-value" id="stat-interventions">0</span>
          <span class="card-subtitle">Interventions</span>
        </div>
        <div class="session-stat-card">
          <span class="session-stat-value" id="stat-kept">100%</span>
          <span class="card-subtitle">Kept Share</span>
        </div>
        <div class="session-stat-card">
          <span class="session-stat-value" id="stat-added">0</span>
          <span class="card-subtitle">Added Skills</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Tab 3: Skill Library -->
  <div class="tab-content" id="tab-library" role="tabpanel" aria-labelledby="btn-tab-library">
    <div class="library-header">
      <div class="search-box-row">
        <svg class="search-icon" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M11.5 7a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0zm-.8 3.9l3.6 3.6.7-.7-3.6-3.6a5.5 5.5 0 1 0-.7.7z"/></svg>
        <input type="text" id="lib-search-input" class="search-input" placeholder="Search skills or what you want to do" aria-label="Search skills" autocomplete="off" spellcheck="false">
        <button id="lib-search-clear" class="search-clear-btn hidden" aria-label="Clear search" title="Clear search (Esc)">&times;</button>
      </div>
      <div class="search-count-badge"><span id="lib-search-count">Loading skills...</span></div>
      <div class="mode-switch" id="lib-mode-switch" role="radiogroup" aria-label="How to browse the library">
        <button class="mode-btn active" data-mode="family" role="radio" aria-checked="true" tabindex="0" title="Browse by area: design, security, agents...">Areas</button>
        <button class="mode-btn" data-mode="purpose" role="radio" aria-checked="false" tabindex="-1" title="Browse by what you want to get done">Goals</button>
        <button class="mode-btn" data-mode="bundle" role="radio" aria-checked="false" tabindex="-1" title="Ready-made sets of skills for one job">Bundles</button>
        <button class="mode-btn" data-mode="cluster" role="radio" aria-checked="false" tabindex="-1" title="Skills grouped by topic">Clusters</button>
      </div>
    </div>

    <div class="new-bundle-bar" id="lib-new-bundle-bar">
      <button class="btn" id="lib-new-bundle-btn">+ New bundle</button>
    </div>

    <div class="state-box hidden" id="lib-state-loading">
      <span>Loading skill library...</span>
    </div>

    <div class="state-box hidden" id="lib-state-empty">
      <p class="state-msg">Nothing matches that. Try one word, like &ldquo;docker&rdquo; or &ldquo;tests&rdquo;, or clear the search.</p>
    </div>

    <div class="state-box error hidden" id="lib-state-error">
      <p class="state-msg" id="lib-error-msg">Failed to load skill library.</p>
      <button class="btn btn-primary" id="lib-error-btn">Open settings</button>
    </div>

    <div class="groups-container" id="lib-groups-container"></div>

    <div class="library-footer">
      <span class="footer-counts" id="lib-footer-counts"></span>
      <button class="icon-btn" id="lib-git-btn" aria-label="Add a skill from Git" title="Add a skill from a Git repository"><svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M7.5 3h1v4.5H13v1H8.5V13h-1V8.5H3v-1h4.5V3z"/></svg></button>
      <button class="icon-btn" id="lib-refresh-btn" aria-label="Refresh library" title="Refresh library">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M13.6 2.4A7 7 0 1 0 15 8h-1.5a5.5 5.5 0 1 1-1.1-4.4L10 6h5V1l-1.4 1.4z"/></svg>
      </button>
    </div>
  </div>

  <!-- Tab 4: Insights -->
  <div class="tab-content" id="tab-insights" role="tabpanel" aria-labelledby="btn-tab-insights">
    <div class="section">
      <div class="section-title"><span>Skill history</span></div>
      <div id="history-list" class="changes-list"><div class="empty-text">No skills have been given to the agent yet.</div></div>
    </div>
    <div class="section">
      <div class="section-title">
        <span>Connection &amp; Health</span>
        <button class="btn btn-secondary" data-action="runDoctor" id="btn-run-doctor">Check connection</button>
      </div>
      <div id="insights-doctor-container" class="doctor-container">
        ${lastDoctorResult ? hive.renderDoctorHtml(lastDoctorResult) : '<div class="state-box"><span>Click Check connection to verify the hive.</span></div>'}
      </div>
    </div>
    <div class="section">
      <div class="section-title">
        <span>Learning &amp; Usage</span>
        <button class="btn btn-secondary" data-action="train" aria-label="Train model">Train</button>
      </div>
      <div class="state-box hidden" id="insights-loading-state">
        <svg class="spin-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1.5a6.5 6.5 0 1 0 6.5 6.5h-1.5A5 5 0 1 1 8 3v-1.5z"/></svg>
        <span>Loading learning history...</span>
      </div>
      <div class="state-box" id="insights-empty-state">
        <svg viewBox="0 0 16 16"><path fill="currentColor" d="M1 14h14v1H1v-1zm2-2h2V7H3v5zm4 0h2V3H7v9zm4 0h2V5h-2v7z"/></svg>
        <span>No learning decisions recorded yet. Start choosing skills and reporting feedback.</span>
      </div>
      <div class="state-box error-state hidden" id="insights-error-state">
        <svg viewBox="0 0 16 16"><path fill="currentColor" d="M8.865 1.52c-.418-.723-1.312-.723-1.73 0L.14 13.56c-.418.723.03 1.64.865 1.64h14c.836 0 1.283-.917.865-1.64L8.865 1.52zM8 4a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 8 4zm0 8.5a1 1 0 1 1 0-2 1 1 0 0 1 0 2z"/></svg>
        <span>Could not read feedback logs in ~/.sfp. Run python3 mcp/sfp_hive.py train.</span>
      </div>
    </div>
  </div>
  </div>

  <script nonce="${nonce}" src="${iconsUri}"></script>
  <script nonce="${nonce}" src="${scriptUri}"></script>
  <script nonce="${nonce}" src="${libraryScriptUri}"></script>
</body>
</html>`;
  }
}

export class LibraryViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'sfpHive.library';
  public _view?: vscode.WebviewView;
  private _query = '';
  private _mode: library.GroupMode = 'family';

  constructor(private readonly extensionPath: string) {
    if (extContext) {
      this._mode = extContext.workspaceState?.get<library.GroupMode>('sfpHive.libraryMode2', 'family') ?? 'family';
    }
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.file(path.join(this.extensionPath, 'media'))],
    };
    webviewView.webview.html = this.getHtml(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (message) => {
      switch (message.command) {
        case 'ready':
          if (!loadedLibrary) {
            await this.loadLibrary();
          } else {
            this.syncState();
          }
          break;
        case 'search':
          this._query = message.query || '';
          this._mode = message.mode || this._mode;
          this.performSearch(this._query, this._mode);
          break;
        case 'switchMode':
          this._mode = message.mode || 'family';
          if (extContext) {
            void extContext.workspaceState?.update('sfpHive.libraryMode2', this._mode);
          }
          this.performSearch(this._query, this._mode);
          break;
        case 'openSkill':
          if (message.skill) {
            await vscode.commands.executeCommand('sfpHive.openSkill', message.skill);
          }
          break;
        case 'openDetail':
          if (message.skill) {
            await showSkillDetail(String(message.skill));
          }
          break;
        case 'pinSkill':
          if (message.skill) {
            await pinSkillWorkflow(message.skill);
          }
          break;
        case 'addToBundle':
          if (message.skill) {
            await addToBundleWorkflow(message.skill);
          }
          break;
        case 'applyBundle':
          if (message.bundleId) {
            await applyBundleWorkflow(message.bundleId);
          }
          break;
        case 'copyPrompt':
          if (message.bundleId) {
            await copyPromptWorkflow(message.bundleId);
          }
          break;
        case 'newBundle':
          await newBundleWorkflow();
          break;
        case 'addFromGit':
          await addSkillFromGitWorkflow();
          break;
        case 'editBundle':
          if (message.bundleId) {
            await editBundleWorkflow(message.bundleId);
          }
          break;
        case 'deleteBundle':
          if (message.bundleId) {
            await deleteBundleWorkflow(message.bundleId);
          }
          break;
        case 'refresh':
          await this.loadLibrary();
          break;
        case 'openSettings':
          void vscode.commands.executeCommand('workbench.action.openSettings', 'sfpHive.sfpPath');
          break;
      }
    });
  }

  public async loadLibrary(): Promise<void> {
    const root = sfpRoot();
    if (!root) {
      this.postError('SFP checkout not found. Check sfpHive.sfpPath setting.');
      return;
    }
    const cfg = config();
    try {
      const out = await hive.run(hive.pythonCommand(cfg.opts), hive.libraryArgs(root));
      loadedLibrary = hive.parseLibrary(out);
      this.syncState();
    } catch (e) {
      this.postError((e as Error).message);
    }
  }

  public syncState(): void {
    if (!this._view || !loadedLibrary) return;
    const hits = this._query.trim() ? library.searchLibrary(loadedLibrary, this._query.trim()) : undefined;
    const groups = library.groupBy(loadedLibrary, this._mode, hits);
    const summary = library.summary(loadedLibrary);

    this._view.webview.postMessage({
      type: 'update',
      mode: this._mode,
      query: this._query,
      groups,
      summary,
      counts: loadedLibrary.counts,
      skills: loadedLibrary.skills,
      families: loadedLibrary.families,
      purposes: loadedLibrary.purposes,
      clusters: loadedLibrary.clusters,
      bundles: loadedLibrary.bundles,
      error: null,
    });
  }

  public performSearch(query: string, mode: library.GroupMode): void {
    if (!this._view || !loadedLibrary) return;
    const trimmed = query.trim();
    const hits = trimmed ? library.searchLibrary(loadedLibrary, trimmed) : undefined;
    const groups = library.groupBy(loadedLibrary, mode, hits);

    this._view.webview.postMessage({
      type: 'searchResults',
      query,
      mode,
      hits: hits ?? null,
      groups,
      matchCount: hits ? hits.length : loadedLibrary.counts.skills,
      totalCount: loadedLibrary.counts.skills,
    });
  }

  public postError(msg: string): void {
    if (!this._view) return;
    this._view.webview.postMessage({
      type: 'error',
      message: msg,
    });
  }

  public focus(): void {
    this._view?.show?.(true);
  }

  public getHtml(webview: vscode.Webview): string {
    const nonce = getNonce();
    const styleUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'library.css')));
    const scriptUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'library.js')));

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}'; img-src ${webview.cspSource} data:;">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Skill Library</title>
  <link rel="stylesheet" href="${styleUri}">
</head>
<body>
  <div class="library-header">
    <div class="search-box-row">
      <svg class="search-icon" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M11.5 7a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0zm-.8 3.9l3.6 3.6.7-.7-3.6-3.6a5.5 5.5 0 1 0-.7.7z"/></svg>
      <input type="text" id="lib-search-input" class="search-input" placeholder="Search skills or what you want to do" aria-label="Search skills" autocomplete="off" spellcheck="false">
      <button id="lib-search-clear" class="search-clear-btn hidden" aria-label="Clear search" title="Clear search (Esc)">&times;</button>
    </div>
    <div class="search-count-badge"><span id="lib-search-count">Loading skills...</span></div>
    <div class="mode-switch" id="lib-mode-switch" role="radiogroup" aria-label="How to browse the library">
      <button class="mode-btn active" data-mode="family" role="radio" aria-checked="true" tabindex="0" title="Browse by area: design, security, agents...">Areas</button>
      <button class="mode-btn" data-mode="purpose" role="radio" aria-checked="false" tabindex="-1" title="Browse by what you want to get done">Goals</button>
      <button class="mode-btn" data-mode="bundle" role="radio" aria-checked="false" tabindex="-1" title="Ready-made sets of skills for one job">Bundles</button>
      <button class="mode-btn" data-mode="cluster" role="radio" aria-checked="false" tabindex="-1" title="Skills grouped by topic">Clusters</button>
    </div>
  </div>

  <div class="new-bundle-bar" id="lib-new-bundle-bar">
    <button class="btn" id="lib-new-bundle-btn">+ New bundle</button>
  </div>

  <div class="state-box hidden" id="lib-state-loading">
    <span>Loading skill library...</span>
  </div>

  <div class="state-box hidden" id="lib-state-empty">
    <p class="state-msg">Nothing matches that. Try one word, like &ldquo;docker&rdquo; or &ldquo;tests&rdquo;, or clear the search.</p>
  </div>

  <div class="state-box error hidden" id="lib-state-error">
    <p class="state-msg" id="lib-error-msg">Failed to load skill library.</p>
    <button class="btn btn-primary" id="lib-error-btn">Open settings</button>
  </div>

  <div class="groups-container" id="lib-groups-container"></div>

  <div class="library-footer">
    <span class="footer-counts" id="lib-footer-counts"></span>
    <button class="icon-btn" id="lib-git-btn" aria-label="Add a skill from Git" title="Add a skill from a Git repository"><svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M7.5 3h1v4.5H13v1H8.5V13h-1V8.5H3v-1h4.5V3z"/></svg></button>
      <button class="icon-btn" id="lib-refresh-btn" aria-label="Refresh library" title="Refresh library">
      <svg viewBox="0 0 16 16"><path fill="currentColor" d="M13.6 2.4A7 7 0 1 0 15 8h-1.5a5.5 5.5 0 1 1-1.1-4.4L10 6h5V1l-1.4 1.4z"/></svg>
    </button>
  </div>

  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }
}

let detailPanel: vscode.WebviewPanel | undefined;
let detailSkill: string | undefined;

/** The skill detail window: a tab in the editor area with the full description, where the skill is used and similar skills. */
export async function showSkillDetail(name: string): Promise<void> {
  const root = sfpRoot();
  if (!root) {
    void vscode.window.showWarningMessage('SFP checkout not found. Set sfpHive.sfpPath.');
    return;
  }
  let detail: hive.SkillDetail;
  try {
    detail = hive.parseSkillDetail(await hive.run(hive.pythonCommand(config().opts), hive.skillArgs(root, name)));
  } catch (e) {
    void vscode.window.showWarningMessage(`No details for ${name}: ${(e as Error).message}`);
    return;
  }
  const media = vscode.Uri.file(path.join(extContext?.extensionPath ?? '', 'media'));
  if (!detailPanel) {
    detailPanel = vscode.window.createWebviewPanel('sfpHive.skillDetail', detail.name, { viewColumn: vscode.ViewColumn.Beside, preserveFocus: false }, {
      enableScripts: true,
      localResourceRoots: [media],
    });
    detailPanel.onDidDispose(() => { detailPanel = undefined; detailSkill = undefined; });
    detailPanel.webview.onDidReceiveMessage(async (m) => {
      const target = detailSkill;
      switch (m.command) {
        case 'openFile': if (target) await vscode.commands.executeCommand('sfpHive.openSkill', target); break;
        case 'pin': if (target) await pinSkillWorkflow(target); break;
        case 'addToBundle': if (target) await addToBundleWorkflow(target); break;
        case 'showSkill': if (m.skill) await showSkillDetail(String(m.skill)); break;
        case 'showBundle': if (m.bundle) await vscode.commands.executeCommand('sfpHive.focusLibrary'); break;
      }
    });
  } else {
    detailPanel.reveal(undefined, false);
  }
  detailSkill = detail.name;
  detailPanel.title = detail.name;
  const w = detailPanel.webview;
  w.html = hive.skillDetailHtml(detail, w.cspSource, getNonce(),
    String(w.asWebviewUri(vscode.Uri.file(path.join(media.fsPath, 'detail.css')))),
    String(w.asWebviewUri(vscode.Uri.file(path.join(media.fsPath, 'detail.js')))));
}

function getNonce(): string {
  let text = '';
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}

let routerProcess: cp.ChildProcess | undefined;
let routerRunning = false;
let routerPort = 8787;
let routerHealthTimer: NodeJS.Timeout | undefined;

export function isRouterRunning(): boolean {
  return routerRunning;
}

export function getRouterPort(): number {
  return routerPort;
}

export function fetchRouterHealth(port: number = 8787): Promise<hive.RouteStatus | null> {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/health`, { timeout: 2500 }, (res) => {
      if (res.statusCode !== 200) {
        resolve(null);
        return;
      }
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          resolve(hive.parseRouteStatus(data));
        } catch {
          resolve(null);
        }
      });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => {
      req.destroy();
      resolve(null);
    });
  });
}

export function sendRouterTestRequest(
  port: number = 8787,
  prompt: string
): Promise<{ model: string; tier: string; answer: string }> {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      model: 'auto',
      messages: [{ role: 'user', content: prompt }],
    });
    const req = http.request(
      `http://127.0.0.1:${port}/v1/chat/completions`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload),
        },
        timeout: 10000,
      },
      (res) => {
        const modelHeader = (res.headers['x-sfp-model'] as string) || '';
        const tierHeader = (res.headers['x-sfp-tier'] as string) || '';
        let data = '';
        res.on('data', (chunk) => {
          data += chunk;
        });
        res.on('end', () => {
          try {
            const json = JSON.parse(data);
            const content = json.choices?.[0]?.message?.content || (json.error ? json.error.message : data);
            resolve({
              model: modelHeader || json.model || 'auto',
              tier: tierHeader,
              answer: content,
            });
          } catch {
            resolve({
              model: modelHeader || 'unknown',
              tier: tierHeader,
              answer: data,
            });
          }
        });
      }
    );
    req.on('error', (err) => reject(err));
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Router request timed out'));
    });
    req.write(payload);
    req.end();
  });
}

export async function startRouter(port: number = 8787): Promise<boolean> {
  if (routerRunning && routerProcess) return true;
  const root = sfpRoot();
  if (!root) return false;
  const py = hive.pythonCommand(config().opts);
  routerPort = port;

  return new Promise((resolve) => {
    let resolved = false;
    try {
      const proc = cp.spawn(py, [path.join(root, 'mcp', 'sfp_route.py'), 'serve', '--port', String(port)], {
        cwd: root,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      routerProcess = proc;

      proc.stdout?.on('data', (d) => {
        const text = d.toString();
        if (text.includes('SFP router on')) {
          routerRunning = true;
          startRouterHealthPolling();
          modelsProvider?.syncState();
          if (!resolved) {
            resolved = true;
            resolve(true);
          }
        }
      });

      proc.on('error', () => {
        stopRouter();
        if (!resolved) {
          resolved = true;
          resolve(false);
        }
      });

      proc.on('exit', () => {
        stopRouter();
      });

      setTimeout(async () => {
        if (!resolved) {
          const health = await fetchRouterHealth(port);
          if (health) {
            routerRunning = true;
            startRouterHealthPolling();
            modelsProvider?.syncState();
            resolved = true;
            resolve(true);
          } else {
            resolved = true;
            resolve(routerRunning);
          }
        }
      }, 1500);
    } catch {
      routerRunning = false;
      if (!resolved) {
        resolved = true;
        resolve(false);
      }
    }
  });
}

export function stopRouter(): void {
  if (routerHealthTimer) {
    clearInterval(routerHealthTimer);
    routerHealthTimer = undefined;
  }
  if (routerProcess) {
    try {
      routerProcess.kill();
    } catch {}
    routerProcess = undefined;
  }
  routerRunning = false;
  modelsProvider?.syncState();
}

function startRouterHealthPolling() {
  if (routerHealthTimer) clearInterval(routerHealthTimer);
  routerHealthTimer = setInterval(async () => {
    if (!routerRunning) {
      if (routerHealthTimer) clearInterval(routerHealthTimer);
      routerHealthTimer = undefined;
      return;
    }
    const status = await fetchRouterHealth(routerPort);
    if (status) {
      modelsProvider?.updateHealth(status);
    }
  }, 5000);
}

export class ModelsViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'sfpHive.models';
  public _view?: vscode.WebviewView;
  private _config: hive.RouteConfig | null = null;
  private _status: hive.RouteStatus | null = null;
  private _policy: string = 'local-first';
  private _preview: string = '';

  constructor(private readonly extensionPath: string) {}

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.file(path.join(this.extensionPath, 'media'))],
    };
    webviewView.webview.html = this.getHtml(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (message) => {
      switch (message.command) {
        case 'ready':
          await this.loadConfig();
          this.syncState();
          break;
        case 'toggleRouter':
          if (routerRunning) {
            stopRouter();
          } else {
            const ok = await startRouter(routerPort);
            if (!ok && (!this._config || !this._config.providers.length)) {
              void vscode.window
                .showWarningMessage('No models configured for the router. Run Set up first.', 'Set up')
                .then((pick) => pick && vscode.commands.executeCommand('sfpHive.routerSetup'));
            }
          }
          this.syncState();
          break;
        case 'copyUrl':
          if (message.url) {
            await vscode.env.clipboard.writeText(message.url);
            void vscode.window.showInformationMessage('Copied router URL to clipboard.');
          }
          break;
        case 'changePolicy':
          if (message.policy) {
            this._policy = message.policy;
            if (this._config) {
              this._config.policy = this._policy;
              this.saveConfig(this._config);
            }
          }
          break;
        case 'setup': {
          const root = sfpRoot();
          if (!root) return;
          const cfg = config();
          const policy = message.policy || this._policy || 'local-first';
          try {
            if (message.yes) {
              await hive.run(hive.pythonCommand(cfg.opts), hive.routeArgs(root, 'setup', '--policy', policy, '--yes'));
              this._preview = '';
              await this.loadConfig();
              this.syncState();
              void vscode.window.showInformationMessage('Model router configuration written.');
            } else {
              const preview = await hive.run(hive.pythonCommand(cfg.opts), hive.routeArgs(root, 'setup', '--policy', policy));
              this._preview = preview;
              this._view?.webview.postMessage({ type: 'setupPreview', preview });
            }
          } catch (err: any) {
            void vscode.window.showErrorMessage(`Router setup error: ${err.message}`);
          }
          break;
        }
        case 'updateStrength': {
          if (this._config && message.providerId && message.modelId && message.strength) {
            const prov = this._config.providers.find((p) => p.id === message.providerId);
            if (prov) {
              const m = prov.models.find((mod) => mod.id === message.modelId);
              if (m) {
                m.strength = message.strength;
                this.saveConfig(this._config);
                this.syncState();
              }
            }
          }
          break;
        }
        case 'plan': {
          const root = sfpRoot();
          if (!root || !message.task) return;
          const cfg = config();
          try {
            const out = await hive.run(hive.pythonCommand(cfg.opts), hive.routeArgs(root, 'plan', message.task));
            this._view?.webview.postMessage({ type: 'planResult', output: out });
          } catch (err: any) {
            this._view?.webview.postMessage({ type: 'planResult', output: `Error: ${err.message}` });
          }
          break;
        }
        case 'testRequest': {
          if (!message.prompt) return;
          if (!routerRunning) {
            void vscode.window.showWarningMessage('Start the router before sending a test request.');
            this._view?.webview.postMessage({
              type: 'testResult',
              result: { model: 'router stopped', tier: 'none', answer: 'Error: start the router first.' },
            });
            return;
          }
          try {
            const res = await sendRouterTestRequest(routerPort, message.prompt);
            this._view?.webview.postMessage({ type: 'testResult', result: res });
          } catch (err: any) {
            this._view?.webview.postMessage({
              type: 'testResult',
              result: { model: 'error', tier: 'none', answer: `Request failed: ${err.message}` },
            });
          }
          break;
        }
        case 'showInsights':
          await vscode.commands.executeCommand('sfpHive.stack.focus');
          studioProvider?.showTab('insights');
          break;
        case 'runDoctor':
          await runDoctor(true);
          break;
        case 'copyFix':
          if (message.fix) {
            await vscode.env.clipboard.writeText(message.fix);
            void vscode.window.showInformationMessage('Fix command copied to clipboard.');
          }
          break;
      }
    });
  }

  public async loadConfig(): Promise<void> {
    const home = os.homedir();
    const routesPath = path.join(process.env.SFP_DATA_DIR || path.join(home, '.sfp'), 'routes.json');
    try {
      if (fs.existsSync(routesPath)) {
        const raw = fs.readFileSync(routesPath, 'utf8');
        this._config = JSON.parse(raw);
        if (this._config?.policy) {
          this._policy = this._config.policy;
        }
      } else {
        const root = sfpRoot();
        if (root) {
          const out = await hive.run(hive.pythonCommand(config().opts), hive.routeArgs(root, 'setup'));
          this._config = hive.parseRouteConfig(out);
        }
      }
    } catch {
      this._config = null;
    }
  }

  public saveConfig(cfg: hive.RouteConfig): void {
    const home = os.homedir();
    const dir = process.env.SFP_DATA_DIR || path.join(home, '.sfp');
    const routesPath = path.join(dir, 'routes.json');
    try {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(routesPath, JSON.stringify(cfg, null, 1), 'utf8');
    } catch {}
  }

  public updateHealth(status: hive.RouteStatus): void {
    this._status = status;
    this._view?.webview.postMessage({ type: 'healthUpdate', status });
  }

  public syncState(): void {
    if (!this._view) return;
    this._view.webview.postMessage({
      type: 'updateState',
      payload: {
        running: routerRunning,
        port: routerPort,
        baseUrl: `http://127.0.0.1:${routerPort}/v1`,
        config: this._config,
        status: this._status,
        policy: this._policy,
        preview: this._preview,
      },
    });
  }

  public focus(): void {
    this._view?.show?.(true);
  }

  public getHtml(webview: vscode.Webview): string {
    const nonce = getNonce();
    const styleUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'models.css')));
    const scriptUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'models.js')));

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Models</title>
  <link rel="stylesheet" href="${styleUri}">
</head>
<body>
  <div class="models-top-bar">
    <button id="models-check-conn-btn" class="btn btn-secondary btn-small" data-action="runDoctor">Check connection</button>
  </div>
  <div id="models-doctor-container" class="doctor-container">
    ${lastDoctorResult ? hive.doctorSummaryHtml(lastDoctorResult) : ''}
  </div>

  <div class="models-header">
    <div class="models-title">
      <span id="status-dot" class="status-dot" title="Router status"></span>
      <span>Router: <span id="status-text">Stopped</span></span>
    </div>
    <button id="toggle-router-btn" class="btn">Start router</button>
  </div>

  <div id="server-card" class="server-card hidden">
    <div class="server-url-bar">
      <code id="server-url" class="server-url">http://127.0.0.1:8787/v1</code>
      <button id="copy-url-btn" class="btn btn-secondary btn-small" title="Copy base URL">Copy</button>
    </div>
    <div class="server-hint">Set your tool's base URL to this, key anything, model auto</div>
  </div>

  <div class="section">
    <div class="section-title">Configured Models</div>
    <div id="providers-container" class="providers-list">
      <div class="server-hint">Loading models configuration...</div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">Setup & Policy</div>
    <div class="setup-form">
      <div class="form-group">
        <label for="policy-select" class="form-label">Policy:</label>
        <select id="policy-select">
          <option value="local-first">local-first</option>
          <option value="cheap-first">cheap-first</option>
          <option value="strong-first">strong-first</option>
        </select>
      </div>
      <div class="setup-actions">
        <button id="setup-btn" class="btn btn-secondary" style="flex:1;">Set up</button>
        <button id="write-btn" class="btn" style="flex:1;">Write it</button>
      </div>
      <pre id="preview-box" class="config-preview hidden"></pre>
    </div>
  </div>

  <div id="status-section" class="section hidden">
    <div class="section-title">Live Status (every 5s)</div>
    <div id="status-container" class="status-list"></div>
  </div>

  <div class="section">
    <div class="section-title">Try It</div>
    <div class="try-container">
      <input type="text" id="try-prompt-input" placeholder="e.g. refactor the billing service" aria-label="Task or prompt">
      <div class="try-actions">
        <button id="try-plan-btn" class="btn btn-secondary" style="flex:1;">Plan</button>
        <button id="try-send-btn" class="btn" style="flex:1;">Test request</button>
      </div>
      <div id="try-output" class="try-output hidden"></div>
    </div>
  </div>

  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }
}

export function activate(context: vscode.ExtensionContext) {
  extContext = context;
  sessionStats = context.workspaceState?.get<hive.SessionStats>('sfpHive.sessionStats') || hive.defaultSessionStats();

  status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  status.command = 'sfpHive.choose';
  showStatus();
  status.show();

  rightStatus = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  rightStatus.command = 'sfpHive.focusNow';
  updateRightStatus();
  rightStatus.show();

  studioProvider = new StudioViewProvider(context.extensionPath);
  libraryProvider = new LibraryViewProvider(context.extensionPath);
  modelsProvider = new ModelsViewProvider(context.extensionPath);

  const reg = (id: string, fn: (...a: any[]) => unknown) => context.subscriptions.push(vscode.commands.registerCommand(id, fn));
  context.subscriptions.push(
    status,
    rightStatus,
    vscode.window.registerWebviewViewProvider(StudioViewProvider.viewType, studioProvider),
    vscode.window.registerWebviewViewProvider(LibraryViewProvider.viewType, libraryProvider),
    vscode.window.registerWebviewViewProvider(ModelsViewProvider.viewType, modelsProvider)
  );

  // Wire workspace activity listeners for Now tracking
  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (!config().follow) return;
      const p = hive.relative(project(), doc.uri.fsPath);
      if (p) activity.add({ kind: 'save', path: p });
    }),
    vscode.workspace.onDidCreateFiles((e) => {
      if (!config().follow) return;
      for (const f of e.files) {
        const p = hive.relative(project(), f.fsPath);
        if (p) activity.add({ kind: 'create', path: p });
      }
    }),
    vscode.workspace.onDidDeleteFiles((e) => {
      if (!config().follow) return;
      for (const f of e.files) {
        const p = hive.relative(project(), f.fsPath);
        if (p) activity.add({ kind: 'delete', path: p });
      }
    }),
    vscode.window.onDidChangeActiveTextEditor((ed) => {
      if (!config().follow || !ed?.document) return;
      const p = hive.relative(project(), ed.document.uri.fsPath);
      if (p) activity.add({ kind: 'open', path: p });
    })
  );

  let diagTimer: NodeJS.Timeout | undefined;
  context.subscriptions.push(
    vscode.languages.onDidChangeDiagnostics(() => {
      if (!config().follow) return;
      if (diagTimer) return;
      diagTimer = setTimeout(() => {
        diagTimer = undefined;
        const proj = project();
        let errors = 0;
        for (const [uri, diags] of vscode.languages.getDiagnostics()) {
          if (hive.relative(proj, uri.fsPath)) {
            errors += diags.filter((d) => d.severity === vscode.DiagnosticSeverity.Error).length;
          }
        }
        activity.add({ kind: 'diagnostics', errors });
      }, 10000);
      diagTimer.unref?.();
    })
  );

  if ('onDidStartTerminalShellExecution' in vscode.window) {
    try {
      context.subscriptions.push(
        (vscode.window as any).onDidStartTerminalShellExecution((e: any) => {
          const cfg = config();
          if (!cfg.follow || !cfg.followCommands) return;
          const cmd = (e.execution?.commandLine?.value || '').slice(0, 200);
          if (cmd) activity.add({ kind: 'run', command: cmd });
        })
      );
    } catch {
      // shell integration not available
    }
  }

  if ('onDidEndTerminalShellExecution' in vscode.window) {
    try {
      context.subscriptions.push(
        (vscode.window as any).onDidEndTerminalShellExecution((e: any) => {
          const cfg = config();
          if (!cfg.follow || !cfg.followCommands) return;
          const cmd = (e.execution?.commandLine?.value || '').slice(0, 200);
          const exit = typeof e.exitCode === 'number' ? e.exitCode : undefined;
          if (cmd) activity.add({ kind: 'run', command: cmd, exit });
          if (exit !== undefined) {
            void flushActivity();
          }
        })
      );
    } catch {
      // shell integration not available
    }
  }

  // Auto refresh: while the Now tab is on screen, apply new activity every few seconds (sfpHive.autoRefreshSeconds; 0 = manual).
  let refreshTimer: ReturnType<typeof setTimeout> | undefined;
  let stopped = false;
  const scheduleRefresh = () => {
    if (stopped) return;
    const secs = config().autoRefreshSeconds;
    refreshTimer = setTimeout(async () => {
      try {
        if (secs > 0 && studioProvider?._view?.visible !== false) {
          if (activity.size > 0) await flushActivity();
          else studioProvider?.syncState();
        } else if (activity.size > 0) {
          await flushActivity();      // manual mode and a hidden view still apply pending activity, just not often
        }
      } finally {
        scheduleRefresh();
      }
    }, Math.max(secs > 0 ? secs : 20, 2) * 1000);
    refreshTimer.unref?.();
  };
  scheduleRefresh();
  context.subscriptions.push({ dispose: () => { stopped = true; if (refreshTimer) clearTimeout(refreshTimer); } });

  reg('sfpHive.doctor', () => runDoctor(true));
  reg('sfpHive.choose', () => choose());
  reg('sfpHive.focusNow', async () => {
    await vscode.commands.executeCommand('sfpHive.stack.focus');
    studioProvider?.showTab('now');
  });
  reg('sfpHive.toggleAutoSkills', async () => {
    const c = vscode.workspace.getConfiguration('sfpHive');
    const on = !c.get<boolean>('autoSkills', true);
    await c.update('autoSkills', on, vscode.ConfigurationTarget.Workspace);
    autoLastText = '';
    studioProvider?.syncState();
    void vscode.window.showInformationMessage(on ? 'SFP Hive now gives the agent its skills automatically.' : 'Automatic skills are off. Use Copy prompt to give the agent its skills.');
  });
  reg('sfpHive.addFromGit', (source?: string) => addSkillFromGitWorkflow(typeof source === 'string' ? source : undefined));
  reg('sfpHive.focusLibrary', async () => {
    await vscode.commands.executeCommand('sfpHive.stack.focus');
    studioProvider?.showTab('library');
  });
  reg('sfpHive.searchSkills', async () => {
    const root = sfpRoot();
    if (!root) return;
    if (!loadedLibrary) await libraryProvider?.loadLibrary();
    if (!loadedLibrary) return;
    const qp = vscode.window.createQuickPick();
    qp.placeholder = 'Search skills in library (type to filter)...';
    const updateItems = (q: string) => {
      const hits = q ? library.searchLibrary(loadedLibrary!, q) : undefined;
      const names = hits ? hits.map((h) => h.name) : Object.keys(loadedLibrary!.skills).sort();
      qp.items = names.map((name) => {
        const s = loadedLibrary!.skills[name];
        return {
          label: name,
          description: s?.d,
          detail: `${s?.purpose || ''} · ${s?.cluster || ''}${s?.app ? ` · needs ${s.app}` : ''}`,
        };
      });
    };
    updateItems('');
    qp.onDidChangeValue((v) => updateItems(v));
    qp.onDidAccept(async () => {
      const selected = qp.selectedItems[0];
      qp.dispose();
      if (selected) {
        await showSkillDetail(selected.label);
      }
    });
    qp.show();
  });
  reg('sfpHive.applyBundle', async () => {
    const root = sfpRoot();
    if (!root) return;
    if (!loadedLibrary) await libraryProvider?.loadLibrary();
    if (!loadedLibrary) return;
    const picks = loadedLibrary.bundles.map((b) => ({
      label: b.name,
      description: `${b.skills.length} skills (~${b.tokens} tokens)`,
      detail: `${b.goal} [${b.skills.join(' → ')}]`,
      bundleId: b.id,
    }));
    const pick = await vscode.window.showQuickPick(picks, { placeHolder: 'Apply which bundle?' });
    if (pick) {
      await applyBundleWorkflow(pick.bundleId);
    }
  });
  reg('sfpHive.focusModels', async () => {
    const home = os.homedir();
    const routesFile = path.join(process.env.SFP_DATA_DIR || path.join(home, '.sfp'), 'routes.json');
    if (!fs.existsSync(routesFile)) {
      await vscode.commands.executeCommand('sfpHive.routerSetup');
    }
    try {
      modelsProvider?.focus();
      await vscode.commands.executeCommand('sfpHive.models.focus');
    } catch {
      // models view might not be registered yet
    }
  });
  reg('sfpHive.routerStart', async () => {
    await startRouter();
  });
  reg('sfpHive.routerStop', () => {
    stopRouter();
  });
  reg('sfpHive.routerSetup', async () => {
    const root = sfpRoot();
    if (!root) return;
    const cfg = config();
    try {
      await hive.run(hive.pythonCommand(cfg.opts), hive.routeArgs(root, 'setup', '--yes'));
      await modelsProvider?.loadConfig();
      modelsProvider?.syncState();
      void vscode.window.showInformationMessage('SFP Hive: Model router set up successfully.');
    } catch (err: any) {
      void vscode.window.showErrorMessage(`Failed to set up router: ${err.message}`);
    }
  });

  // Watch catalog.json and data files for library reload
  try {
    const sfp = sfpRoot();
    if (sfp && 'createFileSystemWatcher' in vscode.workspace) {
      const home = os.homedir();
      let reloadTimer: NodeJS.Timeout | undefined;
      const triggerReload = () => {
        if (reloadTimer) clearTimeout(reloadTimer);
        reloadTimer = setTimeout(() => {
          void libraryProvider?.loadLibrary();
        }, 1000);
      };
      const catWatcher = vscode.workspace.createFileSystemWatcher(
        'RelativePattern' in vscode
          ? new (vscode as any).RelativePattern(sfp, 'catalog.json')
          : path.join(sfp, 'catalog.json')
      );
      catWatcher.onDidChange?.(triggerReload);
      catWatcher.onDidCreate?.(triggerReload);
      catWatcher.onDidDelete?.(triggerReload);
      const dataWatcher = vscode.workspace.createFileSystemWatcher(
        'RelativePattern' in vscode
          ? new (vscode as any).RelativePattern(path.join(home, '.sfp'), '{bundles.json,clusters.json,feedback.jsonl}')
          : path.join(home, '.sfp', '*.json*')
      );
      dataWatcher.onDidChange?.(triggerReload);
      dataWatcher.onDidCreate?.(triggerReload);
      dataWatcher.onDidDelete?.(triggerReload);
      context.subscriptions.push(catWatcher, dataWatcher);
    }
  } catch {
    // file watchers not supported
  }
  void libraryProvider.loadLibrary();
  reg('sfpHive.copyPrompt', async () => {
    const root = sfpRoot();
    if (!root) return;
    const targetSel = selection || (lastTrackResult?.skills && lastTrackResult.skills.length ? {
      task: `Phase: ${lastTrackResult.phase}`,
      stack: lastTrackResult.skills,
      layers: {
        base: lastTrackResult.skills.filter((s) => s.layer === 'base').map((s) => s.name),
        check: lastTrackResult.skills.filter((s) => s.layer === 'check').map((s) => s.name),
        finish: lastTrackResult.skills.filter((s) => s.layer === 'finish').map((s) => s.name),
      },
      tokens: lastTrackResult.skills.reduce((acc, s) => acc + (s.tokens || 0), 0),
      next: (lastTrackResult.next || []).map((n) => ({ name: n.phase, probability: n.probability })),
    } : undefined);
    if (!targetSel) return;
    await vscode.env.clipboard.writeText(hive.buildPrompt(targetSel, root));
    void vscode.window.showInformationMessage('Prompt copied. Paste it into the agent panel.');
  });
  reg('sfpHive.showSkill', async (arg) => {
    const n = typeof arg === 'string' ? arg : skillOf(arg)?.name;
    if (n) await showSkillDetail(n);
  });
  reg('sfpHive.openSkill', async (arg) => {
    const root = sfpRoot();
    const s = skillOf(arg);
    const file = root && s ? hive.skillFile(root, s) : undefined;
    if (file) await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(file), { preview: true });
  });
  for (const v of ['helped', 'unhelpful', 'ignored'] as const) {
    reg(`sfpHive.${v}`, (arg) => {
      const s = skillOf(arg);
      return s && sendFeedback(v, [s.name]);
    });
  }
  reg('sfpHive.missing', async () => {
    const root = sfpRoot();
    if (!root || !selection) return;
    const chosen = new Set(selection.stack.map((s) => s.name));
    const pick = await vscode.window.showQuickPick(hive.catalogNames(root).filter((n) => !chosen.has(n)), { placeHolder: 'Which skill should have been chosen?' });
    if (pick) await sendFeedback('missing', [pick]);
  });
  reg('sfpHive.status', () => terminal((root) => [`${root}/mcp/sfp_hive.py`, 'status']));
  reg('sfpHive.train', () => terminal((root) => [`${root}/mcp/sfp_hive.py`, 'train']));
  reg('sfpHive.install', async () => {
    const root = sfpRoot();
    if (!root) return;
    const profiles = hive.profileNames(root);
    const profile = await vscode.window.showQuickPick(profiles.length ? profiles : ['starter'], { placeHolder: 'Which preset?' });
    if (profile) terminal((r) => [`${r}/scripts/install.py`, 'install', '--tools', config().tool, '--project', project() ?? '.', '--profile', profile]);
  });
  reg('sfpHive.rules', () => terminal((r) => [`${r}/scripts/install.py`, 'rules', '--tools', config().tool, '--project', project() ?? '.']));
  reg('sfpHive.apps', async () => {
    const root = sfpRoot();
    if (!root) return;
    const apps = hive.appList(root);
    const pick = await vscode.window.showQuickPick(apps.map((a) => ({ label: a.name, description: a.id, detail: a.what })), { placeHolder: 'Show the install plan for...' });
    if (pick) terminal((r) => [`${r}/scripts/install.py`, 'apps', 'install', pick.description!]);
  });
  reg('sfpHive.clusterAdd', () => clusterAddWorkflow());
  reg('sfpHive.clusterRemove', () => clusterRemoveWorkflow());
  void fetchClusters().then(() => studioProvider?.syncState());

  if ('chat' in vscode && typeof (vscode as any).chat?.createChatParticipant === 'function') {
    try {
      const askLiveChat = async (draft: string, state: hive.LiveState | undefined, change: hive.LiveChange) => {
        const root = sfpRoot();
        if (!root) throw new Error('SFP checkout not found');
        const py = hive.pythonCommand(config().opts);
        const args = hive.liveArgs(root, draft, state, project(), config().max, change);
        const out = await hive.run(py, args);
        return hive.parseLive(out);
      };
      const chatLiveSession = new LiveSession({ ask: askLiveChat, show() {} }, config().autoAttachDelayMs);

      const participant = (vscode as any).chat.createChatParticipant('sfp.hive', async (request: any, _chatContext: any, stream: any) => {
        stream.progress('Analyzing prompt with SFP Hive...');
        const root = sfpRoot();
        if (!root) {
          stream.markdown('SFP checkout not found.');
          return;
        }
        try {
          const cfg = config();
          const liveRes = await chatLiveSession.send(request.prompt);
          if (liveRes && liveRes.attached.length > 0) {
            const skillRows = liveRes.attached.map((s) => ({
              name: s.name,
              category: s.category,
              description: s.description,
              layer: 'base' as const,
              tokens: 1000,
            }));
            const sel: hive.Selection = {
              task: request.prompt,
              stack: skillRows,
              layers: {
                base: skillRows.map((s) => s.name),
                check: [],
                finish: [],
              },
              tokens: skillRows.reduce((a, s) => a + s.tokens, 0),
              next: [],
              decision: liveRes.decision,
            };
            selection = sel;
            showStatus();
            updateRightStatus();
            stream.markdown(hive.buildPrompt(sel, root));
          } else {
            const out = await hive.run(hive.pythonCommand(cfg.opts), hive.selectArgs(root, request.prompt, project(), cfg.max));
            const sel = hive.parseSelection(out);
            selection = sel;
            showStatus();
            updateRightStatus();
            stream.markdown(hive.buildPrompt(sel, root));
          }
        } catch (err: any) {
          stream.markdown(`Failed to select skills: ${err.message}`);
        }
      });
      participant.iconPath = vscode.Uri.file(path.join(context.extensionPath, 'media', 'hive.svg'));
      context.subscriptions.push(participant);
    } catch {
      // Chat API not available in this environment
    }
  }

  void runDoctor(false);
  if ('onDidChangeConfiguration' in vscode.workspace && typeof (vscode.workspace as any).onDidChangeConfiguration === 'function') {
    context.subscriptions.push(
      (vscode.workspace as any).onDidChangeConfiguration((e: any) => {
        if (e?.affectsConfiguration?.('sfpHive.sfpPath')) {
          void runDoctor(false);
        }
      })
    );
  }
}

export function deactivate() {
  stopRouter();
}
