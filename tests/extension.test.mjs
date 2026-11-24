import test from "node:test";
import assert from "node:assert/strict";
import {classifyCommand} from "../extension/commands.mjs";

test("browser requests route to Chrome while local file requests stay local", () => {
  assert.deepEqual(classifyCommand("Search Google for Tableau examples"), {kind: "browser-search", query: "Tableau examples"});
  assert.equal(classifyCommand("Open Gmail").kind, "browser-gmail");
  assert.equal(classifyCommand("Read this page").kind, "browser-read");
  assert.equal(classifyCommand("Open the latest picture in my Downloads").kind, "local");
});

test("read-only search terms do not become consequential actions", () => {
  assert.deepEqual(classifyCommand("search Google how to delete a file"), {kind: "browser-search", query: "how to delete a file"});
  assert.equal(classifyCommand("Delete the active tab").kind, "handoff");
  assert.equal(classifyCommand("Send this page to someone").kind, "handoff");
});

test("summarization is not mislabeled as a page read", () => {
  assert.equal(classifyCommand("Summarize this page").kind, "browser-unsupported");
  assert.equal(classifyCommand("Read current tab").kind, "browser-read");
});

test("popup sends browser tasks to Chrome and renders page text as text", async () => {
  const saved = {chrome: globalThis.chrome, document: globalThis.document, window: globalThis.window, fetch: globalThis.fetch};
  const elements = new Map();
  const element = name => ({name, textContent: "", value: "", listeners: {}, addEventListener(type, callback) { this.listeners[type] = callback; }});
  for (const name of ["#command", "#voice", "#connection", "#run", "#tabTitle", "#tabUrl"]) elements.set(name, element(name));
  const title = element("result title"), paragraph = element("result message"), result = element("#result");
  result.querySelector = selector => selector === "strong" ? title : paragraph;
  Object.defineProperty(result, "innerHTML", {set() { throw new Error("Untrusted HTML insertion"); }});
  elements.set("#result", result);
  const localRuns = [];
  const browserRuns = [];
  globalThis.document = {querySelector: selector => elements.get(selector)};
  globalThis.window = {};
  globalThis.chrome = {runtime: {sendMessage(message, callback) {
    if (message.kind === "active-tab") return callback({title: "Active page", url: "https://example.test"});
    browserRuns.push(message.command);
    callback({state: "completed", message: "Read page", evidence: "<img src=x onerror=alert(1)>"});
  }}};
  globalThis.fetch = async (url, options) => {
    if (url.endsWith("/api/snapshot")) return {ok: true};
    localRuns.push(JSON.parse(options.body).command);
    return {ok: true, json: async () => ({state: "launch_requested", events: [{message: "Launch requested", evidence: "file exists"}]})};
  };
  try {
    await import("../extension/popup.js?routing-test");
    elements.get("#command").value = "Read this page";
    await elements.get("#run").listeners.click();
    assert.deepEqual(browserRuns, ["Read this page"]);
    assert.deepEqual(localRuns, []);
    assert.equal(paragraph.textContent, "Read page\n\n<img src=x onerror=alert(1)>");

    elements.get("#command").value = "Open the latest picture in my Downloads";
    await elements.get("#run").listeners.click();
    assert.deepEqual(localRuns, ["Open the latest picture in my Downloads"]);
    assert.equal(title.textContent, "LAUNCH REQUESTED");
  } finally {
    Object.assign(globalThis, saved);
  }
});

test("background performs only the requested browser action", async () => {
  const saved = globalThis.chrome;
  const opened = [];
  let reads = 0;
  let listener;
  globalThis.chrome = {
    tabs: {query: async () => [{id: 7}], create: async ({url}) => { opened.push(url); }},
    scripting: {executeScript: async () => { reads++; return [{result: {title: "Example", url: "https://example.test", text: "Visible page text"}}]; }},
    runtime: {onMessage: {addListener(callback) { listener = callback; }}},
  };
  try {
    await import("../extension/background.js?behavior-test");
    const send = command => new Promise(resolve => listener({kind: "browser-run", command}, {}, resolve));
    assert.equal((await send("Search Google for heat reports")).state, "launch_requested");
    assert.equal(opened[0], "https://www.google.com/search?q=heat%20reports");
    const page = await send("Read this page");
    assert.equal(page.state, "completed");
    assert.equal(page.evidence, "Visible page text");
    assert.equal(reads, 1);
    assert.equal((await send("Summarize this page")).state, "blocked");
    assert.equal((await send("Delete this page")).state, "handoff");
    assert.equal(reads, 1);
  } finally {
    globalThis.chrome = saved;
  }
});
