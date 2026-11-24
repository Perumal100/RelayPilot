# Sanitized development log

## 2026-11-19 (America/New_York)

### 02:53

- Started RelayPilot from an empty local Git repository on Windows.
- Inspected available runtime: Python 3.14, Node 24, and Git are present; GitHub CLI is unavailable.
- Implemented and tested the first end-to-end deterministic offline file workflow with policy enforcement and verification.
- Created the empty `main` bootstrap and pushed the initial tested RelayPilot source to `develop`. No PR was created and `main` has no application source.
- CI initially failed because the hosted runner does not preinstall `setuptools`; replaced the packaging-dependent test setup with a direct `src`-path test invocation.
- CI passed on `develop` after the correction; local and hosted suites each passed all five tests.

### 03:02

- Added a bounded, read-only Heat-Signal status workflow with executor-side HTTPS allow-list enforcement.
- Added mocked connected-read, offline/connectivity, and ungranted-site regression tests; local suite passed 8 tests.
- Pushed the browser milestone to `develop`; the 8-test local and GitHub Actions suites passed.
- Opened review PR #1 from `develop` to `main`.

### 03:23

- Added configurable local settings, redacted local run history, a typed Windows window/monitor adapter, planner extension interfaces, and bounded timeout reconciliation.
- Added the synthetic interactive demo, manual GitHub Pages workflow, portable zipapp packaging script, and deployment/trial guide.
- Ran and passed 15 automated tests, built and inspected `RelayPilot.pyz`, and completed a live read-only Heat-Signal status trial. The initial restricted-network trial reported a clear connectivity blocker; the permitted live retry returned visible page status.
- Remaining verification is intentionally device/account dependent: real Wispr input, interactive multi-monitor operation, sign-in/MFA handoffs, clean-PC installation, and private GitHub Pages entitlement.

### 03:27

- Observed that PR #1 had been merged externally while the final-baseline commit was in progress. Opened PR #2 for the one remaining `develop` commit and left it unmerged.
- Corrected the engine so configured folder scopes drive both planning and permission checks, then added a regression test.

### 03:50

- Replaced the dated Tkinter interface with a local-only, app-style web workspace featuring modern visual hierarchy, live evidence, local grants/history, and browser voice capture that still requires explicit task submission.
- Added a configurable local data-directory override for constrained environments. Automated validation now passes 18 tests and confirms the portable package includes UI assets.
- Local screenshot-level preview could not bind a loopback socket in the coding sandbox; interactive visual and microphone checks remain for the Windows desktop launch.

### 04:02

- Expanded deterministic local commands to count PDFs in Downloads, find/open the oldest PDF, and open approved local folders. Added editable `readable_folders` scopes.
- A routing conflict in the PDF copy command was found by tests and fixed before release. Automated suite now passes 22 tests.
- GitHub Actions exposed a Windows 8.3 short-path representation difference in a test assertion; corrected the test to compare the actual folder identity rather than path spelling.

### 04:07

- Added a Manifest V3 Chrome companion with an explicit command popup, optional voice transcription, active-tab page reading, Google search/Gmail opening, and a localhost bridge to the local executor.
- Restricted extension permissions to the active tab and local bridge; it does not silently access passwords, cookies, private Google data, or all browser tabs. Automated suite passes 23 tests and validates the manifest.
- Added a settings migration so pre-existing installations gain the new routine local actions and readable-folder scopes once, without overriding later user-managed settings.

### 04:20

- Corrected launch reporting so a completed run means the verified target was handed to Windows for default-app launch; it no longer claims the document or image is visibly open. A Windows launcher error now produces a failed run.
- Added deterministic discovery and launch requests for the newest supported image in Downloads (`.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.bmp`, `.tif`, `.tiff`, `.heic`, and `.avif`).
- Added regression coverage for newest-image selection, truthful launch evidence, launch failures, and the settings migration for the new action.
- Changed the visible terminal state for file/folder opens to `launch requested`; only non-launch workflows use `completed`. This prevents the UI from asserting that a PDF or image viewer window was observed.

## 2026-11-24 (America/New_York)

- Hardened the local HTTP bridge against cross-site requests by validating loopback Host and browser Origin before dispatch, restricting CORS responses, and requiring JSON for POST.
- Added regression coverage that an untrusted website cannot trigger a run or read the local snapshot; the app UI remains able to run an ordinary local command.
- All 29 automated tests passed in the Windows environment, including the loopback HTTP integration test. The GitHub repository has been renamed from `Project-X` to `RelayPilot`.

- Added a short-lived in-app image/PDF preview for files selected by local open workflows. Preview bytes are served through a scoped token and blocked if the file changes after selection; the Windows launch state remains accurately labeled.
- Added HTTP integration coverage for preview MIME/body, cross-site rejection, changed-file invalidation, and the copied-PDF preview path.

