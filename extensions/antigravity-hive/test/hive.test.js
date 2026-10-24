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

test('the activity buffer merges repeated saves, drops opens when there is more, and empties on take', () => {
  let now = 100;
  const b = new hive.ActivityBuffer(5, () => now);
  b.add({ kind: 'open', path: 'README.md' });
  b.add({ kind: 'save', path: 'a.go' });
  now = 110;
  b.add({ kind: 'save', path: 'a.go' });
  b.add({ kind: 'run', command: 'go test ./...', exit: 0 });
  const batch = b.take();
  assert.deepStrictEqual(batch.map((e) => e.kind), ['save', 'run']);
  assert.strictEqual(batch[0].t, 110);
  assert.strictEqual(b.size, 0);
  b.add({ kind: 'open', path: 'x' });
  assert.deepStrictEqual(b.take().map((e) => e.kind), ['open']);
  for (let i = 0; i < 9; i++) b.add({ kind: 'run', command: 'c' + i });
  assert.strictEqual(b.size, 5);
});

test('paths outside the workspace are never described', () => {
  assert.strictEqual(hive.relative('/w', '/w/src/a.ts'), 'src/a.ts');
  assert.strictEqual(hive.relative('/w', '/etc/passwd'), undefined);
  assert.strictEqual(hive.relative(undefined, '/w/a'), undefined);
});

test('track and cluster arguments', () => {
  assert.deepStrictEqual(hive.trackArgs('/r', '/p', 3, false, true).slice(1), ['track', '--json', '--max', '3', '--project', '/p', '--no-select', '--reset']);
  assert.deepStrictEqual(hive.clusterAddArgs('/r', 'Mine', ['a', 'b'], 'd').slice(1), ['cluster-add', 'Mine', '--skills', 'a,b', '--description', 'd']);
  assert.deepStrictEqual(hive.clusterRemoveArgs('/r', 'Mine').slice(1), ['cluster-remove', 'Mine']);
});

test('end to end: tracking events gives a phase, a prediction and skills; clusters list every skill', async () => {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hive-track-'));
  process.env.SFP_DATA_DIR = data;
  delete process.env.SFP_NO_USAGE_LOG;
  const python = hive.pythonCommand();
  const events = [0, 30, 60, 90].map((dt) => ({ t: 1000 + dt, kind: 'run', command: 'go test ./...', exit: 0 }));
  const res = hive.parseTrack(await hive.run(python, hive.trackArgs(REPO, undefined, 3), 120000, JSON.stringify(events)));
  assert.strictEqual(res.phase, 'test');
  assert.strictEqual(res.layer, 'check');
  assert.ok(res.confidence > 0 && res.confidence <= 1);
  assert.ok(res.next.length > 0 && res.skills && res.skills.length > 0);
  const clusters = hive.parseClusters(await hive.run(python, hive.clustersArgs(REPO), 120000));
  const total = clusters.reduce((n, c) => n + c.count, 0);
  assert.strictEqual(total, hive.catalogNames(REPO).length);
});

test('notification throttle respects minimum time interval and confidence threshold', () => {
  const t0 = 100000;
  // Not changed -> no notification
  assert.strictEqual(hive.shouldNotifyPhaseChange(t0, t0 + 130000, false, 0.8), false);
  // Confidence too low -> no notification
  assert.strictEqual(hive.shouldNotifyPhaseChange(t0, t0 + 130000, true, 0.5), false);
  // Too soon (< 2 min) -> no notification
  assert.strictEqual(hive.shouldNotifyPhaseChange(t0, t0 + 60000, true, 0.7), false);
  // Changed, high confidence, elapsed >= 120s -> notification fires
  assert.strictEqual(hive.shouldNotifyPhaseChange(t0, t0 + 120000, true, 0.6), true);
  assert.strictEqual(hive.shouldNotifyPhaseChange(t0, t0 + 150000, true, 0.9), true);
});

