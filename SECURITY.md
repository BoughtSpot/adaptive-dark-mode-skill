# Security policy

## Supported versions

Only the latest release gets security fixes.

## What the tools do

- `audit.py` **reads** files under the directory you pass it. It doesn't write files, execute project code, or make network requests.
- `probe.js` runs inside the page you evaluate it in. It reads computed styles and draws same-origin images to an in-memory canvas. It doesn't modify the page or make network requests.
- `probe.mjs` launches a local Playwright browser, loads the URLs you give it, and writes screenshots and JSON to `--out`.

## Reporting a vulnerability

Please don't open a public issue. Use [GitHub private vulnerability reporting](https://github.com/BoughtSpot/adaptive-dark-mode-skill/security/advisories/new) and include steps to reproduce. You should get an acknowledgement within a few days.

Problems with Safari itself go to Apple through [Feedback Assistant](https://feedbackassistant.apple.com/), not here.
