// Screenshot index.html at desktop and phone width: node shot.js <dir>
const { chromium } = require('playwright-core');
(async () => {
  const dir = process.argv[2];
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  for (const [name, w, h] of [['desktop', 1280, 800], ['mobile', 375, 812]]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    await p.goto('file://' + dir + '/index.html', { waitUntil: 'load' });
    await p.waitForTimeout(400);
    await p.screenshot({ path: dir + '/' + name + '.png', fullPage: true });
    await p.close();
  }
  await b.close();
})().catch((e) => { console.error(e.message); process.exit(1); });
