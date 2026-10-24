// Real VS Code check of the Library tab in the SFP Hive studio: it loads, groups by area, searches, opens a skill's detail
// tab, shows bundles, and switches modes. Usage: node test/e2e/library-tab.js <port> <workspace> [screenshot-prefix]
// (start code-server with the extension installed first: see README.md in this folder).
const { chromium } = require('playwright-core');
const assert = require('node:assert');

(async () => {
  const [port, workspace, shots] = [process.argv[2] || '8099', process.argv[3], process.argv[4]];
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || '/opt/pw-browsers/chromium' });
  const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
  await page.goto(`http://127.0.0.1:${port}/?folder=${encodeURIComponent(workspace)}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.monaco-workbench', { timeout: 120000 });
  await page.waitForTimeout(12000);
  await page.locator('[aria-label*="SFP Hive"]').first().click().catch(() => {});
  await page.waitForTimeout(4000);
  const find = async (sel) => { for (const f of page.frames()) { try { if (await f.locator(sel).count()) return f; } catch (e) { /* frame gone */ } } throw new Error('no frame has ' + sel); };
  const studio = await find('.tab-btn');
  await studio.locator('.tab-btn[data-tab="library"]').click();
  await page.waitForFunction(() => true);
  const lib = async () => { const f = await find('#lib-groups-container'); return f; };
  let f = await lib();
  await f.waitForFunction(() => document.querySelectorAll('#lib-groups-container .area').length >= 8, null, { timeout: 30000 });
  const count = await f.locator('#lib-search-count').innerText();
  assert.match(count, /819 skills/, 'the library should say how many skills it has: ' + count);
  assert.ok((await f.locator('#lib-groups-container .area').count()) >= 8, 'areas should be listed');
  if (shots) await page.screenshot({ path: shots + '-areas.png' });

  await f.locator('#lib-search-input').fill('docker');
  await f.waitForFunction(() => /of 819/.test(document.getElementById('lib-search-count').textContent), null, { timeout: 15000 });
  assert.ok((await f.locator('.skill-row').count()) > 0, 'searching should list skills');
  assert.ok((await f.locator('mark').count()) > 0, 'the matching letters should be highlighted');
  if (shots) await page.screenshot({ path: shots + '-search.png' });

  await f.locator('.skill-row').first().click();
  await page.waitForTimeout(5000);
  const tabTitles = await page.locator('.tab .label-name').allInnerTexts();
  assert.ok(tabTitles.length >= 2, 'a skill detail tab should open: ' + JSON.stringify(tabTitles));
  if (shots) await page.screenshot({ path: shots + '-detail.png' });

  await f.locator('#lib-search-clear').click();
  await f.locator('.mode-btn[data-mode="bundle"]').click();
  await f.waitForFunction(() => document.querySelectorAll('#lib-groups-container .bundle').length >= 10, null, { timeout: 15000 });
  await f.locator('.bundle-head').first().click();
  assert.ok((await f.locator('[data-action="applyBundle"]').count()) > 0, 'an opened bundle should offer Apply');
  if (shots) await page.screenshot({ path: shots + '-bundles.png' });

  await browser.close();
  console.log('library tab: all checks passed');
})().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });
