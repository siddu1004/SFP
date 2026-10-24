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
    clusters: [],
    selectedClusterId: null,
    libraryFilter: '',
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
      btn.setAttribute('tabindex', match ? '0' : '-1');
    });

    tabContents.forEach((content) => {
      const match = content.id === `tab-${tabId}`;
      content.classList.toggle('active', match);
    });

    vscode.setState({ currentTab });
  }

  // Keyboard navigation for tab bar: roving tabindex, Left, Right, Home, End
  const tabBar = document.querySelector('.tab-bar');
  if (tabBar) {
    tabBar.addEventListener('keydown', (e) => {
      const tabs = Array.from(tabButtons);
      const idx = tabs.findIndex((t) => t.getAttribute('data-tab') === currentTab);
      let nextTab = null;

      if (e.key === 'ArrowRight') {
        e.preventDefault();
        nextTab = tabs[(idx + 1) % tabs.length];
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        nextTab = tabs[(idx - 1 + tabs.length) % tabs.length];
      } else if (e.key === 'Home') {
        e.preventDefault();
        nextTab = tabs[0];
      } else if (e.key === 'End') {
        e.preventDefault();
        nextTab = tabs[tabs.length - 1];
      }

      if (nextTab) {
        nextTab.focus();
        setTab(nextTab.getAttribute('data-tab'));
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
          if (dropdown) dropdown.classList.add('hidden');
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
      case 'selectCluster': {
        const clusterId = target.getAttribute('data-cluster-id');
        if (clusterId) {
          state.selectedClusterId = clusterId;
          renderLibrary();
        }
        break;
      }
      case 'backToClusters': {
        state.selectedClusterId = null;
        renderLibrary();
        break;
      }
      case 'newCluster': {
        vscode.postMessage({ command: 'newCluster' });
        break;
      }
      case 'removeCluster': {
        const name = target.getAttribute('data-cluster-name');
        if (name) {
          vscode.postMessage({ command: 'removeCluster', name });
        }
        break;
      }
      case 'pinSkill': {
        if (skill) {
          vscode.postMessage({ command: 'pinSkill', skill });
        }
        break;
      }
      case 'addToMyCluster': {
        if (skill) {
          vscode.postMessage({ command: 'addToMyCluster', skill });
        }
      case 'liveRemove': {
        if (skill) {
          vscode.postMessage({
            command: 'liveChange',
            draft: chooseTaskInput ? chooseTaskInput.value : '',
            change: { remove: [skill] },
          });
        }
        break;
      }
      case 'liveRestore': {
        if (skill) {
          vscode.postMessage({
            command: 'liveChange',
            draft: chooseTaskInput ? chooseTaskInput.value : '',
            change: { restore: [skill] },
          });
        }
        break;
      }
      case 'livePin': {
        if (skill) {
          vscode.postMessage({
            command: 'liveChange',
            draft: chooseTaskInput ? chooseTaskInput.value : '',
            change: { pin: [skill] },
          });
        }
        break;
      }
    }
  });

  function renderLive() {
    const container = document.getElementById('choose-live-container');
    const chipsBar = document.getElementById('choose-live-chips');
    const waitingLabel = document.getElementById('choose-live-waiting');
    const removedBar = document.getElementById('choose-live-removed');
    if (!container || !chipsBar) return;

    const live = state.live;
    if (!live) {
      container.classList.add('hidden');
      return;
    }

    container.classList.remove('hidden');

    // Waiting state
    if (waitingLabel) {
      if (live.status === 'waiting' && (!live.attached || live.attached.length === 0)) {
        waitingLabel.classList.remove('hidden');
      } else {
        waitingLabel.classList.add('hidden');
      }
    }

    // Attached chips
    if (live.attached && live.attached.length) {
      chipsBar.innerHTML = live.attached
        .map((s) => {
          const isPinned = s.source === 'pinned';
          const badgeClass = isPinned ? 'badge-pinned' : 'badge-auto';
          const badgeText = isPinned ? 'pinned' : 'auto';
          return `
            <span class="live-chip">
              <span class="live-chip-badge ${badgeClass}">${badgeText}</span>
              <span class="live-chip-name" title="${escapeHtml(s.description || s.name)}">${escapeHtml(s.name)}</span>
              <button class="live-chip-remove" data-action="liveRemove" data-skill="${escapeHtml(s.name)}" title="Remove skill">&times;</button>
            </span>
          `;
        })
        .join('');
    } else {
      chipsBar.innerHTML = '';
    }

    // Removed skills for restoration
    const removed = live.state?.removed || [];
    if (removedBar) {
      if (removed.length > 0) {
        removedBar.classList.remove('hidden');
        removedBar.innerHTML = removed
          .map((n) => `
            <span class="live-removed-chip">
              <span>${escapeHtml(n)}</span>
              <button class="live-chip-restore" data-action="liveRestore" data-skill="${escapeHtml(n)}">restore</button>
            </span>
          `)
          .join('');
      } else {
        removedBar.classList.add('hidden');
        removedBar.innerHTML = '';
      }
    }
  }

  // Task input submits on Enter or types live
  const chooseTaskInput = document.getElementById('choose-task-input');
  if (chooseTaskInput) {
    chooseTaskInput.addEventListener('input', () => {
      const text = chooseTaskInput.value;
      vscode.postMessage({ command: 'liveType', draft: text });
    });

    chooseTaskInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const text = chooseTaskInput.value.trim();
        if (text) {
          state.include = [];
          state.exclude = [];
          vscode.postMessage({ command: 'choose', task: text });
        }
      }
    });
  }

  // Catalog search input
  const catalogSearch = document.getElementById('choose-catalog-search');
  const catalogResults = document.getElementById('choose-catalog-results');
  if (catalogSearch && catalogResults) {
    catalogSearch.addEventListener('input', () => {
      const q = catalogSearch.value.trim().toLowerCase();
      if (!q || !state.catalog || !state.catalog.length) {
        catalogResults.classList.add('hidden');
        return;
      }
      const matches = state.catalog.filter((name) => name.toLowerCase().includes(q)).slice(0, 8);
      if (!matches.length) {
        catalogResults.classList.add('hidden');
        return;
      }
      catalogResults.classList.remove('hidden');
      catalogResults.innerHTML = matches
        .map((m) => `<div class="catalog-item" data-action="addCatalogSkill" data-skill="${escapeHtml(m)}">${escapeHtml(m)}</div>`)
        .join('');
    });

    catalogResults.addEventListener('click', (e) => {
      const item = e.target.closest('.catalog-item');
      if (item) {
        const skillName = item.getAttribute('data-skill');
        if (skillName) {
          if (!state.include.includes(skillName)) state.include.push(skillName);
          state.exclude = state.exclude.filter((s) => s !== skillName);
          catalogSearch.value = '';
          catalogResults.classList.add('hidden');
          const input = document.getElementById('choose-task-input');
          const text = input ? input.value.trim() : (state.selection?.task || '');
          vscode.postMessage({
            command: 'rechoose',
            task: text,
            include: state.include,
            exclude: state.exclude,
          });
        }
      }
    });
  }

  // Follow the agent toggle switch
  const followToggle = document.getElementById('follow-toggle');
  if (followToggle) {
    followToggle.addEventListener('change', () => {
      vscode.postMessage({ command: 'toggleFollow', value: followToggle.checked });
    });
  }

  // Library search input typing
  const librarySearch = document.getElementById('library-search-input');
  if (librarySearch) {
    librarySearch.addEventListener('input', () => {
      state.libraryFilter = librarySearch.value.trim().toLowerCase();
      renderLibrary();
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
      case 'state': {
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
          if (Array.isArray(msg.payload.clusters)) {
            state.clusters = msg.payload.clusters;
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
          if (msg.payload.live !== undefined) {
            state.live = msg.payload.live;
            renderLive();
          }
          renderChoose();
        }
        break;
      }
      case 'liveResult': {
        if (msg.result) {
          state.live = msg.result;
          renderLive();
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
          if (v === undefined || v === null) {
            return `<div class="signal-bar signal-bar-empty" title="${k}: none"></div>`;
          }
          const p = Math.min(100, Math.max(10, Math.round(Number(v) * 100)));
          const bar = document.createElement('div');
          bar.className = 'signal-bar';
          bar.title = `${k}: ${p}%`;
          const fill = document.createElement('div');
          fill.className = 'signal-bar-fill';
          fill.style.width = `${p}%`;
          bar.appendChild(fill);
          return bar.outerHTML;
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
        steerSection.classList.remove('hidden');
        if (state.diff && (state.diff.added.length || state.diff.removed.length)) {
          if (diffSummary) {
            diffSummary.classList.remove('hidden');
            const addedHtml = state.diff.added.map((n) => `<span class="diff-added">+ ${escapeHtml(n)}</span>`).join('  ');
            const removedHtml = state.diff.removed.map((n) => `<span class="diff-removed">- ${escapeHtml(n)}</span>`).join('  ');
            diffSummary.innerHTML = `<strong>Changes:</strong> ${addedHtml} ${removedHtml}`;
          }
        } else if (diffSummary) {
          diffSummary.classList.add('hidden');
        }
      } else {
        steerSection.classList.add('hidden');
      }
    }

    // Decision ID in Choose header
    const chooseDecision = document.getElementById('choose-decision-id');
    if (chooseDecision) {
      chooseDecision.textContent = sel && sel.decision ? `Decision: ${sel.decision}` : '';
    }

    // Chosen Stack
    const emptyBox = document.getElementById('choose-empty-state');
    const stackList = document.getElementById('choose-stack-list');
    const addSection = document.getElementById('choose-add-section');

    if (sel && sel.stack && sel.stack.length) {
      if (emptyBox) emptyBox.classList.add('hidden');
      if (addSection) addSection.classList.remove('hidden');
      if (stackList) {
        stackList.classList.remove('hidden');
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
                const dec = sel.decision || '';
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
                      <button class="btn btn-secondary" data-action="helped" data-skill="${escapeHtml(s.name)}" data-decision="${escapeHtml(dec)}">Helped</button>
                      <button class="btn btn-secondary" data-action="unhelpful" data-skill="${escapeHtml(s.name)}" data-decision="${escapeHtml(dec)}">Unhelpful</button>
                      <button class="btn btn-secondary btn-danger" data-action="steerRemove" data-skill="${escapeHtml(s.name)}">Remove</button>
                    </div>
                  </div>
                `;
              })
              .join('');
            return `
              <div class="flex-col">
                <div class="section-title">${escapeHtml(layerLabel)}</div>
                ${cardsHtml}
              </div>
            `;
          })
          .join('');
      }
    } else {
      if (emptyBox) emptyBox.classList.remove('hidden');
      if (addSection) addSection.classList.add('hidden');
      if (stackList) {
        stackList.classList.add('hidden');
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
          consideredSection.classList.remove('hidden');
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
                  <td><button class="btn btn-secondary btn-small" data-action="steerAdd" data-skill="${escapeHtml(c.name)}">Add</button></td>
                </tr>
              `;
            })
            .join('');
        } else {
          consideredSection.classList.add('hidden');
        }
      } else {
        consideredSection.classList.add('hidden');
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
    const nowDecision = document.getElementById('now-decision-id');

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

    const decisionId = track.decision || state.decision || state.selection?.decision;
    if (nowDecision) {
      nowDecision.textContent = decisionId ? `Decision: ${decisionId}` : '';
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
      sharesBar.innerHTML = '';
      entries.forEach(([p, share]) => {
        const l = PHASE_LAYERS[p] || 'base';
        const pPct = Math.round((share / total) * 100);
        const seg = document.createElement('div');
        seg.className = `stacked-phase-segment layer-${l}`;
        seg.style.width = `${pPct}%`;
        seg.title = `${p}: ${pPct}%`;
        sharesBar.appendChild(seg);
      });
    }

    // Next likely chips
    const nextSection = document.getElementById('now-next-section');
    const nextChips = document.getElementById('now-next-chips');
    if (nextSection && nextChips) {
      if (track.next && track.next.length) {
        nextSection.classList.remove('hidden');
        nextChips.innerHTML = track.next
          .map((n) => {
            const probPct = Math.round(n.probability * 100);
            return `<span class="chip ${n.probability >= 0.3 ? 'active' : ''}">${escapeHtml(n.phase)} <span class="chip-pct">${probPct}%</span></span>`;
          })
          .join('');
      } else {
        nextSection.classList.add('hidden');
      }
    }

    // Skills for this phase
    const emptyBox = document.getElementById('now-empty-state');
    const skillsList = document.getElementById('now-skills-list');
    const copyBtn = document.getElementById('now-copy-btn');

    if (track.skills && track.skills.length) {
      if (emptyBox) emptyBox.classList.add('hidden');
      if (copyBtn) copyBtn.classList.remove('hidden');
      if (skillsList) {
        skillsList.classList.remove('hidden');
        skillsList.innerHTML = track.skills
          .map((s) => {
            const reasonsHtml = s.reasons && s.reasons.length
              ? `<ul class="skill-reasons">${s.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join('')}</ul>`
              : '';
            const tokens = s.tokens ? `<span>· ${s.tokens} tokens</span>` : '';
            const score = typeof s.score === 'number' ? `<span>· score ${s.score.toFixed(2)}</span>` : '';
            const dec = decisionId || '';
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
                  <button class="btn btn-secondary" data-action="helped" data-skill="${escapeHtml(s.name)}" data-decision="${escapeHtml(dec)}">Helped</button>
                  <button class="btn btn-secondary" data-action="unhelpful" data-skill="${escapeHtml(s.name)}" data-decision="${escapeHtml(dec)}">Unhelpful</button>
                  <button class="btn btn-secondary btn-danger" data-action="removeSkill" data-skill="${escapeHtml(s.name)}">Remove</button>
                </div>
              </div>
            `;
          })
          .join('');
      }
    } else {
      if (emptyBox) emptyBox.classList.remove('hidden');
      if (copyBtn) copyBtn.classList.add('hidden');
      if (skillsList) {
        skillsList.classList.add('hidden');
        skillsList.innerHTML = '';
      }
    }

    // Coming up: skills for next phase
    const upcomingSection = document.getElementById('now-upcoming-section');
    const upcomingSkills = document.getElementById('now-upcoming-skills');
    if (upcomingSection && upcomingSkills) {
      if (track.upcoming && track.upcoming.skills && track.upcoming.skills.length) {
        upcomingSection.classList.remove('hidden');
        upcomingSkills.innerHTML = track.upcoming.skills
          .map((name) => `
            <div class="skill-card card-compact">
              <div class="card-header">
                <span class="card-title">${escapeHtml(name)}</span>
                <span class="studio-badge">${escapeHtml(track.upcoming.phase)}</span>
              </div>
            </div>
          `)
          .join('');
      } else {
        upcomingSection.classList.add('hidden');
      }
    }

    // Last 5 phase changes
    const changesSection = document.getElementById('now-changes-section');
    const changesList = document.getElementById('now-changes-list');
    if (changesSection && changesList) {
      if (track.changes && track.changes.length) {
        changesSection.classList.remove('hidden');
        const recent = track.changes.slice(-5).reverse();
        changesList.innerHTML = recent
          .map((c) => {
            const timeStr = c.t ? new Date(c.t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
            return `<div class="change-item"><span>${escapeHtml(c.from)} → ${escapeHtml(c.to)}</span><span>${timeStr}</span></div>`;
          })
          .join('');
      } else {
        changesSection.classList.add('hidden');
      }
    }
  }

  // Restore saved state
  const prev = vscode.getState();
  if (prev?.currentTab) {
    setTab(prev.currentTab);
  }

  // Notify extension host that frontend is ready
  vscode.postMessage({ command: 'ready' });
})();
