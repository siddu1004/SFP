// Loads the compiled extension against a small stand-in for the VS Code API, so the glue code is exercised
// without an editor: activate, choose skills with the real hive, read the tree, copy the prompt, send feedback.
const test = require('node:test');
const assert = require('node:assert');
const Module = require('module');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO = path.resolve(__dirname, '..', '..', '..');
const commands = new Map();
const state = { clipboard: '', messages: [], inputs: [], picks: [], contexts: {}, providers: {} };

class EventEmitter { constructor() { this.listeners = []; this.event = (l) => this.listeners.push(l); } fire() { this.listeners.forEach((l) => l()); } }
class TreeItem { constructor(label, collapsibleState) { this.label = label; this.collapsibleState = collapsibleState; } }
class ThemeIcon { constructor(id) { this.id = id; } }
class MarkdownString { constructor(v) { this.value = v; } }
const note = (kind) => async (m) => { state.messages.push([kind, m]); };

const vscode = {
  EventEmitter, TreeItem, ThemeIcon, MarkdownString,
  TreeItemCollapsibleState: { None: 0, Collapsed: 1, Expanded: 2 },
  StatusBarAlignment: { Left: 1, Right: 2 },
  ProgressLocation: { Window: 10 },
  ConfigurationTarget: { Global: 1, Workspace: 2, WorkspaceFolder: 3 },
  DiagnosticSeverity: { Error: 0, Warning: 1, Information: 2, Hint: 3 },
  window: {
    createStatusBarItem: (alignment, priority) => {
      const item = { alignment, priority, text: '', tooltip: '', command: '', show() {}, dispose() {} };
      state.statusBarItems = state.statusBarItems || [];
      state.statusBarItems.push(item);
      return item;
    },
    registerTreeDataProvider: (id, p) => { state.providers[id] = p; return { dispose() {} }; },
    registerWebviewViewProvider: (id, p) => { state.webviewProviders = state.webviewProviders || {}; state.webviewProviders[id] = p; return { dispose() {} }; },
    showInputBox: async () => state.inputs.shift(),
    showQuickPick: async (items) => state.picks.length ? state.picks.shift() : undefined,
    showInformationMessage: note('info'), showErrorMessage: note('error'), showWarningMessage: note('warn'),
    setStatusBarMessage: (m) => state.messages.push(['status', m]),
    withProgress: async (_o, fn) => fn(),
    createTerminal: () => ({ show() {}, sendText: (t) => state.messages.push(['terminal', t]) }),
    showTextDocument: async () => {},
    onDidChangeActiveTextEditor: (l) => { state.openListeners = state.openListeners || []; state.openListeners.push(l); return { dispose() {} }; },
    onDidStartTerminalShellExecution: (l) => { state.termStartListeners = state.termStartListeners || []; state.termStartListeners.push(l); return { dispose() {} }; },
    onDidEndTerminalShellExecution: (l) => { state.termEndListeners = state.termEndListeners || []; state.termEndListeners.push(l); return { dispose() {} }; },
  },
  commands: {
    registerCommand: (id, fn) => { commands.set(id, fn); return { dispose() {} }; },
    executeCommand: async (id, ...args) => {
      if (id === 'setContext') { state.contexts[args[0]] = args[1]; return; }
      return commands.has(id) ? commands.get(id)(...args) : undefined;
    },
  },
  workspace: {
    workspaceFolders: [{ uri: { fsPath: REPO } }],
    getConfiguration: () => ({
      get: (k, d) => ({ sfpPath: REPO, maxSkills: 3, follow: true, followCommands: true }[k] ?? d),
      update: async (k, v) => { state.settings = state.settings || {}; state.settings[k] = v; },
    }),
    openTextDocument: async (f) => f,
    onDidSaveTextDocument: (l) => { state.saveListeners = state.saveListeners || []; state.saveListeners.push(l); return { dispose() {} }; },
    onDidCreateFiles: (l) => { state.createListeners = state.createListeners || []; state.createListeners.push(l); return { dispose() {} }; },
    onDidDeleteFiles: (l) => { state.deleteListeners = state.deleteListeners || []; state.deleteListeners.push(l); return { dispose() {} }; },
  },
  languages: {
    onDidChangeDiagnostics: (l) => { state.diagListeners = state.diagListeners || []; state.diagListeners.push(l); return { dispose() {} }; },
    getDiagnostics: () => state.diagnostics || [],
  },
  env: { clipboard: { writeText: async (t) => { state.clipboard = t; } } },
  Uri: { file: (f) => ({ fsPath: f }) },
  chat: {
    createChatParticipant: (id, handler) => {
      state.chatParticipants = state.chatParticipants || new Map();
      state.chatParticipants.set(id, handler);
      return { iconPath: undefined, dispose() {} };
    },
  },
};

