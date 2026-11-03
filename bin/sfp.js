#!/usr/bin/env node

/**
 * SFP (Skills for Productivity) CLI & MCP Runner
 * Cross-platform entry point for npx / global npm install.
 * Includes automated update notifications and self-update capabilities.
 */

const { spawn, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');
const https = require('https');

const PKG_DIR = path.resolve(__dirname, '..');
const REPO_URL = 'https://github.com/siddu1004/SFP.git';
const GITHUB_API_TAGS = 'https://api.github.com/repos/siddu1004/SFP/tags';
const NPM_REGISTRY_LATEST = 'https://registry.npmjs.org/sfp-hive/latest';
const UPDATE_CHECK_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes

function getLatestReleaseTag(rootDir) {
  const res = spawnSync('git', ['-C', rootDir, 'tag', '-l', 'v*'], { encoding: 'utf-8' });
  if (res.status === 0 && res.stdout) {
    const lines = res.stdout.trim().split(/\r?\n/);
    const tags = [];
    for (const line of lines) {
      const m = line.trim().match(/^v(\d+)\.(\d+)\.(\d+)$/);
      if (m) {
        tags.push({
          raw: line.trim(),
          sem: [parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10)]
        });
      }
    }
    tags.sort((a, b) => {
      for (let i = 0; i < 3; i++) {
        if (b.sem[i] !== a.sem[i]) return b.sem[i] - a.sem[i];
      }
      return 0;
    });
    if (tags.length > 0) return tags[0].raw;
  }
  return null;
}

// Whether release tag vX.Y.Z is newer than the SFP checked out in rootDir: an update never moves back to an older
// release (the newest tag can lag behind main until the next release is tagged).
function isNewerRelease(tag, rootDir) {
  const m = (tag || '').match(/^v(\d+)\.(\d+)\.(\d+)$/);
  if (!m) return false;
  let mine = null;
  try {
    const v = JSON.parse(fs.readFileSync(path.join(rootDir, 'package.json'), 'utf-8')).version || '';
    const mm = v.match(/^(\d+)\.(\d+)\.(\d+)/);
    if (mm) mine = [1, 2, 3].map((i) => parseInt(mm[i], 10));
  } catch {}
  if (!mine) return true;
  for (let i = 0; i < 3; i++) {
    const t = parseInt(m[i + 1], 10);
    if (t !== mine[i]) return t > mine[i];
  }
  return false;
}

function findPython() {
  const candidates = process.platform === 'win32'
    ? ['python3', 'python', 'py -3', 'py']
    : ['python3', 'python'];

  for (const cmd of candidates) {
    try {
      const parts = cmd.split(' ');
      const bin = parts[0];
      const testArgs = parts.slice(1).concat(['-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)']);
      const res = spawnSync(bin, testArgs, { stdio: 'ignore' });
      if (res.status === 0) {
        return { bin, extraArgs: parts.slice(1) };
      }
    } catch {
      // Continue to next candidate
    }
  }
  return null;
}

function getUpdateCachePath() {
  const dir = path.join(os.homedir(), '.sfp');
  return path.join(dir, 'update_check.json');
}

function readUpdateCache() {
  try {
    const file = getUpdateCachePath();
    if (fs.existsSync(file)) {
      return JSON.parse(fs.readFileSync(file, 'utf-8'));
    }
  } catch {}
  return { lastChecked: 0, hasUpdate: false };
}

function writeUpdateCache(data) {
  try {
    const file = getUpdateCachePath();
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(data, null, 2), 'utf-8');
  } catch {}
}

function fetchJson(url, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'sfp-cli',
        ...headers
      },
      timeout: 4000
    }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(fetchJson(res.headers.location, headers));
      }
      if (res.statusCode !== 200) {
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      let raw = '';
      res.on('data', chunk => { raw += chunk; });
      res.on('end', () => {
        try {
          resolve(JSON.parse(raw));
        } catch (e) {
          reject(e);
        }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('timeout'));
    });
  });
}

function isSemverNewer(remote, local) {
  if (!remote || !local) return false;
  const parse = v => (String(v).replace(/^v/, '').split('.').map(x => parseInt(x, 10) || 0));
  const r = parse(remote);
  const l = parse(local);
  for (let i = 0; i < 3; i++) {
    const rv = r[i] || 0;
    const lv = l[i] || 0;
    if (rv > lv) return true;
    if (rv < lv) return false;
  }
  return false;
}

