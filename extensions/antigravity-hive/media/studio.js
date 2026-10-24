// SFP Hive Studio Frontend Script
(function () {
  const vscode = acquireVsCodeApi();

  // State
  let currentTab = 'now';
  let state = {
    phase: null,
    confidence: 0,
    skills: [],
    loading: false,
    error: null,
  };

  // Cache DOM elements
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  function setTab(tabId) {
    currentTab = tabId;
    tabButtons.forEach((btn) => {
      const match = btn.getAttribute('data-tab') === tabId;
      btn.classList.toggle('active', match);
      btn.setAttribute('aria-selected', match ? 'true' : 'false');
    });

    tabContents.forEach((content) => {
      const match = content.id === `tab-${tabId}`;
      content.classList.toggle('active', match);
    });

    vscode.setState({ currentTab });
  }

  // Keyboard navigation for tab bar
  const tabBar = document.querySelector('.tab-bar');
  if (tabBar) {
    tabBar.addEventListener('keydown', (e) => {
      const tabs = Array.from(tabButtons);
      const idx = tabs.findIndex((t) => t.getAttribute('data-tab') === currentTab);
      if (e.key === 'ArrowRight') {
        const next = tabs[(idx + 1) % tabs.length];
        next.focus();
        setTab(next.getAttribute('data-tab'));
      } else if (e.key === 'ArrowLeft') {
        const prev = tabs[(idx - 1 + tabs.length) % tabs.length];
        prev.focus();
        setTab(prev.getAttribute('data-tab'));
      }
    });
  }

  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      setTab(btn.getAttribute('data-tab'));
    });
  });

  // Action dispatches
  document.addEventListener('click', (e) => {
    const target = e.target.closest('[data-action]');
    if (!target) return;
    const action = target.getAttribute('data-action');
    const skill = target.getAttribute('data-skill');
    const decision = target.getAttribute('data-decision');

    switch (action) {
      case 'choose': {
        const input = document.getElementById('choose-task-input');
        const text = input ? input.value.trim() : '';
        if (text) {
          vscode.postMessage({ command: 'choose', task: text });
        }
        break;
      }
      case 'helped':
      case 'unhelpful':
      case 'ignored': {
        if (skill) {
          vscode.postMessage({ command: 'feedback', verdict: action, skill, decision });
        }
        break;
      }
      case 'openSkill': {
        if (skill) {
          vscode.postMessage({ command: 'openSkill', skill });
        }
        break;
      }
      case 'copyPrompt': {
        vscode.postMessage({ command: 'copyPrompt' });
        break;
      }
      case 'train': {
        vscode.postMessage({ command: 'train' });
        break;
      }
      case 'refresh': {
        vscode.postMessage({ command: 'refresh' });
        break;
      }
    }
  });

  // Handle messages from the extension host
  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg) return;

    switch (msg.type) {
      case 'switchTab': {
        if (msg.tab) setTab(msg.tab);
        break;
      }
      case 'updateState': {
        state = { ...state, ...msg.payload };
        renderState(state);
        break;
      }
    }
  });

  function renderState(s) {
    // Helper to render state updates
    const nowContent = document.getElementById('tab-now');
    if (!nowContent) return;
    // Renders can dynamically update contents or sections as needed
  }

  // Restore tab on load
  const prev = vscode.getState();
  if (prev && prev.currentTab) {
    setTab(prev.currentTab);
  }

  // Signal ready
  vscode.postMessage({ command: 'ready' });
})();
