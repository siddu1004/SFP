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

export function run(python: string, args: string[], timeoutMs = 60000): Promise<string> {
  return new Promise((resolve, reject) => {
    // No shell: the task text is passed as one argument, never interpreted.
    const child = spawn(python, args, { env: process.env });
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
