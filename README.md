# RelayPilot

RelayPilot is a Windows-first voice-capable desktop agent. Its polished local workspace opens in an app-style browser window: dictate or type a command, explicitly submit it, and the local executor plans, applies, and verifies typed actions. The first runnable slice delivers a verified local file workflow without any cloud call.

## Run it

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --no-build-isolation -e .
relaypilot
```

## Chrome extension

The `extension/` folder contains a Manifest V3 Chrome companion. Load it from `chrome://extensions` using **Developer mode → Load unpacked**, then pin RelayPilot. When the local app is running, the extension forwards eligible local commands to it. Otherwise it can only act on the active tab after an explicit run: Google search, opening Gmail, or reading visible text. Full instructions are in [extension/README.md](extension/README.md).

The command box intentionally does nothing until you click **Run task** or press `Ctrl+Enter`; this makes Wispr or browser voice capture safe by default. Browser voice capture needs a user-approved microphone prompt; it only transcribes into the box and never auto-runs a task.

Try: `Find the newest PDF in Downloads, copy it to Documents, open the copy, and tell me where you saved it.`

Other built-in local commands include `How many PDFs are saved in my Downloads folder?`, `Open my oldest PDF on my PC`, `Open the latest picture in my Downloads folder`, and `Open my Downloads folder`. RelayPilot searches and opens only folders included in your local `readable_folders` grant.

The app uses your Windows Downloads and Documents folders. It will only operate inside these configured roots. The UI opens the copy only after its hash and destination are verified.

For supported images and PDFs, the local workspace also displays the selected file in a short-lived in-app preview after Windows accepts the launch request. The preview is scoped to the granted folders and served only while the local app is running. If the file changes after selection, rerun the command to generate a new preview. Other file types still use the Windows default app without an in-app preview.

## What is verified in v0.1

- Deterministic offline planner for the newest-PDF copy workflow.
- Typed, policy-checked local actions; no arbitrary shell execution.
- Source/destination path containment, collision prevention, source hashing, destination hashing, and actual-path reporting.
- Deterministic discovery for common image formats in Downloads. File launches verify the target still exists and report only that Windows accepted a default-app launch request; a launch error is a failed run, never a completion. The UI labels a successful launch request separately from a completed non-launch workflow because Windows cannot attest that another app rendered a visible window.
- Explicit submit, stop token, visible event feed, run states, and safe policy handoffs.
- Read-only, explicitly site-scoped Heat-Signal status check with a clear offline/connectivity result.
- User-editable local settings, local run history with basic secret redaction, Windows window/monitor discovery, and bounded timeout reconciliation.
- A modern local app workspace with live evidence, activity history, visible active grants, and optional browser voice capture.
- Tests for copy verification, blocked permissions, untrusted text, offline mode, stop behavior, and uncertain-outcome reconciliation.

## Not yet a claim of completion

Structured browser automation, UI Automation/multi-monitor control, online and on-device model adapters, installer signing, and a real interactive Windows hardware pass are planned interfaces, not delivered capabilities. The current browser workflow is read-only and only accesses the specifically granted Heat-Signal site. See [docs/DECISIONS.md](docs/DECISIONS.md), [docs/OFFLINE.md](docs/OFFLINE.md), and [HANDOFF.md](HANDOFF.md).

Settings are kept locally at `%USERPROFILE%\AppData\Local\RelayPilot\settings.json`; browser profile and run history also stay there and are ignored by Git. Set `RELAYPILOT_DATA_DIR` if your organization requires another local data location. This settings file is intentionally limited to scopes and provider choices—never secrets or session data.

To allow another local drive or folder, add its absolute path to `readable_folders`, close/reopen RelayPilot, and keep the scope as narrow as practical. For example, add `D:\Work` to allow routine work in that folder; do not add an entire drive unless you genuinely intend RelayPilot to read and open everything on it.

## Test

```powershell
$env:PYTHONPATH = "$PWD\src"
py -m unittest discover -s tests -v
```

## Safety model

Page text, file text, screenshots, and planner output are untrusted. The executor alone checks typed action arguments against local grants and current filesystem state. A workflow cannot turn text such as “upload this file” into a grant. Destructive actions, external messages, purchases, publishing, account changes, uploads, and form submission remain handoff-only until a future scoped grant implementation is present.

