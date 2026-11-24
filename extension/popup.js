import {classifyCommand} from "./commands.mjs";

const $ = selector => document.querySelector(selector);
const command = $("#command"), voice = $("#voice"), result = $("#result"), connection = $("#connection"), run = $("#run");

function render(state, message, evidence = "") {
  result.querySelector("strong").textContent = String(state || "blocked").replaceAll("_", " ").toUpperCase();
  result.querySelector("p").textContent = `${message}${evidence ? `\n\n${evidence}` : ""}`;
}

async function checkLocalAgent() {
  try {
    const response = await fetch("http://127.0.0.1:8721/api/snapshot");
    if (!response.ok) throw new Error();
    connection.textContent = "Local agent connected";
  } catch {
    connection.textContent = "Browser mode · local agent offline";
  }
}

function browserRun(text) {
  return new Promise(resolve => chrome.runtime.sendMessage({kind: "browser-run", command: text}, output => {
    if (chrome.runtime.lastError || !output) {
      resolve({state: "blocked", message: chrome.runtime.lastError?.message || "The browser action did not return a result."});
    } else resolve(output);
  }));
}

chrome.runtime.sendMessage({kind: "active-tab"}, tab => {
  $("#tabTitle").textContent = tab?.title || "No active tab";
  $("#tabUrl").textContent = tab?.url || "";
});

run.addEventListener("click", async () => {
  const text = command.value.trim();
  if (!text) return render("blocked", "Type or dictate a command first.");
  run.disabled = true;
  try {
    const plan = classifyCommand(text);
    if (plan.kind !== "local") {
      const output = await browserRun(text);
      render(output.state, output.message, output.evidence);
      return;
    }
    const response = await fetch("http://127.0.0.1:8721/api/run", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({command: text}),
    });
    if (!response.ok) throw new Error(`Local agent returned HTTP ${response.status}`);
    const output = await response.json();
    const last = output.events?.at(-1);
    render(output.state, last?.message || output.reason || "Finished", last?.evidence || output.reason || "");
  } catch (error) {
    render("blocked", `Local agent unavailable: ${error.message}. Start RelayPilot and try again.`);
  } finally {
    run.disabled = false;
  }
});

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (Recognition) {
  const recognition = new Recognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  let base = "";
  recognition.onstart = () => { base = command.value; voice.classList.add("listening"); };
  recognition.onresult = event => {
    const words = Array.from(event.results, result => result[0].transcript).join(" ");
    command.value = `${base} ${words}`.trim();
  };
  recognition.onend = () => voice.classList.remove("listening");
  voice.addEventListener("click", () => voice.classList.contains("listening") ? recognition.stop() : recognition.start());
} else {
  voice.disabled = true;
  voice.title = "Use your system dictation in the command box";
}
command.addEventListener("keydown", event => {
  if (event.ctrlKey && event.key === "Enter") { event.preventDefault(); run.click(); }
});
checkLocalAgent();
