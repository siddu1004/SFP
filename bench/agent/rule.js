// Build the rule text the SFP Hive extension would write, from a `sfp_hive.py select --json` result on stdin.
// Usage: node rule.js <sfp checkout> < selection.json
const hive = require('../../extensions/antigravity-hive/out/hive.js');
const sel = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const stack = sel.stack || [];
const bundles = sel.bundle ? [{ name: sel.bundle.name, skills: stack.map((s) => s.name) }] : [];
process.stdout.write(hive.activeSkillsRule({ source: 'task', task: sel.task, skills: stack, bundles }, process.argv[2]));
