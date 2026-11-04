---
name: adaptive-dark-mode
description: Audit a website's theming and make it ready for Safari's Adaptive Dark Mode (Safari 27.3+), which automatically darkens light sites that don't declare dark-mode support. Use this whenever the user mentions Adaptive Dark Mode, Safari's automatic or forced dark mode, `color-scheme`, `light-dark()`, `prefers-color-scheme`, adding or fixing a dark theme, dark-mode bugs in Safari (white boxes, inverted or vanishing logos, invisible icons, unreadable text, wrong-colored form controls), a theme toggle that flashes, or a color-token or theming audit, even if they never say "Adaptive Dark Mode". Covers a static code audit, a runtime page probe, deciding between owning dark mode, letting Safari convert the page, or opting elements out, framework-specific fixes (Tailwind, next-themes, shadcn/ui, SvelteKit, Rails, Bootstrap, MUI, WordPress), and a Safari verification checklist.
license: MIT
compatibility: Works in any agent that can read files and run shell commands. audit.py needs Python 3.9+ (Pillow optional). probe.js runs in any browser automation tool; probe.mjs needs Node 18+ and an existing Playwright install.
metadata:
  author: BoughtSpot
  version: "1.0.0"
  repository: https://github.com/BoughtSpot/adaptive-dark-mode-skill
  source-of-truth: https://webkit.org/blog/18541/introducing-adaptive-dark-mode/
  facts-as-of: "2026-11-03 (Safari 27.3 beta 1)"
---

# Adaptive Dark Mode readiness

