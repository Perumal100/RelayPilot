import {classifyCommand} from "./commands.mjs";

async function activeTab() {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  return tab;
}

async function readActivePage() {
  const tab = await activeTab();
  if (!tab?.id) throw new Error("No active browser tab is available.");
  const [result] = await chrome.scripting.executeScript({
    target: {tabId: tab.id},
    func: () => ({title: document.title, url: location.href, text: document.body?.innerText?.slice(0, 5000) || ""}),
  });
  if (!result?.result) throw new Error("Chrome could not read this page. Select a normal website tab and try again.");
  return result.result;
}

async function runBrowserCommand(command) {
  const plan = classifyCommand(command);
  if (plan.kind === "handoff") {
    return {state: "handoff", message: "This could send, publish, buy, share, upload, or delete. RelayPilot stopped before taking that consequential action."};
  }
  if (plan.kind === "browser-search") {
    await chrome.tabs.create({url: `https://www.google.com/search?q=${encodeURIComponent(plan.query)}`});
    return {state: "launch_requested", message: `Requested a Google search tab for “${plan.query}”.`};
  }
  if (plan.kind === "browser-gmail") {
    await chrome.tabs.create({url: "https://mail.google.com/"});
    return {state: "launch_requested", message: "Requested a Gmail tab in your Chrome profile. Sign-in and account prompts remain yours."};
  }
  if (plan.kind === "browser-read") {
    const page = await readActivePage();
    return {state: "completed", message: `Read visible text from: ${page.title || page.url}`, evidence: page.text.slice(0, 700) || "No readable page text."};
  }
  if (plan.kind === "browser-unsupported") return {state: "blocked", message: "Summarization is not configured. Try “read this page” to inspect visible text."};
  return {state: "blocked", message: "Use a local RelayPilot command, “search Google …”, “open Gmail”, or “read this page”."};
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.kind === "browser-run") {
    runBrowserCommand(message.command).then(sendResponse).catch(error => sendResponse({state: "blocked", message: error.message}));
    return true;
  }
  if (message.kind === "active-tab") {
    activeTab().then(tab => sendResponse({title: tab?.title || "No active tab", url: tab?.url || ""}))
      .catch(error => sendResponse({title: "Tab unavailable", url: "", error: error.message}));
    return true;
  }
});
