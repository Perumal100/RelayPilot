const previewTypes = new Set([
  "image/avif", "image/bmp", "image/gif", "image/jpeg", "image/png", "image/webp", "application/pdf",
]);

export function localPreview(result) {
  if (result?.state !== "launch_requested" || !previewTypes.has(result.preview_type)) return null;
  if (!/^\/api\/preview\/[A-Za-z0-9_-]{32}$/.test(result.preview_url || "")) return null;
  return {
    url: `http://127.0.0.1:8721${result.preview_url}`,
    type: result.preview_type,
    name: String(result.preview_name || "Selected file"),
  };
}
