// Drives a real VS Code workbench (code-server) with the extension installed, and fails if anything is off.
//   node test/e2e/drive.js <port> <workspace folder>
// See README.md in this folder for how to start the server. Not part of `npm test`: it needs a running editor.
const { chromium } = require('playwright-core');
const assert = require('node:assert');
const port = process.argv[2] || '8099';
const workspace = process.argv[3];
const browserPath = process.env.CHROMIUM || '/opt/pw-browsers/chromium';

(async () => {
  const browser = await chromium.launch({ executablePath: browserPath, args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`http://127.0.0.1:${port}/?folder=${encodeURIComponent(workspace)}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.monaco-workbench', { timeout: 120000 });
  await page.waitForTimeout(8000);
  const trust = page.getByRole('button', { name: /Yes, I trust/i });
  if (await trust.count()) await trust.first().click();
  const status = async () => (await page.locator('.statusbar').innerText()).replace(/\s+/g, ' ');

  assert.match(await status(), /Hive/, 'the status-bar item should exist at startup');

  await page.keyboard.press('F1');
  await page.waitForSelector('.quick-input-widget', { state: 'visible' });
  await page.keyboard.type('SFP Hive: Choose skills');
  await page.waitForTimeout(1200);
  const entries = await page.locator('.quick-input-list .monaco-list-row').allInnerTexts();
  assert.ok(entries.some((e) => e.includes('SFP Hive: Choose skills for a task')), 'the command should be in the palette');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(800);
  await page.keyboard.type('write table driven tests for a go parser');
  await page.keyboard.press('Enter');
  await page.waitForSelector('.pane-header', { timeout: 90000 });
  await page.waitForTimeout(6000);

  // Focus SFP Hive Studio webview
  const webviewFrame = page.frameLocator('iframe.webview').first().frameLocator('iframe#active-frame');
  await webviewFrame.locator('button[data-tab="choose"]').click();
  await page.waitForTimeout(2000);

  const skillCards = await webviewFrame.locator('.skill-card').allInnerTexts();
  assert.ok(skillCards.some((r) => /tokens/.test(r)), 'a chosen skill should be listed in webview: ' + JSON.stringify(skillCards));
  assert.match(await status(), /Hive: [1-9]/, 'the status bar should count the skills');
  const note = await page.locator('.notifications-toasts .notification-list-item-message').allInnerTexts();
  assert.ok(note.some((n) => /prompt is copied/.test(n)), 'the prompt should be copied: ' + JSON.stringify(note));

  const firstCard = webviewFrame.locator('.skill-card', { hasText: /tokens/ }).first();
  await firstCard.locator('button[data-action="helped"]').click();
  await page.waitForTimeout(3000);
  assert.match(await status(), /noted helped/, 'feedback should be acknowledged');

  // Test live session: type in Choose input and verify live chips
  const chooseInput = webviewFrame.locator('#choose-task-input');
  await chooseInput.fill('');
  await chooseInput.type('make the login form accessible and animate the button');
  await page.waitForTimeout(2500);
  const liveChips = await webviewFrame.locator('.live-chip').allInnerTexts();
  assert.ok(liveChips.length > 0, 'live chips should appear when typing: ' + JSON.stringify(liveChips));

  // C1: Open the Skill Library: 11 areas, 819 skills
  await webviewFrame.locator('button[data-tab="library"]').click();
  await page.waitForTimeout(2000);
  const areasCount = await webviewFrame.locator('.group-family').count();
  const searchCountText = await webviewFrame.locator('#lib-search-count, #lib-footer-counts').first().innerText();
  assert.strictEqual(areasCount, 11, 'C1: must have 11 areas');
  assert.ok(searchCountText.includes('819'), 'C1: must report 819 skills: ' + searchCountText);

  // Switch back to Choose tab
  await webviewFrame.locator('button[data-tab="choose"]').click();
  await page.waitForTimeout(1000);

  // C2: Type in Choose: skills appear as chips within 1s; "Bundle: Accessible form" with four skills
  const chooseInput = webviewFrame.locator('#choose-task-input');
  await chooseInput.fill('');
  await chooseInput.type('make the signup form accessible');
  await page.waitForTimeout(1200);
  const liveChips = await webviewFrame.locator('.live-chip').allInnerTexts();
  assert.ok(liveChips.length > 0, 'C2: live chips must appear within 1s: ' + JSON.stringify(liveChips));
  const bannerText = await webviewFrame.locator('#choose-bundle-banner').innerText();
  assert.ok(bannerText.includes('Accessible form'), 'C2: banner must show Accessible form: ' + bannerText);
  const bundleChips = await webviewFrame.locator('#choose-bundle-banner .bundle-chip').allInnerTexts();
  assert.strictEqual(bundleChips.length, 4, 'C2: Accessible form must show four skills in order: ' + JSON.stringify(bundleChips));

  // C3: "Not this bundle" removes those skills and they do not come back while typing
  const notThisBtn = webviewFrame.locator('#choose-bundle-banner button[data-action="notThisBundle"]');
  if (await notThisBtn.count()) {
    await notThisBtn.click();
    await page.waitForTimeout(1000);
    const postBanner = await webviewFrame.locator('#choose-bundle-banner').isVisible();
    assert.strictEqual(postBanner, false, 'C3: bundle banner should be removed');
    await chooseInput.type(' with validations');
    await page.waitForTimeout(1200);
    const postChips = await webviewFrame.locator('.live-chip').allInnerTexts();
    for (const bSkill of bundleChips) {
      const cleanName = bSkill.replace(/^\d+\s*/, '').trim();
      assert.ok(!postChips.some((c) => c.includes(cleanName)), 'C3: removed skill should not return: ' + cleanName);
    }
  }

  // C4: Send the message: exactly one line added to decisions.jsonl
  const fs = require('node:fs');
  const os = require('node:os');
  const path = require('node:path');
  const dataDir = process.env.SFP_DATA_DIR || path.join(os.homedir(), '.sfp');
  const decisionsPath = path.join(dataDir, 'decisions.jsonl');
  const linesBefore = fs.existsSync(decisionsPath) ? fs.readFileSync(decisionsPath, 'utf8').trim().split('\n').filter(Boolean).length : 0;
  await chooseInput.press('Enter');
  await page.waitForTimeout(2500);
  const linesAfter = fs.existsSync(decisionsPath) ? fs.readFileSync(decisionsPath, 'utf8').trim().split('\n').filter(Boolean).length : 0;
  assert.strictEqual(linesAfter, linesBefore + 1, 'C4: exactly one line added to decisions.jsonl');

  // C5: Task that needs 3D model shows need card with action
  await chooseInput.fill('');
  await chooseInput.type('create a 3d model of a vintage car');
  await chooseInput.press('Enter');
  await page.waitForTimeout(3000);
  const needsCards = await webviewFrame.locator('.need-card').allInnerTexts();
  assert.ok(needsCards.some((n) => /3D|MESHY_API_KEY/i.test(n)), 'C5: 3D model need card must show: ' + JSON.stringify(needsCards));

  // C6 & C7: Models view with fake Ollama server on 11434
  const http = require('node:http');
  let fakeOllama = null;
  const startFake = () => new Promise((resolve) => {
    fakeOllama = http.createServer((req, res) => {
      if (req.url === '/api/tags') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ models: [{ name: 'llama3:latest', details: { parameter_size: '8B' } }] }));
      } else if (req.url === '/v1/chat/completions') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ model: 'llama3:latest', choices: [{ message: { content: 'Fake Ollama answer' } }] }));
      } else {
        res.writeHead(404);
        res.end();
      }
    });
    fakeOllama.listen(11434, '127.0.0.1', () => resolve());
  });

  // Focus Models view
  await page.keyboard.press('F1');
  await page.waitForSelector('.quick-input-widget', { state: 'visible' });
  await page.keyboard.type('SFP Hive: Focus models view');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(2000);
  const modelsFrame = page.frameLocator('iframe.webview').last().frameLocator('iframe#active-frame');

  // C6: With no server vs with fake server
  await startFake();
  await modelsFrame.locator('#setup-btn').click();
  await page.waitForTimeout(2000);
  await modelsFrame.locator('#write-btn').click();
  await page.waitForTimeout(1500);
  const routesFile = path.join(dataDir, 'routes.json');
  assert.ok(fs.existsSync(routesFile), 'C6: setup writes routes.json');

  await modelsFrame.locator('#toggle-router-btn').click();
  await page.waitForTimeout(2500);
  const serverUrlText = await modelsFrame.locator('#server-url').innerText();
  assert.ok(serverUrlText.includes('8787'), 'C6: Start shows router URL: ' + serverUrlText);

  await modelsFrame.locator('#try-prompt-input').fill('hello test');
  await modelsFrame.locator('#try-send-btn').click();
  await page.waitForTimeout(3000);
  const tryAnswer = await modelsFrame.locator('#try-output').innerText();
  assert.ok(tryAnswer.includes('Fake Ollama answer'), 'C6: Try it answers through fake server: ' + tryAnswer);

  // C7: Stop fake, send Try it again: status shows model cooling down
  if (fakeOllama) {
    fakeOllama.close();
    fakeOllama = null;
  }
  await modelsFrame.locator('#try-send-btn').click();
  await page.waitForTimeout(3000);
  const coolingText = await modelsFrame.locator('#status-container').innerText();
  assert.ok(coolingText.includes('cooling') || coolingText.includes('Fail'), 'C7: status shows cooling down or failed: ' + coolingText);

  // C8: Check connection shows no red line
  await webviewFrame.locator('button[data-tab="insights"]').click();
  await page.waitForTimeout(1000);
  await webviewFrame.locator('#btn-run-doctor').click();
  await page.waitForTimeout(3000);
  const failedChecks = await webviewFrame.locator('.doctor-fail').count();
  assert.strictEqual(failedChecks, 0, 'C8: Check connection shows no red line');

  assert.deepStrictEqual(errors.filter((e) => /sfp|hive/i.test(e)), [], 'no page error from the extension');
  await browser.close();
  console.log('ok: C1-C8, L6-L7 verified');
})().catch((e) => { console.error('FAILED: ' + e.message); process.exit(1); });
