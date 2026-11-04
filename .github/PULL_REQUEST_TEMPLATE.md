## What and why

<!-- What does this change, and what goes wrong without it? -->

## Checklist

- [ ] `npm test` passes (or at least `python3 -I -m unittest discover -s tests` and `python3 -I tests/validate_skill.py`)
- [ ] New or changed checks have a fixture in `tests/fixtures/` and an assertion, and `good/` still has zero findings
- [ ] Safari facts cite an official WebKit/Apple source; anything else is under "Open questions" in `adm-facts.md`
- [ ] Nothing under `skills/` assumes a specific agent product or a local path
- [ ] The light theme stays unchanged in any fix guidance
- [ ] `CHANGELOG.md` has an `[Unreleased]` entry
