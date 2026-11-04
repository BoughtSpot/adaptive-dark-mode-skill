/* Adaptive Dark Mode runtime probe.
 * A single expression: paste it into a browser console, pass it to a browser-automation
 * "evaluate JavaScript" tool, or run it via probe.mjs. It returns a JSON-serializable report
 * of the page as currently rendered (run it once with the light and once with the dark
 * scheme emulated). It does not modify the page.
 * Measures the site's own rendering: Safari's Adaptive Dark Mode cannot be emulated.
 */
(() => {
  const LIMIT = { textEls: 4000, scanEls: 6000, examples: 20, images: 120, svgs: 300 };
  const vw = innerWidth, vh = innerHeight, vArea = vw * vh;

  // ---- color helpers (canvas normalizes any CSS color, incl. oklch/color())
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const cache = new Map();
  const RGBA = /^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/;
  function rgba(str) {
    if (!str || str === 'none') return null;
    if (cache.has(str)) return cache.get(str);
    let out = null; const m = str.match(RGBA);
    if (m) { const a = m[4] === undefined ? 1 : m[4].endsWith('%') ? parseFloat(m[4]) / 100 : parseFloat(m[4]); out = [+m[1], +m[2], +m[3], a]; }
    else if (str === 'transparent') out = [0, 0, 0, 0];
    else {
      try { cx.clearRect(0, 0, 1, 1); cx.fillStyle = 'rgba(0,0,0,0)'; cx.fillStyle = str; cx.fillRect(0, 0, 1, 1);
        const d = cx.getImageData(0, 0, 1, 1).data; out = [d[0], d[1], d[2], d[3] / 255]; } catch { out = null; }
    }
    cache.set(str, out); return out;
  }
  const lin = c => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const lum = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const over = (top, bot) => { const a = top[3] + bot[3] * (1 - top[3]); if (!a) return [0, 0, 0, 0];
    return [0, 1, 2].map(i => (top[i] * top[3] + bot[i] * bot[3] * (1 - top[3])) / a).concat(a); };
  const hex = c => c ? '#' + c.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, '0')).join('') + (c[3] < 1 ? `/${c[3].toFixed(2)}` : '') : null;

  // ---- element helpers
  const rootCS = getComputedStyle(document.documentElement);
  const prefersDark = matchMedia('(prefers-color-scheme: dark)').matches;
  // computed color-scheme is 'normal' when only the <meta> declares it; the meta then applies document-wide
  const metaCS = ((document.querySelector('meta[name="color-scheme"]') || {}).content || '').toLowerCase();
  const schemeOf = (cs) => { const v = (cs.colorScheme || 'normal').toLowerCase(); return v === 'normal' && metaCS ? metaCS : v; };
  const usedDark = (cs) => { const v = schemeOf(cs);
    if (v.includes('dark') && v.includes('light')) return prefersDark; return v.includes('dark'); };
  const rootUsedDark = usedDark(rootCS);
  const canvasColor = rootUsedDark ? [30, 30, 30, 1] : [255, 255, 255, 1]; // UA canvas approximation
  function sel(el) {
    const parts = []; let e = el;
    for (let i = 0; e && e.nodeType === 1 && i < 4; i++, e = e.parentElement) {
      let s = e.tagName.toLowerCase();
      if (e.id) { s += '#' + e.id; parts.unshift(s); break; }
      const cls = typeof e.className === 'string' ? e.className.trim().split(/\s+/).filter(c => c && c.length < 30).slice(0, 2) : [];
      if (cls.length) s += '.' + cls.join('.');
      parts.unshift(s);
    }
    return parts.join(' > ');
  }
  function visible(el, cs) {
    cs = cs || getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return false;
    const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1;
  }
  const bgMemo = new Map();
  function effectiveBg(el) {
    if (bgMemo.has(el)) return bgMemo.get(el);
    const layers = []; let overImage = false; let e = el;
    while (e && e.nodeType === 1) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') overImage = true;
      const c = rgba(cs.backgroundColor);
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 0.99) break; }
      e = e.parentElement;
    }
    let base = (e && e.nodeType === 1) ? layers.pop() : canvasColor;
    if (!base) base = canvasColor;
    for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
    const res = { color: base, overImage, assumedCanvas: !e };
    bgMemo.set(el, res); return res;
  }
  const cap = (arr, x) => { if (arr.length < LIMIT.examples) arr.push(x); };

  const report = {
    url: location.href, viewport: `${vw}x${vh}`, prefersDark,
    declared: {
      meta: [...document.querySelectorAll('meta[name="color-scheme"]')].map(m => m.content),
      rootColorScheme: rootCS.colorScheme, bodyColorScheme: document.body ? getComputedStyle(document.body).colorScheme : null,
      themeColor: [...document.querySelectorAll('meta[name="theme-color"]')].map(m => ({ content: m.content, media: m.media || null })),
      rootClass: document.documentElement.className || null,
      rootDataTheme: document.documentElement.dataset.theme || document.documentElement.dataset.bsTheme || null,
    },
    summary: {}, textContrastFailures: [], lightIslands: [], lowContrastIcons: [], images: [], backgroundImages: [],
    canvases: [], iframes: [], blendAndMask: [], colorSchemeOverrides: [], formControls: {},
  };

  // ---- page background
  const pageBg = effectiveBg(document.body || document.documentElement).color;
  const pageL = lum(pageBg);
  report.summary.pageBackground = hex(pageBg);
  report.summary.pageLooksDark = pageL < 0.2;
  report.summary.usedScheme = rootUsedDark ? 'dark' : 'light';
  // the key Adaptive-Dark-Mode-readiness signal: does the declared/used scheme match what the page paints?
  report.summary.schemeMismatch = rootUsedDark && pageL > 0.4 ? 'used scheme is dark but the page paints light (declared dark support without a dark theme?)'
    : !rootUsedDark && pageL < 0.2 ? 'page paints dark but the used scheme is light (UA controls/scrollbars stay light; missing color-scheme declaration?)'
    : null;

  // ---- text contrast
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT, {
    acceptNode: n => n.nodeValue.trim().length > 1 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT });
  const seen = new Set(); let checked = 0, failures = 0;
  while (walker.nextNode() && seen.size < LIMIT.textEls) {
    const el = walker.currentNode.parentElement;
    if (!el || seen.has(el) || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|OPTION)$/.test(el.tagName)) continue;
    seen.add(el);
    const cs = getComputedStyle(el); if (!visible(el, cs)) continue;
    if (el.closest('svg')) continue;
    const fg = rgba(cs.color); if (!fg || fg[3] === 0) continue;
    const bgInfo = effectiveBg(el); const fgFlat = over(fg, bgInfo.color);
    const r = ratio(fgFlat, bgInfo.color); checked++;
    const size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const need = large ? 3 : 4.5;
    if (r < need) {
      failures++;
      cap(report.textContrastFailures, { sel: sel(el), text: walker.currentNode.nodeValue.trim().slice(0, 50), fg: hex(fg), bg: hex(bgInfo.color),
        ratio: +r.toFixed(2), need, overImage: bgInfo.overImage || undefined, disabled: el.closest(':disabled,[aria-disabled="true"]') ? true : undefined });
    }
  }
  report.summary.textChecked = checked; report.summary.textFailures = failures;

  // ---- element scan: islands, background images, effects, color-scheme overrides
  const all = document.body ? document.body.getElementsByTagName('*') : [];
  const islands = [];
  for (let i = 0; i < all.length && i < LIMIT.scanEls; i++) {
    const el = all[i]; const cs = getComputedStyle(el);
    if (cs.display === 'none') continue;
    const r = el.getBoundingClientRect(); const area = r.width * r.height;
    const bg = rgba(cs.backgroundColor);
    if (report.summary.pageLooksDark && bg && bg[3] > 0.9 && lum(bg) > 0.6 && area > vArea * 0.02 && visible(el, cs))
      islands.push({ sel: sel(el), bg: hex(bg), size: `${Math.round(r.width)}x${Math.round(r.height)}`, area,
        intentional: /light/.test(cs.colorScheme) && !/dark/.test(cs.colorScheme) || undefined });
    if (cs.backgroundImage && cs.backgroundImage.includes('url(')) {
      const url = (cs.backgroundImage.match(/url\(["']?([^"')]+)/) || [])[1] || '';
      const raster = !/\.svg(\?|#|$)|^data:image\/svg/i.test(url);
      const tiled = !/no-repeat/.test(cs.backgroundRepeat);
      const sprite = /-\d/.test(cs.backgroundPosition) && r.width <= 128 && r.height <= 128;
      if (raster) cap(report.backgroundImages, { sel: sel(el), url: url.slice(0, 120), tiled: tiled || undefined, sprite: sprite || undefined });
      report.summary.rasterBackgrounds = (report.summary.rasterBackgrounds || 0) + (raster ? 1 : 0);
    }
    const mask = cs.maskImage || cs.webkitMaskImage;
    if ((cs.mixBlendMode && cs.mixBlendMode !== 'normal') || (mask && mask !== 'none'))
      cap(report.blendAndMask, { sel: sel(el), mixBlendMode: cs.mixBlendMode !== 'normal' ? cs.mixBlendMode : undefined,
        mask: mask && mask !== 'none' ? mask.slice(0, 80) : undefined });
    const parent = el.parentElement;
    if (parent && cs.colorScheme !== getComputedStyle(parent).colorScheme)
      cap(report.colorSchemeOverrides, { sel: sel(el), colorScheme: cs.colorScheme, usedDark: usedDark(cs) });
  }
  islands.sort((a, b) => b.area - a.area);
  report.lightIslands = islands.slice(0, 15).map(({ area, ...x }) => x);
  report.summary.lightIslands = islands.length;

  // ---- images
  const imgs = [...document.images].slice(0, LIMIT.images);
  const scv = document.createElement('canvas'); const sx = scv.getContext('2d', { willReadFrequently: true });
  let rasterCount = 0;
  for (const img of imgs) {
    const src = img.currentSrc || img.src || '';
    if (!visible(img)) continue;
    const raster = !/\.svg(\?|#|$)|^data:image\/svg/i.test(src);
    if (!raster) continue;
    rasterCount++;
    const rect = img.getBoundingClientRect();
    const hint = `${src} ${img.alt} ${img.className} ${img.parentElement && img.parentElement.className}`;
    const entry = { sel: sel(img), src: src.slice(0, 120), size: `${Math.round(rect.width)}x${Math.round(rect.height)}`,
      likelyLogo: /logo|brand|wordmark/i.test(hint) || undefined,
      darkSource: !!(img.parentElement && img.parentElement.tagName === 'PICTURE' &&
        img.parentElement.querySelector('source[media*="prefers-color-scheme"]')) || undefined };
    if (img.complete && img.naturalWidth > 8) {
      try {
        const w = Math.min(64, img.naturalWidth), h = Math.max(1, Math.round(w * img.naturalHeight / img.naturalWidth));
        scv.width = w; scv.height = h; sx.clearRect(0, 0, w, h); sx.drawImage(img, 0, 0, w, h);
        const d = sx.getImageData(0, 0, w, h).data; let bw = 0, bt = 0, bn = 0, ol = 0, on = 0;
        for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
          const k = (y * w + x) * 4, a = d[k + 3];
          if (x === 0 || y === 0 || x === w - 1 || y === h - 1) { bn++;
            if (a > 245 && d[k] > 238 && d[k + 1] > 238 && d[k + 2] > 238) bw++; if (a < 16) bt++; }
          if (a > 200) { on++; ol += lum([d[k], d[k + 1], d[k + 2]]); }
        }
        if (bn && bw / bn > 0.85) entry.bakedWhiteBackground = true;
        if (bn && bt / bn > 0.6 && on && ol / on < 0.08) entry.darkOnTransparent = true;
        const effBg = effectiveBg(img).color;
        if (entry.darkOnTransparent && lum(effBg) < 0.2) entry.vanishesHere = true;
        if (entry.bakedWhiteBackground && lum(effBg) < 0.2) entry.whiteBoxHere = true;
      } catch { entry.pixels = 'cross-origin (not readable)'; }
    }
    if (entry.likelyLogo || entry.bakedWhiteBackground || entry.darkOnTransparent || entry.pixels) cap(report.images, entry);
  }
  report.summary.rasterImages = rasterCount;

  // ---- inline SVG icon contrast (non-text 3:1)
  let svgChecked = 0, svgLow = 0;
  for (const svg of [...document.querySelectorAll('svg')].slice(0, LIMIT.svgs)) {
    if (!visible(svg) || svg.closest('svg') !== svg) continue;
    const shape = svg.querySelector('path,circle,rect,polygon,polyline,ellipse,line,text,use');
    if (!shape) continue;
    const scs = getComputedStyle(shape);
    const paint = [scs.fill, scs.stroke].map(p => (p && !p.startsWith('url') && p !== 'none') ? rgba(p) : null).find(c => c && c[3] > 0);
    if (!paint) continue;
    svgChecked++;
    const bg = effectiveBg(svg.parentElement || svg).color; const r = ratio(over(paint, bg), bg);
    if (r < 3) { svgLow++; cap(report.lowContrastIcons, { sel: sel(svg), paint: hex(paint), bg: hex(bg), ratio: +r.toFixed(2),
      label: (svg.getAttribute('aria-label') || svg.closest('a,button')?.textContent || '').trim().slice(0, 40) || undefined }); }
  }
  report.summary.svgChecked = svgChecked; report.summary.svgLowContrast = svgLow;

  // ---- canvas, iframes, form controls
  for (const c of document.querySelectorAll('canvas')) {
    if (!visible(c)) continue; const r = c.getBoundingClientRect(); const cs = getComputedStyle(c);
    cap(report.canvases, { sel: sel(c), size: `${Math.round(r.width)}x${Math.round(r.height)}`, cssBackground: hex(rgba(cs.backgroundColor)) });
  }
  for (const f of document.querySelectorAll('iframe')) {
    const r = f.getBoundingClientRect(); let origin = '';
    try { origin = new URL(f.src, location.href).origin; } catch {}
    cap(report.iframes, { sel: sel(f), origin: origin || '(srcdoc/blank)', size: `${Math.round(r.width)}x${Math.round(r.height)}`,
      sameOrigin: origin === location.origin, colorScheme: getComputedStyle(f).colorScheme });
  }
  const controls = [...document.querySelectorAll('input:not([type=hidden]),select,textarea')].filter(e => visible(e));
  const pageDark = report.summary.pageLooksDark;
  const mismatched = controls.filter(e => { const bg = rgba(getComputedStyle(e).backgroundColor);
    if (!bg || bg[3] < 0.5) return false; const L = lum(bg); return pageDark ? L > 0.6 : L < 0.1; });
  report.formControls = { count: controls.length, mismatched: mismatched.length,
    meaning: mismatched.length ? (pageDark ? 'light controls on a dark page' : 'dark controls on a light page') : undefined,
    examples: mismatched.slice(0, 5).map(e => sel(e)), accentColor: rootCS.accentColor };

  report.summary.canvases = report.canvases.length; report.summary.iframes = report.iframes.length;
  report.summary.blendOrMask = report.blendAndMask.length;
  return report;
})()
