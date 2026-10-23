(function () {
  const vscode = acquireVsCodeApi();

  const promptInput = document.getElementById('promptInput');
  const projectTagsContainer = document.getElementById('projectTags');
  const diffContainer = document.getElementById('diffContainer');
  const diffChips = document.getElementById('diffChips');
  const tokenCountEl = document.getElementById('tokenCount');
  const tokenFillEl = document.getElementById('tokenFill');
  const baseSkillsContainer = document.getElementById('baseSkills');
  const checkSkillsContainer = document.getElementById('checkSkills');
  const finishSkillsContainer = document.getElementById('finishSkills');
  const baseCountEl = document.getElementById('baseCount');
  const checkCountEl = document.getElementById('checkCount');
  const finishCountEl = document.getElementById('finishCount');
  const emptyState = document.getElementById('emptyState');
  const copyStackBtn = document.getElementById('copyStackBtn');
  const trainBtn = document.getElementById('trainBtn');

  let debounceTimer = null;
  let currentStack = [];
  let userExcluded = new Set();
  let currentDecisionId = null;

  // Handle typing in prompt
  promptInput.addEventListener('input', (e) => {
    clearTimeout(debounceTimer);
    const text = e.target.value.trim();
    debounceTimer = setTimeout(() => {
      vscode.postMessage({
        command: 'promptChanged',
        text: text
      });
    }, 250);
  });

  copyStackBtn.addEventListener('click', () => {
    vscode.postMessage({
      command: 'copyStack',
      skills: currentStack.filter(s => !userExcluded.has(s.name)).map(s => s.name)
    });
  });

  trainBtn.addEventListener('click', () => {
    trainBtn.innerText = '⏳ Training...';
    vscode.postMessage({ command: 'train' });
  });

  // Handle messages sent from the extension host
  window.addEventListener('message', (event) => {
    const message = event.data;
    switch (message.command) {
      case 'updateState':
        renderState(message.payload);
        break;
      case 'trainingFinished':
        trainBtn.innerText = '⚡ Train Model';
        break;
    }
  });

  function renderState(payload) {
    const { res, diff, excluded, initialPrompt } = payload;
    if (initialPrompt && !promptInput.value) {
      promptInput.value = initialPrompt;
    }

    userExcluded = new Set(excluded || []);

    if (!res || !res.stack || res.stack.length === 0) {
      emptyState.style.display = 'block';
      baseSkillsContainer.innerHTML = '';
      checkSkillsContainer.innerHTML = '';
      finishSkillsContainer.innerHTML = '';
      baseCountEl.innerText = '0';
      checkCountEl.innerText = '0';
      finishCountEl.innerText = '0';
      tokenCountEl.innerText = '0 / 12,000';
      tokenFillEl.style.width = '0%';
      diffContainer.style.display = 'none';
      return;
    }

    emptyState.style.display = 'none';
    currentStack = res.stack;
    currentDecisionId = res.decision;

    // Render project evidence tags
    if (res.project && res.project.technologies) {
      projectTagsContainer.innerHTML = res.project.technologies
        .map(t => `<span class="project-tag">${escapeHtml(t)}</span>`)
        .join('');
    }

    // Render dynamic additions/subtractions diff
    if (diff && (diff.added.length > 0 || diff.removed.length > 0)) {
      diffContainer.style.display = 'block';
      let chipsHtml = '';
      diff.added.forEach(s => {
        chipsHtml += `<span class="diff-chip added">+ ${escapeHtml(s)}</span>`;
      });
      diff.removed.forEach(s => {
        chipsHtml += `<span class="diff-chip removed">- ${escapeHtml(s)}</span>`;
      });
      diffChips.innerHTML = chipsHtml;
    } else {
      diffContainer.style.display = 'none';
    }

    // Render token budget
    const tokens = res.tokens || 0;
    const maxBudget = 12000;
    const pct = Math.min(100, Math.round((tokens / maxBudget) * 100));
    tokenCountEl.innerText = `${tokens.toLocaleString()} / ${maxBudget.toLocaleString()} tokens`;
    tokenFillEl.style.width = `${pct}%`;
    tokenFillEl.style.background = pct > 80 ? '#ef4444' : pct > 50 ? '#f59e0b' : '#10b981';

    // Render layers
    const baseList = res.stack.filter(s => s.layer === 'base');
    const checkList = res.stack.filter(s => s.layer === 'check');
    const finishList = res.stack.filter(s => s.layer === 'finish');

    baseCountEl.innerText = String(baseList.length);
    checkCountEl.innerText = String(checkList.length);
    finishCountEl.innerText = String(finishList.length);

    baseSkillsContainer.innerHTML = renderSkillCards(baseList);
    checkSkillsContainer.innerHTML = renderSkillCards(checkList);
    finishSkillsContainer.innerHTML = renderSkillCards(finishList);

    attachCardListeners();
  }

  function renderSkillCards(skills) {
    if (!skills.length) {
      return '<div style="font-size: 11px; color: var(--text-muted); padding: 4px 0;">No active skills in this layer.</div>';
    }
    return skills.map(skill => {
      const isExcluded = userExcluded.has(skill.name);
      const scorePct = Math.round(skill.score * 100);
      const reasons = (skill.reasons || []).map(r => `<span class="reason-tag">${escapeHtml(r)}</span>`).join('');

      return `
        <div class="skill-card ${isExcluded ? 'excluded' : ''}" data-skill="${escapeHtml(skill.name)}">
          <div class="skill-card-top">
            <div class="skill-name-row">
              <input type="checkbox" class="skill-toggle" ${!isExcluded ? 'checked' : ''} data-skill="${escapeHtml(skill.name)}" />
              <span class="skill-name" data-path="${escapeHtml(skill.path)}" title="Click to view SKILL.md">${escapeHtml(skill.name)}</span>
              <span class="skill-cat">${escapeHtml(skill.category)}</span>
            </div>
            <div class="skill-score">${scorePct}%</div>
          </div>
          <div class="skill-reasons">${reasons}</div>
          <div class="skill-card-bottom">
            <span class="token-cost">${(skill.tokens || 0).toLocaleString()} tokens (${escapeHtml(skill.phase)})</span>
            <div class="feedback-buttons">
              <button class="fb-btn help-btn" data-skill="${escapeHtml(skill.name)}" title="Skill helped">👍</button>
              <button class="fb-btn unhelp-btn" data-skill="${escapeHtml(skill.name)}" title="Skill was unhelpful">👎</button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  function attachCardListeners() {
    // Checkbox toggle
    document.querySelectorAll('.skill-toggle').forEach(input => {
      input.addEventListener('change', (e) => {
        const skill = e.target.getAttribute('data-skill');
        const enabled = e.target.checked;
        vscode.postMessage({
          command: 'toggleSkill',
          skill: skill,
          enabled: enabled
        });
      });
    });

    // Skill name click to open file in editor
    document.querySelectorAll('.skill-name').forEach(el => {
      el.addEventListener('click', (e) => {
        const p = e.target.getAttribute('data-path');
        vscode.postMessage({
          command: 'openSkillFile',
          path: p
        });
      });
    });

    // Feedback buttons
    document.querySelectorAll('.help-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const skill = e.target.getAttribute('data-skill');
        btn.classList.add('active-help');
        vscode.postMessage({
          command: 'feedback',
          decisionId: currentDecisionId,
          skill: skill,
          verdict: 'helped'
        });
      });
    });

    document.querySelectorAll('.unhelp-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const skill = e.target.getAttribute('data-skill');
        btn.classList.add('active-unhelp');
        vscode.postMessage({
          command: 'feedback',
          decisionId: currentDecisionId,
          skill: skill,
          verdict: 'unhelpful'
        });
      });
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Request initial state
  vscode.postMessage({ command: 'ready' });
})();
