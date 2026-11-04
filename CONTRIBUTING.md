# Contributing

Thanks for helping. This project is most useful when it matches what Safari actually does, so **reports of real-world Safari behavior are as valuable as code.**

## Ways to help

- **Safari observations.** Did Adaptive Dark Mode behave differently from what [`adm-facts.md`](skills/adaptive-dark-mode/references/adm-facts.md) says, or resolve one of its open questions (iframes, plain `light`, script-set declarations, …)? Open a "Safari behavior" issue with the Safari version, OS, a URL or minimal HTML, and screenshots.
- **False positives and negatives.** The audit is heuristic. A minimal snippet that reproduces a wrong finding is the most helpful bug report.
- **Framework notes.** Corrections or new sections for `frameworks.md`. Please include the framework version you tested.
- **Code.** New checks, better heuristics, fixes.

## Development setup

```bash
git clone https://github.com/BoughtSpot/adaptive-dark-mode-skill.git
cd adaptive-dark-mode-skill
npm install
npx playwright install chromium webkit
npm test
```

The audit tests and the validator need only Python 3.9+. The probe tests need Node 18+ and Playwright.

## Pull requests

- Read [AGENTS.md](AGENTS.md). Its invariants are also the review checklist, and `tests/validate_skill.py` enforces most of them.
- Every new check needs a fixture in `tests/fixtures/` and an assertion. `good/` must stay clean.
- Keep `audit.py` on the standard library, and keep `probe.js` a single expression that doesn't touch the page.
- Safari facts must cite an official WebKit or Apple source. Anything else goes under "Open questions".
- Keep the light theme unchanged in any fix guidance.
- Add a line to `CHANGELOG.md` under `[Unreleased]`.
- Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.

## Code of conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
