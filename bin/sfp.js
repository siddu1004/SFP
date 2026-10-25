#!/usr/bin/env node

/**
 * SFP (Skills for Productivity) CLI & MCP Runner
 * Cross-platform entry point for npx / global npm install.
 */

const { spawn, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const PKG_DIR = path.resolve(__dirname, '..');

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

function resolveSfpRoot() {
  // 1. If running inside a full SFP repository checkout, use it directly
  if (fs.existsSync(path.join(PKG_DIR, 'catalog.json')) && fs.existsSync(path.join(PKG_DIR, 'mcp', 'sfp_hive.py'))) {
    return PKG_DIR;
  }

  // 2. Otherwise use ~/.sfp/SFP (or $SFP_DIR)
  const defaultDir = path.join(os.homedir(), '.sfp', 'SFP');
  const targetDir = process.env.SFP_DIR || defaultDir;

  if (!fs.existsSync(path.join(targetDir, '.git'))) {
    console.log(`\x1b[36mSetting up SFP in ${targetDir}...\x1b[0m`);
    fs.mkdirSync(path.dirname(targetDir), { recursive: true });
    const cloneRes = spawnSync('git', ['clone', '--depth', '1', 'https://github.com/siddu1004/SFP.git', targetDir], {
      stdio: 'inherit'
    });
    if (cloneRes.status !== 0) {
      console.error('\x1b[31mError: Failed to clone SFP repository. Please ensure git is installed.\x1b[0m');
      process.exit(1);
    }
  }

  return targetDir;
}

function showHelp() {
  console.log(`
\x1b[1m\x1b[36mSFP (Skills for Productivity)\x1b[0m — 819 skills, one intelligent hive.
Give your AI coding agent the right skills for the job, not all of them.

\x1b[1mUSAGE:\x1b[0m
  \x1b[32mnpx sfp-hive\x1b[0m <command> [options]
  \x1b[32msfp\x1b[0m <command> [options]

\x1b[1mCOMMANDS:\x1b[0m
  \x1b[33minstall\x1b[0m [options]     Install skills into detected IDEs (Claude Code, Cursor, Copilot, etc.)
  \x1b[33mmcp\x1b[0m                 Run the SFP MCP server on stdio (for Claude Desktop, Cursor, Cline)
  \x1b[33mselect\x1b[0m "<task>"      Ask the hive which skills to load for a task
  \x1b[33mneeds\x1b[0m "<task>"       Check what capabilities or external tools a task needs
  \x1b[33mdoctor\x1b[0m              Check catalog, index, local models, and hive connections
  \x1b[33mroute\x1b[0m [args]          Manage or start the local model router (Ollama, LM Studio, etc.)
  \x1b[33mlist\x1b[0m                List categories and install profiles
  \x1b[33mhelp\x1b[0m                Show this help message

\x1b[1mEXAMPLES:\x1b[0m
  $ \x1b[32mnpx sfp-hive install\x1b[0m                      # Install starter set into every IDE found
  $ \x1b[32mnpx sfp-hive install --profile backend-dev\x1b[0m # Install backend-focused skills
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
  const py = findPython();
  if (!py) {
    console.error('\x1b[31mError: Python 3.8+ is required to run SFP.\x1b[0m');
    console.error('Please install Python 3 from https://www.python.org/downloads/ and ensure it is on your PATH.');
    process.exit(1);
  }

  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === 'help' || command === '--help' || command === '-h') {
    showHelp();
    process.exit(0);
  }

  const rootDir = resolveSfpRoot();

  let targetScript = null;
  let targetArgs = [];

  switch (command) {
    case 'mcp':
      targetScript = path.join(rootDir, 'mcp', 'sfp_mcp.py');
      targetArgs = args.slice(1);
      break;

    case 'select':
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

    case 'install':
      targetScript = path.join(rootDir, 'scripts', 'install.py');
      targetArgs = ['install', ...args.slice(1)];
      break;

    case 'list':
      targetScript = path.join(rootDir, 'scripts', 'install.py');
      targetArgs = ['list', ...args.slice(1)];
      break;

    case 'uninstall':
      targetScript = path.join(rootDir, 'scripts', 'install.py');
      targetArgs = ['uninstall', ...args.slice(1)];
      break;

    default:
      // If it looks like an install flag (e.g. --profile, --tools), pass to install.py
      if (command.startsWith('-')) {
        targetScript = path.join(rootDir, 'scripts', 'install.py');
        targetArgs = ['install', ...args];
      } else {
        console.error(`\x1b[31mUnknown command:\x1b[0m ${command}\n`);
        showHelp();
        process.exit(1);
      }
      break;
  }

  const env = {
    ...process.env,
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
