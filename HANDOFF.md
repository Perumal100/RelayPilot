# RelayPilot handoff

## Current state

The GitHub repository is now `Perumal100/RelayPilot` (renamed from `Project-X`). PRs #1–#5 were merged; the current `develop` branch still contains the tested app baseline. The expected command finds the newest `.pdf` under Downloads, copies it into Documents, verifies both hashes, and requests that Windows launch the verified copy when allowed.

The connected `Open Heat-Signal and report the visible status` workflow is now also available. It is read-only, checks a single granted HTTPS site, and reports a connectivity blocker instead of guessing when offline.

The local settings file makes allowed folders/sites editable, and a local JSONL history records redacted run evidence. `scripts/package.ps1` produces `dist\\RelayPilot.pyz`; `docs/DEPLOYMENT.md` contains the full trial and GitHub Pages process. The interactive synthetic demo is `demo/index.html` and the manual Pages workflow is `.github/workflows/pages.yml`.

Verified in this development environment: automated tests, portable package contents, and a live read-only Heat-Signal status response. The test results are recorded in `docs/DEVELOPMENT_LOG.md`.

The current UI is served locally by `relaypilot.webapp` and launched as an app-style browser window by `relaypilot.app`. It provides optional browser voice capture as transcription only; the user still explicitly runs each task. Validate the visual layout and microphone browser prompt on the interactive Windows desktop after updating from `develop`.

Deterministic local file workflows now also cover counting PDFs in Downloads, opening the oldest PDF, opening the latest supported picture in Downloads, and opening approved local folders. File-launch evidence now accurately records the verified target and Windows launch request; it does not claim that an app window became visible. The UI records this as `launch requested`, not `completed`. Add a local folder to `readable_folders` in settings before using it; latest automated validation is recorded in the development log.

The local HTTP bridge now checks the loopback Host, restricts browser Origins to its own UI and Chrome extension origins, and requires JSON for POST. Cross-site requests cannot invoke `/api/run` or read `/api/snapshot` through a browser. The loopback server still accepts explicit local command-line clients without an Origin header.

The local workspace now offers a short-lived in-app preview for selected images and PDFs. The engine records the file selected after a Windows launch request; the service issues an opaque preview token, rechecks the file scope and modification time, and streams it to the local UI. The visible image load is distinct from the native viewer launch state. Unsupported formats still use the native viewer alone.

## Resume steps

1. Run `py -m unittest discover -s tests -v`.
2. Launch with `py -m relaypilot.app` and exercise the command using a non-sensitive test PDF.
3. Add Windows UI Automation behind `DesktopAdapter` and structured browser control behind `BrowserAdapter`; do not weaken `Policy` or expose shell access.
4. Continue committing all source work to `develop` and open or update a review PR. Merge it into `main` only after review.

## Still unverified on Perumal's PC

- Wispr dictation focus and submit behavior.
- Interactive Windows open action, second monitor, and mixed-DPI UI automation.
- Browser sign-in/MFA handoffs and any online planner/provider.
- Clean-machine packaged installation.
- GitHub Pages availability/deployment for this private repository, which depends on the account's Pages entitlement and an explicit manual workflow run.

