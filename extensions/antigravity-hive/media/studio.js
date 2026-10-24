// SFP Hive Studio Frontend Script
(function () {
  const vscode = acquireVsCodeApi();

  // State
  let currentTab = 'now';
  let state = {
    track: null,
    selection: null,
    follow: true,
  };

  // Cache DOM elements
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

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
      case 'removeSkill': {
        if (skill) {
          vscode.postMessage({ command: 'removeSkill', skill });
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

  const followToggle = document.getElementById('follow-toggle');
  if (followToggle) {
    followToggle.addEventListener('change', (e) => {
      vscode.postMessage({ command: 'toggleFollow', value: e.target.checked });
    });
  }

  // Handle messages from the extension host
  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg) return;

    switch (msg.type) {
      case 'switchTab': {
        if (msg.tab) setTab(msg.tab);
        break;
      }
      case 'updateTrack': {
        state.track = msg.track;
        if (typeof msg.follow === 'boolean') {
          state.follow = msg.follow;
        }
        renderTrack(state.track, state.follow);
        break;
      }
      case 'updateState': {
        if (msg.payload) {
          state.selection = msg.payload;
          if (typeof msg.payload.follow === 'boolean') {
            state.follow = msg.payload.follow;
          }
          if (msg.payload.track) {
            state.track = msg.payload.track;
            renderTrack(state.track, state.follow);
          }
        }
        break;
      }
    }
  });

  function renderTrack(track, follow) {
    if (followToggle && typeof follow === 'boolean') {
      followToggle.checked = follow;
    }

    if (!track) return;

    // Phase and confidence
    const phaseName = document.getElementById('now-phase-name');
    const confBadge = document.getElementById('now-confidence-badge');
    const confFill = document.getElementById('now-confidence-fill');
    const phaseDetail = document.getElementById('now-phase-detail');

    const phase = track.phase ? track.phase[0].toUpperCase() + track.phase.slice(1) : 'Idle';
    const layer = track.layer ? ` (${track.layer} layer)` : '';
    const pct = Math.round((track.confidence || 0) * 100);

    if (phaseName) phaseName.textContent = `${phase}${layer}`;
    if (confBadge) confBadge.textContent = `${pct}% conf`;
    if (confFill) confFill.style.width = `${pct}%`;
    if (phaseDetail) {
      phaseDetail.textContent = track.phase
        ? `Estimated from workspace activity with Kalman filter`
        : `Watching workspace events`;
    }

    // Thin stacked bar of phase shares
    const sharesBar = document.getElementById('now-stacked-shares');
    if (sharesBar && track.shares) {
      const PHASE_LAYERS = {
        research: 'base', plan: 'base', design: 'base', build: 'base', debug: 'base',
        test: 'check', secure: 'check', review: 'check',
        optimize: 'finish', document: 'finish', ship: 'finish',
      };
      const entries = Object.entries(track.shares).filter(([_, s]) => s > 0.01);
      const total = entries.reduce((acc, [_, s]) => acc + s, 0) || 1;
      sharesBar.innerHTML = entries
        .map(([p, share]) => {
          const l = PHASE_LAYERS[p] || 'base';
          const pPct = Math.round((share / total) * 100);
          return `<div class="stacked-phase-segment layer-${l}" style="width: ${pPct}%;" title="${p}: ${pPct}%"></div>`;
        })
        .join('');
    }

    // Next likely chips
    const nextSection = document.getElementById('now-next-section');
    const nextChips = document.getElementById('now-next-chips');
    if (nextSection && nextChips) {
      if (track.next && track.next.length) {
        nextSection.style.display = 'flex';
        nextChips.innerHTML = track.next
          .map((n) => {
            const probPct = Math.round(n.probability * 100);
            return `<span class="chip ${n.probability >= 0.3 ? 'active' : ''}">${escapeHtml(n.phase)} <span class="chip-pct">${probPct}%</span></span>`;
          })
          .join('');
      } else {
        nextSection.style.display = 'none';
      }
    }

    // Skills for this phase
    const emptyBox = document.getElementById('now-empty-state');
    const skillsList = document.getElementById('now-skills-list');
    const copyBtn = document.getElementById('now-copy-btn');

    if (track.skills && track.skills.length) {
      if (emptyBox) emptyBox.style.display = 'none';
      if (copyBtn) copyBtn.style.display = 'inline-flex';
      if (skillsList) {
        skillsList.style.display = 'flex';
        skillsList.innerHTML = track.skills
          .map((s) => {
            const reasonsHtml = s.reasons && s.reasons.length
              ? `<ul class="skill-reasons">${s.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join('')}</ul>`
              : '';
            const tokens = s.tokens ? `<span>· ${s.tokens} tokens</span>` : '';
            const score = typeof s.score === 'number' ? `<span>· score ${s.score.toFixed(2)}</span>` : '';
            return `
              <div class="skill-card">
                <div class="card-header">
                  <span class="card-title">${escapeHtml(s.name)}</span>
                  <span class="studio-badge">${escapeHtml(s.layer || 'base')}</span>
                </div>
                <div class="card-meta">
                  <span>${s.phase ? escapeHtml(s.phase) : ''}</span>
                  ${tokens}
                  ${score}
                </div>
                ${reasonsHtml}
                <div class="skill-actions">
                  <button class="btn btn-secondary" data-action="openSkill" data-skill="${escapeHtml(s.name)}">Open</button>
                  <button class="btn btn-secondary" data-action="helped" data-skill="${escapeHtml(s.name)}">Helped</button>
                  <button class="btn btn-secondary" data-action="unhelpful" data-skill="${escapeHtml(s.name)}">Unhelpful</button>
                  <button class="btn btn-secondary" data-action="removeSkill" data-skill="${escapeHtml(s.name)}">Remove</button>
                </div>
              </div>
            `;
          })
          .join('');
      }
    } else {
      if (emptyBox) emptyBox.style.display = 'flex';
      if (copyBtn) copyBtn.style.display = 'none';
      if (skillsList) {
        skillsList.style.display = 'none';
        skillsList.innerHTML = '';
      }
    }

    // Coming up: skills for next phase
    const upcomingSection = document.getElementById('now-upcoming-section');
    const upcomingSkills = document.getElementById('now-upcoming-skills');
    if (upcomingSection && upcomingSkills) {
      if (track.upcoming && track.upcoming.skills && track.upcoming.skills.length) {
        upcomingSection.style.display = 'flex';
        upcomingSkills.innerHTML = track.upcoming.skills
          .map((name) => `
            <div class="skill-card" style="padding: 6px 8px;">
              <div class="card-header">
                <span class="card-title" style="font-size: var(--font-xs);">${escapeHtml(name)}</span>
                <span class="studio-badge">${escapeHtml(track.upcoming.phase)}</span>
              </div>
            </div>
          `)
          .join('');
      } else {
        upcomingSection.style.display = 'none';
      }
    }

    // Last 5 phase changes
    const changesSection = document.getElementById('now-changes-section');
    const changesList = document.getElementById('now-changes-list');
    if (changesSection && changesList) {
      if (track.changes && track.changes.length) {
        changesSection.style.display = 'flex';
        const recent = track.changes.slice(-5).reverse();
        changesList.innerHTML = recent
          .map((c) => {
            const timeStr = c.t ? new Date(c.t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
            return `<div class="change-item"><span>${escapeHtml(c.from)} → ${escapeHtml(c.to)}</span><span>${timeStr}</span></div>`;
          })
          .join('');
      } else {
        changesSection.style.display = 'none';
      }
    }
  }

  // Restore tab on load
  const prev = vscode.getState();
  if (prev && prev.currentTab) {
    setTab(prev.currentTab);
  }

  // Signal ready
  vscode.postMessage({ command: 'ready' });
})();
