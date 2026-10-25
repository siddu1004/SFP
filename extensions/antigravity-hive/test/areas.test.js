// Areas (families) in the library and the skill detail window, against the real payload and the real detail command.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const hive = require('../out/hive.js');
const lib = require('../out/library.js');

const REPO = path.resolve(__dirname, '..', '..', '..');
process.env.SFP_DATA_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'areas-test-'));
let payload;
test.before(async () => {
  payload = hive.parseLibrary(await hive.run(hive.pythonCommand(), hive.libraryArgs(REPO)));
});

test('the library has a few areas and every skill is in one', () => {
  assert.ok(payload.families.length >= 8 && payload.families.length <= 12);
  const ids = new Set(payload.families.map((f) => f.id));
  for (const [name, s] of Object.entries(payload.skills)) assert.ok(ids.has(s.family), name);
  assert.strictEqual(payload.families.reduce((n, f) => n + f.count, 0), payload.counts.skills);
});

test('the Areas grouping has bundles and topics inside each area, and puts known things where people look', () => {
  const groups = lib.groupBy(payload, 'family');
  const by = Object.fromEntries(groups.map((g) => [g.id, g]));
  assert.ok(by.cyber.bundles.some((b) => b.id === 'harden-an-app'));
  assert.ok(by.design.children.some((c) => c.id === 'accessibility'));
  assert.ok(groups.every((g) => g.blurb && g.icon));
  assert.strictEqual(groups.reduce((n, g) => n + (g.bundles || []).length, 0), payload.bundles.length);
});

test('searching keeps only the areas, bundles and topics that match, in rank order', () => {
  const hits = lib.searchLibrary(payload, 'docker');
  const groups = lib.groupBy(payload, 'family', hits);
  assert.ok(groups.length >= 1 && groups.length < payload.families.length);
  const ship = groups.find((g) => g.id === 'ship');
  assert.ok(ship.skills.includes('docker-patterns'));
  for (const g of groups) for (const c of g.children || []) assert.ok(c.skills.length > 0);
});

test('bundles and clusters are ordered by area', () => {
  const order = payload.families.map((f) => f.id);
  for (const mode of ['bundle', 'cluster']) {
    const idx = lib.groupBy(payload, mode).filter((g) => g.family !== 'mine').map((g) => order.indexOf(g.family));
    assert.deepStrictEqual(idx, [...idx].sort((a, b) => a - b), mode);
  }
});

test('the detail command gives everything the window shows', async () => {
  const d = hive.parseSkillDetail(await hive.run(hive.pythonCommand(), hive.skillArgs(REPO, 'frontend-a11y')));
  assert.strictEqual(d.family.id, 'design');
  assert.ok(d.bundles.some((b) => b.id === 'accessible-form'));
  assert.ok(d.similar.length > 0 && !d.similar.includes('frontend-a11y'));
  assert.throws(() => hive.parseSkillDetail('{"name":1}'));
});

test('the detail page escapes everything and loads only its own files', () => {
  const d = { name: '<img src=x onerror=alert(1)>', description: 'Does <b>things</b>. Use when "x" & y.', use_when: 'Use when "x" & y.', category: 'c<',
    family: { id: 'f', name: 'F<' }, cluster: { id: 'c', name: 'C<' }, purpose: { id: 'p', name: 'P<' }, also: [{ id: 'a', name: 'A<' }],
    bundles: [{ id: 'b"', name: 'B<' }], similar: ['s<'], tokens: 12, path: 'p', app: 'x<' };
  const html = hive.skillDetailHtml(d, 'vscode-resource:', 'N0NCE', 'style.css', 'detail.js');
  assert.ok(!html.includes('<img src=x'));
  assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;'));
  assert.ok(!/<b>things/.test(html));
  assert.ok(html.includes("script-src 'nonce-N0NCE'") && !html.includes('unsafe-inline') && !/https?:/.test(html.replace(/vscode-resource:/g, '')));
  assert.ok(!/ style=/.test(html));
});

test('the Models view shows one line about the connection check, escaped, and a way to the full list', () => {
  const ok = hive.doctorSummaryHtml({ status: 'ok', checks: [{ name: 'Python', status: 'ok', detail: '3', fix: '' }] });
  assert.ok(ok.includes('Everything is connected.') && ok.includes('data-action="showInsights"'));
  const bad = hive.doctorSummaryHtml({ status: 'warn', checks: [
    { name: '<b>Router</b>', status: 'warn', detail: '', fix: '' }, { name: 'Index', status: 'warn', detail: '', fix: '' },
    { name: 'A', status: 'warn', detail: '', fix: '' }, { name: 'B', status: 'fail', detail: '', fix: '' }] });
  assert.ok(bad.includes('4 things to look at') && bad.includes('&lt;b&gt;Router') && bad.includes('…'));
  assert.ok(!bad.includes('<b>Router'));
});

test('the Now tab says what it shows in plain words, loads bundles, and refreshes by itself', () => {
  const studio = fs.readFileSync(path.join(__dirname, '..', 'media', 'studio.js'), 'utf8');
  const ext = fs.readFileSync(path.join(__dirname, '..', 'src', 'extension.ts'), 'utf8');
  for (const text of [studio, ext]) assert.ok(!/kalman/i.test(text.replace(/\/\/.*$/gm, '')), 'no filter jargon in what the user reads');
  assert.ok(ext.includes('Loaded bundles') && ext.includes('now-bundles-list'));
  assert.ok(studio.includes('track.bundles') && studio.includes('Confidence ${pct}%'));
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
  const setting = pkg.contributes.configuration.properties['sfpHive.autoRefreshSeconds'];
  assert.ok(setting && setting.default > 0 && setting.minimum === 0);
});
