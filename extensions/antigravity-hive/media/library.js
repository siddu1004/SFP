// SFP Skill Library Sidebar View Script
(function () {
  const vscode = acquireVsCodeApi();

  let state = {
    mode: 'bundle',
    query: '',
    groups: [],
    skills: {},
    purposes: [],
    clusters: [],
    bundles: [],
    summary: null,
    totalCount: 819,
    matchCount: 819,
    hitsMap: new Map(), // name -> Hit
    collapsedGroups: new Set(),
    error: null,
    loading: true,
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

  function highlightName(name, marks) {
    if (!marks || !marks.length) return escapeHtml(name);
    let res = '';
    let last = 0;
    for (const [start, end] of marks) {
      if (start > last) {
        res += escapeHtml(name.slice(last, start));
      }
      res += `<mark>${escapeHtml(name.slice(start, end))}</mark>`;
      last = end;
    }
    if (last < name.length) {
      res += escapeHtml(name.slice(last));
    }
    return res;
  }

  // Icons
  const ICONS = {
    chevron: '<svg class="group-chevron" viewBox="0 0 16 16"><path fill="currentColor" d="M11 8l-5 5-.7-.7L9.6 8 5.3 3.7 6 3z"/></svg>',
    refresh: '<svg viewBox="0 0 16 16"><path fill="currentColor" d="M13.6 2.4A7 7 0 1 0 15 8h-1.5a5.5 5.5 0 1 1-1.1-4.4L10 6h5V1l-1.4 1.4z"/></svg>',
    folder: '<svg class="group-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M14.5 3H7.7L6.3 1.5H1.5C.7 1.5 0 2.2 0 3v10c0 .8.7 1.5 1.5 1.5h13c.8 0 1.5-.7 1.5-1.5V4.5c0-.8-.7-1.5-1.5-1.5zm.5 10c0 .3-.2.5-.5.5h-13c-.3 0-.5-.2-.5-.5V3c0-.3.2-.5.5-.5h4.4l1.4 1.5h6.7c.3 0 .5.2.5.5v8.5z"/></svg>',
    package: '<svg class="group-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8.5 1.1l6 3.5v7l-6 3.5-6-3.5v-7l6-3.5zm0 1.2L3.5 5.2 8.5 8l5-2.8-5-2.9zM2.5 6.4v5.3l5 2.9V9.3l-5-2.9zm11 0l-5 2.9v5.3l5-2.9V6.4z"/></svg>',
    purposeDefault: '<svg class="group-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 13A6 6 0 1 1 8 2a6 6 0 0 1 0 12z"/></svg>',
  };

  // DOM Elements
  const searchInput = document.getElementById('lib-search-input');
  const searchClearBtn = document.getElementById('lib-search-clear');
  const searchCountBadge = document.getElementById('lib-search-count');
  const modeSwitch = document.getElementById('lib-mode-switch');
  const modeBtns = document.querySelectorAll('.mode-btn');
  const groupsContainer = document.getElementById('lib-groups-container');
  const newBundleBar = document.getElementById('lib-new-bundle-bar');
  const newBundleBtn = document.getElementById('lib-new-bundle-btn');
  const footerCounts = document.getElementById('lib-footer-counts');
  const footerRefreshBtn = document.getElementById('lib-refresh-btn');
  const stateLoading = document.getElementById('lib-state-loading');
  const stateEmpty = document.getElementById('lib-state-empty');
  const stateError = document.getElementById('lib-state-error');
  const stateErrorMsg = document.getElementById('lib-error-msg');
  const stateErrorBtn = document.getElementById('lib-error-btn');

  // Debounced search
  let searchTimeout = null;
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value;
      if (searchClearBtn) {
        if (q.length > 0) searchClearBtn.classList.remove('hidden');
        else searchClearBtn.classList.add('hidden');
      }
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        state.query = q;
        vscode.postMessage({ command: 'search', query: q, mode: state.mode });
      }, 80);
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        searchInput.value = '';
        state.query = '';
        if (searchClearBtn) searchClearBtn.classList.add('hidden');
        vscode.postMessage({ command: 'search', query: '', mode: state.mode });
        e.preventDefault();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        const firstBtn = groupsContainer.querySelector('button, [tabindex="0"]');
        if (firstBtn) firstBtn.focus();
      }
    });
  }

  if (searchClearBtn) {
    searchClearBtn.addEventListener('click', () => {
      if (searchInput) {
        searchInput.value = '';
        searchInput.focus();
      }
      state.query = '';
      searchClearBtn.classList.add('hidden');
      vscode.postMessage({ command: 'search', query: '', mode: state.mode });
    });
  }

  // Mode segmented switch
  if (modeSwitch) {
    modeSwitch.addEventListener('click', (e) => {
      const btn = e.target.closest('.mode-btn');
      if (!btn) return;
      const targetMode = btn.getAttribute('data-mode');
      if (targetMode === state.mode) return;
      setMode(targetMode);
    });

    modeSwitch.addEventListener('keydown', (e) => {
      const activeBtn = document.activeElement;
      if (!activeBtn || !activeBtn.classList.contains('mode-btn')) return;
      const modes = ['purpose', 'cluster', 'bundle'];
      let idx = modes.indexOf(state.mode);
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        idx = (idx + 1) % modes.length;
        setMode(modes[idx]);
        const nextBtn = document.querySelector(`.mode-btn[data-mode="${modes[idx]}"]`);
        if (nextBtn) nextBtn.focus();
        e.preventDefault();
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        idx = (idx - 1 + modes.length) % modes.length;
        setMode(modes[idx]);
        const prevBtn = document.querySelector(`.mode-btn[data-mode="${modes[idx]}"]`);
        if (prevBtn) prevBtn.focus();
        e.preventDefault();
      }
    });
  }

  function setMode(newMode) {
    state.mode = newMode;
    modeBtns.forEach((b) => {
      const active = b.getAttribute('data-mode') === newMode;
      b.classList.toggle('active', active);
      b.setAttribute('aria-checked', active ? 'true' : 'false');
      b.setAttribute('tabindex', active ? '0' : '-1');
    });
    if (newBundleBar) {
      if (newMode === 'bundle') newBundleBar.classList.remove('hidden');
      else newBundleBar.classList.add('hidden');
    }
    vscode.postMessage({ command: 'switchMode', mode: newMode, query: state.query });
  }

  if (newBundleBtn) {
    newBundleBtn.addEventListener('click', () => {
      vscode.postMessage({ command: 'newBundle' });
    });
  }

  if (footerRefreshBtn) {
    footerRefreshBtn.addEventListener('click', () => {
      showLoading(true);
      vscode.postMessage({ command: 'refresh' });
    });
  }

  if (stateErrorBtn) {
    stateErrorBtn.addEventListener('click', () => {
      vscode.postMessage({ command: 'openSettings' });
    });
  }

  // Delegated events for groups and actions
  if (groupsContainer) {
    groupsContainer.addEventListener('click', (e) => {
      const header = e.target.closest('.group-header');
      if (header) {
        const section = header.closest('.group-section');
        if (section) {
          const groupId = section.getAttribute('data-group-id');
          section.classList.toggle('collapsed');
          const isCollapsed = section.classList.contains('collapsed');
          header.setAttribute('aria-expanded', isCollapsed ? 'false' : 'true');
          if (isCollapsed) state.collapsedGroups.add(groupId);
          else state.collapsedGroups.delete(groupId);
        }
        return;
      }

      const btn = e.target.closest('[data-action]');
      if (!btn) return;
      const action = btn.getAttribute('data-action');
      const skill = btn.getAttribute('data-skill');
      const bundleId = btn.getAttribute('data-bundle');

      switch (action) {
        case 'openSkill':
          if (skill) vscode.postMessage({ command: 'openSkill', skill });
          break;
        case 'pinSkill':
          if (skill) vscode.postMessage({ command: 'pinSkill', skill });
          break;
        case 'addToBundle':
          if (skill) vscode.postMessage({ command: 'addToBundle', skill });
          break;
        case 'applyBundle':
          if (bundleId) vscode.postMessage({ command: 'applyBundle', bundleId });
          break;
        case 'copyPrompt':
          if (bundleId) vscode.postMessage({ command: 'copyPrompt', bundleId });
          break;
        case 'editBundle':
          if (bundleId) vscode.postMessage({ command: 'editBundle', bundleId });
          break;
        case 'deleteBundle':
          if (bundleId) vscode.postMessage({ command: 'deleteBundle', bundleId });
          break;
      }
    });
  }

  function showLoading(show) {
    state.loading = show;
    if (stateLoading) {
      if (show) stateLoading.classList.remove('hidden');
      else stateLoading.classList.add('hidden');
    }
  }

  function renderView() {
    showLoading(false);

    if (state.error) {
      if (stateError) {
        stateError.classList.remove('hidden');
        if (stateErrorMsg) stateErrorMsg.textContent = state.error;
      }
      if (groupsContainer) groupsContainer.innerHTML = '';
      if (stateEmpty) stateEmpty.classList.add('hidden');
      return;
    }

    if (stateError) stateError.classList.add('hidden');

    // Update search count
    if (searchCountBadge) {
      if (state.query && state.query.trim().length > 0) {
        searchCountBadge.textContent = `${state.matchCount} of ${state.totalCount}`;
      } else {
        searchCountBadge.textContent = `${state.totalCount} skills`;
      }
    }

    // Check empty results
    const hasResults = state.groups && state.groups.some((g) => g.skills && g.skills.length > 0);
    if (!hasResults) {
      if (stateEmpty) stateEmpty.classList.remove('hidden');
      if (groupsContainer) groupsContainer.innerHTML = '';
    } else {
      if (stateEmpty) stateEmpty.classList.add('hidden');
      renderGroups();
    }

    // Footer counts
    if (footerCounts && state.summary) {
      const s = state.summary;
      footerCounts.textContent = `${s.skills} skills · ${s.used} used · ${s.purposes} purposes · ${s.clusters} clusters · ${s.bundles} bundles`;
    }
  }

  function renderGroups() {
    if (!groupsContainer) return;
    const isSearching = Boolean(state.query && state.query.trim().length > 0);

    const html = state.groups
      .filter((g) => g.skills && g.skills.length > 0)
      .map((g) => {
        // While searching, expand matching groups; otherwise respect user collapse
        const isCollapsed = isSearching ? false : state.collapsedGroups.has(g.id);
        const countText = isSearching ? `${g.skills.length} of ${g.total}` : `${g.total}`;

        let iconSvg = ICONS.purposeDefault;
        if (state.mode === 'cluster') iconSvg = ICONS.folder;
        else if (state.mode === 'bundle') iconSvg = ICONS.package;

        let contentHtml = '';
        if (state.mode === 'bundle') {
          contentHtml = renderBundleCards(g);
        } else {
          contentHtml = renderSkillRows(g.skills);
        }

        return `
          <div class="group-section ${isCollapsed ? 'collapsed' : ''}" data-group-id="${escapeHtml(g.id)}">
            <button class="group-header" aria-expanded="${isCollapsed ? 'false' : 'true'}" title="${escapeHtml(g.description || g.name)}">
              ${ICONS.chevron}
              ${iconSvg}
              <span class="group-title">${escapeHtml(g.name)}</span>
              <span class="group-count">${escapeHtml(countText)}</span>
            </button>
            <div class="group-content">
              ${contentHtml}
            </div>
          </div>
        `;
      })
      .join('');

    groupsContainer.innerHTML = html;
  }

  function renderSkillRows(skillNames) {
    return skillNames
      .map((name) => {
        const skill = state.skills[name] || { d: '', category: '', cluster: '', purpose: '' };
        const hit = state.hitsMap.get(name);
        const marks = hit ? hit.marks : undefined;
        const highlightedName = highlightName(name, marks);

        const purposeObj = state.purposes.find((p) => p.id === skill.purpose);
        const purposeName = purposeObj ? purposeObj.name : skill.purpose;
        const clusterObj = state.clusters.find((c) => c.id === skill.cluster);
        const clusterName = clusterObj ? clusterObj.name : skill.cluster;

        let usageHtml = '';
        if (skill.usage && skill.usage.chosen > 0) {
          const helpedStr = skill.usage.helped ? `, helped ${skill.usage.helped}` : '';
          usageHtml = `<span class="usage-mark" title="Chosen ${skill.usage.chosen} times${helpedStr}">chosen ${skill.usage.chosen}${helpedStr}</span>`;
        }

        let appHtml = '';
        if (skill.app) {
          appHtml = `<span class="badge badge-app" title="Requires program: ${escapeHtml(skill.app)}">needs ${escapeHtml(skill.app)}</span>`;
        }

        return `
          <div class="skill-row" tabindex="0">
            <div class="skill-row-top">
              <span class="skill-name" title="${escapeHtml(name)}">${highlightedName}</span>
              <div class="skill-actions">
                <button class="btn-small btn-secondary" data-action="openSkill" data-skill="${escapeHtml(name)}" title="Open SKILL.md">Open</button>
                <button class="btn-small btn-secondary" data-action="pinSkill" data-skill="${escapeHtml(name)}" title="Pin to current task">Pin</button>
                <button class="btn-small btn-secondary" data-action="addToBundle" data-skill="${escapeHtml(name)}" title="Add to bundle...">+ Bundle</button>
              </div>
            </div>
            <div class="skill-desc" title="${escapeHtml(skill.d)}">${escapeHtml(skill.d)}</div>
            <div class="skill-meta">
              <span class="badge badge-purpose" title="Purpose: ${escapeHtml(purposeName)}">${escapeHtml(purposeName)}</span>
              <span class="badge badge-cluster" title="Cluster: ${escapeHtml(clusterName)}">${escapeHtml(clusterName)}</span>
              ${appHtml}
              ${usageHtml}
            </div>
          </div>
        `;
      })
      .join('');
  }

  function renderBundleCards(group) {
    const bundle = group.bundle;
    if (!bundle) return renderSkillRows(group.skills);

    const isMine = Boolean(bundle.mine);
    const mineBadge = isMine ? '<span class="badge badge-mine">yours</span>' : '';
    const chipsHtml = (bundle.skills || [])
      .map((s, idx) => `<span class="bundle-chip" title="Step ${idx + 1}: ${escapeHtml(s)}"><span class="chip-num">${idx + 1}</span>${escapeHtml(s)}</span>`)
      .join('');

    const mineActions = isMine
      ? `<button class="btn-small btn-secondary" data-action="editBundle" data-bundle="${escapeHtml(bundle.id)}">Edit</button>
         <button class="btn-small btn-danger" data-action="deleteBundle" data-bundle="${escapeHtml(bundle.id)}">Delete</button>`
      : '';

    return `
      <div class="bundle-card" tabindex="0">
        <div class="bundle-top">
          <span class="bundle-title">
            <strong>${escapeHtml(bundle.name)}</strong>
            ${mineBadge}
          </span>
          <span class="bundle-tokens">~${escapeHtml(String(bundle.tokens))} tokens</span>
        </div>
        <div class="bundle-goal">${escapeHtml(bundle.goal)}</div>
        ${bundle.when ? `<div class="bundle-when">${escapeHtml(bundle.when)}</div>` : ''}
        <div class="bundle-chips">${chipsHtml}</div>
        <div class="bundle-actions">
          <button class="btn-small btn-primary" data-action="applyBundle" data-bundle="${escapeHtml(bundle.id)}">Apply</button>
          <button class="btn-small btn-secondary" data-action="copyPrompt" data-bundle="${escapeHtml(bundle.id)}">Copy prompt</button>
          ${mineActions}
        </div>
      </div>
    `;
  }

  // Receive messages from extension host
  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg) return;

    switch (msg.type) {
      case 'update': {
        state.mode = msg.mode || state.mode;
        state.groups = msg.groups || [];
        state.summary = msg.summary || state.summary;
        state.skills = msg.skills || state.skills;
        state.purposes = msg.purposes || state.purposes;
        state.clusters = msg.clusters || state.clusters;
        state.bundles = msg.bundles || state.bundles;
        state.totalCount = msg.counts ? msg.counts.skills : state.totalCount;
        state.matchCount = state.totalCount;
        state.hitsMap.clear();
        state.error = msg.error || null;

        // Sync mode buttons UI
        modeBtns.forEach((b) => {
          const active = b.getAttribute('data-mode') === state.mode;
          b.classList.toggle('active', active);
          b.setAttribute('aria-checked', active ? 'true' : 'false');
          b.setAttribute('tabindex', active ? '0' : '-1');
        });
        if (newBundleBar) {
          if (state.mode === 'bundle') newBundleBar.classList.remove('hidden');
          else newBundleBar.classList.add('hidden');
        }

        renderView();
        break;
      }
      case 'searchResults': {
        state.mode = msg.mode || state.mode;
        state.query = msg.query ?? state.query;
        state.groups = msg.groups || [];
        state.matchCount = msg.matchCount ?? state.totalCount;
        state.totalCount = msg.totalCount ?? state.totalCount;

        state.hitsMap.clear();
        if (Array.isArray(msg.hits)) {
          for (const h of msg.hits) {
            state.hitsMap.set(h.name, h);
          }
        }

        renderView();
        break;
      }
      case 'error': {
        state.error = msg.message || 'An unexpected error occurred.';
        renderView();
        break;
      }
    }
  });

  // Signal ready to extension host
  vscode.postMessage({ command: 'ready' });
})();