const load = Module._load;
Module._load = function (request, ...rest) { return request === 'vscode' ? vscode : load.call(this, request, ...rest); };
const ext = require('../out/extension.js');

test('activates and registers every command in package.json', () => {
  const workspaceStateData = new Map();
  ext.activate({
    subscriptions: [],
    extensionPath: REPO,
    workspaceState: {
      get: (k, d) => (workspaceStateData.has(k) ? workspaceStateData.get(k) : d),
      update: async (k, v) => workspaceStateData.set(k, v),
    },
  });
  const declared = require('../package.json').contributes.commands.map((c) => c.command);
  declared.forEach((id) => assert.ok(commands.has(id), id));
  assert.ok(state.providers['sfpHive.stack']);
  assert.ok(state.chatParticipants && state.chatParticipants.has('sfp.hive'));
});

test('choosing skills fills the tree, copies the prompt and sets the context', async () => {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hive-ext-'));
  process.env.SFP_DATA_DIR = data;
  delete process.env.SFP_NO_USAGE_LOG;
  state.inputs.push('write table driven tests for a go parser');
  await commands.get('sfpHive.choose')();
  assert.strictEqual(state.contexts['sfpHive.hasSelection'], true);
  const tree = state.providers['sfpHive.stack'];
  const layers = tree.getChildren();
  assert.ok(layers.length > 0);
  const skills = layers.flatMap((l) => tree.getChildren(l));
  assert.ok(skills.length > 0);
  const item = tree.getTreeItem(skills[0]);
  assert.strictEqual(item.contextValue, 'skill');
  assert.strictEqual(item.command.command, 'sfpHive.openSkill');
  assert.ok(state.clipboard.includes(skills[0].skill.name));
});

test('marking a skill helped records feedback and updates the tree', async () => {
  const tree = state.providers['sfpHive.stack'];
  const node = tree.getChildren().flatMap((l) => tree.getChildren(l))[0];
  await commands.get('sfpHive.helped')(node);
  assert.strictEqual(tree.getTreeItem(node).iconPath.id, 'thumbsup');
  const log = path.join(process.env.SFP_DATA_DIR, 'feedback.jsonl');
  assert.match(fs.readFileSync(log, 'utf8'), new RegExp(node.skill.name));
});

