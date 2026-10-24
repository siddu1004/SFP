// Run with: npm test (compiles first). Uses only node's built-in test runner.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const hive = require('../out/hive.js');

const fixture = fs.readFileSync(path.join(__dirname, 'selection.fixture.json'), 'utf8');
const REPO = path.resolve(__dirname, '..', '..', '..');

test('parses a real answer from the hive', () => {
  const sel = hive.parseSelection(fixture);
  assert.ok(sel.stack.length > 0);
  assert.ok(sel.stack.every((s) => typeof s.name === 'string'));
});

test('rejects an answer that is not a selection', () => {
  assert.throws(() => hive.parseSelection('{"hello": 1}'));
  assert.throws(() => hive.parseSelection('not json'));
});

test('groups skills by layer in the order to use them', () => {
  const sel = { stack: [{ name: 'c', layer: 'finish' }, { name: 'a', layer: 'base' }, { name: 'b', layer: 'check' }, { name: 'd', layer: 'base' }] };
  assert.deepStrictEqual(hive.byLayer(sel).map((g) => [g.layer, g.skills.map((s) => s.name)]),
    [['base', ['a', 'd']], ['check', ['b']], ['finish', ['c']]]);
});

test('the prompt names every skill, in order, with its file and the decision id', () => {
  const sel = hive.parseSelection(JSON.stringify({ ...JSON.parse(fixture), decision: 'd_test1234' }));
  const prompt = hive.buildPrompt(sel, '/sfp');
  sel.stack.forEach((s, i) => {
    assert.ok(prompt.includes(`${i + 1}. ${s.name}`), s.name);
    assert.ok(prompt.includes(path.join('/sfp', s.path)), s.path);
  });
  assert.ok(prompt.includes('d_test1234'));
  assert.ok(prompt.includes('give_feedback'));
});

test('without a decision id the answer still parses and the prompt says learning is off', () => {
  const raw = JSON.parse(fixture);
  delete raw.decision;
  const sel = hive.parseSelection(JSON.stringify(raw));
  assert.strictEqual(sel.decision, undefined);
  assert.match(hive.buildPrompt(sel), /Learning is switched off/);
});

test('an empty selection says so instead of listing nothing', () => {
  assert.match(hive.buildPrompt({ task: "x", decision: "d_1", stack: [] }), /no skill that fits/);
});

test('feedback arguments carry the verdict, the skills and the decision', () => {
  assert.deepStrictEqual(hive.feedbackArgs('/r', 'd_1', 'helped', ['a', 'b']).slice(1), ['feedback', 'd_1', '--helped', 'a,b']);
  assert.deepStrictEqual(hive.feedbackArgs('/r', 'd_1', 'missing', ['a'], 'a task').slice(-2), ['--task', 'a task']);
});

test('steering adds include, exclude and explain to the command', () => {
  const args = hive.selectArgs('/r', 't', undefined, 4, { include: ['a', 'b'], exclude: ['c'], explain: true });
  assert.deepStrictEqual(args.slice(-5), ['--include', 'a,b', '--exclude', 'c', '--explain']);
  assert.ok(!hive.selectArgs('/r', 't', undefined, 4).includes('--explain'));
});

test('an intervention becomes feedback: removed is unhelpful, added is missing', () => {
  const before = { stack: [{ name: 'x' }, { name: 'y' }] };
  assert.deepStrictEqual(hive.interventionFeedback(before, { exclude: ['x', 'never-chosen'], include: ['z', 'y'] }),
    [{ verdict: 'unhelpful', skills: ['x'] }, { verdict: 'missing', skills: ['z'] }]);
  assert.deepStrictEqual(hive.interventionFeedback(before, {}), []);
});

