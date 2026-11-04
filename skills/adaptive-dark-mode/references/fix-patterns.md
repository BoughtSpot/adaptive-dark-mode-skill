# Fix patterns

Copy-ready patterns for each fix layer, in the order SKILL.md applies them. Adapt names to the project's existing token naming rather than introducing a parallel system.

## Contents
- §1 Declaration
- §2 Theme switching without mismatches or flashes
- §3 Tokens and `light-dark()`
- §4 UA-painted surfaces
- §5 Images, logos, icons
- §6 Canvas, charts, maps, embeds, iframes
- §7 Shadows, elevation, blend modes, masks
- §8 Brand and semantic colors
- §9 Path B checklist (making a page convert well)

---

## §1 Declaration

**Path A (own it): declare in both places, statically.**

```html
<head>
  <meta charset="utf-8">
  <meta name="color-scheme" content="light dark">   <!-- before any stylesheet -->
  <link rel="stylesheet" href="/app.css">
```

```css
:root { color-scheme: light dark; }
```

Why both:
- The meta tag is seen before CSS loads, so the canvas behind the page is already dark on first paint. That avoids a white flash.
- The CSS declaration travels with the stylesheet and is what `light-dark()` resolves against.

**Path B (let Safari convert):** declare nothing, or `:root { color-scheme: light; }`. Remove any stray `color-scheme: light dark` or `dark` that isn't backed by real dark styles. It's often left behind by a CSS reset or a component library.

**Islands (path C):**

```css
.brand-lockup, .chart-frame, .code-preview { color-scheme: light only; }
```

Ship them, but note that `only` doesn't take effect in Safari 27.3 beta 1.

Under path A, an island needs `color-scheme: light` *and* light values for its own colors. With `light-dark()` tokens it gets those automatically, because tokens resolve against the element's own used scheme.

**Don't:**
- set `color-scheme` only from JavaScript
- declare `dark` alone (`color-scheme: dark`) at the root of a site that also has a light theme
- declare on `body` only. The meta tag and `:root` are what count for the page canvas.

---

## §2 Theme switching without mismatches or flashes

Rule: **the static CSS says `light dark`, and the toggle only narrows it.** The class or attribute that selects your dark styles and the `color-scheme` value must never disagree, including before JavaScript runs.

### Attribute-driven, with `light-dark()` tokens (simplest correct setup)

```css
:root                     { color-scheme: light dark; }   /* system default */
:root[data-theme="light"] { color-scheme: light; }
:root[data-theme="dark"]  { color-scheme: dark; }
/* every themed color is light-dark(...), so nothing else is needed */
```

```html
<script>
  /* inline, blocking, in <head> before stylesheets that might paint */
  try {
    const t = localStorage.getItem('theme');           // 'light' | 'dark' | null (system)
    if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t;
  } catch {}
</script>
```

With no stored choice, no attribute is set, so `light dark` follows the OS. That also works with JavaScript disabled.

### Class-driven dark styles (Tailwind `dark:`, `.dark {}` blocks)

The trap: when the system is dark and no class has been applied yet, `color-scheme: light dark` resolves dark, so the UA surfaces go dark, but the `.dark` styles aren't active. Pick one fix:

1. **Make the dark selector also match the system preference unless light was chosen** (preferred, because it works without JS). See frameworks.md for Tailwind's syntax. In plain CSS:

   ```css
   :root { color-scheme: light dark; }
   :root.light { color-scheme: light; }
   :root.dark  { color-scheme: dark; }

   .dark { --bg: #0f1115; --fg: #e7e9ee; }
   @media (prefers-color-scheme: dark) {
     :root:not(.light) { --bg: #0f1115; --fg: #e7e9ee; }
   }
   ```

