// SFP Hive Studio Frontend Script
(function () {
  const vscode = acquireVsCodeApi();

  // State
  let currentTab = 'now';
  let state = {
    track: null,
    selection: null,
    baselineSelection: null,
    diff: null,
    include: [],
    exclude: [],
    catalog: [],
    sessionStats: {
      decisions: 0,
      interventions: 0,
      chosenTotal: 0,
      keptTotal: 0,
      addedSkills: 0,
      helped: 0,
      unhelpful: 0,
    },
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
          state.include = [];
          state.exclude = [];
          vscode.postMessage({ command: 'choose', task: text });
        }
        break;
      }
      case 'rechoose': {
        const input = document.getElementById('choose-task-input');
        const text = input ? input.value.trim() : (state.selection?.task || '');
        if (text) {
          vscode.postMessage({
            command: 'rechoose',
            task: text,
            include: state.include,
            exclude: state.exclude,
          });
        }
        break;
      }
      case 'applyStack': {
        const fbCheckbox = document.getElementById('choose-feedback-checkbox');
        const sendFeedback = fbCheckbox ? fbCheckbox.checked : true;
        vscode.postMessage({
          command: 'applyStack',
          sendFeedback,
          include: state.include,
          exclude: state.exclude,
        });
        break;
      }
      case 'steerAdd': {
        if (skill) {
          if (!state.include.includes(skill)) state.include.push(skill);
          state.exclude = state.exclude.filter((s) => s !== skill);
          const input = document.getElementById('choose-task-input');
          const text = input ? input.value.trim() : (state.selection?.task || '');
          vscode.postMessage({
            command: 'rechoose',
            task: text,
            include: state.include,
            exclude: state.exclude,
          });
        }
        break;
      }
      case 'steerRemove': {
        if (skill) {
          if (!state.exclude.includes(skill)) state.exclude.push(skill);
          state.include = state.include.filter((s) => s !== skill);
          const input = document.getElementById('choose-task-input');
          const text = input ? input.value.trim() : (state.selection?.task || '');
          vscode.postMessage({
            command: 'rechoose',
            task: text,
            include: state.include,
            exclude: state.exclude,
          });
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
      case 'addCatalogSkill': {
        const searchInput = document.getElementById('choose-catalog-search');
        const val = searchInput ? searchInput.value.trim() : '';
        if (val) {
          if (!state.include.includes(val)) state.include.push(val);
          state.exclude = state.exclude.filter((s) => s !== val);
          if (searchInput) searchInput.value = '';
          const dropdown = document.getElementById('choose-catalog-results');
          if (dropdown) dropdown.style.display = 'none';
          const input = document.getElementById('choose-task-input');
          const text = input ? input.value.trim() : (state.selection?.task || '');
          vscode.postMessage({
            command: 'rechoose',
            task: text,
            include: state.include,
            exclude: state.exclude,
          });
        }
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

  // Catalog search input typing
  const catalogSearch = document.getElementById('choose-catalog-search');
  const catalogResults = document.getElementById('choose-catalog-results');
  if (catalogSearch && catalogResults) {
    catalogSearch.addEventListener('input', () => {
      const q = catalogSearch.value.trim().toLowerCase();
      if (!q || !state.catalog || !state.catalog.length) {
        catalogResults.style.display = 'none';
        catalogResults.innerHTML = '';
        return;
      }
      const matches = state.catalog.filter((n) => n.toLowerCase().includes(q)).slice(0, 10);
      if (matches.length) {
        catalogResults.style.display = 'block';
        catalogResults.innerHTML = matches
          .map((m) => `<div class="catalog-item" data-skill="${escapeHtml(m)}">${escapeHtml(m)}</div>`)
          .join('');
      } else {
        catalogResults.style.display = 'none';
      }
    });

    catalogResults.addEventListener('click', (e) => {
      const item = e.target.closest('.catalog-item');
      if (item) {
        const s = item.getAttribute('data-skill');
        if (s) {
          catalogSearch.value = s;
          catalogResults.style.display = 'none';
        }
      }
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
          if (msg.payload.selection) {
            state.selection = msg.payload.selection;
          }
          if (msg.payload.baselineSelection) {
            state.baselineSelection = msg.payload.baselineSelection;
          }
          if (msg.payload.diff) {
            state.diff = msg.payload.diff;
          }
          if (msg.payload.include) {
            state.include = msg.payload.include;
          }
          if (msg.payload.exclude) {
            state.exclude = msg.payload.exclude;
          }
          if (msg.payload.catalog) {
            state.catalog = msg.payload.catalog;
          }
          if (msg.payload.sessionStats) {
            state.sessionStats = msg.payload.sessionStats;
          }
          if (typeof msg.payload.follow === 'boolean') {
            state.follow = msg.payload.follow;
          }
          if (msg.payload.track) {
            state.track = msg.payload.track;
            renderTrack(state.track, state.follow);
          }
          if (msg.payload.editorSelection) {
            const taskInput = document.getElementById('choose-task-input');
            if (taskInput && !taskInput.value.trim()) {
              taskInput.value = msg.payload.editorSelection;
            }
          }
          renderChoose();
        }
        break;
      }
    }
  });

  function renderSignalBars(signals) {
    if (!signals) return '';
    const keys = ['words', 'project', 'role', 'category', 'history'];
    return (
      `<div class="signal-bars">` +
      keys
        .map((k) => {
          const v = signals[k];
          if (v === null || v === undefined) {
            return `<div class="signal-bar signal-bar-empty" title="${k}: abstained"></div>`;
          }
          const p = Math.min(100, Math.round(v * 100));
          return `<div class="signal-bar" title="${k}: ${p}%"><div class="signal-bar-fill" style="width: ${p}%;"></div></div>`;
        })
        .join('') +
      `</div>`
    );
  }

  function renderChoose() {
    const sel = state.selection;
    const taskInput = document.getElementById('choose-task-input');
    if (taskInput && sel?.task && !taskInput.value.trim()) {
      taskInput.value = sel.task;
    }

    // Steer section & diff
    const steerSection = document.getElementById('choose-steer-section');
    const diffSummary = document.getElementById('choose-diff-summary');
    if (steerSection) {
      if (sel) {
        steerSection.style.display = 'block';
        if (state.diff && (state.diff.added.length || state.diff.removed.length)) {
          if (diffSummary) {
            diffSummary.style.display = 'block';
            const addedHtml = state.diff.added.map((n) => `<span class="diff-added">+ ${escapeHtml(n)}</span>`).join('  ');
            const removedHtml = state.diff.removed.map((n) => `<span class="diff-removed">- ${escapeHtml(n)}</span>`).join('  ');
            diffSummary.innerHTML = `<strong>Changes:</strong> ${addedHtml} ${removedHtml}`;
          }
        } else if (diffSummary) {
          diffSummary.style.display = 'none';
        }
      } else {
        steerSection.style.display = 'none';
      }
    }

    // Chosen Stack
    const emptyBox = document.getElementById('choose-empty-state');
    const stackList = document.getElementById('choose-stack-list');
    const addSection = document.getElementById('choose-add-section');

    if (sel && sel.stack && sel.stack.length) {
      if (emptyBox) emptyBox.style.display = 'none';
      if (addSection) addSection.style.display = 'block';
      if (stackList) {
        stackList.style.display = 'flex';
        // Group by layer: Base, Check, Finish
        const layers = ['base', 'check', 'finish'];
        stackList.innerHTML = layers
          .map((layerName) => {
            const inLayer = sel.stack.filter((s) => (s.layer || 'base') === layerName);
            if (!inLayer.length) return '';
            const layerLabel = layerName[0].toUpperCase() + layerName.slice(1);
            const cardsHtml = inLayer
              .map((s) => {
                const isPinned = state.include.includes(s.name) || (sel.intervention?.pinned?.includes(s.name));
                const reasons = (s.reasons || []).concat(isPinned ? ['pinned by you'] : []);
                const reasonsHtml = reasons.length
                  ? `<ul class="skill-reasons">${reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join('')}</ul>`
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
                      <button class="btn btn-secondary" data-action="steerRemove" data-skill="${escapeHtml(s.name)}">Remove</button>
                      <button class="btn btn-secondary" data-action="helped" data-skill="${escapeHtml(s.name)}" data-decision="${escapeHtml(sel.decision || '')}">Helped</button>
                      <button class="btn btn-secondary" data-action="unhelpful" data-skill="${escapeHtml(s.name)}" data-decision="${escapeHtml(sel.decision || '')}">Unhelpful</button>
                      <button class="btn btn-secondary" data-action="ignored" data-skill="${escapeHtml(s.name)}" data-decision="${escapeHtml(sel.decision || '')}">Ignored</button>
                    </div>
                  </div>
                `;
              })
              .join('');
            return `
              <div style="display: flex; flex-direction: column; gap: 4px;">
                <div class="section-title" style="margin-top: 4px;">${escapeHtml(layerLabel)}</div>
                ${cardsHtml}
              </div>
            `;
          })
          .join('');
      }
    } else {
      if (emptyBox) emptyBox.style.display = 'flex';
      if (addSection) addSection.style.display = 'none';
      if (stackList) {
        stackList.style.display = 'none';
        stackList.innerHTML = '';
      }
    }

    // Considered but not taken
    const consideredSection = document.getElementById('choose-considered-section');
    const consideredBody = document.getElementById('choose-considered-body');
    if (consideredSection && consideredBody) {
      if (sel && sel.explain && sel.explain.length) {
        const notTaken = sel.explain.filter((c) => c.status !== 'chosen' && !sel.stack.some((s) => s.name === c.name));
        if (notTaken.length) {
          consideredSection.style.display = 'block';
          consideredBody.innerHTML = notTaken
            .map((c) => {
              const reason = c.status.replace(/^dropped:\s*/, '');
              const backersStr = (c.backers || []).join(', ') || 'none';
              const learnedStr = c.learned > 0 ? `+${c.learned}` : c.learned < 0 ? `${c.learned}` : '0';
              return `
                <tr>
                  <td><strong>${escapeHtml(c.name)}</strong></td>
                  <td title="${escapeHtml(c.status)}">${escapeHtml(reason)}</td>
                  <td>${renderSignalBars(c.signals)}</td>
                  <td>${escapeHtml(backersStr)} · ${escapeHtml(learnedStr)}</td>
                  <td><button class="btn btn-secondary" style="padding: 2px 6px; font-size: 11px;" data-action="steerAdd" data-skill="${escapeHtml(c.name)}">Add</button></td>
                </tr>
              `;
            })
            .join('');
        } else {
          consideredSection.style.display = 'none';
        }
      } else {
        consideredSection.style.display = 'none';
      }
    }

    // Session counters
    const stats = state.sessionStats;
    const statDec = document.getElementById('stat-decisions');
    const statInter = document.getElementById('stat-interventions');
    const statKept = document.getElementById('stat-kept');
    const statAdded = document.getElementById('stat-added');

    if (statDec) statDec.textContent = String(stats.decisions);
    if (statInter) statInter.textContent = String(stats.interventions);
    if (statKept) {
      const share = stats.chosenTotal > 0 ? Math.round((stats.keptTotal / stats.chosenTotal) * 100) : 100;
      statKept.textContent = `${share}%`;
    }
    if (statAdded) statAdded.textContent = String(stats.addedSkills);
  }

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
