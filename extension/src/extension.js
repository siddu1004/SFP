const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const { HiveBridge } = require('./hiveBridge');

/**
 * SkillMonitorProvider implements the WebviewViewProvider for SFP Hive
 */
class SkillMonitorProvider {
  static viewType = 'sfp.skillMonitor';

  constructor(extensionUri, sfpRoot) {
    this._extensionUri = extensionUri;
    this._sfpRoot = sfpRoot;
    this._bridge = new HiveBridge(sfpRoot);
    this._view = undefined;
    this._statusBarItem = null;

    this._currentPrompt = '';
    this._currentRes = null;
    this._previousSkillNames = new Set();
    this._userExcluded = new Set();
  }

  setStatusBarItem(item) {
    this._statusBarItem = item;
  }

  async syncFromActiveEditor() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showInformationMessage('No active editor open to sync prompt from.');
      return;
    }
    const selection = editor.document.getText(editor.selection).trim();
    const lineText = editor.document.lineAt(editor.selection.active.line).text.trim();
    const promptText = selection || lineText;

    if (promptText) {
      await this.analyzePrompt(promptText);
      vscode.window.setStatusBarMessage(`SFP Hive: Synced prompt from editor selection`, 3000);
    } else {
      vscode.window.showInformationMessage('Please select text or place cursor on a prompt/task line.');
    }
  }

  resolveWebviewView(webviewView, context, _token) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (message) => {
      switch (message.command) {
        case 'ready': {
          this._syncWebviewState();
          break;
        }

        case 'promptChanged': {
          await this.analyzePrompt(message.text);
          break;
        }

        case 'syncEditor': {
          await this.syncFromActiveEditor();
          break;
        }

        case 'toggleSkill': {
          if (message.enabled) {
            this._userExcluded.delete(message.skill);
          } else {
            this._userExcluded.add(message.skill);
          }
          this._syncWebviewState();
          break;
        }

        case 'openSkillFile': {
          await this._openSkillFile(message.path);
          break;
        }

        case 'feedback': {
          await this._recordFeedback(message.decisionId, message.skill, message.verdict);
          break;
        }

        case 'copyStack': {
          await this._copyStack(message.skills);
          break;
        }

        case 'train': {
          await this._trainHive();
          break;
        }
      }
    });
  }

  async analyzePrompt(promptText) {
    this._currentPrompt = (promptText || '').trim();

    if (!this._currentPrompt) {
      this._previousSkillNames.clear();
      this._currentRes = null;
      this._syncWebviewState({ added: [], removed: [] });
      if (this._statusBarItem) {
        this._statusBarItem.text = '$(sparkle) SFP Hive: Ready';
        this._statusBarItem.tooltip = 'Click to open SFP Live Skill Monitor';
      }
      vscode.commands.executeCommand('setContext', 'sfp.hasActiveSkills', false);
      return;
    }

    try {
      const workspaceFolders = vscode.workspace.workspaceFolders;
      const projectPath = workspaceFolders && workspaceFolders.length > 0 ? workspaceFolders[0].uri.fsPath : this._sfpRoot;

      const res = await this._bridge.selectSkills(this._currentPrompt, projectPath);
      if (res && res.stack) {
        const currentNames = new Set(res.stack.map(s => s.name));
        const added = [...currentNames].filter(x => !this._previousSkillNames.has(x));
        const removed = [...this._previousSkillNames].filter(x => !currentNames.has(x));

        this._previousSkillNames = currentNames;
        this._currentRes = res;

        if (this._statusBarItem) {
          const count = res.stack.length;
          this._statusBarItem.text = `$(sparkle) SFP Hive: ${count} skill${count === 1 ? '' : 's'}`;
          this._statusBarItem.tooltip = `Active skills: ${res.stack.map(s => s.name).join(', ')}`;
        }

        this._syncWebviewState({ added, removed });
        vscode.commands.executeCommand('setContext', 'sfp.hasActiveSkills', true);
      }
    } catch (err) {
      console.error('Error analyzing prompt in SFP Hive:', err);
    }
  }

  _syncWebviewState(diff = null) {
    if (!this._view) return;

    this._view.webview.postMessage({
      command: 'updateState',
      payload: {
        res: this._currentRes,
        diff: diff,
        excluded: Array.from(this._userExcluded),
        initialPrompt: this._currentPrompt
      }
    });
  }

  async _openSkillFile(relativePath) {
    try {
      let targetPath = '';
      if (relativePath && fs.existsSync(relativePath)) {
        targetPath = relativePath;
      } else if (relativePath) {
        targetPath = path.join(this._sfpRoot, relativePath);
      }

      if (targetPath && fs.existsSync(targetPath)) {
        const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(targetPath));
        await vscode.window.showTextDocument(doc);
      } else {
        vscode.window.showWarningMessage(`Skill file not found: ${relativePath}`);
      }
    } catch (e) {
      vscode.window.showErrorMessage(`Failed to open skill file: ${e.message}`);
    }
  }

  async _recordFeedback(decisionId, skill, verdict) {
    try {
      const feedbackPayload = {
        helped: verdict === 'helped' ? [skill] : [],
        unhelpful: verdict === 'unhelpful' ? [skill] : []
      };
      await this._bridge.giveFeedback(decisionId || 'last', feedbackPayload);
      vscode.window.setStatusBarMessage(`SFP Hive: Recorded ${verdict} for "${skill}"`, 3500);
    } catch (e) {
      console.error('Failed to record feedback:', e);
    }
  }

  async _copyStack(skills) {
    const active = (skills || []).filter(s => !this._userExcluded.has(s));
    if (!active.length) {
      vscode.window.showWarningMessage('No active skills in stack to copy.');
      return;
    }

    const textToCopy = `Skills: ${active.join(', ')}`;
    await vscode.env.clipboard.writeText(textToCopy);
    vscode.window.showInformationMessage(`Copied ${active.length} skills to clipboard!`);
  }

  async _trainHive() {
    vscode.window.withProgress({
      location: vscode.ProgressLocation.Notification,
      title: 'SFP Hive: Training model from benchmarks...',
      cancellable: false
    }, async () => {
      try {
        const result = await this._bridge.train();
        if (this._view) {
          this._view.webview.postMessage({ command: 'trainingFinished' });
        }
        vscode.window.showInformationMessage(
          `SFP Hive model trained! Learned associations: ${result.model_associations || 0} (${result.cases_processed || 0} cases)`
        );
      } catch (e) {
        if (this._view) {
          this._view.webview.postMessage({ command: 'trainingFinished' });
        }
        vscode.window.showErrorMessage(`Hive training failed: ${e.message}`);
      }
    });
  }

  _getHtmlForWebview(webview) {
    const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'style.css'));
    const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'main.js'));

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SFP Hive Live Monitor</title>
  <link rel="stylesheet" href="${styleUri}">
