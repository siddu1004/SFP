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

test('adding a skill from Git: the arguments, the result, and the typed text are checked', async () => {
  assert.deepStrictEqual(hive.repoToSkillArgs('/r', ' owner/repo ', ['claude', 'antigravity']).slice(1), ['owner/repo', '--json', '--install', 'claude,antigravity']);
  assert.ok(!hive.repoToSkillArgs('/r', 'a/b').includes('--install'));
  for (const ok of ['https://github.com/o/r', 'git@github.com:o/r.git', 'owner/repo', '/home/me/code/repo', '~/code/repo', 'C:\\code\\repo', './repo']) assert.ok(hive.looksLikeRepo(ok), ok);
  for (const bad of ['', 'hello world', 'just-a-word', 'a b/c']) assert.ok(!hive.looksLikeRepo(bad), bad);
  assert.strictEqual(hive.parseRepoSkill('{"skill_name":"x","skill_path":"/p/SKILL.md","status":"ok","installed":{},"category":"c","registered":false}').skill_name, 'x');
  assert.throws(() => hive.parseRepoSkill('{"status":"fail","error":"Could not clone x"}'), /Could not clone x/);
  assert.throws(() => hive.parseRepoSkill('{}'));
});

test('the real converter turns a folder into a skill that has its README commands', async () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'repo-'));
  fs.writeFileSync(path.join(repo, 'README.md'), '# Demo\n\nDemo is a tool that formats logs nicely for you.\n\n## Install\n\n```bash\nnpm install -g demo-logs\n```\n');
  const out = await hive.run(hive.pythonCommand(), hive.repoToSkillArgs(REPO, repo, []));
  const res = hive.parseRepoSkill(out);
  assert.ok(res.skill_path.startsWith(process.env.SFP_DATA_DIR), 'it writes to the data folder, not the checkout');
  const md = fs.readFileSync(res.skill_path, 'utf8');
  assert.ok(md.startsWith('---') && md.includes('npm install -g demo-logs'));
});

test('the automatic skills rule lists the chosen skills in order, with their files, and adds the rest of a loaded bundle', () => {
  const paths = hive.catalogPaths(REPO);
  assert.ok(paths['golang-testing'] && !paths['golang-testing'].includes('\\'));
  const text = hive.activeSkillsRule({ source: 'activity', phase: 'test', confidence: 0.69,
    skills: [{ name: 'golang-testing', layer: 'base', reasons: ['task words: test'] }, { name: 'tdd-workflow', layer: 'check' }],
    bundles: [{ name: 'Table-driven Go tests', skills: ['golang-testing', 'tdd-workflow', 'verification-loop'] }] }, REPO, new Date('2026-10-25T09:00:00Z'));
  assert.ok(text.startsWith('---\ntrigger: always_on\n---'));
  assert.ok(text.includes('Current phase: test (confidence 69%)'));
  assert.ok(text.indexOf('1. **golang-testing** (base)') < text.indexOf('2. **tdd-workflow** (check)'));
  assert.ok(text.includes(path.join(REPO, paths['golang-testing'])), 'each skill names the file to read');
  assert.ok(text.includes('3. **verification-loop**'), 'the rest of the bundle reaches the agent, in the bundle order');
  const typed = hive.activeSkillsRule({ source: 'task', task: 't', skills: [{ name: 'golang-testing' }], bundles: [{ name: 'B', skills: ['golang-testing', 'tdd-workflow'] }] }, REPO);
  assert.ok(typed.includes('**tdd-workflow** (from the bundle)'), 'for a typed task the bundle extras are added after the stack');
  assert.strictEqual((text.match(/\*\*golang-testing\*\*/g) || []).length, 1, 'no skill twice');
  assert.ok(text.includes('Updated 2026-10-25 09:00 UTC.'));
  const task = hive.activeSkillsRule({ source: 'task', task: 'add tests', skills: [] }, REPO);
  assert.ok(task.includes('Task: add tests') && task.includes('No skills are selected right now.'));
});

test('the automatic skills setting, file and command are declared', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
  const props = pkg.contributes.configuration.properties;
  assert.strictEqual(props['sfpHive.autoSkills'].default, true);
  assert.strictEqual(props['sfpHive.autoSkillsFile'].default, '.agents/rules/sfp-active-skills.md');
  assert.ok(pkg.contributes.commands.some((c) => c.command === 'sfpHive.toggleAutoSkills'));
});

test('the skill history keeps what the agent was given, newest first, and skips bad lines', () => {
  const a = hive.historyEntry({ source: 'task', task: 'make the signup form accessible', skills: [{ name: 'frontend-a11y' }], bundles: [{ name: 'Accessible form', skills: [] }] }, 1000);
  const b = hive.historyEntry({ source: 'activity', phase: 'test', skills: [{ name: 'golang-testing' }] }, 2000);
  assert.deepStrictEqual(a, { t: 1000, source: 'task', what: 'make the signup form accessible', skills: ['frontend-a11y'], bundles: ['Accessible form'] });
  assert.strictEqual(b.what, 'Phase: test');
  const text = JSON.stringify(a) + '\nnot json\n' + JSON.stringify(b) + '\n';
  assert.deepStrictEqual(hive.readHistory(text).map((e) => e.t), [2000, 1000]);
  assert.strictEqual(hive.readHistory(text, 1).length, 1);
});

test('from activity alone the agent gets the bundle in order plus only the skills the hive is sure of', () => {
  const a = { source: 'activity', phase: 'debug', confidence: 0.55,
    skills: [{ name: 'using-n8n-mcp-skills', score: 0.83 }, { name: 'orch-fix-defect', score: 1.0 }, { name: 'nodejs-keccak256', score: 0.71 }, { name: 'python-testing', score: 0.93 }],
    bundles: [{ name: 'Fix a bug properly', skills: ['investigate-first', 'orch-fix-defect', 'surgical-patch', 'verify-and-stop'] }, { name: 'Other', skills: ['x'] }] };
  const f = hive.focusActivity(a);
  assert.deepStrictEqual(f.skills.map((s) => s.name), ['investigate-first', 'orch-fix-defect', 'surgical-patch', 'verify-and-stop', 'python-testing']);
  assert.strictEqual(f.bundles.length, 1);
  const text = hive.activeSkillsRule(a, REPO);
  assert.ok(!text.includes('using-n8n-mcp-skills') && !text.includes('nodejs-keccak256'), 'weak guesses stay out');
  const noBundle = hive.focusActivity({ ...a, bundles: [] });
  assert.deepStrictEqual(noBundle.skills.map((s) => s.name), ['orch-fix-defect', 'python-testing']);
  const typed = { source: 'task', task: 't', skills: a.skills };
  assert.strictEqual(hive.focusActivity(typed), typed, 'a task you typed keeps the full choice');
});