async function checkRemoteUpdate(rootDir) {
  let remoteCommit = '';
  let localCommit = '';
  let remoteVersion = '';
  let localVersion = '';
  let hasUpdate = false;

  // 1. Check local commit / version
  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(PKG_DIR, 'package.json'), 'utf-8'));
    localVersion = pkg.version || '';
  } catch {}

  if (fs.existsSync(path.join(rootDir, '.git'))) {
    const rev = spawnSync('git', ['-C', rootDir, 'rev-parse', 'HEAD'], { encoding: 'utf-8' });
    if (rev.status === 0 && rev.stdout) {
      localCommit = rev.stdout.trim();
    }
  }

  // 2. Check GitHub remote commit
  try {
    const commitData = await fetchJson(GITHUB_API_COMMITS);
    if (commitData && commitData.sha) {
      remoteCommit = commitData.sha;
      if (localCommit && !remoteCommit.startsWith(localCommit) && !localCommit.startsWith(remoteCommit)) {
        hasUpdate = true;
      }
    }
  } catch {}

  // 3. Check npm registry version
  try {
    const npmData = await fetchJson(NPM_REGISTRY_LATEST);
    if (npmData && npmData.version) {
      remoteVersion = npmData.version;
      if (localVersion && isSemverNewer(remoteVersion, localVersion)) {
        hasUpdate = true;
      }
    }
  } catch {}

  const cache = {
    lastChecked: Date.now(),
    hasUpdate,
    remoteCommit: remoteCommit.slice(0, 7),
    localCommit: localCommit.slice(0, 7),
    remoteVersion,
    localVersion
  };

  writeUpdateCache(cache);
  return cache;
}

function spawnBackgroundUpdateCheck(rootDir) {
  try {
    const child = spawn(process.execPath, [__filename, '__bg_check_update', rootDir], {
      detached: true,
      stdio: 'ignore'
    });
    child.unref();
  } catch {}
}

function printUpdateNotice(info) {
  const localRef = info.localVersion || (info.localCommit ? info.localCommit.slice(0, 7) : 'installed');
  const remoteRef = info.remoteVersion || (info.remoteCommit ? info.remoteCommit.slice(0, 7) : 'latest');
  const line1 = `  Update available! SFP repository has updates: ${localRef} -> ${remoteRef}  `;
  const line2 = `  Run 'sfp update' or 'npx sfp-hive update' to automatically update.  `;
  const len = Math.max(line1.length, line2.length);
  const border = '─'.repeat(len);
  const pad1 = ' '.repeat(len - line1.length);
  const pad2 = ' '.repeat(len - line2.length);

  console.error('\n\x1b[33m┌' + border + '┐\x1b[0m');
  console.error('\x1b[33m│\x1b[0m\x1b[1m\x1b[32m' + line1 + pad1 + '\x1b[0m\x1b[33m│\x1b[0m');
  console.error('\x1b[33m│\x1b[0m\x1b[36m' + line2 + pad2 + '\x1b[0m\x1b[33m│\x1b[0m');
  console.error('\x1b[33m└' + border + '┘\x1b[0m\n');
}