2. **Resolve the system preference before first paint**, in the head script. Always apply `.dark` or `.light`, and listen for changes:

   ```html
   <script>
     (() => {
       const root = document.documentElement;
       const mq = matchMedia('(prefers-color-scheme: dark)');
       const apply = () => {
         let t = null; try { t = localStorage.getItem('theme'); } catch {}
         const dark = t ? t === 'dark' : mq.matches;
         root.classList.toggle('dark', dark);
         root.classList.toggle('light', !dark);
       };
       apply();
       mq.addEventListener('change', apply);
     })();
   </script>
   ```

   Keep the static `:root { color-scheme: light dark; }` and the `.light`/`.dark` narrowing rules. The script only picks the class.

**Default theme:**
- **System** is the only default that works well with Adaptive Dark Mode.
- A **light** default means every first-time visitor with a dark system sees the light theme, and Safari then converts it, so your real dark theme is never shown.
- A **dark** default ignores the user's OS setting.

**No flash:** the head script must be inline and run before first paint. Put it before stylesheets, or at least before the body. No `defer`, no `async`, no `type="module"`.

---

## §3 Tokens and `light-dark()`

`light-dark(<light>, <dark>)` picks a value based on the element's used `color-scheme`. Support is Baseline 2024 (Safari 17.5, Chrome 123, Firefox 120). **Without a `color-scheme` that includes `dark`, it always returns the light value**, so a token file full of `light-dark()` with no declaration has a dark theme that never activates.

```css
:root {
  color-scheme: light dark;

  /* surfaces: elevation goes up in lightness on dark, not via shadow */
  --surface-0: light-dark(#ffffff, #0f1115);   /* page */
  --surface-1: light-dark(#f6f7f9, #161920);   /* cards */
  --surface-2: light-dark(#eef0f3, #1d212a);   /* raised / menus */
  --border:    light-dark(#e2e5ea, #2a2f3a);

  --text:        light-dark(#14161a, #e7e9ee);
  --text-muted:  light-dark(#5b6270, #a2a9b6);
  --link:        light-dark(oklch(50% .18 255), oklch(75% .13 255));
  --focus-ring:  light-dark(oklch(55% .2 255), oklch(78% .15 255));
}
body { background: var(--surface-0); color: var(--text); }
```

Why this shape:
- Custom properties holding `light-dark()` are resolved **where they're used**, against that element's `color-scheme`. So a `color-scheme: light` island automatically gets light values.
- The light value is the existing literal, so the light theme doesn't change.

**Converting existing literals**, highest visual area first:
1. page and section backgrounds
2. card and panel backgrounds
3. body text
4. borders and dividers
5. secondary text
6. everything else

Replace `background: #fff` with `background: var(--surface-0)`, not with a new literal.

**Fallback for very old browsers** (only if analytics show it matters):

```css
:root { --surface-0: #fff; --text: #14161a; }
@media (prefers-color-scheme: dark) { :root { --surface-0: #0f1115; --text: #e7e9ee; } }
```

This doesn't respond to a site toggle unless you duplicate it under `:root.dark`.

**Translucent colors:** `rgb(0 0 0 / .05)` hover tints vanish on dark. Use `color-mix(in oklch, var(--text) 8%, transparent)` so the tint follows the text color, or give it a `light-dark()` pair.

**Dark palette starting points:**
- Avoid pure `#000` pages (harsh, and they smear on OLED scrolling) and pure `#fff` text (glare). Aim for a background around L 12–18% and text around L 90–93% in OKLCH.
- Check every text/background pair for ≥ 4.5:1 (normal text) or ≥ 3:1 (large text and UI parts).

---

## §4 UA-painted surfaces

- **Form controls, scrollbars, the canvas, default link and text colors** follow `color-scheme` automatically. That's the main reason path A needs the declaration even if your CSS already goes dark via media queries.
- **Custom-styled controls:**

  ```css
  input, select, textarea {
    background: var(--surface-1); color: var(--text); border-color: var(--border);
  }
  ::placeholder { color: var(--text-muted); }
  ```

