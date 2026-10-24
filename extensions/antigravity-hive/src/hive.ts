// The part of the extension that does not need VS Code: finding the SFP checkout, calling the hive, and
// turning its answer into a prompt. Kept free of the vscode module so `node --test` can run it.
import { spawn } from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

export interface Skill {
  name: string;
  phase?: string;
  layer?: string;
  category?: string;
  tokens?: number;
  score?: number;
  path?: string;
  reasons?: string[];
}

export interface Candidate {
  name: string;
  status: string; // 'chosen', 'pinned by you', 'excluded by you', or 'dropped: <reason>'
  quality: number;
  signals: { words: number | null; project: number | null; role: number | null; category: number | null; history: number | null };
  backers: string[];
  relation?: string;
  learned: number;
  tokens: number;
}

export interface Steer {
  include?: string[]; // skills the user pinned
  exclude?: string[]; // skills the user ruled out
  explain?: boolean; // ask for every top candidate and why it was or was not taken
  bundle?: string; // a bundle id or name: all its skills are pinned, in order
}

export interface Selection {
  task: string;
  decision?: string; // absent when the user switched logging off (SFP_NO_USAGE_LOG)
  stack: Skill[];
  layers: { base: string[]; check: string[]; finish: string[] };
  tokens: number;
  next: { name: string; probability: number }[];
  explain?: Candidate[];
  intervention?: { pinned: string[]; excluded: string[] };
  bundle?: { id: string; name: string };
  needs?: Need[];
  preload?: { name: string; why: string }[];
  bundles?: BundleMatch[]; // bundles that fit the task, best first; the first is attached whole when `bundle` is set
}

/** A bundle that fits the task: pushed (attached whole, in order) when push is true, otherwise only suggested. */
export interface BundleMatch {
  id: string; name: string; score: number; push: boolean; applied?: boolean;
  skills: string[]; missing: string[]; why: string;
}

/** Something the task needs that the model cannot do alone, from `sfp_hive.py needs`. */
export interface Need {
  id: string; name: string; why: string; score: number;
  attach: string; preload: string[]; skills: string[];
  apps?: { id: string; name: string; state: string; installed: boolean | null; running: boolean | null; install: string; start: string }[];
  env_missing?: string[];
  router?: { configured: boolean; models: number; running: boolean; port: number };
  action?: string; // 'ready', or the one command or step that unblocks it (only with --check)
}

export type Verdict = 'helped' | 'unhelpful' | 'ignored' | 'missing';

export interface Options {
  sfpPath?: string;
  python?: string;
  home?: string;
}

/** The SFP checkout: the setting, then the folder the installer recorded in ~/.sfp/root. */
export function findSfpRoot(opts: Options = {}): string | undefined {
  const candidates: string[] = [];
  if (opts.sfpPath) candidates.push(opts.sfpPath);
  const home = opts.home ?? os.homedir();
  try {
    const recorded = fs.readFileSync(path.join(home, '.sfp', 'root'), 'utf8').trim();
    if (recorded) candidates.push(recorded);
  } catch {
    // not installed through the SFP installer
  }
  return candidates.find((c) => fs.existsSync(path.join(c, 'mcp', 'sfp_hive.py')));
}

export function pythonCommand(opts: Options = {}): string {
  return opts.python || (process.platform === 'win32' ? 'python' : 'python3');
}

export function selectArgs(root: string, task: string, project: string | undefined, max: number, steer: Steer = {}): string[] {
  const args = [path.join(root, 'mcp', 'sfp_hive.py'), 'select', task, '--json', '--max', String(max)];
  if (project) args.push('--project', project);
  if (steer.include && steer.include.length) args.push('--include', steer.include.join(','));
  if (steer.exclude && steer.exclude.length) args.push('--exclude', steer.exclude.join(','));
  if (steer.explain) args.push('--explain');
  if (steer.bundle) args.push('--bundle', steer.bundle);
  return args;
}

/** The feedback an intervention implies: a chosen skill the user removed did not help; one they added was missing. */
export function interventionFeedback(before: Selection, steer: Steer): { verdict: Verdict; skills: string[] }[] {
  const chosen = new Set(before.stack.map((s) => s.name));
  const removed = (steer.exclude ?? []).filter((n) => chosen.has(n));
  const added = (steer.include ?? []).filter((n) => !chosen.has(n));
  const out: { verdict: Verdict; skills: string[] }[] = [];
  if (removed.length) out.push({ verdict: 'unhelpful', skills: removed });
  if (added.length) out.push({ verdict: 'missing', skills: added });
  return out;
}

