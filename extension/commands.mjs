const consequential = /\b(send|submit|publish|post|buy|purchase|delete|remove|upload|share|invite|pay)\b/i;

export function classifyCommand(command) {
  const text = String(command || "").trim();
  const search = /^search google(?: for)?\s+(.+)$/i.exec(text);
  if (search) return {kind: "browser-search", query: search[1].trim()};
  if (/^(?:open|go to)\s+(?:gmail|google mail)\s*[.!?]?$/i.test(text)) return {kind: "browser-gmail"};
  if (/^(?:read|inspect)\s+(?:(?:this|the|current|active)\s+)?(?:page|tab)\s*[.!?]?$/i.test(text)
      || /^what(?:'s| is) on\s+(?:(?:this|the|current|active)\s+)?(?:page|tab)\s*[.!?]?$/i.test(text)) {
    return {kind: "browser-read"};
  }
  if (/^summari[sz]e\b/i.test(text)) return {kind: "browser-unsupported"};
  if (consequential.test(text)) return {kind: "handoff"};
  return {kind: "local"};
}
