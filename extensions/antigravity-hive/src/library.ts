// The skill library's logic: search and grouping over the payload from `sfp_hive.py library`. No editor code, so
// it is unit tested on its own. The tokenizer is a port of the one in mcp/sfp_mcp.py (a parity test runs both).

export interface Usage {
  chosen?: number;
  helped?: number;
  unhelpful?: number;
  ignored?: number;
  missing?: number;
}

export interface LibrarySkill {
  d: string; // a short description
  category: string;
  cluster: string; // the home cluster id
  purpose: string; // the primary purpose id
  also: string[]; // secondary purpose ids
  n: string[]; // stemmed words of the name
  t: string[]; // stemmed words of the description that say the most
  usage?: Usage;
  app?: string; // the program the skill needs installed
}

export interface Purpose {
  id: string;
  name: string;
  description: string;
  icon: string; // a codicon name
  count: number;
  used: number;
}

export interface LibraryCluster {
  id: string;
  name: string;
  description: string;
  mine: boolean;
  count: number;
  used: number;
  skills: string[];
}

export interface Bundle {
  id: string;
  name: string;
  goal: string;
  purpose: string;
  when: string;
  skills: string[]; // in the order to use them
  mine: boolean;
  recipe: boolean;
  tokens: number;
}

export interface Library {
  version: number;
  counts: { skills: number; purposes: number; clusters: number; bundles: number };
  purposes: Purpose[];
  clusters: LibraryCluster[];
  bundles: Bundle[];
  skills: Record<string, LibrarySkill>;
}

// ---------------------------------------------------------------- the tokenizer, as in mcp/sfp_mcp.py

const STOP = new Set(
  ('a an the and or of to in on at by for with from into onto up out my our your its it is are be do does how what ' +
    'which that this these those i me we you can could should would will please need want make').split(' '),
);
const ALIASES: [string, string][] = [['c++', ' cpp '], ['c#', ' csharp '], ['f#', ' fsharp '], ['.net', ' dotnet '],
  ['node.js', ' nodejs '], ['next.js', ' nextjs '], ['nuxt.js', ' nuxtjs ']];

const stemCache = new Map<string, string>();

export function stem(word: string): string {
  const hit = stemCache.get(word);
  if (hit !== undefined) return hit;
  let w = word;
  for (const suf of ['ing', 'ed', 'es', 's']) {
    if (w.endsWith(suf) && w.length - suf.length >= 3 && !w.endsWith('ss')) {
      w = w.slice(0, -suf.length);
      break;
    }
  }
  if (w.length > 4 && w.endsWith('e')) w = w.slice(0, -1);
  stemCache.set(word, w);
  return w;
}

export function rawWords(text: string): string[] {
  let t = (text || '').toLowerCase();
  for (const [src, dst] of ALIASES) t = t.split(src).join(dst);
  return t.split(/[^a-z0-9]+/).filter((w) => w.length > 1);
}

export function tokens(text: string): string[] {
  return rawWords(text).filter((w) => !STOP.has(w)).map(stem);
}

// ---------------------------------------------------------------- search

export interface Hit {
  name: string;
  score: number;
  marks: [number, number][]; // [start, end) ranges of the name to highlight
}

export interface SearchOptions {
  purpose?: string;
  cluster?: string;
  limit?: number;
}

/** Words of one family, such as accessible and accessibility: a long shared start, covering most of the shorter. */
export function related(a: string, b: string): boolean {
  const n = Math.min(a.length, b.length);
  if (n < 6) return false;
  let i = 0;
  while (i < n && a[i] === b[i]) i++;
  return i >= 6 && i >= 0.75 * n;
}

/** True when a and b differ by one insertion, deletion, substitution or swap of neighbours. */
export function withinOneEdit(a: string, b: string): boolean {
  if (a === b) return true;
  const la = a.length;
  const lb = b.length;
  if (Math.abs(la - lb) > 1) return false;
  let i = 0;
  while (i < la && i < lb && a[i] === b[i]) i++;
  if (la === lb) {
    if (a.slice(i + 1) === b.slice(i + 1)) return true; // one substitution
    return i + 1 < la && a[i] === b[i + 1] && a[i + 1] === b[i] && a.slice(i + 2) === b.slice(i + 2); // a swap
  }
  return la > lb ? a.slice(i + 1) === b.slice(i) : b.slice(i + 1) === a.slice(i);
}

function marksFor(name: string, words: string[]): [number, number][] {
  const lower = name.toLowerCase();
  const marks: [number, number][] = [];
  for (const w of words) {
    if (w.length < 2) continue;
    let from = 0;
    for (;;) {
      const at = lower.indexOf(w, from);
      if (at < 0) break;
      marks.push([at, at + w.length]);
      from = at + w.length;
    }
  }
  marks.sort((x, y) => x[0] - y[0]);
  const merged: [number, number][] = [];
  for (const m of marks) {
    const last = merged[merged.length - 1];
    if (last && m[0] <= last[1]) last[1] = Math.max(last[1], m[1]);
    else merged.push([m[0], m[1]]);
  }
  return merged;
}

/**
 * Rank skills for a query. A query word scores most for a whole word in the skill's name, then for the start of
 * one, then for a word that names its purpose or cluster, then for a description word, and a word of five or more
 * letters may be one typo away. A skill that matches more of the query ranks higher.
 */
