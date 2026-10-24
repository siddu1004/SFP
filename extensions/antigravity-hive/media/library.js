// SFP Skill Library sidebar. The extension host does the search and the grouping (src/library.ts); this file only draws
// what it is sent and posts what the user does. Every dynamic string goes through escapeHtml.
(function () {
  const vscode = window.vscode || (window.vscode = acquireVsCodeApi());

  const MODES = ['family', 'purpose', 'bundle', 'cluster'];
  let state = {
    mode: 'family',
    query: '',
    groups: [],
    skills: {},
    families: [],
    purposes: [],
    clusters: [],
    bundles: [],
    summary: null,
    totalCount: 0,
    matchCount: 0,
    hitsMap: new Map(),
    open: new Set(), // ids of the groups, bundles and clusters the user opened
    error: null,
    loading: true,
  };
  try {
    const saved = vscode.getState();
    if (saved && Array.isArray(saved.open)) state.open = new Set(saved.open);
  } catch (e) { /* no saved state */ }
  const remember = () => { try { vscode.setState({ open: [...state.open] }); } catch (e) { /* ignore */ } };

  function escapeHtml(str) {
    if (str === undefined || str === null) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function highlightName(name, marks) {
    if (!marks || !marks.length) return escapeHtml(name);
    let res = '';
    let last = 0;
    for (const [start, end] of marks) {
      if (start > last) res += escapeHtml(name.slice(last, start));
      res += `<mark>${escapeHtml(name.slice(start, end))}</mark>`;
      last = end;
    }
    if (last < name.length) res += escapeHtml(name.slice(last));
    return res;
  }

  const ICONS = {
    chevron: '<svg class="chevron" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M6 3.5l5 4.5-5 4.5-.8-.9L9.3 8 5.2 4.4z"/></svg>',
    info: '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 13A6 6 0 1 1 8 2a6 6 0 0 1 0 12zm-.5-8.5h1V7h-1V5.5zm0 2.5h1v4h-1V8z"/></svg>',
    pin: '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M10.7 1.3l4 4-1 .7-1 3.6 1 1-.7.7-3-3-4.6 4.6-.7-.7L9.3 8.3l-3-3 .7-.7 1 1 3.6-1 .7-1.7z"/></svg>',
    plus: '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M7.5 3h1v4.5H13v1H8.5V13h-1V8.5H3v-1h4.5V3z"/></svg>',
    stack: '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 1.5l6.5 3.2L8 8 1.5 4.7 8 1.5zm-5.8 6L8 10.4l5.8-2.9.4.8L8 11.5 1.8 8.3l.4-.8zm0 3L8 13.4l5.8-2.9.4.8L8 14.5 1.8 11.3l.4-.8z"/></svg>',
  };
  const PURPOSE_ICONS = {
    'tools': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M14.6 3.4l-2.2 2.2-1.9-.5-.5-1.9 2.2-2.2a4 4 0 0 0-4.9 5.1L1.5 11.7a1.4 1.4 0 0 0 2 2l5.7-5.8a4 4 0 0 0 5.4-4.5z"/></svg>',
    'sparkle': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M7 1l1.4 4.6L13 7l-4.6 1.4L7 13 5.6 8.4 1 7l4.6-1.4L7 1zm6 8l.7 2.3L16 12l-2.3.7L13 15l-.7-2.3L10 12l2.3-.7L13 9z"/></svg>',
    'plug': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M5 1v4H4v3a4 4 0 0 0 3 3.9V15h2v-3.1A4 4 0 0 0 12 8V5h-1V1h-1.5v4h-3V1H5z"/></svg>',
    'package': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8.5 1.1l6 3.5v7l-6 3.5-6-3.5v-7l6-3.5zm0 1.2L3.5 5.2 8.5 8l5-2.8-5-2.9zM2.5 6.4v5.3l5 2.9V9.3l-5-2.9zm11 0l-5 2.9v5.3l5-2.9V6.4z"/></svg>',
    'account': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm0 1c-3 0-5.5 1.6-5.5 4v1.5h11V13c0-2.4-2.5-4-5.5-4z"/></svg>',
    'symbol-color': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1a7 7 0 0 0-7 7c0 2.4 1.2 4.5 3 5.7V12a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1V9a2 2 0 0 1 2-2h1a2 2 0 0 1 2 2v.5a.5.5 0 0 0 1 0V9a3 3 0 0 0-3-3h-.5A2.5 2.5 0 0 1 7 3.5V2.1A6.98 6.98 0 0 0 8 1z"/></svg>',
    'code': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M4.7 3.3L1 7l3.7 3.7.7-.7L2.4 7l3-3-.7-.7zm6.6 0l-.7.7 3 3-3 3 .7.7L15 7l-3.7-3.7zM9.1 2l-3.5 12h1.1l3.5-12H9.1z"/></svg>',
    'beaker': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M14.5 13.5L10 4V2h1V1H5v1h1v2L1.5 13.5A1.5 1.5 0 0 0 2.8 15h10.4a1.5 1.5 0 0 0 1.3-1.5zM6.8 5l3.2 6.8H2.8L6 5.2V2h4v3.2L6.8 5z"/></svg>',
    'bug': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M15 8h-2.1a4.96 4.96 0 0 0-.6-2.1l1.5-1.5-.7-.7-1.7 1.7A4.95 4.95 0 0 0 9 4.1V2h1V1H6v1h1v2.1c-.8.1-1.6.4-2.4 1.1L3.9 3.5l-.7.7 1.5 1.5c-.3.7-.5 1.4-.6 2.3H1v1h2.1c0 .7.2 1.4.5 2l-1.5 1.5.7.7 1.7-1.7c.7.6 1.6.9 2.5 1v2H6v1h4v-1h-1v-2c.9-.1 1.8-.4 2.5-1l1.7 1.7.7-.7-1.5-1.5c.3-.6.5-1.3.5-2H15V8zM8 12c-1.7 0-3-1.3-3-3s1.3-3 3-3 3 1.3 3 3-1.3 3-3 3z"/></svg>',
    'shield': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1l6 2.5v4.8c0 4.2-3.3 7.2-6 7.7-2.7-.5-6-3.5-6-7.7V3.5L8 1zm0 1.1L3 4.2v4.1c0 3.5 2.7 6.1 5 6.6 2.3-.5 5-3.1 5-6.6V4.2L8 2.1z"/></svg>',
    'checklist': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M2 3h2v2H2V3zm0 4h2v2H2V7zm0 4h2v2H2v-2zm4-8h8v1H6V3zm0 4h8v1H6V7zm0 4h8v1H6v-1z"/></svg>',
    'dashboard': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 2a7 7 0 0 0-7 7c0 2 .8 3.8 2.1 5.1l.7-.7A6 6 0 1 1 14 9c0 1.7-.7 3.2-1.8 4.4l.7.7A7 7 0 0 0 8 2zm1 4H7v4.2l3 1.8.5-.9-2.5-1.5V6z"/></svg>',
    'rocket': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8.5 1.5C9.9 2.9 11 5 11 7l3 3-1 2-2-1-3 3c-2 0-4.1-1.1-5.5-2.5l2-2-1.5-1.5-1.5 1.5-1-1 3-3c0-2 1.1-4.1 2.5-5.5l2 2 1.5-1.5-1.5-1.5 1.5-1.5zM4 14l-2 1 1-2 1 1z"/></svg>',
    'map': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M10 2l-4 1.5L2 2v11l4-1.5L10 13l4-1.5V1l-4 1zM9 3.2v8.6l-3-1.1V2.1l3 1.1zm4 .8v8.2l-3 1.1V4.8l3-.8zM3 3.8l2 .7v8.7l-2-.7V3.8z"/></svg>',
    'search': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M11.5 7a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0zm-.8 3.9l3.6 3.6.7-.7-3.6-3.6a5.5 5.5 0 1 0-.7.7z"/></svg>',
    'book': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M14 2H3a2 2 0 0 0-2 2v9a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V3a1 1 0 0 0-1-1zm0 10H3a1 1 0 0 1 0-2h11v2zm0-3H3a2 2 0 0 0-1 .3V4a1 1 0 0 1 1-1h11v6z"/></svg>',
    'robot': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M7.5 1h1v2h-1V1zM3 4h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm0 1a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1H3zm3 2a1 1 0 1 1 0 2 1 1 0 0 1 0-2zm4 0a1 1 0 1 1 0 2 1 1 0 0 1 0-2zm-5 4h6v1H5v-1z"/></svg>',
    'extensions': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M11.5 2a2.5 2.5 0 0 0-2.4 1.8H6.5a2.5 2.5 0 0 0-4.7 1.4v2.6a2.5 2.5 0 0 0 1.8 2.4v2.3h2.3a2.5 2.5 0 0 0 2.4-1.8h2.6a2.5 2.5 0 0 0 2.4 1.8H15V9.7a2.5 2.5 0 0 0-1.8-2.4V4.7a2.5 2.5 0 0 0 1.8-2.4H11.5z"/></svg>',
    'wand': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M14.7.3a1 1 0 0 0-1.4 0L1 12.6l2.4 2.4L15.7 2.7a1 1 0 0 0 0-1.4L14.7.3zM10 5l1 1-7 7-1-1 7-7zM2 2l1 .5L3.5 4 4 3l1.5-.5L4 2l-.5-1.5L3 2H2zm8 8l.5 1 1 .5-1 .5-.5 1-.5-1-1-.5 1-.5.5-1z"/></svg>',
    'briefcase': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M14 4h-3V2a1 1 0 0 0-1-1H6a1 1 0 0 0-1 1v2H2a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1zM6 2h4v2H6V2zm8 4l-6 3.5L2 6V5h12v1zm0 7H2V7.2l6 3.5 6-3.5V13z"/></svg>',
    'design': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1a7 7 0 0 0-7 7c0 2.4 1.2 4.5 3 5.7V12a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1V9a2 2 0 0 1 2-2h1a2 2 0 0 1 2 2v.5a.5.5 0 0 0 1 0V9a3 3 0 0 0-3-3h-.5A2.5 2.5 0 0 1 7 3.5V2.1A6.98 6.98 0 0 0 8 1z"/></svg>',
    'build': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M4.7 3.3L1 7l3.7 3.7.7-.7L2.4 7l3-3-.7-.7zm6.6 0l-.7.7 3 3-3 3 .7.7L15 7l-3.7-3.7zM9.1 2l-3.5 12h1.1l3.5-12H9.1z"/></svg>',
    'test': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M14.5 13.5L10 4V2h1V1H5v1h1v2L1.5 13.5A1.5 1.5 0 0 0 2.8 15h10.4a1.5 1.5 0 0 0 1.3-1.5zM6.8 5l3.2 6.8H2.8L6 5.2V2h4v3.2L6.8 5z"/></svg>',
    'debug': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M15 8h-2.1a4.96 4.96 0 0 0-.6-2.1l1.5-1.5-.7-.7-1.7 1.7A4.95 4.95 0 0 0 9 4.1V2h1V1H6v1h1v2.1c-.8.1-1.6.4-2.4 1.1L3.9 3.5l-.7.7 1.5 1.5c-.3.7-.5 1.4-.6 2.3H1v1h2.1c0 .7.2 1.4.5 2l-1.5 1.5.7.7 1.7-1.7c.7.6 1.6.9 2.5 1v2H6v1h4v-1h-1v-2c.9-.1 1.8-.4 2.5-1l1.7 1.7.7-.7-1.5-1.5c.3-.6.5-1.3.5-2H15V8zM8 12c-1.7 0-3-1.3-3-3s1.3-3 3-3 3 1.3 3 3-1.3 3-3 3z"/></svg>',
    'secure': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1l6 2.5v4.8c0 4.2-3.3 7.2-6 7.7-2.7-.5-6-3.5-6-7.7V3.5L8 1zm0 1.1L3 4.2v4.1c0 3.5 2.7 6.1 5 6.6 2.3-.5 5-3.1 5-6.6V4.2L8 2.1z"/></svg>',
    'review': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M2 3h2v2H2V3zm0 4h2v2H2V7zm0 4h2v2H2v-2zm4-8h8v1H6V3zm0 4h8v1H6V7zm0 4h8v1H6v-1z"/></svg>',
    'speed': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 2a7 7 0 0 0-7 7c0 2 .8 3.8 2.1 5.1l.7-.7A6 6 0 1 1 14 9c0 1.7-.7 3.2-1.8 4.4l.7.7A7 7 0 0 0 8 2zm1 4H7v4.2l3 1.8.5-.9-2.5-1.5V6z"/></svg>',
    'deploy': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8.5 1.5C9.9 2.9 11 5 11 7l3 3-1 2-2-1-3 3c-2 0-4.1-1.1-5.5-2.5l2-2-1.5-1.5-1.5 1.5-1-1 3-3c0-2 1.1-4.1 2.5-5.5l2 2 1.5-1.5-1.5-1.5 1.5-1.5zM4 14l-2 1 1-2 1 1z"/></svg>',
    'plan': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M10 2l-4 1.5L2 2v11l4-1.5L10 13l4-1.5V1l-4 1zM9 3.2v8.6l-3-1.1V2.1l3 1.1zm4 .8v8.2l-3 1.1V4.8l3-.8zM3 3.8l2 .7v8.7l-2-.7V3.8z"/></svg>',
    'research': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M11.5 7a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0zm-.8 3.9l3.6 3.6.7-.7-3.6-3.6a5.5 5.5 0 1 0-.7.7z"/></svg>',
    'document': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M14 2H3a2 2 0 0 0-2 2v9a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V3a1 1 0 0 0-1-1zm0 10H3a1 1 0 0 1 0-2h11v2zm0-3H3a2 2 0 0 0-1 .3V4a1 1 0 0 1 1-1h11v6z"/></svg>',
    'create': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M14.7.3a1 1 0 0 0-1.4 0L1 12.6l2.4 2.4L15.7 2.7a1 1 0 0 0 0-1.4L14.7.3zM10 5l1 1-7 7-1-1 7-7zM2 2l1 .5L3.5 4 4 3l1.5-.5L4 2l-.5-1.5L3 2H2zm8 8l.5 1 1 .5-1 .5-.5 1-.5-1-1-.5 1-.5.5-1z"/></svg>',
    'business': '<svg class="purpose-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M14 4h-3V2a1 1 0 0 0-1-1H6a1 1 0 0 0-1 1v2H2a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1zM6 2h4v2H6V2zm8 4l-6 3.5L2 6V5h12v1zm0 7H2V7.2l6 3.5 6-3.5V13z"/></svg>',
  };

  const iconFor = (name) => PURPOSE_ICONS[name] || PURPOSE_ICONS.package;
  const $ = (id) => document.getElementById(id);
  const searchInput = $('lib-search-input');
  const searchClearBtn = $('lib-search-clear');
  const searchCountBadge = $('lib-search-count');
  const modeSwitch = $('lib-mode-switch');
  const groupsContainer = $('lib-groups-container');
  const newBundleBar = $('lib-new-bundle-bar');
  const footerCounts = $('lib-footer-counts');
  const stateLoading = $('lib-state-loading');
  const stateEmpty = $('lib-state-empty');
  const stateError = $('lib-state-error');

  const accentOf = (familyId) => {
    const i = (state.families || []).findIndex((f) => f.id === familyId);
    return i < 0 ? 0 : (i % 7) + 1;
  };
  const purposeName = (id) => ((state.purposes || []).find((p) => p.id === id) || {}).name || id || '';
  const clusterName = (id) => ((state.clusters || []).find((c) => c.id === id) || {}).name || id || '';
  const searching = () => Boolean(state.query && state.query.trim());

  // ---- input
  let searchTimeout = null;
  searchInput.addEventListener('input', () => {
    const q = searchInput.value;
    searchClearBtn.classList.toggle('hidden', q.length === 0);
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      state.query = q;
      vscode.postMessage({ command: 'search', query: q, mode: state.mode });
    }, 80);
  });
  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      clearSearch();
      e.preventDefault();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      const first = groupsContainer.querySelector('button, [tabindex="0"]');
      if (first) first.focus();
    }
  });
  function clearSearch() {
    searchInput.value = '';
    state.query = '';
    searchClearBtn.classList.add('hidden');
    vscode.postMessage({ command: 'search', query: '', mode: state.mode });
  }
  searchClearBtn.addEventListener('click', () => { clearSearch(); searchInput.focus(); });

  function setMode(mode) {
    state.mode = mode;
    paintModes();
    vscode.postMessage({ command: 'switchMode', mode, query: state.query });
  }
  function paintModes() {
    modeSwitch.querySelectorAll('.mode-btn').forEach((b) => {
      const on = b.getAttribute('data-mode') === state.mode;
      b.classList.toggle('active', on);
      b.setAttribute('aria-checked', on ? 'true' : 'false');
      b.setAttribute('tabindex', on ? '0' : '-1');
    });
    newBundleBar.classList.toggle('hidden', state.mode !== 'bundle');
  }
  modeSwitch.addEventListener('click', (e) => {
    const btn = e.target.closest('.mode-btn');
    if (btn && btn.getAttribute('data-mode') !== state.mode) setMode(btn.getAttribute('data-mode'));
  });
  modeSwitch.addEventListener('keydown', (e) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step && e.key !== 'Home' && e.key !== 'End') return;
    let i = MODES.indexOf(state.mode);
    i = e.key === 'Home' ? 0 : e.key === 'End' ? MODES.length - 1 : (i + step + MODES.length) % MODES.length;
    setMode(MODES[i]);
    const b = modeSwitch.querySelector(`.mode-btn[data-mode="${MODES[i]}"]`);
    if (b) b.focus();
    e.preventDefault();
  });
  $('lib-new-bundle-btn').addEventListener('click', () => vscode.postMessage({ command: 'newBundle' }));
  $('lib-refresh-btn').addEventListener('click', () => { showLoading(true); vscode.postMessage({ command: 'refresh' }); });
  $('lib-error-btn').addEventListener('click', () => vscode.postMessage({ command: 'openSettings' }));

  groupsContainer.addEventListener('click', (e) => {
    const act = e.target.closest('[data-action]');
    if (act) {
      const a = act.getAttribute('data-action');
      const skill = act.getAttribute('data-skill');
      const bundleId = act.getAttribute('data-bundle');
      if (a === 'toggle') return toggle(act.getAttribute('data-id'));
      if (skill && ['openDetail', 'openSkill', 'pinSkill', 'addToBundle'].includes(a)) vscode.postMessage({ command: a, skill });
      else if (bundleId && ['applyBundle', 'copyPrompt', 'editBundle', 'deleteBundle'].includes(a)) vscode.postMessage({ command: a, bundleId });
      e.stopPropagation();
      return;
    }
    const row = e.target.closest('.skill-row');
    if (row) vscode.postMessage({ command: 'openDetail', skill: row.getAttribute('data-skill') });
  });
  groupsContainer.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.classList.contains('skill-row')) {
      vscode.postMessage({ command: 'openDetail', skill: e.target.getAttribute('data-skill') });
    }
  });

  function toggle(id) {
    if (state.open.has(id)) state.open.delete(id);
    else state.open.add(id);
    remember();
    renderGroups();
    const el = groupsContainer.querySelector(`[data-id="${CSS.escape(id)}"]`);
    if (el) el.focus();
  }
  const isOpen = (id) => searching() || state.open.has(id);

  function showLoading(on) {
    state.loading = on;
    stateLoading.classList.toggle('hidden', !on);
  }

  // ---- drawing
  function renderView() {
    showLoading(false);
    paintModes();
    if (state.error) {
      stateError.classList.remove('hidden');
      $('lib-error-msg').textContent = state.error;
      groupsContainer.innerHTML = '';
      stateEmpty.classList.add('hidden');
      return;
    }
    stateError.classList.add('hidden');
    searchCountBadge.textContent = searching() ? `${state.matchCount} of ${state.totalCount} skills` : `${state.totalCount} skills`;
    const any = state.groups.some((g) => (g.skills && g.skills.length) || (g.bundles && g.bundles.length));
    stateEmpty.classList.toggle('hidden', any);
    if (!any) { groupsContainer.innerHTML = ''; } else { renderGroups(); }
    if (state.summary) {
      const s = state.summary;
      footerCounts.textContent = `${s.skills} skills · ${s.bundles} bundles · ${s.used} used`;
    }
  }

  function renderGroups() {
    let html = '';
    let lastFamily = null;
    for (const g of state.groups) {
      if (!((g.skills && g.skills.length) || (g.bundles && g.bundles.length))) continue;
      if ((state.mode === 'bundle' || state.mode === 'cluster') && g.family !== lastFamily) {
        lastFamily = g.family;
        const f = state.families.find((x) => x.id === g.family);
        if (f) html += `<div class="area-heading" data-accent="${accentOf(f.id)}">${iconFor(f.icon)}<span>${escapeHtml(f.name)}</span></div>`;
      }
      html += state.mode === 'family' ? renderFamily(g) : state.mode === 'bundle' ? renderBundle(g.bundle, true) : renderPlainGroup(g);
    }
    groupsContainer.innerHTML = html;
  }

  const countText = (g) => (searching() ? `${g.skills.length} of ${g.total}` : `${g.total}`);

  function renderFamily(g) {
    const open = isOpen('f:' + g.id);
    const bundles = (g.bundles || []);
    const topics = (g.children || []).filter((c) => c.skills && c.skills.length);
    const body = open
      ? `<div class="area-body">
          ${bundles.length ? `<div class="section-label">Bundles</div>${bundles.map((b) => renderBundle(b, false)).join('')}` : ''}
          ${topics.length ? `<div class="section-label">Skills</div>${topics.map((c) => renderPlainGroup(c, true)).join('')}` : ''}
        </div>`
      : '';
    const sub = `${g.total}`;
    return `
      <section class="area ${open ? 'open' : ''}" data-accent="${accentOf(g.id)}">
        <button class="area-head" data-action="toggle" data-id="f:${escapeHtml(g.id)}" aria-expanded="${open}" title="${escapeHtml(g.blurb || '')}">
          <span class="area-icon">${iconFor(g.icon)}</span>
          <span class="area-text">
            <span class="area-name">${escapeHtml(g.name)}</span>
            <span class="area-blurb">${escapeHtml(g.blurb || '')}</span>
          </span>
          <span class="area-meta">${escapeHtml(searching() ? `${g.skills.length} of ${g.total}` : sub)}</span>
          ${ICONS.chevron}
        </button>
        ${body}
      </section>`;
  }

  function renderPlainGroup(g, nested) {
    const id = (nested ? 'c:' : 'g:') + g.id;
    const open = isOpen(id);
    const icon = state.mode === 'purpose' ? `<span class="group-icon">${iconFor(g.icon)}</span>` : '';
    return `
      <div class="group ${open ? 'open' : ''} ${nested ? 'nested' : ''}">
        <button class="group-head" data-action="toggle" data-id="${escapeHtml(id)}" aria-expanded="${open}" title="${escapeHtml(g.description || g.name)}">
          ${ICONS.chevron}${icon}
          <span class="group-title">${escapeHtml(g.name)}</span>
          <span class="count">${escapeHtml(countText(g))}</span>
        </button>
        ${open ? `<div class="group-body">${renderSkillRows(g.skills)}</div>` : ''}
      </div>`;
  }

  function renderSkillRows(names) {
    return names.map((name) => {
      const s = state.skills[name] || {};
      const hit = state.hitsMap.get(name);
      const used = s.usage && s.usage.chosen > 0 ? `<span class="tag tag-used" title="Chosen ${escapeHtml(s.usage.chosen)} times">used ${escapeHtml(s.usage.chosen)}</span>` : '';
      const app = s.app ? `<span class="tag tag-app" title="Needs the program ${escapeHtml(s.app)}">needs a program</span>` : '';
      const n = escapeHtml(name);
      return `
        <div class="skill-row" tabindex="0" data-skill="${n}" title="Click for details">
          <div class="skill-main">
            <span class="skill-name">${highlightName(name, hit ? hit.marks : undefined)}</span>
            <span class="skill-sub">${escapeHtml(purposeName(s.purpose))}${s.cluster ? ' · ' + escapeHtml(clusterName(s.cluster)) : ''}</span>
          </div>
          <div class="skill-tags">${used}${app}</div>
          <div class="skill-actions">
            <button class="icon-btn" data-action="openDetail" data-skill="${n}" aria-label="Details of ${n}" title="Details">${ICONS.info}</button>
            <button class="icon-btn" data-action="pinSkill" data-skill="${n}" aria-label="Pin ${n} to the task" title="Pin to the current task">${ICONS.pin}</button>
            <button class="icon-btn" data-action="addToBundle" data-skill="${n}" aria-label="Add ${n} to a bundle" title="Add to a bundle">${ICONS.plus}</button>
          </div>
        </div>`;
    }).join('');
  }

  function renderBundle(b, standalone) {
    if (!b) return '';
    const id = 'b:' + b.id;
    const open = isOpen(id);
    const mine = b.mine ? '<span class="tag tag-mine">yours</span>' : '';
    const chips = (b.skills || []).map((s, i) => `<button class="chip" data-action="openDetail" data-skill="${escapeHtml(s)}" title="Step ${i + 1}: ${escapeHtml(s)}"><span class="chip-num">${i + 1}</span>${escapeHtml(s)}</button>`).join('');
    const own = b.mine
      ? `<button class="btn" data-action="editBundle" data-bundle="${escapeHtml(b.id)}">Edit</button><button class="btn btn-danger" data-action="deleteBundle" data-bundle="${escapeHtml(b.id)}">Delete</button>`
      : '';
    const body = open
      ? `<div class="bundle-body">
          <p class="bundle-goal">${escapeHtml(b.goal)}</p>
          ${b.when ? `<p class="bundle-when"><b>Use it when</b> ${escapeHtml(b.when)}</p>` : ''}
          <div class="chips">${chips}</div>
          <div class="bundle-foot"><span class="tokens">about ${escapeHtml(b.tokens)} tokens</span></div>
          <div class="bundle-actions">
            <button class="btn btn-primary" data-action="applyBundle" data-bundle="${escapeHtml(b.id)}">Apply to task</button>
            <button class="btn" data-action="copyPrompt" data-bundle="${escapeHtml(b.id)}">Copy prompt</button>${own}
          </div>
        </div>`
      : '';
    return `
      <div class="bundle ${open ? 'open' : ''} ${standalone ? 'standalone' : ''}" data-accent="${accentOf(b.family)}">
        <button class="bundle-head" data-action="toggle" data-id="${escapeHtml(id)}" aria-expanded="${open}" title="${escapeHtml(b.goal)}">
          ${ICONS.chevron}
          <span class="bundle-icon">${ICONS.stack}</span>
          <span class="bundle-text"><span class="bundle-name">${escapeHtml(b.name)}</span>${mine}
            <span class="bundle-sub">${escapeHtml(purposeName(b.purpose))}</span></span>
          <span class="count">${escapeHtml((b.skills || []).length)} steps</span>
        </button>
        ${body}
      </div>`;
  }

  // ---- messages from the extension
  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg) return;
    if (msg.type === 'update') {
      state.mode = msg.mode || state.mode;
      state.groups = msg.groups || [];
      state.summary = msg.summary || state.summary;
      state.skills = msg.skills || state.skills;
      state.families = msg.families || state.families;
      state.purposes = msg.purposes || state.purposes;
      state.clusters = msg.clusters || state.clusters;
      state.bundles = msg.bundles || state.bundles;
      state.totalCount = msg.counts ? msg.counts.skills : state.totalCount;
      state.matchCount = state.totalCount;
      state.hitsMap.clear();
      state.error = msg.error || null;
      renderView();
    } else if (msg.type === 'searchResults') {
      state.mode = msg.mode || state.mode;
      state.query = msg.query ?? state.query;
      state.groups = msg.groups || [];
      state.matchCount = msg.matchCount ?? state.totalCount;
      state.totalCount = msg.totalCount ?? state.totalCount;
      state.hitsMap.clear();
      if (Array.isArray(msg.hits)) for (const h of msg.hits) state.hitsMap.set(h.name, h);
      renderView();
    } else if (msg.type === 'error') {
      state.error = msg.message || 'Something went wrong.';
      renderView();
    }
  });

  vscode.postMessage({ command: 'ready' });
})();
