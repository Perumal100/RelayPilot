from __future__ import annotations

import hashlib
import os
import shutil
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from .models import Action
from .policy import Policy


class StopRequested(RuntimeError):
    pass


class ConnectivityRequired(RuntimeError):
    """The requested read-only browser workflow needs an available network."""


class FileLaunchFailed(RuntimeError):
    """Windows could not hand a verified target to its default application."""


class LocalExecutor:
    def __init__(self, policy: Policy, stop_requested=lambda: False, opener=None, page_fetcher=None) -> None:
        self.policy = policy
        self.stop_requested = stop_requested
        self.opener = opener or self._default_open
        self.page_fetcher: Callable[[str], str] = page_fetcher or self._fetch_page

    def execute(self, action: Action, context: dict[str, Any]) -> tuple[str, str]:
        self._check_stop()
        if action.kind == "find_newest_pdf":
            folder = Path(action.arguments["folder"])
            self.policy.authorize(Action("find_newest_pdf", {"folder": folder}))
            candidates = _pdfs(folder)
            if not candidates:
                raise FileNotFoundError(f"No PDF found in {folder}")
            newest = max(candidates, key=lambda item: item.stat().st_mtime)
            context["newest_pdf"] = newest.resolve()
            return (f"Found newest PDF: {newest.name}", str(newest.resolve()))

        if action.kind == "find_oldest_pdf":
            folder = Path(action.arguments["folder"])
            self.policy.authorize(Action("find_oldest_pdf", {"folder": folder}))
            candidates = _pdfs(folder)
            if not candidates:
                raise FileNotFoundError(f"No PDF found in {folder}")
            oldest = min(candidates, key=lambda item: item.stat().st_mtime)
            context["selected_pdf"] = oldest.resolve()
            return (f"Found oldest PDF: {oldest.name}", str(oldest.resolve()))

        if action.kind == "find_newest_image":
            folder = Path(action.arguments["folder"])
            self.policy.authorize(Action("find_newest_image", {"folder": folder}))
            candidates = _images(folder)
            if not candidates:
                raise FileNotFoundError(f"No supported picture found in {folder}")
            newest = max(candidates, key=lambda item: item.stat().st_mtime)
            context["selected_file"] = newest.resolve()
            return (f"Found newest picture: {newest.name}", str(newest.resolve()))

        if action.kind == "count_pdfs":
            folder = Path(action.arguments["folder"])
            self.policy.authorize(Action("count_pdfs", {"folder": folder}))
            count = len(_pdfs(folder))
            context["pdf_count"] = count
            return (f"Counted {count} PDF{'s' if count != 1 else ''}", f"folder={folder.resolve()}; count={count}")

        if action.kind == "copy_file":
            source = context["newest_pdf"] if action.arguments["source"] == "@newest_pdf" else Path(action.arguments["source"])
            destination_folder = Path(action.arguments["destination_folder"])
            destination = destination_folder / source.name
            self.policy.authorize(Action("copy_file", {"source": source, "destination": destination}))
            self._check_stop()
            if destination.exists():
                raise FileExistsError(f"Destination already exists: {destination}")
            source_hash = _sha256(source)
            shutil.copy2(source, destination)
            self._check_stop()
            destination_hash = _sha256(destination)
            if source_hash != destination_hash:
                destination.unlink(missing_ok=True)
                raise IOError("Verification failed: copied file hash does not match source")
            context["copied_pdf"] = destination.resolve()
            return (f"Copied and verified: {destination.name}", f"sha256={destination_hash}; path={destination.resolve()}")

        if action.kind == "open_file":
            if action.arguments["path"] == "@copied_pdf":
                target = context["copied_pdf"]
            elif action.arguments["path"] == "@newest_pdf":
                target = context["newest_pdf"]
            elif action.arguments["path"] == "@selected_pdf":
                target = context["selected_pdf"]
            elif action.arguments["path"] == "@selected_file":
                target = context["selected_file"]
            else:
                target = Path(action.arguments["path"])
            self.policy.authorize(Action("open_file", {"path": target}))
            self._check_stop()
            if not target.exists():
                raise FileNotFoundError(f"Verified file no longer exists: {target}")
            self._launch(target)
            context["opened_file"] = target.resolve()
            return (
                f"Requested Windows default-app launch: {target.name}",
                f"target exists and Windows accepted the launch request; path={target.resolve()}",
            )

        if action.kind == "open_path":
            target = Path(action.arguments["path"])
            self.policy.authorize(Action("open_path", {"path": target}))
            self._check_stop()
            if not target.exists():
                raise FileNotFoundError(f"Path does not exist: {target}")
            self._launch(target)
            return (
                f"Requested Windows Explorer launch: {target.name or target.drive}",
                f"target exists and Windows accepted the launch request; path={target.resolve()}",
            )

        if action.kind == "browser_read_status":
            self.policy.authorize(action)
            url = str(action.arguments["url"])
            try:
                html = self.page_fetcher(url)
            except (OSError, URLError, TimeoutError) as error:
                raise ConnectivityRequired(f"Connectivity is required to read {url}: {error}") from error
            self._check_stop()
            status = _visible_status(html)
            context["browser_status"] = status
            return ("Read visible page status", f"url={url}; visible status={status}")
        raise ValueError(f"Unsupported action: {action.kind}")

    def _check_stop(self) -> None:
        if self.stop_requested():
            raise StopRequested("Stop requested; no further input or actions were issued")

    def _launch(self, target: Path) -> None:
        try:
            self.opener(target)
        except OSError as error:
            raise FileLaunchFailed(f"Windows could not launch {target.name}: {error}") from error

    @staticmethod
    def _default_open(path: Path) -> None:
        if os.name != "nt":
            raise FileLaunchFailed("Opening a file requires Windows")
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except OSError as error:
            raise FileLaunchFailed(f"Windows default-app launch failed for {path.name}: {error}") from error

    @staticmethod
    def _fetch_page(url: str) -> str:
        request = Request(url, headers={"User-Agent": "RelayPilot/0.1 (read-only status check)"})
        with urlopen(request, timeout=10) as response:  # nosec B310: URL is policy-checked before this call.
            return response.read(1_000_000).decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pdfs(folder: Path) -> list[Path]:
    return [item for item in folder.rglob("*") if item.is_file() and item.suffix.lower() == ".pdf"]


_IMAGE_SUFFIXES = {".avif", ".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def _images(folder: Path) -> list[Path]:
    return [item for item in folder.rglob("*") if item.is_file() and item.suffix.lower() in _IMAGE_SUFFIXES]


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def _visible_status(html: str) -> str:
    """Return a bounded visible-text status; page text is never treated as instructions."""
    parser = _VisibleTextParser()
    parser.feed(html)
    text = " ".join(" ".join(parser.parts).split())
    marker = text.lower().find("status")
    if marker >= 0:
        return text[marker : marker + 160]
    return text[:160] or "No visible status text was found."