export function feedbackArgs(root: string, decision: string, verdict: Verdict, skills: string[], task?: string): string[] {
  const args = [path.join(root, 'mcp', 'sfp_hive.py'), 'feedback', decision, `--${verdict}`, skills.join(',')];
  if (task) args.push('--task', task);
  return args;
}

export function run(python: string, args: string[], timeoutMs = 60000, input?: string): Promise<string> {
  return new Promise((resolve, reject) => {
    // No shell: the task text is passed as one argument, never interpreted.
    const child = spawn(python, args, { env: process.env });
    if (input !== undefined) {
      child.stdin.write(input);
    }
    child.stdin.end();
    let out = '';
    let err = '';
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error('the hive did not answer in time'));
    }, timeoutMs);
    child.stdout.on('data', (d) => (out += d));
    child.stderr.on('data', (d) => (err += d));
    child.on('error', (e) => {
      clearTimeout(timer);
      reject(new Error(`could not start ${python}: ${e.message}`));
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      if (code === 0) resolve(out);
      else reject(new Error((err || out).trim().split('\n').slice(-3).join(' ') || `exit ${code}`));
    });
  });
}

export function parseSelection(json: string): Selection {
  const raw = JSON.parse(json);
  if (!raw || !Array.isArray(raw.stack)) {
    throw new Error('unexpected answer from the hive');
  }
  return {
    task: String(raw.task ?? ''),
    decision: typeof raw.decision === 'string' ? raw.decision : undefined,
    stack: raw.stack,
    layers: raw.layers ?? { base: [], check: [], finish: [] },
    tokens: Number(raw.tokens ?? 0),
    next: Array.isArray(raw.next) ? raw.next : [],
    explain: Array.isArray(raw.explain) ? raw.explain : undefined,
    intervention: raw.intervention,
  };
}

/** The skills grouped by layer, in the order to use them: base, then check, then finish. */
export function byLayer(sel: Selection): { layer: string; skills: Skill[] }[] {
  const order = ['base', 'check', 'finish'];
  const groups = order.map((layer) => ({ layer, skills: sel.stack.filter((s) => (s.layer ?? 'base') === layer) }));
  const known = new Set(order);
  const other = sel.stack.filter((s) => !known.has(s.layer ?? 'base'));
  if (other.length) groups.push({ layer: 'other', skills: other });
  return groups.filter((g) => g.skills.length > 0);
}

/** Diff between two selections: returns added and removed skill names. */
export function selectionDiff(before: Selection | undefined, after: Selection): { added: string[]; removed: string[] } {
  const beforeNames = new Set((before?.stack || []).map((s) => s.name));
  const afterNames = new Set((after?.stack || []).map((s) => s.name));
  const added = Array.from(afterNames).filter((n) => !beforeNames.has(n));
  const removed = Array.from(beforeNames).filter((n) => !afterNames.has(n));
  return { added, removed };
}

export interface SessionStats {
  decisions: number;
  interventions: number;
  chosenTotal: number;
  keptTotal: number;
  addedSkills: number;
  helped: number;
  unhelpful: number;
}

export function defaultSessionStats(): SessionStats {
  return {
    decisions: 0,
    interventions: 0,
    chosenTotal: 0,
    keptTotal: 0,
    addedSkills: 0,
    helped: 0,
    unhelpful: 0,
  };
}

export function updateSessionStats(
  current: SessionStats,
  event:
    | { type: 'decision'; chosenCount: number }
    | { type: 'intervention'; beforeCount: number; keptCount: number; addedCount: number }
    | { type: 'feedback'; verdict: 'helped' | 'unhelpful' }
): SessionStats {
  const stats = { ...current };
  if (event.type === 'decision') {
    stats.decisions += 1;
    stats.chosenTotal += event.chosenCount;
    stats.keptTotal += event.chosenCount;
  } else if (event.type === 'intervention') {
    stats.interventions += 1;
    const droppedFromBefore = Math.max(0, event.beforeCount - event.keptCount);
    stats.keptTotal = Math.max(0, stats.keptTotal - droppedFromBefore);
    stats.addedSkills += event.addedCount;
  } else if (event.type === 'feedback') {
    if (event.verdict === 'helped') stats.helped += 1;
    else if (event.verdict === 'unhelpful') stats.unhelpful += 1;
  }
  return stats;
}

