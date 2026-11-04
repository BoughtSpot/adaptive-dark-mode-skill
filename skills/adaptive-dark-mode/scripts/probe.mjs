#!/usr/bin/env node
// Run probe.js against a URL in light and dark color schemes with Playwright.
// Usage: node probe.mjs <url> [more urls…] [--out dir] [--browser webkit|chromium|firefox] [--mobile] [--wait ms]
// Resolves `playwright` (or `@playwright/test`) from the current working directory, so run
// it from a project that already has Playwright installed. It does not install anything.
// Note: this emulates prefers-color-scheme only. Safari's Adaptive Dark Mode can't be automated.
import { createRequire } from 'node:module';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const args = process.argv.slice(2);
const opt = (name, dflt) => { const i = args.indexOf(name); if (i < 0) return dflt; const v = args[i + 1]; args.splice(i, 2); return v; };
const flag = (name) => { const i = args.indexOf(name); if (i < 0) return false; args.splice(i, 1); return true; };
const out = opt('--out', 'adm-probe');
const browserName = opt('--browser', 'webkit');
const waitMs = +opt('--wait', '500');
const mobile = flag('--mobile');
const urls = args.filter(a => !a.startsWith('--'));
if (!urls.length) { console.error('usage: node probe.mjs <url> [--out dir] [--browser webkit|chromium|firefox] [--mobile]'); process.exit(2); }

const req = createRequire(path.join(process.cwd(), 'package.json'));
let pw;
for (const name of ['playwright', '@playwright/test', 'playwright-core']) {
  try { pw = await import(pathToFileURL(req.resolve(name)).href); break; } catch {}
}
if (!pw) {
  console.error('Playwright not found from ' + process.cwd() + '. Ask the user before installing it ' +
    '(npm i -D playwright && npx playwright install webkit), or use the in-app browser with probe.js instead.');
  process.exit(3);
}
pw = pw.default ?? pw;
const probeSrc = await readFile(path.join(path.dirname(fileURLToPath(import.meta.url)), 'probe.js'), 'utf8');

const browser = await pw[browserName].launch();
await mkdir(out, { recursive: true });
const summary = [];
for (const url of urls) {
  const slug = url.replace(/^https?:\/\//, '').replace(/[^\w.-]+/g, '_').slice(0, 80);
  for (const scheme of ['light', 'dark']) {
    const ctx = await browser.newContext({
      colorScheme: scheme,
      viewport: mobile ? { width: 390, height: 844 } : { width: 1280, height: 900 },
      deviceScaleFactor: 1, isMobile: mobile && browserName !== 'firefox', hasTouch: mobile,
    });
    const page = await ctx.newPage();
    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
    } catch (e) {
      try { await page.goto(url, { waitUntil: 'load', timeout: 45000 }); } catch (e2) { console.error(`${url} [${scheme}]: ${e2.message}`); await ctx.close(); continue; }
    }
    await page.waitForTimeout(waitMs);
    const shot = path.join(out, `${slug}.${scheme}.png`);
    await page.screenshot({ path: shot, fullPage: true });
    const result = await page.evaluate(probeSrc);
    await writeFile(path.join(out, `${slug}.${scheme}.json`), JSON.stringify(result, null, 2));
    summary.push({ url, scheme, screenshot: shot, ...result.summary, declaredMeta: result.declared.meta.join(' | ') || '-',
      rootColorScheme: result.declared.rootColorScheme, mismatchedControls: result.formControls.mismatched });
    await ctx.close();
  }
}
await browser.close();
console.table(summary.map(s => ({ url: s.url.slice(0, 40), scheme: s.scheme, dark: s.pageLooksDark, bg: s.pageBackground,
  meta: s.declaredMeta, rootCS: s.rootColorScheme, textFail: `${s.textFailures}/${s.textChecked}`, islands: s.lightIslands,
  iconsLow: s.svgLowContrast, canvases: s.canvases, iframes: s.iframes, blendMask: s.blendOrMask, badInputs: s.mismatchedControls, mismatch: s.schemeMismatch ? 'YES' : '' })));
console.log(`\nJSON and screenshots in ${path.resolve(out)} (browser: ${browserName}; not Safari Adaptive Dark Mode).`);
