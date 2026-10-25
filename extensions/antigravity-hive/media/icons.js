// SFP Hive Icons - Small inline SVGs in one file
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.SFPIcons = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  return {
    now: '<svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M1 8.5h3.2l1.6-4.5 3.4 9 2.1-5.5H15v-1h-4.2l-1.6 4.2-3.4-9-2.1 6.8H1v1z"/></svg>',
    choose: '<svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M11.5 7a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0zm-.8 3.9l3.6 3.6.7-.7-3.6-3.6a5.5 5.5 0 1 0-.7.7z"/></svg>',
    library: '<svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M3 2v12h10V2H3zm9 11H4V3h8v10zM5 5h6v1H5V5zm0 3h6v1H5V8zm0 3h4v1H5v-1z"/></svg>',
    insights: '<svg class="tab-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M1 14h14v1H1v-1zm2-2h2V7H3v5zm4 0h2V3H7v9zm4 0h2V5h-2v7z"/></svg>',
    refresh: '<svg viewBox="0 0 16 16"><path fill="currentColor" d="M13.6 2.4A7 7 0 1 0 15 8h-1.5a5.5 5.5 0 1 1-1.1-4.4L10 6h5V1l-1.4 1.4z"/></svg>',
    info: '<svg viewBox="0 0 16 16"><path fill="currentColor" d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 13a6 6 0 1 1 0-12 6 6 0 0 1 0 12zm-.5-9h1v2h-1V5zm0 3h1v4h-1V8z"/></svg>',
    search: '<svg viewBox="0 0 16 16"><path fill="currentColor" d="M11.5 7a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0zm-.8 3.9l3.6 3.6.7-.7-3.6-3.6a5.5 5.5 0 1 0-.7.7z"/></svg>',
    loading: '<svg class="spin-icon" viewBox="0 0 16 16"><path fill="currentColor" d="M8 1.5a6.5 6.5 0 1 0 6.5 6.5h-1.5A5 5 0 1 1 8 3v-1.5z"/></svg>',
    warning: '<svg viewBox="0 0 16 16"><path fill="currentColor" d="M8.865 1.52c-.418-.723-1.312-.723-1.73 0L.14 13.56c-.418.723.03 1.64.865 1.64h14c.836 0 1.283-.917.865-1.64L8.865 1.52zM8 4a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 8 4zm0 8.5a1 1 0 1 1 0-2 1 1 0 0 1 0 2z"/></svg>'
  };
});
