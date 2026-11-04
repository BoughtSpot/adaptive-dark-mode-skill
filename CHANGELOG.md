# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The skill's Safari facts are dated separately in `SKILL.md` (`metadata.facts-as-of`). A change in Safari's documented behavior is at least a minor release.

## [Unreleased]

## [1.0.0] - 2026-11-04

First public release. Safari facts as of WebKit's announcement on 2026-11-03 (Safari 27.3 beta 1).

### Added
- `adaptive-dark-mode` Agent Skill: a workflow to orient, audit, probe, decide, fix, verify and report, with a three-path decision (own dark mode / make it convertible / opt out islands) and the rule "never declare `light dark` without dark styles".
- `references/adm-facts.md`: Safari's documented behavior, kept separate from open questions.
- `references/fix-patterns.md` §1–§9: declaration, three-state theme toggle without a flash, `light-dark()` tokens, UA surfaces, images, canvas and embeds, elevation and effects, brand colors, and a path B checklist.
- `references/frameworks.md`: Tailwind v3/v4, shadcn/ui, Next.js + next-themes, SvelteKit + mode-watcher, Nuxt, Astro, Rails, Bootstrap 5.3, MUI, Chakra, CSS-in-JS, WordPress, plain CSS.
- `references/verification.md`: automated checks, page and state checklist, flash and persistence test, Safari 27.3 steps.
- `scripts/audit.py`: static audit with a verdict, stack detection, declaration and mechanism inventory, color tokenization stats, and 20+ finding types. Has `--json`, `--fail-on`, `--exclude` and `--no-images`. Optional Pillow pixel checks.
- `scripts/probe.js`: runtime probe with `schemeMismatch`, text contrast, light islands, low-contrast icons, image checks, background images, canvas, iframes, blend modes and masks, `color-scheme` overrides, and form-control mismatches.
- `scripts/probe.mjs`: Playwright runner for light and dark, with screenshots and JSON.
- Claude Code plugin and marketplace manifests, fixtures, regression tests (Python 3.9–3.14, Chromium, WebKit), spec validator, and CI.

[Unreleased]: https://github.com/BoughtSpot/adaptive-dark-mode-skill/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/BoughtSpot/adaptive-dark-mode-skill/releases/tag/v1.0.0
