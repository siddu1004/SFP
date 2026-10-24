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
      updateRightStatus();
      studioProvider?.syncState();
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
    studioProvider?.syncState();
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
          this.syncState();
          break;
        case 'choose':
          if (message.task) await choose(message.task);
          break;
        case 'feedback':
          if (message.skill && message.verdict) {
            await sendFeedback(message.verdict, [message.skill]);
          }
          break;
        case 'openSkill':
          const root = sfpRoot();
          if (root && message.skill) {
            const skill = selection?.stack.find((s) => s.name === message.skill);
            const file = skill ? hive.skillFile(root, skill) : undefined;
            if (file) {
              await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(file), { preview: true });
            }
          }
          break;
        case 'copyPrompt':
          await vscode.commands.executeCommand('sfpHive.copyPrompt');
          break;
        case 'train':
          await vscode.commands.executeCommand('sfpHive.train');
          break;
      }
    });
  }

  public showTab(tab: 'now' | 'choose' | 'library' | 'insights') {
    if (this._view) {
      this._view.show?.(true);
      this._view.webview.postMessage({ type: 'switchTab', tab });
    }
  }

  public syncState() {
    if (!this._view) return;
    this._view.webview.postMessage({
      type: 'updateState',
      payload: {
        task: selection?.task ?? '',
        skills: selection?.stack ?? [],
        decision: selection?.decision,
      },
    });
  }

  private getHtml(webview: vscode.Webview): string {
    const nonce = getNonce();
    const styleUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'studio.css')));
    const scriptUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'studio.js')));
    const iconUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.extensionPath, 'media', 'hive.svg')));

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}'; img-src ${webview.cspSource} https: data:;">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SFP Hive Studio</title>
  <link rel="stylesheet" href="${styleUri}">
