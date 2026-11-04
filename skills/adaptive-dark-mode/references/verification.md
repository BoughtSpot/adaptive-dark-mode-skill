# Verification

Verify in layers: automated checks you can run yourself, then a state walkthrough, then the Safari-only checks you hand to the user. When reporting, say exactly which of these you ran.

## 1. Automated

- **Static re-audit:** `python3 -I scripts/audit.py <root>`.
  - Path A: expect a static declaration and no "declared but no dark styles" or "dark theme but undeclared" findings.
  - Path B: expect no accidental `dark` declarations.
- **Runtime probe in both schemes:** use `probe.js` via the in-app browser or `probe.mjs` via Playwright. On path A, the dark run should show:
  - `summary.pageLooksDark: true`, `summary.usedScheme: "dark"`, `summary.schemeMismatch: null`, and `formControls.mismatched: 0`. The light run should show the same with `"light"`.
  - zero or near-zero `textContrastFailures` (inspect any that remain, since text over images is low confidence)
  - no large `lightIslands` except intentional tiles
  - no `lowContrastIcons`
  - `colorSchemeOverrides` limited to intended islands
  - the light run unchanged from before your edits
- **Screenshots:** compare before and after for the light scheme (it should be identical unless light changes were intended), and look at the dark one with your own eyes.
- **Type check, build, and the project's tests**, if you touched components.
- **Keep it from regressing:** suggest adding `python3 -I <skill-dir>/scripts/audit.py . --fail-on high` (or a vendored copy) to the project's CI. It exits 1 on high-severity findings such as an undeclared dark theme or a declaration with no dark styles.

## 2. Pages and states to walk (dark scheme, then light)

Probe and screenshot a representative set, not just the home page:

| Area | Check |
|---|---|
| Home, landing | hero text over images/gradients, logo, nav, footer |
| Long-form content | body text, links (visited too), blockquotes, code blocks, tables (zebra rows), `<hr>`, embedded media |
| Listing, product | product photos (white boxes?), badges, price colors, ratings stars |
| Forms | inputs, placeholders, autofill, focus ring, validation errors, disabled state, checkboxes and radios (`accent-color`), selects, date pickers |
| Overlays | dropdowns, hover menus, tooltips, modals, the backdrop, toasts, popovers |
| Data | charts (canvas vs SVG), maps, dashboards |
| Embeds | video, payments, social posts, third-party widgets, own iframes |
| States | hover, active, selected, `::selection`, skeleton loaders, empty states, 404 and error pages |
| Auth | login, sign-up, password reset (often a separate layout) |

With a browser automation tool, trigger hover and focus states with hover actions and Tab key presses, then screenshot.

## 3. Flash and persistence test

1. Set the system (or emulated) scheme to dark, clear site storage, and hard-reload with the cache disabled. There should be no white flash before the page goes dark.
2. Choose "light" in the site toggle and reload. It should stay light, with no dark flash.
3. Choose "system", then flip the OS scheme. The page should follow without a reload, if the toggle supports live updates.
4. With JavaScript disabled (if feasible), the page should still be consistent: either fully light or fully dark, never UA-dark controls in light panels.
5. Navigate between pages (client routing, Turbo, View Transitions). The theme should persist with no flash.

## 4. Safari 27.3 (hand to the user; Adaptive Dark Mode can't be automated)

Give the user these steps, filled in with the specific URLs and states from your findings:

1. Use Safari 27.3 beta or later on macOS or iOS, with System Settings › Appearance set to Dark.
2. Open the site.
   - **Path A:** Safari shouldn't transform it. What you see is your own dark theme. If Safari offers the "Try" preview, the declaration probably isn't being picked up: check that the meta tag is in the delivered HTML (view source) and not only added by JavaScript.
   - **Path B:** accept the "Try" preview, then walk the table in §2. Pay extra attention to raster logos, photos, canvas and charts, anything using blend modes or masks, and iframes.
3. Check every opt-out island (`light only`). It has no effect in 27.3 beta 1, so record what happens and re-check on later builds.
4. Report site problems through Feedback Assistant. Contact web-evangelist@apple.com for site-owner questions.

## 5. Contrast thresholds used

- Normal text: ≥ 4.5:1 (WCAG 1.4.3 AA). Large text (≥ 24px, or ≥ 18.66px bold): ≥ 3:1.
- Icons, focus rings, input borders, and other meaningful non-text UI: ≥ 3:1 (WCAG 1.4.11).
- Disabled controls are exempt, but should still look intentionally disabled, not broken.