/** A prompt to paste into an agent panel: which skills to read, in what order, and how to report back. */
export function buildPrompt(sel: Selection, root?: string): string {
  if (!sel.stack.length) return `The hive found no skill that fits: ${sel.task}`;
  const lines = [`Task: ${sel.task}`, '', 'Use these SFP skills, in this order. Read only these, and follow them:'];
  sel.stack.forEach((s, i) => {
    const where = s.path ? (root ? path.join(root, s.path) : s.path) : '';
    const why = s.reasons && s.reasons.length ? ` (${s.reasons[0]})` : '';
    lines.push(`${i + 1}. ${s.name}${s.layer ? ` [${s.layer}]` : ''}${why}${where ? `\n   ${where}` : ''}`);
  });
  lines.push('', sel.decision
    ? `When the task ends, report how each skill went with give_feedback (decision ${sel.decision}): helped, unhelpful, ignored (chosen but not used) or missing (should have been chosen).`
    : 'Learning is switched off here, so there is no feedback to report.');
  return lines.join('\n');
}

export function skillFile(root: string, s: Skill): string | undefined {
  if (!s.path) return undefined;
  const full = path.resolve(root, s.path);
  // Only files inside the SFP checkout.
  return full.startsWith(path.resolve(root) + path.sep) && fs.existsSync(full) ? full : undefined;
}

export function catalogNames(root: string): string[] {
  try {
    const cat = JSON.parse(fs.readFileSync(path.join(root, 'catalog.json'), 'utf8'));
    return (cat.skills as { name: string }[]).map((s) => s.name).sort();
  } catch {
    return [];
  }
}

export function profileNames(root: string): string[] {
  try {
    return Object.keys(JSON.parse(fs.readFileSync(path.join(root, 'catalog.json'), 'utf8')).profiles ?? {});
  } catch {
    return [];
  }
}

export function appList(root: string): { id: string; name: string; what: string }[] {
  try {
    const apps = JSON.parse(fs.readFileSync(path.join(root, 'apps', 'apps.json'), 'utf8'));
    return Object.entries(apps).map(([id, a]) => ({ id, name: (a as any).name, what: (a as any).what }));
  } catch {
    return [];
  }
}