test('phase bar view model normalizes percentages and maps layers', () => {
  const shares = { test: 0.5, build: 0.3, ship: 0.2 };
  const vm = hive.phaseBarViewModel(shares);
  assert.strictEqual(vm.length, 3);
  const testSeg = vm.find((s) => s.phase === 'test');
  assert.ok(testSeg);
  assert.strictEqual(testSeg.percent, 50);
  assert.strictEqual(testSeg.layer, 'check');

  const buildSeg = vm.find((s) => s.phase === 'build');
  assert.ok(buildSeg);
  assert.strictEqual(buildSeg.layer, 'base');

  const shipSeg = vm.find((s) => s.phase === 'ship');
  assert.ok(shipSeg);
  assert.strictEqual(shipSeg.layer, 'finish');
});

test('chips view model creates chip labels and assigns layer classes', () => {
  const next = [{ phase: 'debug', probability: 0.45 }, { phase: 'review', probability: 0.3 }];
  const chips = hive.chipsViewModel(next);
  assert.strictEqual(chips.length, 2);
  assert.strictEqual(chips[0].label, 'Debug 45%');
  assert.strictEqual(chips[0].layer, 'base');
  assert.strictEqual(chips[1].label, 'Review 30%');
  assert.strictEqual(chips[1].layer, 'check');
});

test('phase changes view model formats and orders changes', () => {
  const changes = [
    { t: 100, from: 'plan', to: 'build' },
    { t: 200, from: 'build', to: 'test' },
  ];
  const vm = hive.phaseChangesViewModel(changes);
  assert.strictEqual(vm.length, 2);
  assert.strictEqual(vm[0].label, 'build → test');
  assert.strictEqual(vm[1].label, 'plan → build');
});

test('selectionDiff computes added and removed skills accurately', () => {
  const before = {
    task: 'test',
    stack: [{ name: 'skill-a' }, { name: 'skill-b' }],
  };
  const after = {
    task: 'test',
    stack: [{ name: 'skill-b' }, { name: 'skill-c' }],
  };
  const diff = hive.selectionDiff(before, after);
  assert.deepStrictEqual(diff.added, ['skill-c']);
  assert.deepStrictEqual(diff.removed, ['skill-a']);
});

test('updateSessionStats tracks decisions, interventions and feedback', () => {
  let stats = hive.defaultSessionStats();
  assert.strictEqual(stats.decisions, 0);

  stats = hive.updateSessionStats(stats, { type: 'decision', chosenCount: 3 });
  assert.strictEqual(stats.decisions, 1);
  assert.strictEqual(stats.chosenTotal, 3);
  assert.strictEqual(stats.keptTotal, 3);

  stats = hive.updateSessionStats(stats, { type: 'intervention', beforeCount: 3, keptCount: 2, addedCount: 1 });
  assert.strictEqual(stats.interventions, 1);
  assert.strictEqual(stats.keptTotal, 2);
  assert.strictEqual(stats.addedSkills, 1);

  stats = hive.updateSessionStats(stats, { type: 'feedback', verdict: 'helped' });
  stats = hive.updateSessionStats(stats, { type: 'feedback', verdict: 'unhelpful' });
  assert.strictEqual(stats.helped, 1);
  assert.strictEqual(stats.unhelpful, 1);
});

test('parseNeeds parses valid JSON and throws on invalid', () => {
  const json = JSON.stringify([
    {
      id: 'make-3d',
      name: 'Make 3D models',
      why: 'Needs 3D tools',
      score: 1.0,
      skills: ['image-to-3d'],
      attach: 'image-to-3d',
      preload: ['multi-image-to-3d'],
      action: 'set MESHY_API_KEY in your environment',
    },
  ]);
  const needs = hive.parseNeeds(json);
  assert.strictEqual(needs.length, 1);
  assert.strictEqual(needs[0].id, 'make-3d');
  assert.throws(() => hive.parseNeeds('{"invalid": true}'));
});

