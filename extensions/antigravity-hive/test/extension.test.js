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
    createQuickPick: () => ({
      items: [],
      placeholder: '',
      selectedItems: [],
      onDidChangeValue: () => {},
      onDidAccept: () => {},
      show() {},
      dispose() {},
    }),
    showInformationMessage: async (m, ...items) => {
      state.messages.push(['info', m]);
      if (state.picks.length) return state.picks.shift();
      if (items.includes('Run')) return 'Run';
      return undefined;
    },
    showErrorMessage: note('error'), showWarningMessage: note('warn'),
    setStatusBarMessage: (m) => state.messages.push(['status', m]),
    withProgress: async (_o, fn) => fn(),
    createTerminal: (name) => ({ name, show() {}, sendText: (t, addNewLine = true) => state.messages.push(['terminal', t, addNewLine]) }),
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
    createFileSystemWatcher: () => ({
      onDidChange: () => ({ dispose() {} }),
      onDidCreate: () => ({ dispose() {} }),
      onDidDelete: () => ({ dispose() {} }),
      dispose() {},
    }),
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
  RelativePattern: class { constructor(base, pattern) { this.base = base; this.pattern = pattern; } },
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
  assert.ok(state.webviewProviders['sfpHive.stack']);
  assert.ok(state.chatParticipants && state.chatParticipants.has('sfp.hive'));
});

test('choosing skills updates selection, copies the prompt and sets the context', async () => {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hive-ext-'));
  process.env.SFP_DATA_DIR = data;
  delete process.env.SFP_NO_USAGE_LOG;
  state.inputs.push('write table driven tests for a go parser');
  await commands.get('sfpHive.choose')();
  assert.strictEqual(state.contexts['sfpHive.hasSelection'], true);
  assert.ok(state.clipboard.includes('Use these SFP skills, in this order'));
});