/** One argument quoted for the integrated terminal (the shell is unknown, so quote conservatively). */
export function quote(arg: string): string {
  if (/^[\w@%+=:,./-]+$/.test(arg)) return arg;
  return process.platform === 'win32' ? `"${arg.replace(/"/g, '\\"')}"` : `'${arg.replace(/'/g, `'\\''`)}'`;
}

// ------------------------------------------------------------------ following the agent

/** One thing that happened in the workspace, in the shape `sfp_hive.py track` reads. */
export interface ActivityEvent {
  t: number; // seconds since 1970
  kind: 'prompt' | 'save' | 'edit' | 'create' | 'delete' | 'open' | 'run' | 'diagnostics' | 'git';
  path?: string;
  command?: string;
  exit?: number;
  errors?: number;
  text?: string;
}

export interface TrackResult {
  phase: string | null;
  layer: 'base' | 'check' | 'finish' | null;
  confidence: number; // 0..1, from the Kalman filter's variance
  shares: Record<string, number>; // each phase's share of the current work
  changed: boolean;
  changes: { t: number; from: string; to: string }[];
  next: { phase: string; probability: number }[]; // the Markov chain's prediction
  words: string[];
  skills?: Skill[];
  upcoming?: { phase: string; skills: string[] };
}

export function trackArgs(root: string, project: string | undefined, max: number, select = true, reset = false): string[] {
  const args = [path.join(root, 'mcp', 'sfp_hive.py'), 'track', '--json', '--max', String(max)];
  if (project) args.push('--project', project);
  if (!select) args.push('--no-select');
  if (reset) args.push('--reset');
  return args;
}

export function parseTrack(json: string): TrackResult {
  const raw = JSON.parse(json);
  if (!raw || typeof raw !== 'object' || !('phase' in raw) || !raw.shares) throw new Error('unexpected answer from the tracker');
  return raw as TrackResult;
}

/** Paths are sent relative to the workspace, so nothing outside it is described. */
export function relative(workspace: string | undefined, file: string): string | undefined {
  if (!workspace) return undefined;
  const rel = path.relative(workspace, file);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel)) return undefined;
  return rel.split(path.sep).join('/');
}

/**
 * Collects workspace events and hands them over in batches. Repeated saves of one file within a batch count
 * once, opening files is ignored unless nothing else happened, and the buffer never grows past `limit`.
 */
export class ActivityBuffer {
  private events: ActivityEvent[] = [];

  constructor(private readonly limit = 200, private readonly clock: () => number = () => Date.now() / 1000) {}

  add(e: Omit<ActivityEvent, 't'> & { t?: number }): void {
    const ev = { ...e, t: e.t ?? this.clock() } as ActivityEvent;
    const last = this.events[this.events.length - 1];
    if (last && last.kind === ev.kind && ev.path && last.path === ev.path && (ev.kind === 'save' || ev.kind === 'edit')) {
      last.t = ev.t; // the same file saved again: one event, the latest time
      return;
    }
    this.events.push(ev);
    if (this.events.length > this.limit) this.events.splice(0, this.events.length - this.limit);
  }

  get size(): number {
    return this.events.length;
  }

  /** The batch to send, emptied. Opens are kept only when nothing more telling happened. */
  take(): ActivityEvent[] {
    const out = this.events.some((e) => e.kind !== 'open') ? this.events.filter((e) => e.kind !== 'open') : this.events;
    this.events = [];
    return out;
  }
}

export const PHASE_LAYERS: Record<string, 'base' | 'check' | 'finish'> = {
  research: 'base',
  plan: 'base',
  design: 'base',
  build: 'base',
  debug: 'base',
  test: 'check',
  secure: 'check',
  review: 'check',
  optimize: 'finish',
  document: 'finish',
  ship: 'finish',
};

/**
 * Throttle phase change notifications: at most one every 2 minutes (minIntervalMs),
 * and only when the phase changed with a confidence of at least 0.6 (minConfidence).
 */
export function shouldNotifyPhaseChange(
  lastNotifyTime: number,
  now: number,
  changed: boolean,
  confidence: number,
  minIntervalMs = 120000,
  minConfidence = 0.6
): boolean {
  return changed && confidence >= minConfidence && (now - lastNotifyTime >= minIntervalMs);
}

export interface PhaseBarSegment {
  phase: string;
  share: number;
  percent: number;
  layer: 'base' | 'check' | 'finish';
}

export function phaseBarViewModel(shares: Record<string, number>): PhaseBarSegment[] {
  const entries = Object.entries(shares || {}).filter(([_, s]) => s > 0.005);
  const total = entries.reduce((acc, [_, s]) => acc + s, 0) || 1;
  return entries.map(([phase, share]) => ({
    phase,
    share,
    percent: Math.round((share / total) * 100),
    layer: PHASE_LAYERS[phase] ?? 'base',
  }));
}

export interface NextChip {
  phase: string;
  probability: number;
  percent: number;
  label: string;
  layer: 'base' | 'check' | 'finish';
}

export function chipsViewModel(next: { phase: string; probability: number }[]): NextChip[] {
  return (next || []).map((n) => ({
    phase: n.phase,
    probability: n.probability,
    percent: Math.round(n.probability * 100),
    label: `${n.phase[0].toUpperCase() + n.phase.slice(1)} ${Math.round(n.probability * 100)}%`,
    layer: PHASE_LAYERS[n.phase] ?? 'base',
  }));
}

export interface PhaseChangeItem {
  from: string;
  to: string;
  t: number;
  label: string;
}

export function phaseChangesViewModel(changes: { t: number; from: string; to: string }[]): PhaseChangeItem[] {
  return (changes || []).slice(-5).reverse().map((c) => ({
    from: c.from,
    to: c.to,
    t: c.t,
    label: `${c.from} → ${c.to}`,
  }));
}

// ------------------------------------------------------------------ clusters

export interface ClusterSkill {
  name: string;
  category: string;
  also_in: string[];
  description: string;
  usage?: { chosen?: number; helped?: number; unhelpful?: number; ignored?: number; missing?: number };
}

export interface Cluster {
  id: string;
  name: string;
  description: string;
  mine: boolean;
  count: number;
  used?: number;
  skills: ClusterSkill[];
}

export function clustersArgs(root: string): string[] {
  return [path.join(root, 'mcp', 'sfp_hive.py'), 'clusters', '--json'];
}

export function clusterAddArgs(root: string, name: string, skills: string[], description = ''): string[] {
  const args = [path.join(root, 'mcp', 'sfp_hive.py'), 'cluster-add', name, '--skills', skills.join(',')];
  if (description) args.push('--description', description);
  return args;
}

export function clusterRemoveArgs(root: string, name: string): string[] {
  return [path.join(root, 'mcp', 'sfp_hive.py'), 'cluster-remove', name];
}

export function parseClusters(json: string): Cluster[] {
  const raw = JSON.parse(json);
  if (!Array.isArray(raw)) throw new Error('unexpected answer for clusters');
  return raw as Cluster[];
}

// ------------------------------------------------------------------ the library

export function libraryArgs(root: string): string[] {
  return [path.join(root, 'mcp', 'sfp_hive.py'), 'library'];
}

export function parseLibrary(json: string): import('./library').Library {
  const raw = JSON.parse(json);
  if (!raw || typeof raw !== 'object' || !raw.skills || !Array.isArray(raw.purposes) || !Array.isArray(raw.bundles)) {
    throw new Error('unexpected answer for the library');
  }
  return raw;
}

export function bundleAddArgs(root: string, name: string, skills: string[], goal = '', purpose = 'build', when = ''): string[] {
  const args = [path.join(root, 'mcp', 'sfp_hive.py'), 'bundle-add', name, '--skills', skills.join(','), '--purpose', purpose];
  if (goal) args.push('--goal', goal);
  if (when) args.push('--when', when);
  return args;
}

export function bundleRemoveArgs(root: string, name: string): string[] {
  return [path.join(root, 'mcp', 'sfp_hive.py'), 'bundle-remove', name];
}

export interface LiveSkill { name: string; category: string; description: string; source: 'auto' | 'pinned' }
export interface LiveState { anchor: string[]; auto: string[]; pinned: string[]; removed: string[] }
export interface LiveResult { status: 'waiting' | 'kept' | 'updated' | 'committed'; changed: boolean; needs?: Need[]; bundles?: BundleMatch[]; attached: LiveSkill[]; state: LiveState; words: string[]; decision?: string }
export interface LiveChange { pin?: string[]; unpin?: string[]; remove?: string[]; restore?: string[]; commit?: boolean }

export function liveArgs(root: string, draft: string, state: LiveState | undefined, project: string | undefined, max: number, change: LiveChange = {}): string[] {
  const args = [path.join(root, 'mcp', 'sfp_hive.py'), 'live', draft, '--json', '--max', String(max)];
  if (state) args.push('--state', JSON.stringify(state));
  if (project) args.push('--project', project);
  for (const k of ['pin', 'unpin', 'remove', 'restore'] as const) {
    const v = change[k];
    if (v && v.length) args.push('--' + k, v.join(','));
  }
  if (change.commit) args.push('--commit');
  return args;
}

export function parseLive(json: string): LiveResult {
  const r = JSON.parse(json);
  if (!r || !Array.isArray(r.attached) || !r.state) throw new Error('unexpected output from the hive live command');
  return r as LiveResult;
}

export function escapeHtml(str: string): string {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function needsArgs(root: string, task: string, project?: string, check = false): string[] {
  const args = [path.join(root, 'mcp', 'sfp_hive.py'), 'needs', task, '--json'];
  if (project) args.push('--project', project);
  if (check) args.push('--check');
  return args;
}

<<<<<<< HEAD
export function parseNeeds(json: string): Need[] {
  const r = JSON.parse(json);
  if (!Array.isArray(r)) throw new Error('unexpected output from the hive needs command');
  return r as Need[];
}

export function renderNeedCard(need: Need): string {
  const name = escapeHtml(need.name);
  const why = escapeHtml(need.why);
  const attach = escapeHtml(need.attach);
  const preloadHtml = (need.preload || [])
    .map((s) => `<span class="badge badge-preload">${escapeHtml(s)}</span>`)
    .join(' ');
  const action = need.action || '';
  let actionHtml = '';
  if (action && action !== 'ready') {
    const isRouter = need.id === 'never-run-out';
    const actionBtn = isRouter
      ? `<button class="btn-small btn-primary" data-action="focusModels">Open Models</button>`
      : `<button class="btn-small btn-primary" data-action="runNeedAction" data-action-cmd="${escapeHtml(action)}">Run in terminal</button>`;
    actionHtml = `
      <div class="need-action-bar">
        <span class="need-action-cmd" title="${escapeHtml(action)}">${escapeHtml(action)}</span>
        <div class="need-action-btns">
          <button class="btn-small btn-secondary" data-action="copyNeedAction" data-action-cmd="${escapeHtml(action)}">Copy</button>
          ${actionBtn}
        </div>
      </div>`;
  }
  return `
    <div class="need-card" data-need-id="${escapeHtml(need.id)}">
      <div class="need-header">
        <span class="need-title">${name}</span>
        <span class="badge badge-attached">Attached: ${attach}</span>
      </div>
      <div class="need-why">${why}</div>
      ${preloadHtml ? `<div class="need-preload"><span class="need-preload-label">Preload:</span> ${preloadHtml}</div>` : ''}
      ${actionHtml}
    </div>`.trim();
}

// ------------------------------------------------------------------ the router

export interface RouteModel {
  id: string;
  strength: number;
  ctx?: number;
  tools?: boolean;
}

export interface RouteProvider {
  id: string;
  name: string;
  kind: 'local' | 'free' | 'paid' | string;
  base_url: string;
  api_key_env: string;
  models: RouteModel[];
}

export interface RouteConfig {
  policy: 'local-first' | 'cheap-first' | 'strong-first' | string;
  providers: RouteProvider[];
}

export interface RouteStatusModel {
  model: string;
  kind: string;
  strength: number;
  state: string;
  ok: number;
  failed: number;
  last_error: string;
}

export interface RouteStatus {
  policy: string;
  models: RouteStatusModel[];
}

export interface RoutePlanItem {
  num: number;
  model: string;
  strength: number;
  kind: string;
}

export interface RoutePlan {
  tier: string;
  tokens: number;
  order: RoutePlanItem[];
}

export function routeArgs(root: string, cmd: string, ...extra: (string | number)[]): string[] {
  const args = [path.join(root, 'mcp', 'sfp_route.py'), cmd];
  for (const a of extra) {
    if (a !== undefined && a !== null) args.push(String(a));
  }
  return args;
}

export function parseRouteConfig(raw: string): RouteConfig {
  const match = raw.match(/\{[\s\S]*\}/);
  if (!match) throw new Error('no JSON config found in router setup output');
  const cfg = JSON.parse(match[0]);
  if (!cfg || !Array.isArray(cfg.providers)) throw new Error('invalid router config format');
  return cfg as RouteConfig;
}

export function parseRouteStatus(json: string): RouteStatus {
  const raw = JSON.parse(json);
  if (!raw || !Array.isArray(raw.models)) throw new Error('invalid router status format');
  return raw as RouteStatus;
}

export function parseRoutePlan(text: string): RoutePlan {
  const lines = text.trim().split('\n');
  let tier = 'normal';
  let tokens = 0;
  const order: RoutePlanItem[] = [];
  const reqMatch = lines[0]?.match(/request:\s*(\w+)\s*\(about\s*(\d+)\s*tokens\)/);
  if (reqMatch) {
    tier = reqMatch[1];
    tokens = parseInt(reqMatch[2], 10);
  }
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    const m = line.match(/^(\d+)\.\s+([^\s]+)\s+strength\s+(\d+)\s+(.*)$/);
    if (m) {
      order.push({
        num: parseInt(m[1], 10),
        model: m[2],
        strength: parseInt(m[3], 10),
        kind: m[4].trim(),
      });
    }
  }
  return { tier, tokens, order };
}



/** Everything the skill detail window shows, from `sfp_hive.py skill NAME --json`. */
export interface SkillDetail {
  name: string;
  description: string;
  use_when: string;
  category: string;
  family: { id: string; name: string };
  cluster: { id: string; name: string };
  purpose: { id: string; name: string };
  also: { id: string; name: string }[];
  bundles: { id: string; name: string }[];
  similar: string[];
  tokens: number;
  path: string;
  usage?: { chosen?: number; helped?: number; unhelpful?: number; ignored?: number; missing?: number };
  app?: string;
}

export function skillArgs(root: string, name: string): string[] {
  return [path.join(root, 'mcp', 'sfp_hive.py'), 'skill', name, '--json'];
}

export function parseSkillDetail(json: string): SkillDetail {
  const d = JSON.parse(json);
  if (!d || typeof d.name !== 'string' || typeof d.description !== 'string' || !d.family) throw new Error('unexpected answer for a skill');
  return d as SkillDetail;
}

/** The page of the skill detail window. Pure, so it is unit tested; every string is escaped. */
export function skillDetailHtml(d: SkillDetail, cspSource: string, nonce: string, styleUri: string, scriptUri: string): string {
  const e = escapeHtml;
  const btn = (action: string, label: string, extra = '', cls = 'btn') => `<button class="${cls}" data-action="${action}" ${extra}>${label}</button>`;
  const chip = (action: string, key: string, value: string, text: string) =>
    `<button class="chip" data-action="${action}" data-${key}="${e(value)}">${e(text)}</button>`;
  const u = d.usage && (d.usage.chosen ?? 0) > 0
    ? `<li><b>Used</b> ${e(String(d.usage.chosen))} time${d.usage.chosen === 1 ? '' : 's'}${d.usage.helped ? `, helped ${e(String(d.usage.helped))}` : ''}</li>` : '';
  const when = d.use_when ? `<section><h2>Use it when</h2><p>${e(d.use_when.replace(/^Use (this skill )?(when|for|to)\s*/i, ''))}</p></section>` : '';
  const what = d.use_when ? d.description.slice(0, d.description.length - d.use_when.length).trim() || d.description : d.description;
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${cspSource}; script-src 'nonce-${nonce}'; img-src ${cspSource} data:;">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>${e(d.name)}</title>
<link rel="stylesheet" href="${styleUri}"></head>
<body><main>
  <header>
    <p class="crumbs">${e(d.family.name)}${d.cluster.name.toLowerCase() === d.family.name.toLowerCase() ? '' : ` <span>/</span> ${e(d.cluster.name)}`}</p>
    <h1>${e(d.name)}</h1>
    <p class="tags"><span class="tag tag-purpose">${e(d.purpose.name)}</span>${d.also.map((a) => `<span class="tag">${e(a.name)}</span>`).join('')}${d.app ? `<span class="tag tag-app" title="Needs the program ${e(d.app)}">needs a program</span>` : ''}</p>
    <div class="actions">${btn('openFile', 'Open SKILL.md', '', 'btn')}${btn('pin', 'Pin to current task', '', 'btn btn-primary')}${btn('addToBundle', '+ Add to a bundle')}</div>
  </header>
  <section><h2>What it does</h2><p>${e(what)}</p></section>
  ${when}
  ${d.bundles.length ? `<section><h2>In these bundles</h2><div class="chips">${d.bundles.map((b) => chip('showBundle', 'bundle', b.id, b.name)).join('')}</div></section>` : ''}
  ${d.similar.length ? `<section><h2>Similar skills</h2><div class="chips">${d.similar.map((n) => chip('showSkill', 'skill', n, n)).join('')}</div></section>` : ''}
  <section><h2>Details</h2><ul class="facts"><li><b>Area</b> ${e(d.family.name)}</li><li><b>Topic</b> ${e(d.cluster.name)}</li><li><b>Category</b> ${e(d.category)}</li><li><b>Size</b> about ${e(String(d.tokens))} tokens</li>${u}</ul></section>
</main><script nonce="${nonce}" src="${scriptUri}"></script></body></html>`;
}

/** One line of `sfp_hive.py doctor --json`: a part of the hive and whether it works. */
export interface DoctorCheck { name: string; status: 'ok' | 'warn' | 'fail'; detail: string; fix: string }
export interface DoctorResult { status: 'ok' | 'warn' | 'fail'; checks: DoctorCheck[] }

export function doctorArgs(root: string, project?: string, port = 8787): string[] {
  const args = [path.join(root, 'mcp', 'sfp_hive.py'), 'doctor', '--json', '--port', String(port)];
  if (project) args.push('--project', project);
  return args;
}

/** `doctor` exits 1 when something fails but still prints its JSON, so a failed run is parsed from its output. */
export function parseDoctor(json: string): DoctorResult {
  const r = JSON.parse(json);
  if (!r || !Array.isArray(r.checks)) throw new Error('unexpected output from the hive doctor command');
  return r as DoctorResult;
}
