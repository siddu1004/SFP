// The library's search and grouping, against the real payload from `sfp_hive.py library`.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const hive = require('../out/hive.js');
const lib = require('../out/library.js');

const REPO = path.resolve(__dirname, '..', '..', '..');
process.env.SFP_DATA_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'lib-test-'));
delete process.env.SFP_NO_USAGE_LOG;
const payload = hive.parseLibrary(execFileSync(hive.pythonCommand(), hive.libraryArgs(REPO), { maxBuffer: 1 << 26 }).toString());
const names = (hits, n = 5) => hits.slice(0, n).map((h) => h.name);

test('the payload covers every skill with one purpose, one cluster and search terms', () => {
  assert.strictEqual(Object.keys(payload.skills).length, payload.counts.skills);
  assert.strictEqual(payload.purposes.reduce((n, p) => n + p.count, 0), payload.counts.skills);
  assert.strictEqual(payload.clusters.reduce((n, c) => n + c.count, 0), payload.counts.skills);
  for (const s of Object.values(payload.skills)) {
    assert.ok(s.purpose && s.cluster && s.n.length > 0);
  }
});

test('tokenizer parity: the TypeScript tokens equal the Python tokens', () => {
  const texts = Object.values(payload.skills).slice(0, 120).map((s) => s.d).concat([
    'C++ and C# in .NET, Node.js and Next.js', 'The quick brown fox is jumping over lazy dogs', 'testing, tested, tests; scraped scraping',
    'please make me an accessible signup form', 'class glass process address',
  ]);
  const code = 'import sys, json; sys.path.insert(0, %s); import sfp_mcp as m; print(json.dumps([m.tokens(t) for t in json.loads(sys.stdin.read())]))';
  const py = JSON.parse(execFileSync(hive.pythonCommand(), ['-c', code.replace('%s', JSON.stringify(path.join(REPO, 'mcp')))], { input: JSON.stringify(texts), maxBuffer: 1 << 26 }).toString());
  texts.forEach((t, i) => assert.deepStrictEqual(lib.tokens(t), py[i], t));
});

test('a query finds what a person would expect', () => {
  assert.ok(names(lib.searchLibrary(payload, 'anim')).includes('animate'));
  assert.ok(names(lib.searchLibrary(payload, 'anim'), 10).includes('animation-performance'));
  assert.strictEqual(lib.searchLibrary(payload, 'dockr')[0].name, 'docker-patterns'); // a typo
  assert.strictEqual(lib.searchLibrary(payload, 'test go')[0].name, 'golang-testing');
  assert.ok(names(lib.searchLibrary(payload, 'accessible form')).includes('accessibility')); // a related word
  assert.ok(names(lib.searchLibrary(payload, 'explain codebase'), 4).includes('codebase-onboarding'));
  assert.ok(names(lib.searchLibrary(payload, 'kubernetes deploy'), 3).includes('kubernetes-patterns'));
});

test('an exact name comes first, and the name is marked for highlighting', () => {
  const hits = lib.searchLibrary(payload, 'docker patterns');
  assert.strictEqual(hits[0].name, 'docker-patterns');
  assert.deepStrictEqual(hits[0].marks, [[0, 6], [7, 15]]);
  assert.deepStrictEqual(lib.searchLibrary(payload, 'react')[0].marks, [[0, 5]]);
});

test('an empty or filler-only query returns nothing, and a nonsense one too', () => {
  assert.deepStrictEqual(lib.searchLibrary(payload, ''), []);
  assert.deepStrictEqual(lib.searchLibrary(payload, 'the and of'), []);
  assert.deepStrictEqual(lib.searchLibrary(payload, 'qzxwv'), []);
});

test('search can be limited to a purpose or a cluster', () => {
  const secure = lib.searchLibrary(payload, 'test', { purpose: 'secure' });
  assert.ok(secure.every((h) => payload.skills[h.name].purpose === 'secure'));
  const inCluster = lib.searchLibrary(payload, 'patterns', { cluster: 'backend' });
  assert.ok(inCluster.length > 0 && inCluster.every((h) => payload.skills[h.name].cluster === 'backend'));
  assert.strictEqual(lib.searchLibrary(payload, 'test', { limit: 3 }).length, 3);
});