function handleUpdate(rootDir, py, args) {
  console.error('\x1b[1m\x1b[36m=== SFP Updater ===\x1b[0m\n');
  const git = (...a) => spawnSync('git', ['-C', rootDir, '-c', 'core.longpaths=true', ...a], { encoding: 'utf-8' });

  // 1. Pull latest repository changes
  if (fs.existsSync(path.join(rootDir, '.git'))) {
    console.error('\x1b[36m[1/3] Pulling latest repository updates from GitHub...\x1b[0m');
    const status = git('status', '--porcelain').stdout.trim();
    if (status) {
      console.error('\x1b[33m  Note: Working directory has local modifications; skipping git checkout to preserve local edits.\x1b[0m');
    } else {
      console.error('  Fetching release tags...');
      git('fetch', '--tags', 'origin');
      const latestTag = getLatestReleaseTag(rootDir);
      if (latestTag) {
        const curr = git('describe', '--tags', '--exact-match');
        const currTag = (curr.stdout || '').trim();
        if (currTag === latestTag) {
          console.error(`  \x1b[32m✔ Already on latest release tag ${latestTag}.\x1b[0m`);
        } else if (!isNewerRelease(latestTag, rootDir)) {
          console.error(`  \x1b[32m✔ This copy is already newer than the latest release tag ${latestTag}; staying on it.\x1b[0m`);
        } else {
          console.error(`  Checking out latest release tag ${latestTag}...`);
          const co = git('checkout', latestTag);
          if (co.status === 0) {
            console.error(`  \x1b[32m✔ Checked out latest release tag ${latestTag}.\x1b[0m`);
          } else {
            console.error('  \x1b[33mWarning: git checkout failed:\x1b[0m', (co.stderr || co.stdout).trim());
          }
        }
      } else {
        console.error('  No release tags found matching vX.Y.Z.');
      }
    }
  } else {
    console.error('\x1b[36m[1/3] SFP directory is not a git repository; skipping git pull.\x1b[0m');
  }

  // 2. Refresh installed skills in detected IDEs
  console.error('\n\x1b[36m[2/3] Refreshing installed skills into detected IDEs and tools...\x1b[0m');
  const installScript = path.join(rootDir, 'scripts', 'install.py');
  const passArgs = args.filter(a => a !== 'update');
  const installRes = spawnSync(py.bin, [...py.extraArgs, installScript, 'install', ...passArgs], {
    cwd: rootDir,
    stdio: 'inherit',
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      PYTHONPATH: [path.join(rootDir, 'mcp'), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter)
    }
  });

  // 3. Check npm package status
  console.error('\n\x1b[36m[3/3] Checking npm CLI package status...\x1b[0m');
  try {
    const npmOutdated = spawnSync('npm', ['outdated', '-g', 'sfp-hive', '--json'], { encoding: 'utf-8' });
    if (npmOutdated.stdout && npmOutdated.stdout.includes('sfp-hive')) {
      console.error('\x1b[33m  Notice: A newer sfp-hive npm package is available!\x1b[0m');
      console.error('  Run: \x1b[32mnpm install -g sfp-hive\x1b[0m to update the global binary.\n');
    } else {
      console.error('  \x1b[32m✔ npm CLI package is up to date.\x1b[0m');
    }
  } catch {}

  // Reset update check cache
  writeUpdateCache({
    lastChecked: Date.now(),
    hasUpdate: false,
    remoteCommit: '',
    localCommit: ''
  });

  console.error('\n\x1b[1m\x1b[32m✔ SFP is fully up to date!\x1b[0m\n');
  process.exit(installRes.status ?? 0);
}

function resolveSfpRoot() {
  // 1. If running inside a full SFP repository checkout, use it directly
  if (fs.existsSync(path.join(PKG_DIR, 'catalog.json')) && fs.existsSync(path.join(PKG_DIR, 'mcp', 'sfp_hive.py'))) {
    return PKG_DIR;
  }

  // 2. Check ~/.sfp/root pointer written by install.py
  const rootPointer = path.join(os.homedir(), '.sfp', 'root');
  if (fs.existsSync(rootPointer)) {
    try {
      const pointed = fs.readFileSync(rootPointer, 'utf-8').trim();
      if (pointed && fs.existsSync(path.join(pointed, 'catalog.json'))) {
        return pointed;
      }
    } catch {}
  }

  // 3. Otherwise use ~/.sfp/SFP (or $SFP_ROOT / $SFP_DIR)
  const defaultDir = path.join(os.homedir(), '.sfp', 'SFP');
  const targetDir = process.env.SFP_ROOT || process.env.SFP_DIR || defaultDir;

  if (!fs.existsSync(path.join(targetDir, '.git'))) {
    console.error(`\x1b[36mSetting up SFP in ${targetDir}...\x1b[0m`);
    fs.mkdirSync(path.dirname(targetDir), { recursive: true });
    // Clone main branch with automatic fallback
    let cloneRes = spawnSync('git', ['clone', '--depth', '1', '--branch', 'main', '--config', 'advice.detachedHead=false', '--config', 'core.longpaths=true', REPO_URL, targetDir], {
      stdio: ['ignore', 2, 2]
    });
    if (cloneRes.status !== 0) {
      cloneRes = spawnSync('git', ['clone', '--depth', '1', '--config', 'advice.detachedHead=false', '--config', 'core.longpaths=true', REPO_URL, targetDir], {
        stdio: ['ignore', 2, 2]
      });
    }
    if (cloneRes.status !== 0) {
      console.error(`\x1b[31mError: Failed to clone SFP repository from ${REPO_URL}.\x1b[0m`);
      console.error('Please ensure git is installed and network access is available.');
      process.exit(1);
    }
    console.error(`\x1b[32m✔ SFP setup complete in ${targetDir}.\x1b[0m`);
  } else if (process.env.SFP_AUTO_UPDATE === '1' || process.env.SFP_AUTO_UPDATE === 'true') {
    // Automatic update on launch when opt-in SFP_AUTO_UPDATE is enabled: move to latest release tag (never pull main)
    const git = (...a) => spawnSync('git', ['-C', targetDir, '-c', 'core.longpaths=true', ...a], { encoding: 'utf-8' });
    if (!git('status', '--porcelain').stdout.trim()) {
      git('fetch', '--tags', 'origin');
      const latestTag = getLatestReleaseTag(targetDir);
      if (latestTag && isNewerRelease(latestTag, targetDir)) {
        git('checkout', latestTag);
      }
    }
  }

  return targetDir;
}

