from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any, BinaryIO

from .config import RelaySettings, default_settings_path
from .engine import RelayEngine
from .history import RunHistory
from .models import Action, RunState
from .policy import PolicyDenied


_PREVIEW_MIME = {
    ".pdf": "application/pdf", ".avif": "image/avif", ".bmp": "image/bmp", ".gif": "image/gif",
    ".jpeg": "image/jpeg", ".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
}
_PREVIEW_MAX_BYTES = 64 * 1024 * 1024
_PREVIEW_SECONDS = 600


@dataclass(frozen=True)
class PreviewRecord:
    path: Path
    mime: str
    size: int
    modified_ns: int
    device: int
    inode: int
    expires_at: float


class RelayService:
    """Local-only façade shared by the modern UI and executor."""

    def __init__(self, settings_path: Path | None = None) -> None:
        self.settings_path = settings_path or default_settings_path()
        fallback = RelaySettings.defaults(Path.home() / "Downloads", Path.home() / "Documents")
        self.settings = RelaySettings.load(self.settings_path, fallback)
        if not self.settings_path.exists():
            self.settings.save(self.settings_path)
        self.history = RunHistory(self.settings_path.with_name("history.jsonl"))
        self.engine = RelayEngine(Path(self.settings.downloads), Path(self.settings.documents), settings=self.settings, history=self.history)
        self._run_lock = threading.Lock()
        self._preview_lock = threading.Lock()
        self._previews: dict[str, PreviewRecord] = {}

    def run(self, command: str) -> dict[str, Any]:
        if not command.strip():
            return {"state": "blocked", "reason": "Enter a command, then explicitly submit it.", "events": []}
        if not self._run_lock.acquire(blocking=False):
            return {"state": "blocked", "reason": "A run is already active. Stop it or wait for completion.", "events": []}
        try:
            result = self.engine.run(command)
            preview = self._register_preview(result.opened_path) if result.state == RunState.LAUNCH_REQUESTED else None
            return {
                "state": result.state.value,
                "reason": result.reason,
                "saved_path": str(result.saved_path) if result.saved_path else None,
                "preview_url": f"/api/preview/{preview[0]}" if preview else None,
                "preview_type": preview[1] if preview else None,
                "preview_name": result.opened_path.name if preview else None,
                "events": [{"message": event.message, "evidence": event.evidence} for event in result.events],
            }
        finally:
            self._run_lock.release()

    def stop(self) -> dict[str, str]:
        self.engine.request_stop()
        return {"status": "Stop requested. No further actions will be issued."}

    def snapshot(self) -> dict[str, Any]:
        return {
            "folders": {"downloads": self.settings.downloads, "documents": self.settings.documents},
            "sites": self.settings.allowed_sites,
            "history": self.history.recent(8),
            "settings_path": str(self.settings_path),
        }

    def _register_preview(self, path: Path | None) -> tuple[str, str] | None:
        if path is None:
            return None
        mime = _PREVIEW_MIME.get(path.suffix.lower())
        if mime is None:
            return None
        try:
            target = path.resolve(strict=True)
            self.engine.policy.authorize(Action("open_file", {"path": target}))
            stat = target.stat()
            if not target.is_file() or stat.st_size > _PREVIEW_MAX_BYTES:
                return None
        except (OSError, PolicyDenied):
            return None
        token = secrets.token_urlsafe(24)
        record = PreviewRecord(
            target, mime, stat.st_size, stat.st_mtime_ns, stat.st_dev, stat.st_ino,
            time.monotonic() + _PREVIEW_SECONDS,
        )
        with self._preview_lock:
            self._previews = {key: item for key, item in self._previews.items() if item.expires_at > time.monotonic()}
            if len(self._previews) >= 8:
                self._previews.pop(next(iter(self._previews)))
            self._previews[token] = record
        return token, mime

    def open_preview(self, token: str) -> tuple[PreviewRecord, BinaryIO]:
        with self._preview_lock:
            record = self._previews.get(token)
            if record is None or record.expires_at <= time.monotonic():
                self._previews.pop(token, None)
                raise FileNotFoundError("Preview expired or unavailable")
        if record.path.resolve(strict=True) != record.path:
            raise RuntimeError("File changed after selection; run the command again")
        self.engine.policy.authorize(Action("open_file", {"path": record.path}))
        stream = record.path.open("rb")
        try:
            stat = os.fstat(stream.fileno())
            if (stat.st_size, stat.st_mtime_ns, stat.st_dev, stat.st_ino) != (
                record.size, record.modified_ns, record.device, record.inode
            ):
                raise RuntimeError("File changed after selection; run the command again")
            return record, stream
        except Exception:
            stream.close()
            raise


