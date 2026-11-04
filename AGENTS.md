# AGENTS.md

Context for coding agents (and humans) working **on** this repository. If you only want to **use** the skill, read [`skills/adaptive-dark-mode/SKILL.md`](skills/adaptive-dark-mode/SKILL.md) instead.

## What this repo is

An [Agent Skill](https://agentskills.io/specification) named `adaptive-dark-mode`. It teaches an agent to audit a website's theming and make it ready for Safari 27.3's Adaptive Dark Mode, which automatically darkens light sites that don't declare `color-scheme: light dark`. The repo is also a Claude Code plugin and marketplace (`.claude-plugin/`).

Everything an agent loads at runtime lives in `skills/adaptive-dark-mode/`. Everything else (tests, CI, docs, manifests) exists to keep that folder correct.

## Layout

```text
skills/adaptive-dark-mode/
  SKILL.md                 Entry point. Frontmatter (name, description, license, compatibility, metadata)
                           + workflow, three-path decision, fix order, report template. Keep < 500 lines.
  references/
    adm-facts.md           Everything WebKit has published, plus a separate "Open questions" list.
    fix-patterns.md        Copy-ready fixes, sections "## §1" … "## §9". Cited as "fix-patterns §N" everywhere.
    frameworks.md          Per-stack notes. Agents read only the section for the stack they find.
    verification.md        Automated checks, manual state checklist, flash test, Safari-only steps.
  scripts/
    audit.py               Static scanner. Python 3.9+, standard library only, Pillow optional.
    probe.js               Runtime probe. ONE self-contained browser expression returning JSON.
    probe.mjs              Playwright runner for probe.js (light + dark, screenshots, JSON).
tests/
  fixtures/<site>/         Tiny fake sites with known bugs. See tests/fixtures/README.md.
  test_audit.py            unittest: verdict + finding IDs per fixture, CLI flags, directory skipping.
  probe.test.mjs           node:test + Playwright (Chromium, WebKit): probe.js summary per fixture/scheme.
  validate_skill.py        Agent Skills spec checks + repo invariants (see below).
.claude-plugin/            plugin.json, marketplace.json, icon.png
.github/                   CI, Dependabot, issue/PR templates, social preview image
docs/images/               README images (generated, see "Regenerating images")
```

## Commands

```bash
npm install && npx playwright install chromium webkit   # once
npm test                                                # everything below
python3 -I -m unittest discover -s tests -v             # audit tests (no Node needed)
python3 -I tests/validate_skill.py                      # spec + invariants
npm run test:probe                                      # probe tests (PROBE_BROWSERS=chromium to go faster)
claude plugin validate .                                # plugin + marketplace manifests (if Claude Code is installed)
```

CI (`.github/workflows/ci.yml`) runs the audit tests on Python 3.9 (no Pillow), 3.12 and 3.14 (with Pillow), the probe tests in Chromium and WebKit, and `claude plugin validate`.

## Invariants (the validator and tests enforce most of these)

1. **Portable skill.** Nothing under `skills/` may assume a specific agent product. Don't name product-specific tools (`mcp__…`, `resize_window`, and so on) or local paths. Say "a browser automation tool", not a particular one. `validate_skill.py` rejects leaks.
2. **Facts vs. unknowns.** Anything stated as Safari behavior must trace to the WebKit post (or a later official WebKit source) and live in `adm-facts.md` sections 1–7. Anything inferred or untested goes in section 8, "Open questions". When a fact changes, update `adm-facts.md`, the facts bullets in `SKILL.md`, `metadata.facts-as-of`, and `CHANGELOG.md` together.
3. **Spec limits.** `name` matches the directory, `description` ≤ 1024 chars, `compatibility` ≤ 500 chars, SKILL.md body < 500 lines. Keep references one level deep from SKILL.md.
4. **Every bundled file is discoverable.** Each file in `references/` and `scripts/` must be mentioned in SKILL.md, and every mention must exist. Every `§N` citation must match a `## §N` heading in `fix-patterns.md`.
5. **One version everywhere.** `metadata.version` in SKILL.md, `__version__` in audit.py, `.claude-plugin/plugin.json`, the marketplace entry, `package.json`, `CITATION.cff` (plus `date-released`), and the latest `CHANGELOG.md` heading must agree.
6. **audit.py stays dependency-free.** Standard library only. Pillow is optional and must fail soft. It must run on Python 3.9: no `match`, no 3.12-only f-string nesting. It reads files and never writes or executes project code.
7. **probe.js stays a single expression** that returns a JSON-serializable object, uses no imports, makes no network requests, and **never mutates the page** (a test asserts the DOM is unchanged). It must work pasted into a console, through `page.evaluate(string)`, and through `(0, eval)(src)`.
8. **Findings explain themselves.** Each finding has a stable `id` (tests key on it), a severity, a *why* in terms of what Safari does, and a *fix* that cites `fix-patterns §N`.
9. **Light theme is sacred.** Fix guidance must keep the existing light rendering identical (`light-dark(<existing>, <new>)`) unless the user asks otherwise.

## Adding a check

1. Decide whether it's static (audit.py) or rendered (probe.js). Prefer the probe for anything that depends on how colors combine.
2. Add or extend a fixture in `tests/fixtures/` that reproduces it, and document it in `tests/fixtures/README.md`.
3. Implement it.
   - **audit.py:** add a regex near the others, emit it with `rep.add(ID, severity, title, why, fix, ...)` in `scan_text` or `derive_findings`, and keep IDs SCREAMING_SNAKE.
   - **probe.js:** add a field to `report` and a count to `report.summary` if it's a headline number.
4. Assert it in `tests/test_audit.py` or `tests/probe.test.mjs`. Also assert that `good/` stays clean (zero findings, no mismatch).
5. If agents should act on it, mention it in SKILL.md (step 3 lists the probe fields to read first) or in the relevant reference file.
6. Add a CHANGELOG entry under `[Unreleased]`.

## Releasing

1. Bump the version in the seven places listed under invariant 5, then move `[Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD`.
2. Run `npm test` and `claude plugin validate .`.
3. Commit as `chore(release): vX.Y.Z`, tag `vX.Y.Z`, and push the tag. The README's CI snippet pins a tag, so update it on major releases.

## Regenerating images

- `docs/images/the-two-bugs.png`: WebKit screenshots of `tests/fixtures/declared-incomplete/` and `media-undeclared/` with `colorScheme: 'dark'` at 760×660, composed with captions.
- `.claude-plugin/icon.png` (1024², also `docs/images/icon-256.png`) and `.github/social-preview.png` (1280×640): drawn with Pillow. Text uses Inter and IBM Plex Mono, both under the SIL Open Font License. Don't use system fonts whose licenses forbid redistribution in artwork.

## Commit conventions

Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat(audit): …`, `fix(probe): …`, `docs(skill): …`, `test: …`, `ci: …`). Explain *why* in the body, especially any change to Safari facts (cite the source) or to a finding's severity.