</head>
<body>
  <div class="header">
    <div class="brand">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2l8 4.5v9L12 20l-8-4.5v-9L12 2z"></path>
        <path d="M12 12l8-4.5"></path>
        <path d="M12 12v8"></path>
        <path d="M12 12L4 7.5"></path>
      </svg>
      <span>SFP Hive Monitor</span>
    </div>
    <div class="status-indicator">
      <div class="dot"></div>
      <span id="hiveStatusText">Live Hive</span>
    </div>
  </div>

  <div class="project-bar" id="projectTags"></div>

  <div class="prompt-box">
    <label for="promptInput">Prompt Skill Detector</label>
    <textarea id="promptInput" placeholder="Type prompt here... (e.g., 'build react checkout with Stripe and test it')"></textarea>
  </div>

  <div class="diff-container" id="diffContainer">
    <div class="diff-title">Prompt Skill Delta</div>
    <div class="diff-chips" id="diffChips"></div>
  </div>

  <div class="budget-bar">
    <div class="budget-info">
      <span>Context Budget</span>
      <span id="tokenCount">0 / 12,000 tokens</span>
    </div>
    <div class="budget-track">
      <div class="budget-fill" id="tokenFill"></div>
    </div>
  </div>

  <div id="emptyState" class="empty-state">
    <p>Type a task prompt above to see real-time skill detection, layer stacking, and dynamic prompt deltas.</p>
  </div>

  <div class="layer-section">
    <div class="layer-header">
      <div class="layer-title base">
        <span>⚡ Base Layer (Grounding)</span>
      </div>
      <span class="layer-count" id="baseCount">0</span>
    </div>
    <div id="baseSkills"></div>
  </div>

  <div class="layer-section">
    <div class="layer-header">
      <div class="layer-title check">
        <span>🛡️ Check Layer (Safety & Standards)</span>
      </div>
      <span class="layer-count" id="checkCount">0</span>
    </div>
    <div id="checkSkills"></div>
  </div>

  <div class="layer-section">
    <div class="layer-header">
      <div class="layer-title finish">
        <span>✨ Finish Layer (Review & Polish)</span>
      </div>
      <span class="layer-count" id="finishCount">0</span>
    </div>
    <div id="finishSkills"></div>
  </div>

  <div class="action-bar">
    <button id="copyStackBtn" class="btn-primary" title="Copy active skill names">📋 Copy Stack</button>
    <button id="trainBtn" class="btn-secondary" title="Retrain hive model from feedback">⚡ Train Model</button>
  </div>

  <script src="${scriptUri}"></script>
