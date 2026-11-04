# Test fixtures

Each directory is a tiny "site" with known theming problems. `test_audit.py` asserts the static audit's verdict and findings, and `probe.test.mjs` asserts the runtime probe's results in light and dark. When you add a check to `audit.py` or `probe.js`, add or extend a fixture here and assert it.

| Fixture | What it represents | Expected verdict |
|---|---|---|
| `good/` | Static `light dark` declaration, `light-dark()` tokens, `theme-color` per scheme, `currentColor` SVG | skipped (declared), no findings |
| `declared-incomplete/` | Declares `light dark` but every color is a light literal | declared but no dark styles found (`DECLARED_NO_DARK`) |
| `declared-class-only/` | Declares `light dark`; dark tokens only under `.dark` | skipped (declared) + `CLASS_MISMATCH` |
| `media-undeclared/` | Dark theme via `prefers-color-scheme`, no declaration; white promo box; dark-on-transparent logo; near-black icon | probably skipped as already dark (`DARK_UNDECLARED`) |
| `ld-undeclared/` | `light-dark()` tokens but no declaration, so dark never activates | converted (light-dark() without declaration) |
| `js-only-declaration/` | `color-scheme` set only from JavaScript | `JS_ONLY_DECL` |
| `tw-next-undeclared/` | Next.js + Tailwind v3 `darkMode: 'class'` + next-themes `defaultTheme="light"`, sprites, tiled bg, mask icon, blend mode, canvas chart, iframe, raster logo | converted (dark theme exists but is undeclared) |

The PNG/JPEG files are generated, a few hundred bytes each. `test_audit.py` also creates a throwaway `node_modules/` at runtime to prove vendored directories are skipped. (Git ignores `node_modules`, so it can't live in the fixture.)