test('marking a skill helped records feedback to feedback.jsonl', async () => {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hive-ext-'));
  process.env.SFP_DATA_DIR = data;
  delete process.env.SFP_NO_USAGE_LOG;
  state.inputs.push('write table driven tests for a go parser');
  await commands.get('sfpHive.choose')();
  await commands.get('sfpHive.helped')('golang-patterns');
  const log = path.join(process.env.SFP_DATA_DIR, 'feedback.jsonl');
  assert.match(fs.readFileSync(log, 'utf8'), /golang-patterns/);
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
  assert.ok(!html.includes('data-tab="library"'), 'Must not have Library tab in Studio');
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

test('escapeHtml sanitizes dynamic strings against XSS injection', () => {
  const hiveModule = require('../out/hive.js');
  assert.strictEqual(
    hiveModule.escapeHtml('<img src=x onerror=alert(1)>'),
    '&lt;img src=x onerror=alert(1)&gt;'
  );
  assert.strictEqual(
    hiveModule.escapeHtml('Tom & "Jerry" \'show\''),
    'Tom &amp; &quot;Jerry&quot; &#39;show&#39;'
  );
});

test('webview CSP enforces strict origin without unsafe-inline or remote https', () => {
  const provider = state.webviewProviders['sfpHive.stack'];
  let html = '';
  const webviewView = {
    webview: {
      options: {},
      asWebviewUri: (uri) => uri.fsPath,
      cspSource: 'vscode-webview:',
      postMessage: () => {},
      onDidReceiveMessage: () => {},
      set html(val) { html = val; },
    },
    show: () => {},
  };
  provider.resolveWebviewView(webviewView, {}, {});
  const cspMatch = html.match(/<meta http-equiv="Content-Security-Policy" content="([^"]+)">/);
  assert.ok(cspMatch, 'CSP meta tag must be present');
  const csp = cspMatch[1];
  assert.ok(!csp.includes("'unsafe-inline'"), 'CSP must not allow unsafe-inline styles');
  assert.ok(!csp.includes('https:'), 'CSP must not allow arbitrary https image sources');
  assert.ok(csp.includes("style-src vscode-webview:"), 'CSP must allow webview style-src');
  assert.ok(csp.includes("img-src vscode-webview: data:"), 'CSP must restrict img-src to webview and data URIs');
});

test('webview handles choose, refresh, remove, and helped messages', async () => {
  const provider = state.webviewProviders['sfpHive.stack'];
  let webviewMessageHandler;
  let posted = [];
  const webviewView = {
    webview: {
      options: {},
      asWebviewUri: (uri) => uri.fsPath,
      cspSource: 'vscode-webview:',
      postMessage: (m) => { posted.push(m); },
      onDidReceiveMessage: (handler) => { webviewMessageHandler = handler; },
      set html(val) {},
    },
    show: () => {},
  };
  provider.resolveWebviewView(webviewView, {}, {});
  assert.ok(webviewMessageHandler);

  // Test choose message
  posted = [];
  await webviewMessageHandler({ command: 'choose', task: 'write table driven tests for a go parser' });
  assert.ok(posted.some((m) => m.type === 'updateState'), 'choose command should post updateState');

  // Test refresh message
  posted = [];
  await webviewMessageHandler({ command: 'refresh' });
  assert.ok(posted.some((m) => m.type === 'updateState'), 'refresh command should post updateState');

  // Test helped message
  posted = [];
  await webviewMessageHandler({ command: 'feedback', skill: 'golang-patterns', verdict: 'helped' });
  const log = path.join(process.env.SFP_DATA_DIR, 'feedback.jsonl');
  assert.match(fs.readFileSync(log, 'utf8'), /golang-patterns/);

  // Test remove message
  posted = [];
  await webviewMessageHandler({ command: 'removeSkill', skill: 'golang-patterns' });
  const logAfterRemove = fs.readFileSync(log, 'utf8');
  assert.match(logAfterRemove, /unhelpful/);

  // Test liveType and liveChange messages
  posted = [];
  await webviewMessageHandler({ command: 'liveType', draft: 'fix' });
  // wait for debounce
  await new Promise((r) => setTimeout(r, 60));
  await webviewMessageHandler({
    command: 'liveChange',
    draft: 'make login accessible',
    change: { pin: ['accessible'] },
  });

  // Test needs action message handlers
  state.clipboard = '';
  await webviewMessageHandler({
    command: 'copyNeedAction',
    action: 'install agent-reach: python3 apps/sfp_app.py install agent-reach',
  });
  assert.strictEqual(state.clipboard, 'python3 apps/sfp_app.py install agent-reach');
  assert.ok(state.messages.some((m) => m[0] === 'info' && m[1].includes('copied')));

  state.messages = [];
  await webviewMessageHandler({
    command: 'runNeedAction',
    action: 'install agent-reach: python3 apps/sfp_app.py install agent-reach',
  });
  const termMsg = state.messages.find((m) => m[0] === 'terminal');
  assert.ok(termMsg, 'Must create terminal and send command');
  assert.strictEqual(termMsg[1], 'python3 apps/sfp_app.py install agent-reach');
  assert.strictEqual(termMsg[2], false, 'Must not press enter (addNewLine: false)');

  await webviewMessageHandler({ command: 'openChoose', task: 'browse this website' });
  await webviewMessageHandler({ command: 'focusModels' });
});

test('Stage 2: registers the SFP Hive Library webview provider and commands', async () => {
  const libProvider = state.webviewProviders['sfpHive.library'];
  assert.ok(libProvider, 'sfpHive.library provider must be registered');

  let libHtml = '';
  let libMessages = [];
  let onDidReceiveMessageCb;
  const webviewView = {
    webview: {
      options: {},
      asWebviewUri: (uri) => uri.fsPath,
      cspSource: 'vscode-webview:',
      postMessage: (msg) => { libMessages.push(msg); },
      onDidReceiveMessage: (cb) => { onDidReceiveMessageCb = cb; },
      set html(val) { libHtml = val; },
    },
    show: () => {},
  };
  libProvider.resolveWebviewView(webviewView, {}, {});

  // HTML structure & CSP
  assert.ok(libHtml.includes('Content-Security-Policy'), 'Library HTML must have CSP');
  assert.ok(!libHtml.includes("'unsafe-inline'"), 'Library CSP must not have unsafe-inline');
  assert.ok(libHtml.includes('library.css'), 'Library must load library.css');
  assert.ok(libHtml.includes('library.js'), 'Library must load library.js');
  assert.ok(libHtml.includes('id="lib-search-input"'), 'Library must have search input');
  assert.ok(libHtml.includes('data-mode="purpose"'), 'Library must have purpose mode');
  assert.ok(libHtml.includes('data-mode="cluster"'), 'Library must have cluster mode');
  assert.ok(libHtml.includes('data-mode="bundle"'), 'Library must have bundle mode');
  assert.ok(libHtml.includes('id="lib-groups-container"'), 'Library must have groups container');

  // Verify ready message receives library update
  assert.ok(onDidReceiveMessageCb, 'Must register webview message receiver');
  await onDidReceiveMessageCb({ command: 'ready' });
  assert.ok(libMessages.some((m) => m.type === 'update'), 'ready should trigger update message');
  const updateMsg = libMessages.find((m) => m.type === 'update');
  assert.ok(updateMsg.groups && updateMsg.groups.length > 0, 'Must have groups');
  assert.ok(updateMsg.summary && updateMsg.summary.skills > 0, 'Must have summary counts');

  // Search message testing
  libMessages = [];
  await onDidReceiveMessageCb({ command: 'search', query: 'anim' });
  const searchMsg = libMessages.find((m) => m.type === 'searchResults');
  assert.ok(searchMsg, 'search should post searchResults message');
  assert.ok(searchMsg.hits && searchMsg.hits.some((h) => h.name.includes('anim')), 'Hits should match query');

  // Switch mode message testing
  libMessages = [];
  await onDidReceiveMessageCb({ command: 'switchMode', mode: 'cluster' });
  const clusterMsg = libMessages.find((m) => m.type === 'searchResults');
  assert.ok(clusterMsg && clusterMsg.mode === 'cluster');

  // Commands testing
  assert.ok(commands.has('sfpHive.focusLibrary'));
  assert.ok(commands.has('sfpHive.searchSkills'));
  assert.ok(commands.has('sfpHive.applyBundle'));
});

test('Stage 4: registers the Models webview provider and router commands', async () => {
  const modelsProv = state.webviewProviders['sfpHive.models'];
  assert.ok(modelsProv, 'sfpHive.models provider must be registered');

  let modelsHtml = '';
  let modelsMessages = [];
  let onDidReceiveMessageCb;
  const webviewView = {
    webview: {
      options: {},
      asWebviewUri: (uri) => uri.fsPath,
      cspSource: 'vscode-webview:',
      postMessage: (msg) => { modelsMessages.push(msg); },
      onDidReceiveMessage: (cb) => { onDidReceiveMessageCb = cb; },
      set html(val) { modelsHtml = val; },
    },
    show: () => {},
  };
  modelsProv.resolveWebviewView(webviewView, {}, {});

  // HTML structure & CSP
  assert.ok(modelsHtml.includes('Content-Security-Policy'), 'Models HTML must have CSP');
  assert.ok(!modelsHtml.includes("'unsafe-inline'"), 'Models CSP must not have unsafe-inline');
  assert.ok(modelsHtml.includes('models.css'), 'Models must load models.css');
  assert.ok(modelsHtml.includes('models.js'), 'Models must load models.js');
  assert.ok(modelsHtml.includes('id="status-dot"'), 'Models must have status dot');
  assert.ok(modelsHtml.includes('id="toggle-router-btn"'), 'Models must have toggle router button');
  assert.ok(modelsHtml.includes('id="server-card"'), 'Models must have server card');
  assert.ok(modelsHtml.includes('id="server-url"'), 'Models must have server url');
  assert.ok(modelsHtml.includes('id="copy-url-btn"'), 'Models must have copy url button');
  assert.ok(modelsHtml.includes('id="providers-container"'), 'Models must have providers container');
  assert.ok(modelsHtml.includes('id="policy-select"'), 'Models must have policy select');
  assert.ok(modelsHtml.includes('id="setup-btn"'), 'Models must have setup button');
  assert.ok(modelsHtml.includes('id="write-btn"'), 'Models must have write button');
  assert.ok(modelsHtml.includes('id="preview-box"'), 'Models must have preview box');
  assert.ok(modelsHtml.includes('id="status-container"'), 'Models must have status container');
  assert.ok(modelsHtml.includes('id="try-prompt-input"'), 'Models must have try prompt input');
  assert.ok(modelsHtml.includes('id="try-plan-btn"'), 'Models must have try plan button');
  assert.ok(modelsHtml.includes('id="try-send-btn"'), 'Models must have try send button');
  assert.ok(modelsHtml.includes('id="try-output"'), 'Models must have try output box');

  // Verify ready message
  assert.ok(onDidReceiveMessageCb, 'Must register webview message receiver');
  await onDidReceiveMessageCb({ command: 'ready' });
  assert.ok(modelsMessages.some((m) => m.type === 'updateState'), 'ready should post updateState');

  // Verify policy change
  modelsMessages = [];
  await onDidReceiveMessageCb({ command: 'changePolicy', policy: 'cheap-first' });

  // Verify setup preview (dry run)
  modelsMessages = [];
  await onDidReceiveMessageCb({ command: 'setup', policy: 'local-first', yes: false });
  assert.ok(modelsMessages.some((m) => m.type === 'setupPreview'), 'setup without yes should post setupPreview');

  // Verify plan
  modelsMessages = [];
  await onDidReceiveMessageCb({ command: 'plan', task: 'refactor billing' });
  assert.ok(modelsMessages.some((m) => m.type === 'planResult'), 'plan should post planResult');

  // Verify copyUrl
  state.clipboard = '';
  await onDidReceiveMessageCb({ command: 'copyUrl', url: 'http://127.0.0.1:8787/v1' });
  assert.strictEqual(state.clipboard, 'http://127.0.0.1:8787/v1');

  // Commands testing
  assert.ok(commands.has('sfpHive.focusModels'), 'sfpHive.focusModels must be registered');
  assert.ok(commands.has('sfpHive.routerStart'), 'sfpHive.routerStart must be registered');
  assert.ok(commands.has('sfpHive.routerStop'), 'sfpHive.routerStop must be registered');
  assert.ok(commands.has('sfpHive.routerSetup'), 'sfpHive.routerSetup must be registered');

  // Test executing router commands
  await commands.get('sfpHive.routerStop')();
  await commands.get('sfpHive.focusModels')();
});



