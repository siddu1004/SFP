// Skill detail window: posts what was clicked; the extension does the work.
(function () {
  const vscode = acquireVsCodeApi();
  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    vscode.postMessage({ command: el.getAttribute('data-action'), skill: el.getAttribute('data-skill'), bundle: el.getAttribute('data-bundle') });
  });
})();