test('renderNeedCard renders card with escaping and handles action buttons', () => {
  const need = {
    id: 'test-need',
    name: 'Need <script>alert("xss")</script> & More',
    why: 'Why <img src=x onerror=alert(1)> & test',
    score: 0.9,
    skills: ['skill<1>', 'skill-2'],
    attach: 'skill<1>',
    preload: ['skill-2'],
    action: 'install test: python3 apps/sfp_app.py install "test"',
  };
  const html = hive.renderNeedCard(need);
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt; &amp; More'));
  assert.ok(!html.includes('<img'));
  assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt; &amp; test'));
  assert.ok(html.includes('skill&lt;1&gt;'));
  assert.ok(html.includes('skill-2'));
  assert.ok(html.includes('data-action="runNeedAction"'));
  assert.ok(html.includes('data-action="copyNeedAction"'));

  // Test router need action button
  const routerNeed = {
    id: 'never-run-out',
    name: 'Keep working',
    why: 'Router fallback',
    score: 0.8,
    skills: ['sfp-route'],
    attach: 'sfp-route',
    preload: [],
    action: 'start the router: python3 mcp/sfp_route.py serve',
  };
  const routerHtml = hive.renderNeedCard(routerNeed);
  assert.ok(routerHtml.includes('data-action="focusModels"'));
});

test('routeArgs formats arguments for router subcommands', () => {
  const argsDiscover = hive.routeArgs('/root', 'discover');
  assert.deepStrictEqual(argsDiscover, [path.join('/root', 'mcp', 'sfp_route.py'), 'discover']);

  const argsSetup = hive.routeArgs('/root', 'setup', '--policy', 'cheap-first', '--yes');
  assert.deepStrictEqual(argsSetup, [path.join('/root', 'mcp', 'sfp_route.py'), 'setup', '--policy', 'cheap-first', '--yes']);

  const argsServe = hive.routeArgs('/root', 'serve', '--port', 8787);
  assert.deepStrictEqual(argsServe, [path.join('/root', 'mcp', 'sfp_route.py'), 'serve', '--port', '8787']);

  const argsPlan = hive.routeArgs('/root', 'plan', 'refactor the billing service');
  assert.deepStrictEqual(argsPlan, [path.join('/root', 'mcp', 'sfp_route.py'), 'plan', 'refactor the billing service']);
});

test('parseRouteConfig parses setup json output and rejects invalid format', () => {
  const sample = `
{
 "policy": "local-first",
 "providers": [
  {
   "id": "ollama",
   "name": "Ollama",
   "kind": "local",
   "base_url": "http://127.0.0.1:11434/v1",
   "api_key_env": "",
   "models": [
    {"id": "qwen2.5-coder:7b", "strength": 1, "ctx": 8192, "tools": true}
   ]
  }
 ]
}

This is what would be written to /path/to/routes.json. Run again with --yes to write it.
  `;
  const cfg = hive.parseRouteConfig(sample);
  assert.strictEqual(cfg.policy, 'local-first');
  assert.strictEqual(cfg.providers.length, 1);
  assert.strictEqual(cfg.providers[0].id, 'ollama');
  assert.strictEqual(cfg.providers[0].models[0].strength, 1);

  assert.throws(() => hive.parseRouteConfig('no json here'));
  assert.throws(() => hive.parseRouteConfig('{"policy": "local-first"}'));
});

test('parseRouteStatus parses health status and rejects invalid', () => {
  const statusSample = JSON.stringify({
    policy: 'local-first',
    models: [
      {
        model: 'ollama/llama3',
        kind: 'local',
        strength: 1,
        state: 'ready',
        ok: 5,
        failed: 0,
        last_error: '',
      },
      {
        model: 'groq/llama-3.3-70b',
        kind: 'free',
        strength: 3,
        state: 'cooling down 30s: rate limited',
        ok: 2,
        failed: 2,
        last_error: 'rate limited',
      },
    ],
  });
  const st = hive.parseRouteStatus(statusSample);
  assert.strictEqual(st.policy, 'local-first');
  assert.strictEqual(st.models.length, 2);
  assert.strictEqual(st.models[1].failed, 2);

  assert.throws(() => hive.parseRouteStatus('bad json'));
  assert.throws(() => hive.parseRouteStatus('{"policy": "local-first"}'));
});

