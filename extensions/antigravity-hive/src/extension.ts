import * as vscode from 'vscode';
import * as path from 'path';
import * as hive from './hive';

let selection: hive.Selection | undefined;
const verdicts = new Map<string, hive.Verdict>();
let status: vscode.StatusBarItem;
const changed = new vscode.EventEmitter<void>();

type Node = { kind: 'layer'; layer: string; skills: hive.Skill[] } | { kind: 'skill'; skill: hive.Skill };

class StackView implements vscode.TreeDataProvider<Node> {
  onDidChangeTreeData = changed.event;

  getChildren(node?: Node): Node[] {
    if (!selection) return [];
    if (!node) return hive.byLayer(selection).map((g) => ({ kind: 'layer' as const, layer: g.layer, skills: g.skills }));
    return node.kind === 'layer' ? node.skills.map((skill) => ({ kind: 'skill' as const, skill })) : [];
  }

  getTreeItem(node: Node): vscode.TreeItem {
    if (node.kind === 'layer') {
      const item = new vscode.TreeItem(node.layer[0].toUpperCase() + node.layer.slice(1), vscode.TreeItemCollapsibleState.Expanded);
      item.description = node.layer === 'base' ? 'do first' : node.layer === 'check' ? 'then verify' : 'to finish';
      return item;
    }
    const s = node.skill;
    const item = new vscode.TreeItem(s.name, vscode.TreeItemCollapsibleState.None);
    const verdict = verdicts.get(s.name);
    item.description = [s.phase, s.tokens ? `${s.tokens} tokens` : '', verdict ? `(${verdict})` : ''].filter(Boolean).join(' · ');
    item.tooltip = new vscode.MarkdownString([`**${s.name}**`, ...(s.reasons ?? []).map((r) => `- ${r}`)].join('\n\n'));
    item.contextValue = 'skill';
    item.iconPath = new vscode.ThemeIcon(verdict === 'helped' ? 'thumbsup' : verdict === 'unhelpful' ? 'thumbsdown' : verdict === 'ignored' ? 'circle-slash' : 'sparkle');
    item.command = { command: 'sfpHive.openSkill', title: 'Open skill', arguments: [node] };
    return item;
  }
}

function config() {
  const c = vscode.workspace.getConfiguration('sfpHive');
  return {
    opts: { sfpPath: c.get<string>('sfpPath') || undefined, python: c.get<string>('python') || undefined },
    max: c.get<number>('maxSkills', 4),
    copy: c.get<boolean>('copyPromptAfterChoosing', true),
    tool: c.get<string>('installTool', 'antigravity'),
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

function showStatus() {
  status.text = selection ? `$(organization) Hive: ${selection.stack.length}` : '$(organization) Hive';
  status.tooltip = selection ? `Chosen for: ${selection.task}` : 'Choose skills for a task';
}

async function choose(preset?: string) {
  const root = sfpRoot();
  if (!root) return;
  const task = preset ?? (await vscode.window.showInputBox({ prompt: 'What are you about to do?', placeHolder: 'add an accessible signup form', ignoreFocusOut: true }));
  if (!task || !task.trim()) return;
  const cfg = config();
  await vscode.window.withProgress({ location: vscode.ProgressLocation.Window, title: 'SFP Hive: choosing skills' }, async () => {
    try {
      const out = await hive.run(hive.pythonCommand(cfg.opts), hive.selectArgs(root, task.trim(), project(), cfg.max));
      selection = hive.parseSelection(out);
      verdicts.clear();
      await vscode.commands.executeCommand('setContext', 'sfpHive.hasSelection', selection.stack.length > 0);
      changed.fire();
      showStatus();
      await vscode.commands.executeCommand('workbench.view.extension.sfpHive');
      if (!selection.stack.length) {
        void vscode.window.showInformationMessage('The hive found no skill that fits that task.');
      } else if (cfg.copy) {
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
  if (!root || !selection || !names.length) return;
  if (!selection.decision) {
    void vscode.window.showWarningMessage('Feedback is off: SFP_NO_USAGE_LOG is set, so the hive logs nothing and learns nothing.');
    return;
  }
  try {
    await hive.run(hive.pythonCommand(config().opts), hive.feedbackArgs(root, selection.decision, verdict, names, selection.task));
    names.forEach((n) => verdict !== 'missing' && verdicts.set(n, verdict));
    changed.fire();
    void vscode.window.setStatusBarMessage(`SFP Hive: noted ${verdict}: ${names.join(', ')}`, 4000);
  } catch (e) {
    void vscode.window.showErrorMessage(`SFP Hive: ${(e as Error).message}`);
  }
}

function skillOf(arg: unknown): hive.Skill | undefined {
  const node = arg as Node | undefined;
  return node && node.kind === 'skill' ? node.skill : undefined;
}

function terminal(args: (root: string) => string[]) {
  const root = sfpRoot();
  if (!root) return;
  const t = vscode.window.createTerminal({ name: 'SFP', cwd: project() ?? root });
  t.show();
  t.sendText([hive.quote(hive.pythonCommand(config().opts)), ...args(root).map(hive.quote)].join(' '));
}

export function activate(context: vscode.ExtensionContext) {
  const view = new StackView();
  status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  status.command = 'sfpHive.choose';
  showStatus();
  status.show();
  const reg = (id: string, fn: (...a: any[]) => unknown) => context.subscriptions.push(vscode.commands.registerCommand(id, fn));
  context.subscriptions.push(status, vscode.window.registerTreeDataProvider('sfpHive.stack', view));

  reg('sfpHive.choose', () => choose());
  reg('sfpHive.copyPrompt', async () => {
    const root = sfpRoot();
    if (!selection || !root) return;
    await vscode.env.clipboard.writeText(hive.buildPrompt(selection, root));
    void vscode.window.showInformationMessage('Prompt copied. Paste it into the agent panel.');
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

  if ('chat' in vscode && typeof (vscode as any).chat?.createChatParticipant === 'function') {
    try {
      const participant = (vscode as any).chat.createChatParticipant('sfp.hive', async (request: any, _chatContext: any, stream: any) => {
        stream.progress('Analyzing prompt with SFP Hive...');
        const root = sfpRoot();
        if (!root) {
          stream.markdown('SFP checkout not found.');
          return;
        }
        try {
          const cfg = config();
          const out = await hive.run(hive.pythonCommand(cfg.opts), hive.selectArgs(root, request.prompt, project(), cfg.max));
          const sel = hive.parseSelection(out);
          stream.markdown(hive.buildPrompt(sel, root));
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
}

export function deactivate() {}