Safari 27.3 (announced Nov 3, 2026, https://webkit.org/blog/18541/introducing-adaptive-dark-mode/) can render light websites as dark when the user has a dark system appearance and opts in. Your job with this skill is to find out what Safari will do to a given site, decide what it *should* do, and make the code match, without breaking the light theme.

## What Safari does: the facts this skill depends on

- **Skips sites that declare dark support.** `<meta name="color-scheme" content="light dark">` or `color-scheme: light dark` in CSS means "I handle dark mode myself", and Safari "does not change a thing".
- **Skips pages that already render dark.** Safari analyzes colors and leaves predominantly dark pages alone.
- **Converts everything else.** It inverts lightness while keeping hue, targets WCAG 4.5:1 text contrast, converts light CSS gradients, keeps colors it judges to carry meaning, and recolors SVGs when needed.
- **Mostly leaves bitmaps alone.** The exception is simple black-and-white logos, which it may invert based on a pixel histogram.
- **Never touches `<canvas>`.** It may also disable `mask` and `mix-blend-mode` on elements it transforms.
- **Opt-out is `color-scheme: light only`**, on `:root` or on specific elements. **The `only` keyword is not supported in Safari 27.3 beta 1**, so the opt-out is unreliable for now.
- **Invisible to the page.** JavaScript reading colors gets the authored (light) values, and images drawn to canvas stay unconverted.
- **Declare it statically.** The post asks for the declaration in the HTML `<head>` or in CSS, not added later by JavaScript.

Read `references/adm-facts.md` when you need the details, the open questions the post leaves unanswered, or exact wording to cite. Re-check the WebKit blog if the user is on a newer Safari than 27.3 beta 1, because this behavior is new and will change.

## The decision: three paths

Every site ends up on one of these, often with islands of path C:

| Path | What it means | Choose it when |
|---|---|---|
| **A. Own it** | Declare `light dark` and ship a complete dark theme. Safari stays out of the way. | The site has a design system, brand standards, data viz, or already has a partial dark theme. This is the default recommendation, because it's the only path where you control the result in every browser. |
| **B. Make it convertible** | Don't declare. Clean up the things Safari's conversion handles badly. | Content-heavy or legacy sites with little budget, where "Safari's dark version is decent" is good enough. |
| **C. Opt out islands** | `color-scheme: light only` on elements that must not change. | Elements whose colors are the content: brand marks with exact colors, charts with color-coded meaning, code or document previews, print previews, color pickers. |

**The cardinal rule: never declare `light dark` without dark styles for everything that sets a color.** The declaration does two things at once. It turns off Safari's conversion, *and* it switches UA-painted surfaces (page canvas, form controls, scrollbars, default text) to dark. A half-done dark theme behind a `light dark` declaration produces light cards on a dark canvas, dark default text on your white panels, and dark inputs inside light forms. That is worse than letting Safari convert the page. If the dark theme isn't ready, ship path B until it is.

The second most common bug is **a dark theme that Safari can't see**. A Tailwind `.dark` class, a `data-theme` attribute, or next-themes without a static `color-scheme` declaration looks like an undeclared light site whenever its default render is light. Safari then converts the light theme, and the site's real dark theme never appears.

## Workflow

### 1. Orient

Find the theming entry points before touching anything: the root layout or HTML shell, global stylesheets, token files, the Tailwind config or `@theme` block, any theme toggle and its pre-paint script, and the component library. Note the default theme (light, dark, or system) and how a user's choice is persisted.

### 2. Run the static audit

`<skill-dir>` is the directory that contains this SKILL.md.

```bash
python3 -I <skill-dir>/scripts/audit.py <project-root>
```

Options:
- `--json`: machine-readable output.
- `--exclude DIR`: skip a generated or vendored directory the default list misses.
- `--no-images`: skip raster analysis. The pixel checks use Pillow if it's installed.
- `--fail-on high`: exit 1 when there are findings at that severity or above, so a team can run the audit in CI.

The report tells you whether a static declaration exists, which dark-mode mechanisms are in use, how tokenized the colors are, and where the risky assets and effects live.

The audit is regex-based. **Treat every high or medium finding as a lead, and open the file to confirm it before acting on it or reporting it.** It can miss colors defined in CSS-in-JS theme objects, CMS content, or remote stylesheets, and it can't see how colors combine at runtime. The runtime probe covers that.

### 3. Probe the rendered page (when a URL or dev server is available)

`scripts/probe.js` is a self-contained browser expression. It reports the page's declared and computed `color-scheme`, failing text contrast, light "islands" on dark pages, low-contrast icons, raster images with baked-in white or dark-on-transparent content, sprites and tiled backgrounds, canvases, iframes, blend modes and masks, and per-element `color-scheme` overrides.

Run it in whichever of these you have:

- **A browser automation tool** (an in-app browser, Chrome DevTools MCP, Playwright MCP, and so on): emulate `prefers-color-scheme: dark` and reload, then evaluate the file's contents as JavaScript. Repeat with light.
  - Serve the site over HTTP. Some tools always render local `file://` pages in light.
  - To avoid pasting the whole file, copy `probe.js` into the served directory and evaluate `(0, eval)(await (await fetch('/probe.js')).text())`. Delete the copy afterwards.
- **Playwright already installed in the project:** `node <skill-dir>/scripts/probe.mjs <url> --out <dir>` runs both schemes in WebKit, saves full-page screenshots and JSON, and prints a summary table. Don't install Playwright or its browsers into the user's project without asking.

Read `summary.schemeMismatch` first, because it catches both cardinal bugs directly:
- *"used scheme is dark but the page paints light"*: dark support is declared but there's no dark theme.
- *"page paints dark but the used scheme is light"*: there's a dark theme but no declaration.

`formControls.mismatched` shows the same problem on inputs. Then read `lightIslands`, `lowContrastIcons`, `images` (`vanishesHere`, `whiteBoxHere`), and `textContrastFailures`.

What the probe measures is **the site's own light and dark rendering**. No automation tool runs Safari's Adaptive Dark Mode, because it's a Safari feature the user has to opt into. For path B, the probe's light-mode run shows the raw material Safari will convert, and the real check happens in Safari (step 6).

**Look at the screenshots yourself.** Numbers miss things like a logo that's technically visible but looks wrong.

### 4. Decide and confirm scope

Use the audit and probe to state:
- what Safari does to the site today: *converted*, *skipped because declared*, *skipped because already dark*, or *declared with an incomplete dark theme*
- which path you recommend, and why

Adding a declaration, wiring a toggle, or fixing assets is ordinary work, so go ahead when the user asked you to make the site ready. **Building a full dark palette for a site that has none** is a design decision that changes how the brand looks. Propose the token mapping first (a table of light → dark values) and get a yes before rewriting dozens of files. If the user only asked for an audit, stop after the report.

### 5. Fix, in this order

Each layer depends on the ones above it, so working top-down avoids redoing work.

1. **Declaration.** Make it static, early in `<head>` and on `:root`, and true to reality. Path A: `light dark`. Path B: none, or a plain `light`. Islands: `light only` on the element. See `references/fix-patterns.md` §1.
2. **Theme switching.** Use a three-state toggle (system, light, dark) that narrows `color-scheme` rather than replacing it, applied before first paint, with the system default resolved before paint too. The class or attribute and `color-scheme` must never disagree. See §2, and `references/frameworks.md` for the framework you found.
3. **Tokens.** Route colors through custom properties, ideally built with `light-dark()`, so one declaration drives both themes and islands flip automatically. Replace hard-coded literals in components, prioritized by visual area: backgrounds, then text, then borders. See §3.
4. **UA surfaces.** Form controls, scrollbars, selection, `accent-color`, focus rings, autofill, `theme-color`. See §4.
5. **Images and icons.** SVG with `currentColor`, `<picture>` dark sources, transparent cutouts instead of baked-in white, replacing sprites and tiled backgrounds. See §5.
6. **Canvas, charts, maps, embeds, iframes.** Canvas is never converted, so it must theme itself or be a self-contained opaque island. See §6.
7. **Effects.** Shadows don't read on dark, so use lighter surfaces and hairline borders for elevation. Don't let essential rendering depend on `mix-blend-mode` or `mask` on path B. See §7.
8. **Brand and semantic colors.** Lift lightness in OKLCH for dark backgrounds and keep the hue. Keep success, warning, and danger colors distinguishable. See §8.

Keep the light theme pixel-identical unless the user asked for light changes. Using `light-dark(<current light value>, <new dark value>)` gives you that for free.

### 6. Verify

Follow `references/verification.md`: re-run the audit and probe in both schemes, walk the page and state checklist (menus, modals, forms, autofill, focus, errors, tables, code, charts, embeds), test for a flash of the wrong theme on hard reload, and give the user the Safari 27.3 steps for the parts only Safari can show. Say plainly which checks you ran and which remain manual.

### 7. Report

Use this structure. Keep it skimmable, and put locations as `path:line`.

```markdown
# Adaptive Dark Mode readiness: <site/repo>

## Verdict
- Today under Adaptive Dark Mode: <converted | skipped (declared) | skipped (already dark) | declared but incomplete>
- Recommended path: <A / B> <+ C islands: list>
- One-paragraph why.

## Changes made        (omit if audit-only)
- <what, where, why>, grouped by the fix-order layers

## Findings
| Severity | Where | What happens in Safari dark | Fix |
|---|---|---|---|

## Needs a human check in Safari 27.3
- <pages/states the automated checks can't cover>

## Beta caveats and unknowns
- e.g. `light only` unsupported in 27.3 beta 1; iframe behavior undocumented
```

Severity guide: **high** means unreadable or unusable (text, controls, icons, logos disappearing; light-dark mismatch across the page). **Medium** means clearly wrong but usable (white image boxes, glaring light islands, lost elevation, theme flash). **Low** means polish (scrollbar, selection, theme-color, slightly off brand color).

## Reference files

- `references/adm-facts.md`: everything the WebKit post says, what it leaves open, and what JavaScript can and cannot observe. Read it when explaining behavior or caveats.
- `references/fix-patterns.md`: copy-ready CSS, HTML, and JS for each fix layer (§1 to §8). Read it before writing fixes.
- `references/frameworks.md`: Tailwind v3/v4, shadcn/ui, Next.js and next-themes, SvelteKit and mode-watcher, Vue/Nuxt, Astro, Rails, Bootstrap 5.3, MUI, Chakra, WordPress, plain CSS. Read only the sections for the stack you found.
- `references/verification.md`: the automated checks, the manual state checklist, the flash test, and Safari test steps.
- `scripts/audit.py`: static scanner (Python 3, standard library; Pillow optional).
- `scripts/probe.js`: runtime probe, a single browser expression that returns JSON.
- `scripts/probe.mjs`: Playwright runner for `probe.js` across light and dark, with screenshots.