- **`accent-color: var(--link);`** for checkboxes, radios, and range inputs, so they match the brand in both schemes.
- **Selection:** `::selection { background: light-dark(#cfe0ff, #2b4a80); color: inherit; }`
- **Focus:** `:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }`. Dark-blue rings disappear on dark.
- **Autofill:** WebKit paints its own autofill background. Use `input:-webkit-autofill { -webkit-text-fill-color: var(--text); box-shadow: 0 0 0 1000px var(--surface-1) inset; }`, and test it.
- **`theme-color`** (tints the browser UI):

  ```html
  <meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
  <meta name="theme-color" content="#0f1115" media="(prefers-color-scheme: dark)">
  ```

- **Print:** `@media print { :root { color-scheme: light; } }`, so dark-mode users don't print dark pages.

---

## §5 Images, logos, icons

**Logos and icons as SVG using `currentColor`**, so they follow text color in both schemes and Safari can recolor them on path B:

```html
<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="…"/></svg>
```

For multi-color marks, expose custom properties inside the SVG:

```html
<path fill="var(--logo-ink, currentColor)"/>
```

**Separate dark artwork with `<picture>`.** This follows the OS preference, not your site toggle:

```html
<picture>
  <source srcset="/logo-dark.svg" media="(prefers-color-scheme: dark)">
  <img src="/logo.svg" alt="Acme">
</picture>
```

If the site has a toggle, render both and switch with CSS instead:

```css
.logo-dark { display: none; }
:root.dark .logo-light, :root[data-theme="dark"] .logo-light { display: none; }
:root.dark .logo-dark,  :root[data-theme="dark"] .logo-dark  { display: inline; }
@media (prefers-color-scheme: dark) {
  :root:not(.light):not([data-theme="light"]) .logo-light { display: none; }
  :root:not(.light):not([data-theme="light"]) .logo-dark  { display: inline; }
}
```

**SVG loaded through `<img>`** can carry its own media query:

```xml
<style>path{fill:#111}@media (prefers-color-scheme: dark){path{fill:#eee}}</style>
```

This also follows the OS preference, not your toggle.

**Photos with a baked-in white background** (product shots, screenshots, diagrams):
- Best fix: transparent cutouts (PNG, WebP, or AVIF with alpha).
- Alternative: present them on a deliberate light tile so the white reads as design, not a bug:

  ```css
  .product-media { background: #fff; padding: 12px; border-radius: 12px; color-scheme: light; }
  ```

  The padding is what makes it look intentional, which is likely why WebKit recommends container padding.
- Under path A, optionally reduce glare with `:root[data-theme="dark"] img.photo { filter: brightness(.92); }`. Don't do this on path B: Safari doesn't convert images, and your CSS can't detect Adaptive Dark Mode.

**Dark artwork on a transparent background** (black text in a PNG, line art, signatures) vanishes on a dark page:
- Convert it to SVG with `currentColor`.
- Or provide a dark variant.
- Or put it on a light tile as above.

Safari may invert it on path B if it's simple black and white, but colorful artwork won't be inverted.

**Sprites:** replace them with individual SVG icons (inline or `<use href="#id">` from a symbol sheet). Replace image-based button states, rounded corners, and shadows with CSS.

**Tiled background images:** replace them with CSS that themes:

```css
.hero {
  background:
    radial-gradient(circle at 1px 1px, color-mix(in oklch, var(--text) 12%, transparent) 1px, transparent 0)
      0 0 / 16px 16px,
    var(--surface-1);
}
```

Safari converts light gradients but not bitmaps.

---

## §6 Canvas, charts, maps, embeds, iframes

**Canvas is never converted.** Pick one:

- **Theme it yourself (path A).** Read colors at draw time and redraw when the scheme changes:

  ```js
  const css = () => getComputedStyle(document.documentElement);
  function palette() {
    return { text: css().getPropertyValue('--text').trim(), grid: css().getPropertyValue('--border').trim() };
  }
  const redraw = () => chart.update(palette());
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', redraw);
  new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
  ```

  `getPropertyValue` on a `light-dark()` token returns the unresolved string. Resolve it by setting it as a color on a probe element and reading back `getComputedStyle(probe).color`. Or keep plain per-scheme tokens for canvas use. For Chart.js, set `Chart.defaults.color` and `Chart.defaults.borderColor`. For ECharts, switch themes with `echarts.init(el, isDark ? 'dark' : null)`, or call `setOption` with new colors.