function showHelp(skillCount) {
  const countStr = skillCount ? `${skillCount} skills` : '894 skills';
  console.log(`
\x1b[1m\x1b[36mSFP (Skills for Productivity)\x1b[0m — ${countStr}, one intelligent hive.
Give your AI coding agent the right skills for the job, not all of them.

\x1b[1mUSAGE:\x1b[0m
  \x1b[32mnpx sfp-hive\x1b[0m <command> [options]
  \x1b[32msfp\x1b[0m <command> [options]

\x1b[1mCOMMANDS:\x1b[0m
  \x1b[33minstall\x1b[0m [options]     Install skills into detected IDEs (Antigravity, Claude, Cursor, VS Code, etc.)
  \x1b[33mupdate\x1b[0m [options]      Pull latest repository updates and refresh skills in IDEs
  \x1b[33mmcp\x1b[0m [options]         Run the SFP MCP server on stdio (or register with --tools <ide>)
  \x1b[33mrules\x1b[0m [options]       Add standing instructions to use SFP skills on substantial tasks
  \x1b[33mselect\x1b[0m "<task>"      Ask the hive which skills to load for a task
  \x1b[33mneeds\x1b[0m "<task>"       Check what capabilities or external tools a task needs
  \x1b[33mdoctor\x1b[0m              Check catalog, index, local models, and hive connections
  \x1b[33mroute\x1b[0m [args]          Manage or start the local model router (Ollama, LM Studio, etc.)
  \x1b[33mmodels\x1b[0m [probe|add|remove] The models the hive asks: local ones found, plus any you add by API
  \x1b[33mtaste\x1b[0m [--reset]        Learned facet preferences (output forms, delivery style, depth)
  \x1b[33mmentor\x1b[0m [profile|grow]  What you lean towards, and new skills grown from research for it
  \x1b[33mresearch\x1b[0m [args]       Draft, refresh, approve or reject skills written from research papers
  \x1b[33mapps\x1b[0m [args]           Manage companion apps (OmniRoute, Strix, etc.)
  \x1b[33mlist\x1b[0m                List categories and install profiles
  \x1b[33mhelp\x1b[0m                Show this help message

\x1b[1mEXAMPLES:\x1b[0m
  $ \x1b[32mnpx sfp-hive install\x1b[0m                      # Install starter set into every IDE found
  $ \x1b[32mnpx sfp-hive update\x1b[0m                       # Automatically pull latest repo updates & skills
  $ \x1b[32mnpx sfp-hive install --profile backend-dev\x1b[0m # Install backend-focused skills
  $ \x1b[32mnpx sfp-hive mcp --tools antigravity,cursor\x1b[0m # Register MCP server in IDEs
  $ \x1b[32mnpx sfp-hive select "write unit tests"\x1b[0m     # See which skills the hive recommends
  $ \x1b[32mnpx sfp-hive doctor\x1b[0m                        # Verify health of catalog, index, and models

\x1b[1mUSE IN MCP CLIENTS (mcp.json):\x1b[0m
  {
    "mcpServers": {
      "sfp": {
        "command": "npx",
        "args": ["-y", "sfp-hive", "mcp"]
      }
    }
  }

Docs & Source: \x1b[4mhttps://github.com/siddu1004/SFP\x1b[0m
`);
}