</head>
<body>
  <div class="studio-header">
    <div class="studio-title-bar">
      <div class="studio-brand">
        <img class="icon" src="${iconUri}" alt="Hive">
        <span>SFP Hive</span>
      </div>
      <div class="studio-badge" id="studio-status-badge">Ready</div>
    </div>
    <div class="tab-bar" role="tablist" aria-label="SFP Hive Studio Navigation">
      <button class="tab-btn active" data-tab="now" role="tab" aria-selected="true" aria-controls="tab-now" id="btn-tab-now" tabindex="0">
        <svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M1 8.5h3.2l1.6-4.5 3.4 9 2.1-5.5H15v-1h-4.2l-1.6 4.2-3.4-9-2.1 6.8H1v1z"/></svg>
        <span>Now</span>
      </button>
      <button class="tab-btn" data-tab="choose" role="tab" aria-selected="false" aria-controls="tab-choose" id="btn-tab-choose" tabindex="-1">
        <svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M11.5 7a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0zm-.8 3.9l3.6 3.6.7-.7-3.6-3.6a5.5 5.5 0 1 0-.7.7z"/></svg>
        <span>Choose</span>
      </button>
      <button class="tab-btn" data-tab="library" role="tab" aria-selected="false" aria-controls="tab-library" id="btn-tab-library" tabindex="-1">
        <svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M3 2v12h10V2H3zm9 11H4V3h8v10zM5 5h6v1H5V5zm0 3h6v1H5V8zm0 3h4v1H5v-1z"/></svg>
        <span>Library</span>
      </button>
      <button class="tab-btn" data-tab="insights" role="tab" aria-selected="false" aria-controls="tab-insights" id="btn-tab-insights" tabindex="-1">
        <svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M1 14h14v1H1v-1zm2-2h2V7H3v5zm4 0h2V3H7v9zm4 0h2V5h-2v7z"/></svg>
        <span>Insights</span>
      </button>
    </div>
  </div>

  <!-- Tab 1: Now -->
  <div class="tab-content active" id="tab-now" role="tabpanel" aria-labelledby="btn-tab-now">
    <div class="section">
      <div class="section-title">
        <span>Current Phase &amp; Activity</span>
        <button class="btn-icon" data-action="refresh" aria-label="Refresh Phase" title="Refresh">
          <svg viewBox="0 0 16 16"><path fill="currentColor" d="M13.6 2.4A7 7 0 1 0 15 8h-1.5a5.5 5.5 0 1 1-1.1-4.4L10 6h5V1l-1.4 1.4z"/></svg>
        </button>
      </div>
      <div class="card" id="now-phase-card">
        <div class="card-header">
          <span class="card-title" id="now-phase-name">Idle</span>
          <span class="studio-badge" id="now-confidence-badge">0% conf</span>
        </div>
        <div class="progress-container">
          <div class="progress-track"><div class="progress-fill" id="now-confidence-fill" style="width: 0%;"></div></div>
        </div>
        <div class="card-meta">
          <span id="now-phase-detail">Watching workspace events</span>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Active Skills</div>
      <div class="state-box" id="now-empty-state">
        <svg viewBox="0 0 16 16"><path fill="currentColor" d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 13a6 6 0 1 1 0-12 6 6 0 0 1 0 12zm-.5-9h1v2h-1V5zm0 3h1v4h-1V8z"/></svg>
        <span>No workspace activity recorded yet. Edit a file, run a test, or start a task.</span>
      </div>
      <div id="now-skills-list" style="display: none; flex-direction: column; gap: 8px;"></div>
    </div>
  </div>

  <!-- Tab 2: Choose -->
  <div class="tab-content" id="tab-choose" role="tabpanel" aria-labelledby="btn-tab-choose">
    <div class="section">
      <div class="section-title">Task Prompt</div>
      <div style="display: flex; gap: 8px;">
        <input type="text" id="choose-task-input" class="input-text" placeholder="What are you about to do?" aria-label="Task prompt input">
        <button class="btn" data-action="choose" aria-label="Choose skills for task">Choose</button>
      </div>
    </div>
    <div class="section">
      <div class="section-title">Skill Stack</div>
      <div class="state-box" id="choose-empty-state">
        <svg viewBox="0 0 16 16"><path fill="currentColor" d="M11.5 7a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0zm-.8 3.9l3.6 3.6.7-.7-3.6-3.6a5.5 5.5 0 1 0-.7.7z"/></svg>
        <span>Type a task above or select text in the editor to inspect skills.</span>
      </div>
    </div>
  </div>

  <!-- Tab 3: Library -->
  <div class="tab-content" id="tab-library" role="tabpanel" aria-labelledby="btn-tab-library">
    <div class="section">
      <div class="section-title">Skill Library &amp; Clusters</div>
      <input type="text" id="library-search-input" class="input-text" placeholder="Search 819 skills..." aria-label="Search skills and clusters">
      <div class="state-box" id="library-empty-state">
        <svg viewBox="0 0 16 16"><path fill="currentColor" d="M3 2v12h10V2H3zm9 11H4V3h8v10zM5 5h6v1H5V5zm0 3h6v1H5V8zm0 3h4v1H5v-1z"/></svg>
        <span>Search 819 skills across 24 categories or browse clusters.</span>
      </div>
    </div>
  </div>

  <!-- Tab 4: Insights -->
  <div class="tab-content" id="tab-insights" role="tabpanel" aria-labelledby="btn-tab-insights">
    <div class="section">
      <div class="section-title">
        <span>Learning &amp; Usage</span>
        <button class="btn btn-secondary" data-action="train" aria-label="Train model">Train</button>
      </div>
      <div class="state-box" id="insights-empty-state">
        <svg viewBox="0 0 16 16"><path fill="currentColor" d="M1 14h14v1H1v-1zm2-2h2V7H3v5zm4 0h2V3H7v9zm4 0h2V5h-2v7z"/></svg>
        <span>No learning decisions recorded yet. Start choosing skills and reporting feedback.</span>
      </div>
    </div>
  </div>

  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }
}

function getNonce(): string {
  let text = '';
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}

export function activate(context: vscode.ExtensionContext) {
  const view = new StackView();
  status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  status.command = 'sfpHive.choose';
  showStatus();
  status.show();

  rightStatus = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  rightStatus.command = 'sfpHive.focusNow';
  updateRightStatus();
  rightStatus.show();

  studioProvider = new StudioViewProvider(context.extensionPath);

  const reg = (id: string, fn: (...a: any[]) => unknown) => context.subscriptions.push(vscode.commands.registerCommand(id, fn));
  context.subscriptions.push(
    status,
    rightStatus,
    vscode.window.registerTreeDataProvider('sfpHive.stack', view),
    vscode.window.registerWebviewViewProvider(StudioViewProvider.viewType, studioProvider)
  );

  reg('sfpHive.choose', () => choose());
  reg('sfpHive.focusNow', async () => {
    await vscode.commands.executeCommand('sfpHive.stack.focus');
    studioProvider?.showTab('now');
  });
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