- **Make it a self-contained island (path B).**
  - Give the canvas an opaque background in its own light palette, plus padding and a radius: `canvas.chart { background: #fff; border-radius: 8px; }`.
  - Draw text and lines that read on that background.
  - A transparent canvas with dark ink becomes dark-on-dark once Safari darkens the page.
  - Under path B, JavaScript reading CSS colors gets the light values, so theming from CSS is fine. It always produces the light palette, which matches the opaque light island.

**Maps** (raster tiles): use the provider's dark style under path A. Under path B the tiles stay light, so frame the map as an island.

**Embeds and iframes** (video players, payment forms, social posts, docs):
- For your own iframe documents, declare `color-scheme` and theme them like any page.
- Third-party embeds often take a theme parameter, e.g. `?theme=dark`. Pick it from the same source as your toggle.
- The post doesn't document how conversion treats iframes, so list each embed for a manual Safari check.

---

## §7 Shadows, elevation, blend modes, masks

**Elevation:** dark shadows on dark surfaces are invisible. Use progressively lighter surfaces (`--surface-1/2`) plus a hairline border:

```css
.card {
  background: var(--surface-1);
  border: 1px solid light-dark(transparent, color-mix(in oklch, white 8%, transparent));
  box-shadow: 0 1px 3px light-dark(rgb(0 0 0 / .12), rgb(0 0 0 / .5));
}
```

`light-dark()` only accepts colors. Wrap the color *inside* a shadow, border, or gradient, never the whole value. To change shadow geometry per scheme, use two custom properties selected by `:root[data-theme]` or a media query.

**`mix-blend-mode: multiply` to knock out white backgrounds:**
- On path A, it does nothing useful on dark. Use transparent assets instead.
- On path B, Safari may disable it on transformed elements, which brings the white box back.

**Masks** (`mask-image`, `-webkit-mask`) **for icons** (the "colored by background-color" icon technique):
- If Safari disables the mask, the element renders as a solid box.
- Prefer inline SVG with `currentColor`.
- Never put essential content behind a mask on path B.

**`filter: invert()` dark-mode hacks:** remove them under path A, because they double-invert images and break brand colors. Under path B they stack with Safari's conversion, so remove them there too.

---

## §8 Brand and semantic colors

**Brand:** keep the hue and raise lightness, lowering chroma slightly, so the color reads on dark:

```css
--brand: light-dark(oklch(52% .19 265), oklch(72% .15 265));
--on-brand: light-dark(white, oklch(18% .03 265));     /* text on brand fills */
```

`contrast-color(var(--brand))` can pick black or white text automatically where it's supported (Safari 26+). Keep a fallback.

**Semantic colors** (success, warning, danger, info): make light-dark pairs for both the fill and the text-on-fill, and check that each stays distinguishable from the others and from the brand color. Red and green lose separation at high lightness, so add icons or labels, not just color.

**Data-viz palettes:** pick colors tuned separately for light and dark backgrounds. Color-coded meaning is the strongest reason to make a chart a path-C island.

---

## §9 Path B checklist (making a page convert well)

When the site will rely on Safari's conversion:
- Make sure nothing declares `dark` by accident: resets, component libraries, an old `color-scheme: light dark` in a theme file.
- Logos and icons: SVG, or simple black-and-white raster that Safari can invert. Colorful raster logos need a light tile.
- Product photos and screenshots: transparent cutouts, or framed light tiles with padding.
- Canvas, maps, and color-critical charts: self-contained opaque islands.
- No essential content depends on `mix-blend-mode` or `mask`.
- No tiled bitmap backgrounds or sprites.
- Containers have padding, so converted backgrounds don't make content collide.
- Text over images uses a solid or gradient scrim in CSS, not baked into the image.
- Optionally add `color-scheme: light only` islands, knowing they don't work in beta 1.
- Verify in Safari 27.3 (verification.md §4).