test('search is fast over the whole library', () => {
  const queries = ['anim', 'docker', 'test go', 'accessible form', 'react performance', 'blender light', 'security audit', 'x'];
  const t = process.hrtime.bigint();
  for (let i = 0; i < 20; i++) for (const q of queries) lib.searchLibrary(payload, q);
  const ms = Number(process.hrtime.bigint() - t) / 1e6 / (20 * queries.length);
  assert.ok(ms < 40, `average ${ms.toFixed(1)} ms per search`);
});

test('one-edit and related-word matching', () => {
  assert.ok(lib.withinOneEdit('docker', 'dockr') && lib.withinOneEdit('docker', 'dcoker') && lib.withinOneEdit('docker', 'dockerx'));
  assert.ok(!lib.withinOneEdit('docker', 'dokr') && !lib.withinOneEdit('abc', 'xyz'));
  assert.ok(lib.related('accessible', 'accessibility') && !lib.related('test', 'testing') && !lib.related('react', 'reaction'));
});

test('grouping by purpose, cluster and bundle lists every skill once, and a search keeps rank order', () => {
  for (const mode of ['purpose', 'cluster']) {
    const all = lib.groupBy(payload, mode).flatMap((g) => g.skills);
    assert.strictEqual(all.length, payload.counts.skills, mode);
    assert.strictEqual(new Set(all).size, all.length, mode);
  }
  const hits = lib.searchLibrary(payload, 'testing');
  const groups = lib.groupBy(payload, 'purpose', hits);
  assert.ok(groups.length > 0 && groups.every((g) => g.skills.length > 0));
  const flat = groups.flatMap((g) => g.skills);
  assert.strictEqual(flat.length, hits.length);
  const bundles = lib.groupBy(payload, 'bundle');
  assert.strictEqual(bundles.length, payload.counts.bundles);
  assert.deepStrictEqual(bundles[0].skills, payload.bundles[0].skills); // a bundle keeps its own order
});

test('bundles are found by name, goal or one of their skills', () => {
  const hits = lib.searchLibrary(payload, 'release');
  const found = lib.searchBundles(payload, 'release', hits).map((b) => b.id);
  assert.ok(found.includes('prepare-release'));
});

test('your own bundle: add it, see it in the library, pin it, remove it', () => {
  const python = hive.pythonCommand();
  execFileSync(python, hive.bundleAddArgs(REPO, 'My kit', ['impeccable', 'frontend-a11y'], 'my goal', 'design'));
  const after = hive.parseLibrary(execFileSync(python, hive.libraryArgs(REPO), { maxBuffer: 1 << 26 }).toString());
  const mine = after.bundles.find((b) => b.id === 'mine-my-kit');
  assert.ok(mine && mine.mine && mine.skills.join() === 'impeccable,frontend-a11y');
  const sel = JSON.parse(execFileSync(python, hive.selectArgs(REPO, 'add a signup page', undefined, 4, { bundle: 'mine-my-kit' })).toString());
  assert.deepStrictEqual(sel.bundle, { id: 'mine-my-kit', name: 'My kit' });
  assert.ok(sel.stack.some((s) => s.name === 'impeccable' && s.reasons[0] === 'pinned by you'));
  execFileSync(python, hive.bundleRemoveArgs(REPO, 'My kit'));
  const gone = hive.parseLibrary(execFileSync(python, hive.libraryArgs(REPO), { maxBuffer: 1 << 26 }).toString());
  assert.ok(!gone.bundles.some((b) => b.id === 'mine-my-kit'));
});

test('a payload that is not a library is refused', () => {
  assert.throws(() => hive.parseLibrary('{"skills": {}}'));
  assert.throws(() => hive.parseLibrary('nope'));
});