</body>
</html>`;
  }
}

function findSfpRoot() {
  const folders = vscode.workspace.workspaceFolders || [];
  for (const f of folders) {
    const p = f.uri.fsPath;
    if (fs.existsSync(path.join(p, 'catalog.json')) && fs.existsSync(path.join(p, 'mcp', 'sfp_hive.py'))) {
      return p;
    }
  }
  const hardcoded = 'c:\\Users\\saisi\\.antigravity-ide\\SFP';
  if (fs.existsSync(path.join(hardcoded, 'catalog.json'))) {
    return hardcoded;
  }
  const rel = path.resolve(__dirname, '../..');
  if (fs.existsSync(path.join(rel, 'catalog.json'))) {
    return rel;
  }
  return hardcoded;
}

/**
 * Activate extension
 */
function activate(context) {
  const sfpRoot = findSfpRoot();
  const provider = new SkillMonitorProvider(context.extensionUri, sfpRoot);

  // Status Bar Item
  const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = 'sfp.showMonitor';
  statusBarItem.text = '$(sparkle) SFP Hive: Ready';
  statusBarItem.tooltip = 'Click to open SFP Live Skill Monitor';
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  provider.setStatusBarItem(statusBarItem);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(SkillMonitorProvider.viewType, provider, {
      webviewOptions: { retainContextWhenHidden: true }
    })
  );

  // Commands
  context.subscriptions.push(
    vscode.commands.registerCommand('sfp.showMonitor', async () => {
      await vscode.commands.executeCommand('sfp.skillMonitor.focus');
    }),

    vscode.commands.registerCommand('sfp.syncEditorSelection', async () => {
      await vscode.commands.executeCommand('sfp.skillMonitor.focus');
      await provider.syncFromActiveEditor();
    }),

    vscode.commands.registerCommand('sfp.analyzePrompt', async () => {
      const input = await vscode.window.showInputBox({
        prompt: 'Enter prompt to analyze skills in SFP Hive',
        placeHolder: 'e.g., build react checkout with Stripe and test it'
      });
      if (input !== undefined) {
        await vscode.commands.executeCommand('sfp.skillMonitor.focus');
        await provider.analyzePrompt(input);
      }
    }),

    vscode.commands.registerCommand('sfp.trainHive', async () => {
      await provider._trainHive();
    }),

    vscode.commands.registerCommand('sfp.refreshCatalog', () => {
      provider._bridge._loadCatalog();
      vscode.window.showInformationMessage('SFP Catalog refreshed!');
    })
  );
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
  SkillMonitorProvider
};