function run() {
  // Internal background worker for async update check
  if (process.argv[2] === '__bg_check_update') {
    const rootDir = process.argv[3] || PKG_DIR;
    checkRemoteUpdate(rootDir).then(() => process.exit(0)).catch(() => process.exit(0));
    return;
  }

  const py = findPython();
  if (!py) {
    console.error('\x1b[31mError: Python 3.8+ is required to run SFP.\x1b[0m');
    console.error('Please install Python 3 from https://www.python.org/downloads/ and ensure it is on your PATH.');
    process.exit(1);
  }

  const args = process.argv.slice(2);
  const command = args[0];

  const rootDir = resolveSfpRoot();

  // Read skill count from catalog for dynamic help display
  let skillCount = null;
  try {
    const catPath = path.join(rootDir, 'catalog.json');
    if (fs.existsSync(catPath)) {
      const cat = JSON.parse(fs.readFileSync(catPath, 'utf-8'));
      if (cat.skills) {
        skillCount = Object.keys(cat.skills).length;
      }
    }
  } catch {}

  if (!command || command === 'help' || command === '--help' || command === '-h') {
    showHelp(skillCount);
    process.exit(0);
  }

  // Handle explicit update command
  if (command === 'update') {
    handleUpdate(rootDir, py, args);
    return;
  }

  // Background update check & notification
  const cache = readUpdateCache();
  if (Date.now() - (cache.lastChecked || 0) > UPDATE_CHECK_INTERVAL_MS) {
    spawnBackgroundUpdateCheck(rootDir);
  } else if (cache.hasUpdate) {
    // Print notification to stderr (never interferes with MCP stdio stream)
    printUpdateNotice(cache);
  }

  let targetScript = null;
  let targetArgs = [];

  switch (command) {
    case 'mcp':
      if (args.slice(1).some((a) => a === '--tools' || a === '--project' || a === '--remove' || a.startsWith('--tools='))) {
        targetScript = path.join(rootDir, 'scripts', 'install.py');
        targetArgs = ['mcp', ...args.slice(1)];
      } else {
        targetScript = path.join(rootDir, 'mcp', 'sfp_mcp.py');
        targetArgs = args.slice(1);
      }
      break;

    case 'select':
    case 'live':
    case 'track':
    case 'feedback':
    case 'clusters':
    case 'library':
    case 'bundles':
      targetScript = path.join(rootDir, 'mcp', 'sfp_hive.py');
      targetArgs = args;
      break;

    case 'needs':
      targetScript = path.join(rootDir, 'mcp', 'sfp_hive.py');
      targetArgs = ['needs', ...args.slice(1)];
      break;

    case 'doctor':
      targetScript = path.join(rootDir, 'mcp', 'sfp_hive.py');
      targetArgs = ['doctor', ...args.slice(1)];
      break;

    case 'route':
      targetScript = path.join(rootDir, 'mcp', 'sfp_route.py');
      targetArgs = args.slice(1);
      break;

    case 'models':
      targetScript = path.join(rootDir, 'mcp', 'sfp_intent.py');
      targetArgs = args.length > 1 ? args.slice(1) : ['models'];
      break;

    case 'taste':
      targetScript = path.join(rootDir, 'mcp', 'sfp_hive.py');
      targetArgs = ['taste', ...args.slice(1)];
      break;
    case 'mentor':
      targetScript = path.join(rootDir, 'mcp', 'sfp_mentor.py');
      targetArgs = args.length > 1 ? args.slice(1) : ['profile'];
      break;

    case 'research':
      targetScript = path.join(rootDir, 'mcp', 'sfp_research.py');
      targetArgs = args.slice(1);
      break;

    case 'install':
    case 'list':
    case 'uninstall':
    case 'rules':
    case 'apps':
      targetScript = path.join(rootDir, 'scripts', 'install.py');
      targetArgs = [command, ...args.slice(1)];
      break;

    default:
      if (command.startsWith('-')) {
        targetScript = path.join(rootDir, 'scripts', 'install.py');
        targetArgs = ['install', ...args];
      } else {
        console.error(`\x1b[31mUnknown command:\x1b[0m ${command}\n`);
        showHelp(skillCount);
        process.exit(1);
      }
      break;
  }

  const env = {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
    PYTHONPATH: [path.join(rootDir, 'mcp'), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter)
  };

  const finalArgs = [...py.extraArgs, targetScript, ...targetArgs];
  const child = spawn(py.bin, finalArgs, {
    cwd: rootDir,
    stdio: 'inherit',
    env
  });

  child.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
    } else {
      process.exit(code ?? 0);
    }
  });

  child.on('error', (err) => {
    console.error(`\x1b[31mFailed to start process:\x1b[0m ${err.message}`);
    process.exit(1);
  });
}

run();
