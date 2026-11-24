# RelayPilot Chrome extension

## Install for local development

1. Start the local RelayPilot app: `py -m relaypilot.app`.
2. In Chrome, open `chrome://extensions` and enable **Developer mode**.
3. Select **Load unpacked** and choose this `extension` folder.
4. Pin RelayPilot. Click it to type or dictate a command, then explicitly choose **Run task**.

## Browser mode

Without the local app running, the extension can explicitly open a Google search, open Gmail in the existing Chrome profile, or read the currently active page after you click Run task. It has only `activeTab` access, not unrestricted background access to every page.

These browser commands now run in Chrome even when the local app is connected. Local file commands go to the local app. `Read this page` returns a bounded visible-text excerpt; RelayPilot does not claim to summarize a page without a configured planner. Reload the unpacked extension in `chrome://extensions` after updating its files.

The extension does not read passwords, browser cookies, or private Google data. Google email, Drive, Calendar, Docs, and other account data require a dedicated OAuth integration with narrow user-approved scopes; that integration is intentionally not silently implied by installing the extension.
