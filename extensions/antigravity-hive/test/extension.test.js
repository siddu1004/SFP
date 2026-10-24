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
  StatusBarAlignment: { Left: 1 },
  ProgressLocation: { Window: 10 },
  window: {
    createStatusBarItem: () => ({ show() {}, dispose() {} }),
    registerTreeDataProvider: (id, p) => { state.providers[id] = p; return { dispose() {} }; },
    showInputBox: async () => state.inputs.shift(),
    showQuickPick: async (items) => state.picks.length ? state.picks.shift() : undefined,
    showInformationMessage: note('info'), showErrorMessage: note('error'), showWarningMessage: note('warn'),
    setStatusBarMessage: (m) => state.messages.push(['status', m]),
    withProgress: async (_o, fn) => fn(),
    createTerminal: () => ({ show() {}, sendText: (t) => state.messages.push(['terminal', t]) }),
    showTextDocument: async () => {},
  },
  commands: {
    registerCommand: (id, fn) => { commands.set(id, fn); return { dispose() {} }; },
    executeCommand: async (id, ...args) => {
      if (id === 'setContext') { state.contexts[args[0]] = args[1]; return; }
      return commands.has(id) ? commands.get(id)(...args) : undefined;
    },
  },
  workspace: {
    workspaceFolders: undefined,
    getConfiguration: () => ({ get: (k, d) => ({ sfpPath: REPO, maxSkills: 3 }[k] ?? d) }),
    openTextDocument: async (f) => f,
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
  ext.activate({ subscriptions: [], extensionPath: REPO });
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