def make_handler(service: RelayService):
    class RelayHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if not self._request_allowed():
                return
            if self.path in {"/", "/index.html"}:
                self._send_bytes(HTTPStatus.OK, "text/html; charset=utf-8", _ui_bytes())
            elif self.path == "/api/snapshot":
                self._send_json(HTTPStatus.OK, service.snapshot())
            elif self.path.startswith("/api/preview/"):
                token = self.path.removeprefix("/api/preview/")
                if re.fullmatch(r"[A-Za-z0-9_-]{32}", token) is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "Preview not found"})
                    return
                try:
                    record, stream = service.open_preview(token)
                except (FileNotFoundError, OSError, PolicyDenied):
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "Preview not found"})
                    return
                except RuntimeError as error:
                    self._send_json(HTTPStatus.CONFLICT, {"error": str(error)})
                    return
                with stream:
                    self._send_preview(record, stream)
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._request_allowed():
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON content type required"})
                return
            payload = self._body_json()
            if self.path == "/api/run":
                self._send_json(HTTPStatus.OK, service.run(str(payload.get("command", ""))))
            elif self.path == "/api/stop":
                self._send_json(HTTPStatus.OK, service.stop())
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def do_OPTIONS(self) -> None:  # noqa: N802
            if not self._request_allowed():
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            self._cors_headers()
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()

        def _body_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            try:
                return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            except json.JSONDecodeError:
                return {}

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            self._send_bytes(status, "application/json; charset=utf-8", json.dumps(payload).encode("utf-8"))

        def _send_preview(self, record: PreviewRecord, stream: BinaryIO) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", record.mime)
            self.send_header("Content-Length", str(record.size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self._cors_headers()
            self.end_headers()
            shutil.copyfileobj(stream, self.wfile, length=64 * 1024)

        def _send_bytes(self, status: HTTPStatus, content_type: str, payload: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self._cors_headers()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _request_allowed(self) -> bool:
            port = self.server.server_port
            if self.headers.get("Host") != f"127.0.0.1:{port}" or not _allowed_origin(self.headers.get("Origin"), port):
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "Request origin is not allowed"})
                return False
            return True

        def _cors_headers(self) -> None:
            origin = self.headers.get("Origin")
            if origin and _allowed_origin(origin, self.server.server_port):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return RelayHandler


def _allowed_origin(origin: str | None, port: int) -> bool:
    if origin is None:
        return True  # Local command-line clients do not send Origin; Host is checked separately.
    if origin == f"http://127.0.0.1:{port}":
        return True
    return re.fullmatch(r"chrome-extension://[a-p]{32}", origin) is not None


def _ui_bytes() -> bytes:
    return files("relaypilot.ui").joinpath("index.html").read_bytes()


def open_app_window(url: str) -> None:
    chrome = shutil.which("chrome") or shutil.which("chrome.exe")
    if chrome:
        subprocess.Popen([chrome, f"--app={url}"], close_fds=True)  # noqa: S603
    else:
        webbrowser.open(url)


def serve(service: RelayService | None = None, *, open_window: bool = True, port: int = 8721) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(service or RelayService()))
    if open_window:
        open_app_window(f"http://127.0.0.1:{server.server_port}")
    return server


def main() -> None:
    server = serve()
    print(f"RelayPilot is running locally at http://127.0.0.1:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
