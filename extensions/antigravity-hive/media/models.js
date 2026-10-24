// SFP Hive Models / Router View Script
(function () {
  const vscode = acquireVsCodeApi();

  let state = {
    running: false,
    port: 8787,
    baseUrl: 'http://127.0.0.1:8787/v1',
    config: null,
    status: null,
    preview: '',
    policy: 'local-first',
    planOutput: '',
    testOutput: null,
  };

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // DOM Elements
  const statusDot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');
  const toggleRouterBtn = document.getElementById('toggle-router-btn');
  const serverCard = document.getElementById('server-card');
  const serverUrl = document.getElementById('server-url');
  const copyUrlBtn = document.getElementById('copy-url-btn');

  const providersContainer = document.getElementById('providers-container');
  const policySelect = document.getElementById('policy-select');
  const setupBtn = document.getElementById('setup-btn');
  const writeBtn = document.getElementById('write-btn');
  const previewBox = document.getElementById('preview-box');

  const statusSection = document.getElementById('status-section');
  const statusContainer = document.getElementById('status-container');

  const tryPromptInput = document.getElementById('try-prompt-input');
  const tryPlanBtn = document.getElementById('try-plan-btn');
  const trySendBtn = document.getElementById('try-send-btn');
  const tryOutput = document.getElementById('try-output');

  function renderServerState() {
    if (statusDot) {
      statusDot.classList.toggle('running', state.running);
    }
    if (statusText) {
      statusText.textContent = state.running ? 'Running' : 'Stopped';
    }
    if (toggleRouterBtn) {
      toggleRouterBtn.textContent = state.running ? 'Stop' : 'Start router';
      toggleRouterBtn.classList.toggle('btn-stop', state.running);
    }
    if (serverCard) {
      serverCard.classList.toggle('hidden', !state.running);
    }
    if (serverUrl) {
      serverUrl.textContent = state.baseUrl;
    }
    if (statusSection) {
      statusSection.classList.toggle('hidden', !state.running);
    }
  }

  function renderProviders() {
    if (!providersContainer) return;
    const cfg = state.config;
    if (!cfg || !cfg.providers || !cfg.providers.length) {
      providersContainer.innerHTML = `
        <div class="server-hint" id="no-providers-hint">
          No models configured yet. Run <strong>Set up</strong> below to discover local servers (Ollama, LM Studio) or detected cloud keys.
        </div>`;
      return;
    }

    providersContainer.innerHTML = cfg.providers
      .map((p) => {
        const isLocal = p.kind === 'local';
        const keyInfo = p.api_key_env ? `<span class="cloud-key-env">${escapeHtml(p.api_key_env)}</span>` : '';
        const modelsHtml = (p.models || [])
          .map((m) => {
            return `
              <div class="model-row">
                <span class="model-id" title="${escapeHtml(m.id)}">${escapeHtml(m.id)}</span>
                <span class="strength-chip" data-action="cycleStrength" data-provider="${escapeHtml(p.id)}" data-model="${escapeHtml(m.id)}" data-strength="${m.strength || 2}" title="Strength (1-3): Click to cycle">
                  Strength: ${m.strength || 2}
                </span>
              </div>`;
          })
          .join('');

        return `
          <div class="provider-item" data-provider-id="${escapeHtml(p.id)}">
            <div class="provider-header">
              <span class="provider-name">${escapeHtml(p.name || p.id)}</span>
              <span class="provider-kind">${escapeHtml(p.kind || 'local')}</span>
            </div>
            ${keyInfo ? `<div>${keyInfo}</div>` : ''}
            <div class="provider-models">${modelsHtml}</div>
          </div>`;
      })
      .join('');
  }

  function renderStatus() {
    if (!statusContainer) return;
    const s = state.status;
    if (!s || !s.models || !s.models.length) {
      statusContainer.innerHTML = `<div class="server-hint">Waiting for router status...</div>`;
      return;
    }

    statusContainer.innerHTML = s.models
      .map((m) => {
        const isReady = m.state === 'ready';
        const isCooling = m.state && m.state.startsWith('cooling');
        const badgeClass = isReady ? 'ready' : isCooling ? 'cooling' : 'nokey';
        const warning = m.failed >= 2;
        const cardClass = warning ? 'status-card warning-card' : 'status-card';
        const lastMark = m.ok > 0 ? `<span class="last-used-mark" title="Used successfully">✓ active</span>` : '';
        const warningBadge = warning ? `<span style="color:var(--error-fg);font-weight:700;">⚠ Failed ${m.failed}x</span>` : '';

        return `
          <div class="${cardClass}">
            <div class="status-row-header">
              <span class="status-model-name">${escapeHtml(m.model)}</span>
              <span class="status-badge ${badgeClass}">${escapeHtml(m.state)}</span>
            </div>
            <div class="status-meta">
              <span>ok: ${m.ok}</span>
              <span>fail: ${m.failed}</span>
              <span>strength: ${m.strength}</span>
              ${lastMark}
              ${warningBadge}
            </div>
            ${m.last_error ? `<div class="server-hint" style="color:var(--error-fg);font-size:10px;">${escapeHtml(m.last_error)}</div>` : ''}
          </div>`;
      })
      .join('');
  }

  function renderPreview() {
    if (!previewBox) return;
    if (state.preview) {
      previewBox.classList.remove('hidden');
      previewBox.textContent = state.preview;
    } else {
      previewBox.classList.add('hidden');
      previewBox.textContent = '';
    }
  }

  function renderTryOutput() {
    if (!tryOutput) return;
    if (state.planOutput) {
      tryOutput.classList.remove('hidden');
      tryOutput.innerHTML = `<strong>Plan:</strong>\n${escapeHtml(state.planOutput)}`;
    } else if (state.testOutput) {
      tryOutput.classList.remove('hidden');
      const badge = state.testOutput.model ? `<div class="try-model-badge">Model: ${escapeHtml(state.testOutput.model)}</div>` : '';
      tryOutput.innerHTML = `${badge}\n${escapeHtml(state.testOutput.answer || '')}`;
    } else {
      tryOutput.classList.add('hidden');
      tryOutput.innerHTML = '';
    }
  }

  function renderAll() {
    renderServerState();
    renderProviders();
    renderStatus();
    renderPreview();
    renderTryOutput();
  }

  // Event Listeners
  if (toggleRouterBtn) {
    toggleRouterBtn.addEventListener('click', () => {
      vscode.postMessage({ command: 'toggleRouter' });
    });
  }

  if (copyUrlBtn) {
    copyUrlBtn.addEventListener('click', () => {
      vscode.postMessage({ command: 'copyUrl', url: state.baseUrl });
    });
  }

  if (policySelect) {
    policySelect.addEventListener('change', () => {
      state.policy = policySelect.value;
      vscode.postMessage({ command: 'changePolicy', policy: state.policy });
    });
  }

  if (setupBtn) {
    setupBtn.addEventListener('click', () => {
      vscode.postMessage({ command: 'setup', policy: state.policy, yes: false });
    });
  }

  if (writeBtn) {
    writeBtn.addEventListener('click', () => {
      vscode.postMessage({ command: 'setup', policy: state.policy, yes: true });
    });
  }

  if (tryPlanBtn) {
    tryPlanBtn.addEventListener('click', () => {
      const task = tryPromptInput ? tryPromptInput.value.trim() : '';
      if (task) {
        state.testOutput = null;
        vscode.postMessage({ command: 'plan', task });
      }
    });
  }

  if (trySendBtn) {
    trySendBtn.addEventListener('click', () => {
      const prompt = tryPromptInput ? tryPromptInput.value.trim() : '';
      if (prompt) {
        state.planOutput = '';
        vscode.postMessage({ command: 'testRequest', prompt });
      }
    });
  }

  // Delegated clicks for strength chips
  document.addEventListener('click', (e) => {
    const target = e.target.closest('[data-action="cycleStrength"]');
    if (target) {
      const providerId = target.getAttribute('data-provider');
      const modelId = target.getAttribute('data-model');
      let cur = parseInt(target.getAttribute('data-strength') || '2', 10);
      const nextStrength = cur >= 3 ? 1 : cur + 1;
      target.setAttribute('data-strength', String(nextStrength));
      target.textContent = `Strength: ${nextStrength}`;
      vscode.postMessage({
        command: 'updateStrength',
        providerId,
        modelId,
        strength: nextStrength,
      });
    }
  });

  // Incoming Messages
  window.addEventListener('message', (event) => {
    const msg = event.data;
    switch (msg.type) {
      case 'state':
      case 'updateState': {
        if (msg.payload) {
          if (typeof msg.payload.running === 'boolean') state.running = msg.payload.running;
          if (msg.payload.port) state.port = msg.payload.port;
          if (msg.payload.baseUrl) state.baseUrl = msg.payload.baseUrl;
          if (msg.payload.config) state.config = msg.payload.config;
          if (msg.payload.status) state.status = msg.payload.status;
          if (msg.payload.policy) {
            state.policy = msg.payload.policy;
            if (policySelect) policySelect.value = state.policy;
          }
          if (msg.payload.preview !== undefined) state.preview = msg.payload.preview;
          renderAll();
        }
        break;
      }
      case 'healthUpdate': {
        if (msg.status) {
          state.status = msg.status;
          renderStatus();
        }
        break;
      }
      case 'setupPreview': {
        state.preview = msg.preview || '';
        renderPreview();
        break;
      }
      case 'planResult': {
        state.testOutput = null;
        state.planOutput = msg.output || '';
        renderTryOutput();
        break;
      }
      case 'testResult': {
        state.planOutput = '';
        state.testOutput = msg.result || null;
        renderTryOutput();
        break;
      }
    }
  });

  // Ready handshake
  vscode.postMessage({ command: 'ready' });
})();