export function searchLibrary(lib: Library, query: string, opts: SearchOptions = {}): Hit[] {
  const words = [...new Set(tokens(query))];
  const typed = rawWords(query);
  if (!words.length) return [];
  const purposeWords = new Map<string, Set<string>>(lib.purposes.map((p) => [p.id, new Set(tokens(p.name))]));
  const clusterWords = new Map<string, Set<string>>(lib.clusters.map((c) => [c.id, new Set(tokens(c.name))]));
  const hits: Hit[] = [];
  const whole = typed.join('-');
  for (const [name, s] of Object.entries(lib.skills)) {
    if (opts.purpose && s.purpose !== opts.purpose) continue;
    if (opts.cluster && s.cluster !== opts.cluster) continue;
    let score = 0;
    let matched = 0;
    for (const w of words) {
      let part = 0;
      if (s.n.includes(w)) part = 10;
      else if (w.length >= 2 && s.n.some((x) => x.startsWith(w))) part = 7;
      else if (w.length >= 6 && s.n.some((x) => related(x, w))) part = 6;
      else if (purposeWords.get(s.purpose)?.has(w) || clusterWords.get(s.cluster)?.has(w)) part = 4;
      else if (s.t.includes(w)) part = 2;
      else if (w.length >= 3 && s.t.some((x) => x.startsWith(w))) part = 1.5;
      else if (w.length >= 5 && s.n.some((x) => withinOneEdit(x, w))) part = 5;
      else if (w.length >= 5 && s.t.some((x) => withinOneEdit(x, w))) part = 1;
      if (part) {
        matched++;
        score += part;
      }
    }
    if (!matched) continue;
    score *= 0.4 + (0.6 * matched) / words.length;
    if (name === whole) score += 20;
    score += 0.05 * Math.min(10, s.usage?.chosen ?? 0) - 0.001 * name.length; // used skills first, then shorter names
    hits.push({ name, score, marks: marksFor(name, typed) });
  }
  hits.sort((a, b) => b.score - a.score || (a.name < b.name ? -1 : 1));
  return hits.slice(0, opts.limit ?? 200);
}

// ---------------------------------------------------------------- grouping

export type GroupMode = 'purpose' | 'cluster' | 'bundle';

export interface Group {
  id: string;
  name: string;
  description: string;
  icon?: string;
  mine?: boolean;
  skills: string[];
  total: number; // how many skills the group has before any search
  bundle?: Bundle;
}

const byUsageThenName = (lib: Library) => (a: string, b: string) =>
  (lib.skills[b]?.usage?.chosen ?? 0) - (lib.skills[a]?.usage?.chosen ?? 0) || (a < b ? -1 : 1);

/** The library as groups. With `hits`, only the matching skills are kept, in rank order, and empty groups are dropped. */
export function groupBy(lib: Library, mode: GroupMode, hits?: Hit[]): Group[] {
  const rank = hits ? new Map(hits.map((h, i) => [h.name, i])) : undefined;
  const keep = (names: string[]) => {
    const list = rank ? names.filter((n) => rank.has(n)).sort((a, b) => rank.get(a)! - rank.get(b)!) : [...names].sort(byUsageThenName(lib));
    return list;
  };
  let groups: Group[];
  if (mode === 'purpose') {
    groups = lib.purposes.map((p) => {
      const members = Object.keys(lib.skills).filter((n) => lib.skills[n].purpose === p.id);
      return { id: p.id, name: p.name, description: p.description, icon: p.icon, skills: keep(members), total: members.length };
    });
  } else if (mode === 'cluster') {
    groups = lib.clusters.map((c) => ({ id: c.id, name: c.name, description: c.description, mine: c.mine, skills: keep(c.skills), total: c.count }));
  } else {
    groups = lib.bundles.map((b) => {
      // A bundle keeps its own order: it is a sequence, not a set.
      const list = rank ? b.skills.filter((n) => rank.has(n)) : b.skills;
      return { id: b.id, name: b.name, description: b.goal, mine: b.mine, skills: list, total: b.skills.length, bundle: b };
    });
  }
  return rank ? groups.filter((g) => g.skills.length > 0) : groups;
}

/** The bundles whose name, goal or purpose match the query (a bundle also matches if one of its skills does). */
export function searchBundles(lib: Library, query: string, hits: Hit[]): Bundle[] {
  const words = new Set(tokens(query));
  if (!words.size) return [];
  const hit = new Set(hits.map((h) => h.name));
  return lib.bundles.filter((b) => {
    const text = new Set(tokens(`${b.name} ${b.goal} ${b.when}`));
    return [...words].some((w) => text.has(w)) || b.skills.some((s) => hit.has(s));
  });
}

/** Counts for the header: how many skills, and how many of them have been used. */
export function summary(lib: Library): { skills: number; used: number; purposes: number; clusters: number; bundles: number } {
  const used = Object.values(lib.skills).filter((s) => (s.usage?.chosen ?? 0) > 0).length;
  return { skills: lib.counts.skills, used, purposes: lib.counts.purposes, clusters: lib.counts.clusters, bundles: lib.counts.bundles };
}
