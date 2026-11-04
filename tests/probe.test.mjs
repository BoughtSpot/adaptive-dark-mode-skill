// Runtime tests for skills/adaptive-dark-mode/scripts/probe.js and probe.mjs.
// Run from the repository root:  npm run test:probe   (needs `npm install` + `npx playwright install chromium webkit`)
// Browsers to test: PROBE_BROWSERS=chromium,webkit (default both).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { readFile, mkdtemp, readdir, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { chromium, webkit } from 'playwright';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures');
const SCRIPTS = path.join(ROOT, 'skills', 'adaptive-dark-mode', 'scripts');
const PROBE = await readFile(path.join(SCRIPTS, 'probe.js'), 'utf8');
const ENGINES = { chromium, webkit };
const BROWSERS = (process.env.PROBE_BROWSERS || 'chromium,webkit').split(',').map(s => s.trim()).filter(Boolean);
const TYPES = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.png': 'image/png', '.jpg': 'image/jpeg' };

let server, base;
before(async () => {
  server = http.createServer(async (req, res) => {
    let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (p.endsWith('/')) p += 'index.html';
    const file = path.join(FIXTURES, path.normalize(p));
    if (!file.startsWith(FIXTURES) || !existsSync(file)) { res.writeHead(404).end(); return; }
    res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
    res.end(await readFile(file));
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(() => server?.close());

async function probe(browser, fixture, colorScheme) {
  const ctx = await browser.newContext({ colorScheme, viewport: { width: 1024, height: 768 } });
  const page = await ctx.newPage();
  await page.goto(`${base}/${fixture}/`, { waitUntil: 'load' });
  const before = await page.evaluate(() => document.documentElement.outerHTML);
  const result = await page.evaluate(PROBE);
  const afterHtml = await page.evaluate(() => document.documentElement.outerHTML);
  await ctx.close();
  assert.equal(afterHtml, before, 'probe.js must not modify the page');
  return result;
}

for (const name of BROWSERS) {
  test(`probe.js in ${name}`, async (t) => {
    const browser = await ENGINES[name].launch();
    try {
      await t.test('good site: clean in both schemes', async () => {
        for (const scheme of ['light', 'dark']) {
          const r = await probe(browser, 'good', scheme);
          assert.equal(r.summary.usedScheme, scheme);
          assert.equal(r.summary.pageLooksDark, scheme === 'dark');
          assert.equal(r.summary.schemeMismatch, null);
          assert.equal(r.summary.textFailures, 0);
          assert.equal(r.formControls.mismatched, 0);
          assert.equal(r.summary.svgLowContrast, 0);
        }
      });

      await t.test('declared without dark styles: mismatch, dark controls on light page', async () => {
        const r = await probe(browser, 'declared-incomplete', 'dark');
        assert.equal(r.declared.meta[0], 'light dark');
        assert.equal(r.summary.usedScheme, 'dark');
        assert.equal(r.summary.pageLooksDark, false);
        assert.match(r.summary.schemeMismatch, /used scheme is dark but the page paints light/);
        assert.ok(r.formControls.mismatched >= 1, 'UA-dark inputs on a light page');
        assert.equal(r.formControls.meaning, 'dark controls on a light page');
        assert.ok(r.textContrastFailures.some(f => f.sel.endsWith('p.muted')), '#888 on white fails 4.5:1');
        assert.ok(r.images.some(i => i.likelyLogo && i.darkOnTransparent), 'logo.png is dark-on-transparent');
        assert.ok(r.images.some(i => i.bakedWhiteBackground), 'product.jpg has a baked-in white background');
        assert.equal(r.summary.canvases, 1);
        const light = await probe(browser, 'declared-incomplete', 'light');
        assert.equal(light.summary.schemeMismatch, null, 'in light mode the site is consistent');
      });

      await t.test('class-only dark styles behind a declaration: mismatch before JS adds .dark', async () => {
        const r = await probe(browser, 'declared-class-only', 'dark');
        assert.match(r.summary.schemeMismatch, /used scheme is dark but the page paints light/);
      });

      await t.test('media-query dark theme without declaration: islands, invisible icon, vanishing logo', async () => {
        const r = await probe(browser, 'media-undeclared', 'dark');
        assert.equal(r.summary.pageLooksDark, true);
        assert.equal(r.summary.usedScheme, 'light');
        assert.match(r.summary.schemeMismatch, /page paints dark but the used scheme is light/);
        assert.ok(r.lightIslands.some(i => i.sel.endsWith('div.promo')), 'white promo box is a light island');
        assert.ok(r.lowContrastIcons.some(i => i.label === 'search'), 'near-black icon on dark page');
        assert.ok(r.images.some(i => i.vanishesHere), 'dark logo vanishes on the dark page');
        assert.equal(r.formControls.meaning, 'light controls on a dark page');
      });

      await t.test('light-dark() tokens without declaration never resolve dark', async () => {
        // ld-undeclared has only a stylesheet; serve it through a tiny page
        const ctx = await browser.newContext({ colorScheme: 'dark' });
        const page = await ctx.newPage();
        await page.route(`${base}/ld-page/`, route => route.fulfill({ contentType: 'text/html',
          body: `<!doctype html><link rel="stylesheet" href="${base}/ld-undeclared/s.css"><p>Text</p>` }));
        await page.goto(`${base}/ld-page/`);
        const r = await page.evaluate(PROBE);
        await ctx.close();
        assert.equal(r.summary.pageLooksDark, false, 'light-dark() picks the light value without color-scheme');
        assert.equal(r.summary.usedScheme, 'light');
      });
    } finally {
      await browser.close();
    }
  });
}

test('probe.mjs CLI writes screenshots and JSON for both schemes', async () => {
  const out = await mkdtemp(path.join(tmpdir(), 'adm-probe-'));
  try {
    const { stdout } = await promisify(execFile)(process.execPath,
      [path.join(SCRIPTS, 'probe.mjs'), `${base}/media-undeclared/`, '--out', out, '--browser', BROWSERS[0]],
      { cwd: ROOT, timeout: 120000 });
    const files = (await readdir(out)).sort();
    assert.equal(files.filter(f => f.endsWith('.png')).length, 2, files.join(', '));
    assert.equal(files.filter(f => f.endsWith('.json')).length, 2, files.join(', '));
    const dark = JSON.parse(await readFile(path.join(out, files.find(f => f.endsWith('.dark.json'))), 'utf8'));
    assert.equal(dark.summary.pageLooksDark, true);
    assert.match(stdout, /not Safari Adaptive Dark Mode/);
  } finally {
    await rm(out, { recursive: true, force: true });
  }
});
