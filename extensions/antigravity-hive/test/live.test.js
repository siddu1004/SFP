// Live attaching: the session logic against a fake host, and the real hive command end to end.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const hive = require('../out/hive.js');
const { LiveSession } = require('../out/live.js');

const REPO = path.resolve(__dirname, '..', '..', '..');
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const result = (n, state) => ({ status: 'updated', changed: true, attached: [], state: state || { anchor: [], auto: [], pinned: [], removed: [] }, words: [], n });

test('liveArgs carries the draft, state, pins and commit', () => {
  const st = { anchor: ['a'], auto: ['x'], pinned: [], removed: [] };
  const a = hive.liveArgs('/r', 'hello there', st, '/p', 4, { pin: ['a', 'b'], remove: ['c'], commit: true });
  assert.deepStrictEqual(a.slice(1, 5), ['live', 'hello there', '--json', '--max']);
  assert.ok(a.includes('--pin') && a[a.indexOf('--pin') + 1] === 'a,b');
  assert.ok(a.includes('--remove') && a.includes('--commit') && a.includes('--project'));
  assert.deepStrictEqual(JSON.parse(a[a.indexOf('--state') + 1]), st);
  assert.ok(!hive.liveArgs('/r', 'x', undefined, undefined, 4).includes('--state'));
});

test('parseLive refuses output that is not a live result', () => {
  assert.throws(() => hive.parseLive('{"x":1}'));
  assert.strictEqual(hive.parseLive('{"attached":[],"state":{}}').attached.length, 0);
});

test('typing is debounced into one call with the last draft', async () => {
  const calls = [];
  const s = new LiveSession({ ask: async (d) => { calls.push(d); return result(calls.length); }, show() {} }, 30);
  s.type('a'); s.type('ab'); s.type('abc');
  await wait(120);
  assert.deepStrictEqual(calls, ['abc']);
});

test('an answer for an older draft is thrown away', async () => {
  const shown = [];
  const s = new LiveSession({
    ask: async (d) => { if (d === 'slow') await wait(80); return result(d); },
    show: (r) => shown.push(r.n),
  }, 10);
  s.type('slow'); await wait(30);
  s.type('fast'); await wait(150);
  assert.deepStrictEqual(shown, ['fast']);
});

test('state is carried between calls, pins ride along, send starts over', async () => {
  const seen = [];
  const s = new LiveSession({
    ask: async (d, st, ch) => { seen.push({ d, st, ch }); return result(d, { anchor: [d], auto: [], pinned: ch.pin || [], removed: [] }); },
    show() {},
  }, 10);
  await s.steer('one two', { pin: ['x'] });
  await s.steer('one two three', {});
  assert.deepStrictEqual(seen[1].st.pinned, ['x']);
  const done = await s.send('one two three');
  assert.ok(seen[2].ch.commit);
  assert.ok(done);
  assert.strictEqual(s.state, undefined);
});

test('a failing host is reported, not thrown', async () => {
  let err;
  const s = new LiveSession({ ask: async () => { throw new Error('boom'); }, show() {}, fail: (e) => { err = e; } }, 10);
  await s.steer('x y z', {});
  assert.strictEqual(err.message, 'boom');
});

test('the real hive: waits, attaches, keeps, and logs only on send', async () => {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'live-test-'));
  process.env.SFP_DATA_DIR = data;
  const py = hive.pythonCommand();
  const ask = async (d, st, ch) => hive.parseLive(await hive.run(py, hive.liveArgs(REPO, d, st, undefined, 4, ch)));
  const shown = [];
  const s = new LiveSession({ ask, show: (r) => shown.push(r.status) }, 10);
  await s.steer('fix', {});
  await s.steer('make the login form accessible and animate the button', {});
  await s.steer('make the login form accessible and animate the button please', {});
  assert.deepStrictEqual(shown, ['waiting', 'updated', 'kept']);
  assert.ok(s.last.attached.length > 0);
  assert.ok(!fs.existsSync(path.join(data, 'decisions.jsonl')));
  const done = await s.send('make the login form accessible and animate the button');
  assert.ok(done.decision);
  assert.strictEqual(fs.readFileSync(path.join(data, 'decisions.jsonl'), 'utf8').trim().split('\n').length, 1);
});
