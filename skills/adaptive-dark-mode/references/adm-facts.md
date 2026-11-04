# Adaptive Dark Mode: what is known and what isn't

Source: "Introducing Adaptive Dark Mode", WebKit blog, Nov 3, 2026.
https://webkit.org/blog/18541/introducing-adaptive-dark-mode/
Status at the time of writing: Safari 27.3 **beta**. Re-read the post (and any follow-ups) before telling a user that something behaves a particular way in a later release.

## Contents
1. Who sees it
2. When Safari leaves a page alone
3. What the conversion does
4. Images, SVG, canvas, effects
5. Opting out
6. What the page can observe
7. WebKit's own recommendations
8. Open questions (not covered by the post)

## 1. Who sees it
- The user's system appearance must be dark.
- Safari offers a preview on a site with a bright background, and the user taps **"Try"** to enable it. It is opt-in and user-driven.
- The post doesn't say whether the setting is per-site or global after opting in, or how it's turned off. Don't guess. Say it isn't documented.
- Feedback channels: site owners can contact web-evangelist@apple.com, and users report problem sites through Feedback Assistant.

## 2. When Safari leaves a page alone
- **Declared support.** A `color-scheme` that includes `dark` in the meta tag or CSS, e.g. `<meta name="color-scheme" content="light dark">` or `:root { color-scheme: light dark; }`.
- **Already dark.** Safari analyzes the page's colors, and a predominantly dark page (dark background, light text) is left as is.
- `prefers-color-scheme` media queries are **not** listed as a skip signal in their own right. They matter only because they make the page render dark when the system is dark, which triggers the "already dark" path. Relying on that heuristic is weaker than declaring support, because:
  - the declaration is the documented contract, while the heuristic is a judgment call
  - without the declaration, UA surfaces (form controls, scrollbars, the canvas behind the page) stay light even though your dark CSS is active
- Declare in HTML or CSS, not by injecting it later with script. The post says this "helps ensure your site is rendered correctly as fast as possible."

## 3. What the conversion does
- Inverts luminosity while preserving hue. Light backgrounds become dark, and dark text becomes light.
- Aims for at least WCAG 4.5:1 text contrast.
- Converts light CSS gradients.
- Distinguishes decorative colors from colors that carry meaning, and keeps the meaningful ones so elements stay visible and usable. The post gives no definition. Its examples include buttons keeping contrast against their backgrounds, text over images staying visible, and hover menus staying clear.
- Treat the decorative-versus-semantic judgment as opaque. **Exact brand colors are not guaranteed to survive.** If exact color fidelity matters, use path A or opt the element out.

## 4. Images, SVG, canvas, effects
- **Most images are left unchanged.**
  - A JPEG product photo on white stays a white rectangle on the now-dark page.
  - A transparent PNG with dark artwork stays dark on the now-dark page and may vanish.
- **SVG** colors are transformed when needed to keep icons and logos visible.
- **Bitmaps:** Safari analyzes pixel histograms and inverts simple black-and-white logos. Colorful raster logos are left alone.
- **`<canvas>`** content is never changed. Charts, maps, games, and signature pads drawn with dark ink on a transparent canvas become dark-on-dark.
- **`mask` and `mix-blend-mode`** may be disabled on transformed elements. Effects such as `mix-blend-mode: multiply` used to knock out white backgrounds, masked icons, or blend-mode text effects can break or show their unmasked form.

## 5. Opting out
- Whole page: `<meta name="color-scheme" content="light only">` or `:root { color-scheme: light only; }`.
- Specific elements: `.chart, .brand-lockup { color-scheme: light only; }`.
- **The `only` keyword is not supported in Safari 27.3 beta 1** ("Check back as Adaptive Dark Mode evolves"). Ship opt-outs if you need them, since they are standard CSS and harmless elsewhere, but tell the user they don't take effect in beta 1 and must be re-verified.
- Spec syntax: `color-scheme: normal | [ light | dark | <custom-ident> ]+ && only?`, so `light only` and `only light` are equivalent.

## 6. What the page can observe
- **Nothing tells the page that Adaptive Dark Mode is active.** There's no media query, no API, and no class.
- `getComputedStyle()` returns the authored (light) values.
- Images drawn to canvas keep their original form.

Consequences:
- You can't collect telemetry on how often it's active or fix it up at runtime. Verification is manual, in Safari.
- On path B, JavaScript that derives colors from CSS (theming a chart from CSS variables, picking black or white text from a computed background) computes light-theme colors while the page is displayed dark.
- It can't be used for fingerprinting, which is good for users.

## 7. WebKit's own recommendations
For sites that want to build their own dark mode:
- `<meta name="color-scheme" content="light dark">`, or `color-scheme` on `:root` or a relevant element
- `@media (prefers-color-scheme: dark)`
- `<picture>` with a dark-mode `<source>`
- `light-dark()`; and the newer `color-mix()` and `contrast-color()`

For sites that want Adaptive Dark Mode to work well:
- Use SVG rather than bitmaps for logos and icons.
- Use solid or gradient CSS colors instead of tiled background images.
- Replace image sprites with modern CSS for rounded corners, shadows, and button states.
- Make content images with transparent backgrounds instead of baking the page color in. This has a trade-off: transparent artwork with dark content can vanish on dark, so check it (see fix-patterns §5).
- Add padding to containers to prevent crowding. The post gives no reason. A likely one is that once backgrounds change, edge-to-edge content loses the visual separation the original colors gave it.

## 8. Open questions (not covered by the post; verify in Safari, don't assert)
- **Iframes:** whether conversion applies inside cross-origin or same-origin iframes, and how a declared iframe inside an undeclared page behaves.
- **Partial declarations:** what happens when only a subtree declares `light dark` while `:root` doesn't. The post mentions "a relevant element", but the conversion boundaries are undocumented.
- **Plain `light`:** whether `color-scheme: light` (without `only`), set because the user picked "light" in a site toggle, is treated like an undeclared light page and converted.
- **Timing:** whether a declaration set by an inline blocking script in `<head>` counts as declared. The post says to avoid JS. A static declaration plus a JS narrowing (fix-patterns §2) sidesteps the question.
- **Elements the post doesn't mention:** shadows, borders, outlines, focus rings, form controls, `accent-color`, `::selection`, scrollbars, `theme-color`, video posters, CSS `filter`, `backdrop-filter`.
- **The already-dark heuristic:** exactly how much of the page has to be dark.
- **Printing:** whether converted colors print. Presumably not, but this isn't documented.
- **Behavior on iPadOS, visionOS, and in web views or Safari View Controller**, and with Reader mode.
