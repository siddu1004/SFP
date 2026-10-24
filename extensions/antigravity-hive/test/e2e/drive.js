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

  assert.deepStrictEqual(errors.filter((e) => /sfp|hive/i.test(e)), [], 'no page error from the extension');
  await browser.close();
  console.log('ok: activated at startup, command in palette, skills listed in webview, prompt copied, feedback sent, live chips verified');
})().catch((e) => { console.error('FAILED: ' + e.message); process.exit(1); });
