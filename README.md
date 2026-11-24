# RelayPilot

RelayPilot is an early Windows task assistant with a local app-style workspace and a Chrome companion extension. You can type a command or dictate into the command box, review it, and explicitly run it. The local planner handles a defined set of file tasks without a cloud model; the extension handles a few explicit Chrome tasks. RelayPilot does not yet understand arbitrary requests or control your whole PC or Google account.

## Project status

As of November 24, 2026, PRs [#7](https://github.com/Perumal100/RelayPilot/pull/7) and [#8](https://github.com/Perumal100/RelayPilot/pull/8) are merged into `develop`. They added reliable browser command routing and in-app previews for selected images and PDFs. `main` has not received those two PRs. Use `develop` for the current trial; review it before promoting it to `main`.

The source, local app, and unpacked Chrome extension are available for a developer trial. There is no signed Windows installer or hosted agent. The [synthetic demo](demo/) is intended for GitHub Pages; it is not the working app. A full interactive pass on a Windows desktop, including microphone behavior and native viewer visibility, is still outstanding.

## Try the current build on Windows

Install Python 3.11 or newer. In PowerShell:

```powershell
git clone --branch develop https://github.com/Perumal100/RelayPilot.git
cd RelayPilot
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
relaypilot
```

The app serves a local workspace at `http://127.0.0.1:8721` and opens it in an app-style browser window. Keep the PowerShell process running while you use it. If you already have a checkout, switch to `develop` and pull before launching. For a source-only run without installation, set `$env:PYTHONPATH = "$PWD\src"` and run `py -m relaypilot.app`.

Enter one of these supported local commands and click **Run task** or press `Ctrl+Enter`:

| Command example | Current behavior |
| --- | --- |
| `Find the newest PDF in Downloads, copy it to Documents, open the copy, and tell me where you saved it.` | Selects the newest PDF, copies it without overwriting an existing file, verifies the destination hash, and requests a Windows default-app launch. |
| `How many PDFs are saved in my Downloads folder?` | Counts PDFs in the configured Downloads folder. |
| `Open my oldest PDF on my PC` | Selects the oldest PDF from the configured Downloads folder and requests a launch. It does not search the whole PC. |
| `Open the latest picture in my Downloads folder` | Selects the newest supported image from Downloads and requests a launch. |
| `Open my Downloads folder` or `Open my Documents folder` | Requests a Windows folder launch. |
| `Open my local disk D` | Requests a launch only if `D:\` is explicitly allowed in `readable_folders`. |
| `Open Heat-Signal and report the visible status` | Reads the specifically granted Heat-Signal HTTPS site; connectivity is required. |

Windows accepting a file launch does not prove that a separate viewer window appeared. RelayPilot reports `launch_requested` for that outcome. For supported images and PDFs, the local workspace also shows a short-lived preview of the selected file. The preview checks the folder grant again and expires or becomes invalid if the file changes. Other file types have no in-app preview.

## Chrome companion

Open `chrome://extensions`, enable **Developer mode**, select **Load unpacked**, choose this repository's `extension` folder, and pin RelayPilot. Reload the unpacked extension there after pulling updates. See the [extension guide](extension/README.md).

The extension recognizes `Search Google for ...`, `Open Gmail`, and `Read this page`. These commands run in Chrome even when the local app is connected. Google search and Gmail open tabs; `Read this page` returns a bounded excerpt of visible text from the active tab. The extension sends supported local file commands to the local app, which must be running for them to work. It does not summarize pages, read Gmail messages, or access Drive, Calendar, browser passwords, cookies, and every tab. It uses Chrome's active-tab grant for page reading.

Voice capture is optional in both interfaces when the browser exposes speech recognition. It places a transcript in the command box and never submits it automatically. Review the text before running it. Browser speech recognition may use the browser vendor's speech service; the local file planner itself does not require a cloud model.

## Settings and limits

Local settings and redacted run history are stored under `%USERPROFILE%\AppData\Local\RelayPilot`. Set `RELAYPILOT_DATA_DIR` before launch to use another local directory. The `settings.json` file contains folder and site grants, not account secrets. By default, the local file workflows use Downloads and Documents.

To allow the existing `Open my local disk D` workflow, add `D:\` to `readable_folders` in `settings.json` using JSON escaping (`"D:\\"`), then restart RelayPilot. Adding another folder grants scope to actions that already target it; it does not teach the deterministic planner a new natural-language command for every path. `documents` is the copy destination for the supported PDF workflow.

RelayPilot checks typed actions against folder and site grants. It does not offer arbitrary shell execution. Sending messages, uploading, purchases, publishing, deletion, form submission, and other consequential actions stop at a handoff. Online or on-device model planning, general browser automation, desktop UI automation, and a signed installer are not implemented. See [design decisions](docs/DECISIONS.md), [offline behavior](docs/OFFLINE.md), and the [trial and packaging guide](docs/DEPLOYMENT.md).

## Tests and packaging

From the repository root, run the Python and extension suites:

```powershell
$env:PYTHONPATH = "$PWD\src"
py -m unittest discover -s tests -v
node --test tests/extension.test.mjs
```

The extension tests use Node.js 22 in CI. The latest merged work passed 31 Python tests and five extension tests in [GitHub Actions](https://github.com/Perumal100/RelayPilot/actions/runs/45510102512). These tests cover the supported workflows and HTTP boundaries; they do not substitute for an interactive hardware trial.

For a Python-equipped Windows machine, `powershell -ExecutionPolicy Bypass -File scripts\package.ps1` creates `dist\RelayPilot.pyz`. Run it with `py dist\RelayPilot.pyz`. This is a portable Python package, not an installer or a cloud deployment link.
