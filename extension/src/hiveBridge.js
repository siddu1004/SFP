const { execFile, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class HiveBridge {
  constructor(sfpRoot) {
    this.sfpRoot = sfpRoot || path.resolve(__dirname, '../..');
    this.pythonBin = process.platform === 'win32' ? 'python' : 'python3';
    this.catalogPath = path.join(this.sfpRoot, 'catalog.json');
    this.hiveScript = path.join(this.sfpRoot, 'mcp', 'sfp_hive.py');
    this.allSkills = [];
    this._loadCatalog();
  }

  _loadCatalog() {
    try {
      if (fs.existsSync(this.catalogPath)) {
        const raw = fs.readFileSync(this.catalogPath, 'utf-8');
        const data = JSON.parse(raw);
        this.allSkills = (data.skills || []).map(s => ({
          name: s.name,
          category: s.category,
          description: s.description,
          path: s.path
        }));
      }
    } catch (e) {
      console.error('Failed to load SFP catalog:', e);
    }
  }

  getAllSkills() {
    if (!this.allSkills.length) {
      this._loadCatalog();
    }
    return this.allSkills;
  }

  runCommand(args, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      const env = Object.assign({}, process.env, {
        SFP_ROOT: this.sfpRoot,
        PYTHONIOENCODING: 'utf-8'
      });

      execFile(
        this.pythonBin,
        [this.hiveScript, ...args],
        { cwd: this.sfpRoot, env, timeout: timeoutMs, maxBuffer: 10 * 1024 * 1024 },
        (error, stdout, stderr) => {
          if (error) {
            return reject(new Error(stderr || error.message));
          }
          try {
            const data = JSON.parse(stdout.trim());
            resolve(data);
          } catch (e) {
            resolve({ raw: stdout.trim(), stderr: stderr.trim() });
          }
        }
      );
    });
  }

  async selectSkills(task, projectPath, options = {}) {
    const args = ['select', task];
    if (projectPath) {
      args.push('--project', projectPath);
    }
    if (options.goal) {
      args.push('--goal', options.goal);
    }
    if (options.after && options.after.length) {
      args.push('--after', Array.isArray(options.after) ? options.after.join(',') : options.after);
    }
    if (options.budget) {
      args.push('--budget', String(options.budget));
    }
    if (options.max) {
      args.push('--max', String(options.max));
    }
    args.push('--json');

    return this.runCommand(args);
  }

  async giveFeedback(decisionId, feedback) {
    const args = ['feedback', decisionId || 'last'];
    if (feedback.helped && feedback.helped.length) {
      args.push('--helped', feedback.helped.join(','));
    }
    if (feedback.unhelpful && feedback.unhelpful.length) {
      args.push('--unhelpful', feedback.unhelpful.join(','));
    }
    if (feedback.ignored && feedback.ignored.length) {
      args.push('--ignored', feedback.ignored.join(','));
    }
    if (feedback.missing && feedback.missing.length) {
      args.push('--missing', feedback.missing.join(','));
    }
    if (feedback.task) {
      args.push('--task', feedback.task);
    }
    return this.runCommand(args);
  }

  async getStatus() {
    return this.runCommand(['status', '--json']);
  }

  async train(reset = false) {
    const args = ['train', '--json'];
    if (reset) args.push('--reset');
    return this.runCommand(args, 60000);
  }
}

module.exports = { HiveBridge };