test('end to end: explain lists candidates with signals, and steering is honoured', async () => {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hive-steer-'));
  process.env.SFP_DATA_DIR = data;
  delete process.env.SFP_NO_USAGE_LOG;
  const python = hive.pythonCommand();
  const first = hive.parseSelection(await hive.run(python, hive.selectArgs(REPO, 'write table driven tests for a go parser', undefined, 3, { explain: true }), 120000));
  assert.ok(first.explain && first.explain.length >= first.stack.length);
  assert.ok(first.explain.every((c) => 'words' in c.signals && typeof c.status === 'string'));
  const out = first.stack[0].name;
  const second = hive.parseSelection(await hive.run(python, hive.selectArgs(REPO, 'write table driven tests for a go parser', undefined, 3, { exclude: [out], include: ['security-review'] }), 120000));
  const names = second.stack.map((s) => s.name);
  assert.ok(!names.includes(out) && names.includes('security-review'));
  assert.deepStrictEqual(second.intervention, { pinned: ['security-review'], excluded: [out] });
});

test('the task is one argument and never reaches a shell', () => {
  const task = 'x; touch /tmp/oops "quoted" $(whoami)';
  const args = hive.selectArgs('/r', task, '/proj', 3);
  assert.strictEqual(args[2], task);
  assert.deepStrictEqual(args.slice(-2), ['--project', '/proj']);
});

test('finds the checkout from the setting, then from ~/.sfp/root', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hive-home-'));
  fs.mkdirSync(path.join(home, '.sfp'));
  assert.strictEqual(hive.findSfpRoot({ home }), undefined);
  fs.writeFileSync(path.join(home, '.sfp', 'root'), REPO + '\n');
  assert.strictEqual(hive.findSfpRoot({ home }), REPO);
  assert.strictEqual(hive.findSfpRoot({ home, sfpPath: '/nope' }), REPO);
  assert.strictEqual(hive.findSfpRoot({ home, sfpPath: REPO }), REPO);
});

test('a skill path outside the checkout is never opened', () => {
  assert.strictEqual(hive.skillFile(REPO, { name: 'x', path: '../../etc/passwd' }), undefined);
  assert.strictEqual(hive.skillFile(REPO, { name: 'x', path: 'plugins/nope/SKILL.md' }), undefined);
});

test('quotes arguments for the terminal', () => {
  assert.strictEqual(hive.quote('install'), 'install');
  if (process.platform !== 'win32') assert.strictEqual(hive.quote("it's here"), `'it'\\''s here'`);
});

test('reads the catalog, the presets and the programs from a real checkout', () => {
  assert.ok(hive.catalogNames(REPO).includes('sfp-hive'));
  assert.ok(hive.profileNames(REPO).includes('starter'));
  assert.ok(hive.appList(REPO).some((a) => a.id === 'omniroute'));
});

test('end to end: the real hive answers, and feedback is recorded', async (t) => {
  const python = hive.pythonCommand();
  try {
    await hive.run(python, ['--version']);
  } catch {
    return t.skip('python is not available');
  }
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hive-data-'));
  process.env.SFP_DATA_DIR = data;
  delete process.env.SFP_NO_USAGE_LOG; // the test needs a decision id, which the hive only gives when it logs
  delete process.env.SFP_NO_LEARNING;
  const out = await hive.run(python, hive.selectArgs(REPO, 'write table driven tests for a go parser', undefined, 3), 120000);
  const sel = hive.parseSelection(out);
  assert.ok(sel.stack.length > 0 && sel.decision);
  await hive.run(python, hive.feedbackArgs(REPO, sel.decision, 'helped', [sel.stack[0].name], sel.task));
  assert.ok(fs.existsSync(path.join(data, 'feedback.jsonl')));
  assert.match(fs.readFileSync(path.join(data, 'feedback.jsonl'), 'utf8'), new RegExp(sel.decision));
});

test('a command that fails reports why, and a missing program says so', async () => {
  await assert.rejects(hive.run(hive.pythonCommand(), ['-c', 'import sys; sys.exit("boom")']), /boom/);
  await assert.rejects(hive.run('no-such-python-xyz', []), /could not start/);
});