test('the install commands send a plan to the terminal, not a silent install', async () => {
  state.picks.push('starter');
  await commands.get('sfpHive.install')();
  const sent = state.messages.filter((m) => m[0] === 'terminal').map((m) => m[1]).join('\n');
  assert.match(sent, /install\.py["']?\s+install --tools antigravity/);
  state.picks.push({ label: 'OmniRoute', description: 'omniroute' });
  await commands.get('sfpHive.apps')();
  assert.match(state.messages.filter((m) => m[0] === 'terminal').pop()[1], /apps install omniroute$/);
});

test('the train command runs sfp_hive.py train in the terminal', async () => {
  await commands.get('sfpHive.train')();
  const lastTerminal = state.messages.filter((m) => m[0] === 'terminal').pop()[1];
  assert.match(lastTerminal, /sfp_hive\.py["']?\s+train/);
});

test('@hive chat participant responds with the skill selection prompt', async () => {
  const handler = state.chatParticipants.get('sfp.hive');
  assert.ok(handler);
  let reply = '';
  const stream = {
    progress: () => {},
    markdown: (md) => { reply += md; },
  };
  await handler({ prompt: 'write table driven tests for a go parser' }, {}, stream);
  assert.ok(reply.includes('Use these SFP skills, in this order'));
});

test('Stage 2: registers the SFP Hive Studio webview provider and right status bar item', async () => {
  assert.ok(state.webviewProviders['sfpHive.stack'], 'webview provider should be registered');
  const provider = state.webviewProviders['sfpHive.stack'];
  let html = '';
  const webviewView = {
    webview: {
      options: {},
      asWebviewUri: (uri) => uri.fsPath,
      cspSource: 'vscode-webview:',
      postMessage: (msg) => { state.lastPostedMessage = msg; },
      onDidReceiveMessage: () => {},
      set html(val) { html = val; },
    },
    show: () => {},
  };
  provider.resolveWebviewView(webviewView, {}, {});
  assert.ok(html.includes('Content-Security-Policy'), 'Must have CSP');
  assert.ok(html.includes('studio.css'), 'Must load studio.css');
  assert.ok(html.includes('studio.js'), 'Must load studio.js');
  assert.ok(html.includes('data-tab="now"'), 'Must have Now tab');
  assert.ok(html.includes('data-tab="choose"'), 'Must have Choose tab');
  assert.ok(html.includes('data-tab="library"'), 'Must have Library tab');
  assert.ok(html.includes('data-tab="insights"'), 'Must have Insights tab');

  const right = state.statusBarItems.find((i) => i.alignment === 2);
  assert.ok(right, 'Right status bar item must exist');
  assert.strictEqual(right.command, 'sfpHive.focusNow');

  await commands.get('sfpHive.focusNow')();
  assert.deepStrictEqual(state.lastPostedMessage, { type: 'switchTab', tab: 'now' });
});

test('Stage 3: workspace events feed ActivityBuffer and flush updates Now state', async () => {
  ext.activity.take(); // clear buffer
  assert.strictEqual(ext.activity.size, 0);

  // Save event
  assert.ok(state.saveListeners && state.saveListeners.length > 0);
  state.saveListeners[0]({ uri: { fsPath: path.join(REPO, 'src', 'app.ts') } });
  assert.strictEqual(ext.activity.size, 1);

  // Create event
  state.createListeners[0]({ files: [{ fsPath: path.join(REPO, 'src', 'new.ts') }] });
  assert.strictEqual(ext.activity.size, 2);

  // Delete event
  state.deleteListeners[0]({ files: [{ fsPath: path.join(REPO, 'src', 'old.ts') }] });
  assert.strictEqual(ext.activity.size, 3);

  // Open event
  state.openListeners[0]({ document: { uri: { fsPath: path.join(REPO, 'README.md') } } });
  assert.strictEqual(ext.activity.size, 4);

  // Terminal run event
  state.termEndListeners[0]({ execution: { commandLine: { value: 'npm test' } }, exitCode: 0 });
  assert.ok(ext.activity.size <= 4);
});

test('Stage 4: Inspector supports steer, diff, and session learning stats', async () => {
  const provider = state.webviewProviders['sfpHive.stack'];
  let webviewMessageHandler;
  let postedMessages = [];
  let html = '';

  const webviewView = {
    webview: {
      options: {},
      asWebviewUri: (uri) => uri.fsPath,
      cspSource: 'vscode-webview:',
      postMessage: (msg) => { postedMessages.push(msg); },
      onDidReceiveMessage: (handler) => { webviewMessageHandler = handler; },
      set html(val) { html = val; },
    },
    show: () => {},
  };

  provider.resolveWebviewView(webviewView, {}, {});

  // Check Inspector HTML markup
  assert.ok(html.includes('id="choose-task-input"'), 'Task input exists');
  assert.ok(html.includes('id="choose-steer-section"'), 'Steer section exists');
  assert.ok(html.includes('data-action="rechoose"'), 'Re-choose button exists');
  assert.ok(html.includes('data-action="applyStack"'), 'Apply button exists');
  assert.ok(html.includes('id="choose-diff-summary"'), 'Diff summary exists');
  assert.ok(html.includes('id="choose-considered-section"'), 'Considered section exists');
  assert.ok(html.includes('id="choose-session-stats"'), 'Session stats grid exists');

  // Trigger ready -> receives updateState
  assert.ok(webviewMessageHandler);
  postedMessages = [];
  await webviewMessageHandler({ command: 'ready' });
  assert.ok(postedMessages.some((m) => m.type === 'updateState'));

  // Trigger rechoose with steer
  postedMessages = [];
  await webviewMessageHandler({
    command: 'rechoose',
    task: 'write table driven tests for a go parser',
    include: ['golang-patterns'],
    exclude: ['caveman'],
  });

  const lastUpdate = postedMessages.filter((m) => m.type === 'updateState').pop();
  assert.ok(lastUpdate, 'Must post updateState after rechoose');
  assert.ok(lastUpdate.payload.include.includes('golang-patterns'));
  assert.ok(lastUpdate.payload.exclude.includes('caveman'));

  // Trigger applyStack
  await webviewMessageHandler({
    command: 'applyStack',
    sendFeedback: true,
  });
  assert.ok(state.clipboard.length > 0, 'Clipboard filled with applied stack prompt');
});


