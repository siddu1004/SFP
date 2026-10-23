const http = require('http');
const fs = require('fs');
const path = require('path');
const { HiveBridge } = require('./src/hiveBridge');

const PORT = 4321;
const sfpRoot = path.resolve(__dirname, '..');
const bridge = new HiveBridge(sfpRoot);

let previousSkills = new Set();
let currentPrompt = '';
let currentRes = null;
let userExcluded = new Set();

const server = http.createServer(async (req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const url = req.url.split('?')[0];

  // Static Assets
  if (url === '/style.css') {
    const css = fs.readFileSync(path.join(__dirname, 'media', 'style.css'), 'utf-8');
    res.writeHead(200, { 'Content-Type': 'text/css' });
    res.end(css);
    return;
  }

  if (url === '/main.js') {
    const js = fs.readFileSync(path.join(__dirname, 'media', 'main.js'), 'utf-8');
    res.writeHead(200, { 'Content-Type': 'application/javascript' });
    res.end(js);
    return;
  }

  if (url === '/icon.svg') {
    const svg = fs.readFileSync(path.join(__dirname, 'media', 'icon.svg'), 'utf-8');
    res.writeHead(200, { 'Content-Type': 'image/svg+xml' });
    res.end(svg);
    return;
  }

  // API Endpoints
  if (req.method === 'POST' && url === '/api/select') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      try {
        const { prompt } = JSON.parse(body || '{}');
        currentPrompt = (prompt || '').trim();

        if (!currentPrompt) {
          previousSkills.clear();
          currentRes = null;
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ res: null, diff: { added: [], removed: [] }, excluded: Array.from(userExcluded), initialPrompt: '' }));
          return;
        }

        const hiveRes = await bridge.selectSkills(currentPrompt, sfpRoot);
        const currentNames = new Set((hiveRes.stack || []).map(s => s.name));
        const added = [...currentNames].filter(x => !previousSkills.has(x));
        const removed = [...previousSkills].filter(x => !currentNames.has(x));

        previousSkills = currentNames;
        currentRes = hiveRes;

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          res: currentRes,
          diff: { added, removed },
          excluded: Array.from(userExcluded),
          initialPrompt: currentPrompt
        }));
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  if (req.method === 'POST' && url === '/api/feedback') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      try {
        const { decisionId, skill, verdict } = JSON.parse(body || '{}');
        const feedbackPayload = {
          helped: verdict === 'helped' ? [skill] : [],
          unhelpful: verdict === 'unhelpful' ? [skill] : []
        };
        await bridge.giveFeedback(decisionId || 'last', feedbackPayload);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true }));
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  if (req.method === 'POST' && url === '/api/train') {
    try {
      const trainRes = await bridge.train();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(trainRes));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // Main HTML Shell
  if (url === '/' || url === '/index.html') {
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SFP Hive Live Skill Monitor</title>
  <link rel="stylesheet" href="/style.css">
  <style>
    body {
      max-width: 420px;
      margin: 0 auto;
      border-left: 1px solid var(--border);
      border-right: 1px solid var(--border);
      min-height: 100vh;
      box-shadow: 0 0 30px rgba(0,0,0,0.5);
    }
  </style>
  <script>
    // Browser Mock for acquireVsCodeApi
    window.acquireVsCodeApi = function() {
      return {
        postMessage: async function(msg) {
          if (msg.command === 'ready') {
            window.postMessage({
              command: 'updateState',
              payload: { res: null, diff: null, excluded: [], initialPrompt: '' }
            }, '*');
          } else if (msg.command === 'promptChanged') {
            try {
              const data = await fetch('/api/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: msg.text })
              }).then(r => r.json());
              window.postMessage({ command: 'updateState', payload: data }, '*');
            } catch (e) {
              console.error('Select failed:', e);
            }
          } else if (msg.command === 'feedback') {
            await fetch('/api/feedback', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(msg)
            });
            console.log('Feedback recorded for:', msg.skill, msg.verdict);
          } else if (msg.command === 'copyStack') {
            navigator.clipboard.writeText('Skills: ' + (msg.skills || []).join(', '));
            alert('Copied ' + (msg.skills ? msg.skills.length : 0) + ' skills to clipboard!');
          } else if (msg.command === 'train') {
            await fetch('/api/train', { method: 'POST' });
            window.postMessage({ command: 'trainingFinished' }, '*');
            alert('SFP Hive model trained successfully!');
          } else if (msg.command === 'openSkillFile') {
            console.log('Opening skill file:', msg.path);
          }
        }
      };
    };
  </script>
</head>
<body>
  <div class="header">
    <div class="brand">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2l8 4.5v9L12 20l-8-4.5v-9L12 2z"></path>
        <path d="M12 12l8-4.5"></path>
        <path d="M12 12v8"></path>
        <path d="M12 12L4 7.5"></path>
      </svg>
      <span>SFP Hive Monitor</span>
    </div>
    <div class="status-indicator">
      <div class="dot"></div>
      <span id="hiveStatusText">Live Hive</span>
    </div>
  </div>

  <div class="project-bar" id="projectTags"></div>

  <div class="prompt-box">
    <label for="promptInput">Prompt Skill Detector</label>
    <textarea id="promptInput" placeholder="Type prompt here... (e.g., 'build react checkout with Stripe and test it')"></textarea>
  </div>

  <div class="diff-container" id="diffContainer">
    <div class="diff-title">Prompt Skill Delta</div>
    <div class="diff-chips" id="diffChips"></div>
  </div>

  <div class="budget-bar">
    <div class="budget-info">
      <span>Context Budget</span>
      <span id="tokenCount">0 / 12,000 tokens</span>
    </div>
    <div class="budget-track">
      <div class="budget-fill" id="tokenFill"></div>
    </div>
  </div>

  <div id="emptyState" class="empty-state">
    <p>Type a task prompt above to see real-time skill detection, layer stacking, and dynamic prompt deltas.</p>
  </div>

  <div class="layer-section">
    <div class="layer-header">
      <div class="layer-title base">
        <span>⚡ Base Layer (Grounding)</span>
      </div>
      <span class="layer-count" id="baseCount">0</span>
    </div>
    <div id="baseSkills"></div>
  </div>

  <div class="layer-section">
    <div class="layer-header">
      <div class="layer-title check">
        <span>🛡️ Check Layer (Safety & Standards)</span>
      </div>
      <span class="layer-count" id="checkCount">0</span>
    </div>
    <div id="checkSkills"></div>
  </div>

  <div class="layer-section">
    <div class="layer-header">
      <div class="layer-title finish">
        <span>✨ Finish Layer (Review & Polish)</span>
      </div>
      <span class="layer-count" id="finishCount">0</span>
    </div>
    <div id="finishSkills"></div>
  </div>

  <div class="action-bar">
    <button id="copyStackBtn" class="btn-primary" title="Copy active skill names">📋 Copy Stack</button>
    <button id="trainBtn" class="btn-secondary" title="Retrain hive model from feedback">⚡ Train Model</button>
  </div>

  <script src="/main.js"></script>
</body>
</html>`;

    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(html);
    return;
  }

  res.writeHead(404);
  res.end('Not Found');
});

server.listen(PORT, () => {
  console.log(`SFP Hive Live Monitor preview server running at http://localhost:${PORT}`);
});