test('parseRoutePlan parses plan output lines', () => {
  const planSample = `request: normal (about 1200 tokens)
1. ollama/llama3  strength 2  local
2. groq/llama-3.3-70b-versatile  strength 3  free`;

  const plan = hive.parseRoutePlan(planSample);
  assert.strictEqual(plan.tier, 'normal');
  assert.strictEqual(plan.tokens, 1200);
  assert.strictEqual(plan.order.length, 2);
  assert.strictEqual(plan.order[0].model, 'ollama/llama3');
  assert.strictEqual(plan.order[0].strength, 2);
  assert.strictEqual(plan.order[0].kind, 'local');
  assert.strictEqual(plan.order[1].model, 'groq/llama-3.3-70b-versatile');
  assert.strictEqual(plan.order[1].strength, 3);
  assert.strictEqual(plan.order[1].kind, 'free');
});
test('doctorArgs formats command and parseDoctor parses output', () => {
  const args = hive.doctorArgs('/path/to/sfp', '/proj', 8787);
  assert.ok(args[0].endsWith('sfp_hive.py'));
  assert.strictEqual(args[1], 'doctor');
  assert.ok(args.includes('--json'));
  assert.ok(args.includes('--port'));
  assert.ok(args.includes('8787'));
  assert.ok(args.includes('--project'));
  assert.ok(args.includes('/proj'));

  const jsonSample = JSON.stringify({
    status: 'warn',
    checks: [
      { name: 'Python', status: 'ok', detail: '3.13.14', fix: '' },
      { name: 'Local models', status: 'warn', detail: 'none found', fix: 'Start Ollama' },
    ],
  });
  const res = hive.parseDoctor(jsonSample);
  assert.strictEqual(res.status, 'warn');
  assert.strictEqual(res.checks.length, 2);
  assert.strictEqual(res.checks[0].name, 'Python');
  assert.throws(() => hive.parseDoctor('bad json'));
  assert.throws(() => hive.parseDoctor('{}'));
});

test('renderDoctorHtml renders green/amber/red marks, details, and escaped fixes', () => {
  const res = {
    status: 'fail',
    checks: [
      { name: 'Python', status: 'ok', detail: '3.13', fix: '' },
      { name: 'Router <script>', status: 'fail', detail: 'down & halted', fix: 'Run "sfp_route" & fix' },
    ],
  };
  const html = hive.renderDoctorHtml(res);
  assert.ok(html.includes('doctor-ok'));
  assert.ok(html.includes('doctor-fail'));
  assert.ok(html.includes('Router &lt;script&gt;'));
  assert.ok(html.includes('down &amp; halted'));
  assert.ok(html.includes('Run &quot;sfp_route&quot; &amp; fix'));
  assert.ok(html.includes('data-action="copyFix"'));
});

test('renderBundleBanner renders pushed bundle with numbered chips and suggested bundle with attach', () => {
  const pushed = {
    id: 'b1',
    name: 'Form & Access',
    skills: ['ux-writing', 'react-patterns'],
  };
  const htmlPushed = hive.renderBundleBanner(pushed);
  assert.ok(htmlPushed.includes('Bundle: <strong>Form &amp; Access</strong>'));
  assert.ok(htmlPushed.includes('data-action="notThisBundle"'));
  assert.ok(htmlPushed.includes('bundle-chip-num">1<'));
  assert.ok(htmlPushed.includes('ux-writing'));
  assert.ok(htmlPushed.includes('bundle-chip-num">2<'));
  assert.ok(htmlPushed.includes('react-patterns'));

  const suggested = {
    id: 'b2',
    name: 'Clean Code',
    score: 0.5,
    push: false,
    skills: ['testing'],
    missing: [],
    why: '',
  };
  const htmlSuggested = hive.renderBundleBanner(undefined, suggested);
  assert.ok(htmlSuggested.includes('Looks like <strong>Clean Code</strong>'));
  assert.ok(htmlSuggested.includes('data-action="attachBundle"'));
  assert.ok(htmlSuggested.includes('data-bundle-id="b2"'));
});
