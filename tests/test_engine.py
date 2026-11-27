from __future__ import annotations

import json
import http.client
import os
import tempfile
import time
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from threading import Thread

from relaypilot.browser import BrowserProfile
from relaypilot.config import RelaySettings, default_settings_path
from relaypilot.engine import RelayEngine
from relaypilot.executor import LocalExecutor, StopRequested
from relaypilot.history import RunHistory
from relaypilot.models import Action, RunState
from relaypilot.policy import Policy, PolicyDenied
from relaypilot.planner import PlannerRouter
from relaypilot.reliability import retry_after_reconciliation
from relaypilot.webapp import RelayService, _ui_bytes, _allowed_origin, make_handler


COMMAND = "Find the newest PDF in Downloads, copy it to Documents, open the copy, and tell me where you saved it."


class RelayEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.downloads, self.documents = root / "Downloads", root / "Documents"
        self.downloads.mkdir()
        self.documents.mkdir()
        (self.downloads / "old.pdf").write_bytes(b"old")
        time.sleep(0.01)
        (self.downloads / "newest.pdf").write_bytes(b"newest content")
        self.opened: list[Path] = []
        self.engine = RelayEngine(self.downloads, self.documents, opener=self.opened.append)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_copies_verifies_and_reports_newest_pdf_offline(self) -> None:
        result = self.engine.run(COMMAND)
        copied = self.documents / "newest.pdf"
        self.assertEqual(result.state, RunState.LAUNCH_REQUESTED)
        self.assertEqual(result.saved_path, copied.resolve())
        self.assertEqual(copied.read_bytes(), b"newest content")
        self.assertEqual((self.downloads / "newest.pdf").read_bytes(), b"newest content")
        self.assertEqual(self.opened, [copied.resolve()])
        self.assertIn(str(copied.resolve()), result.events[-1].evidence)

    def test_no_network_call_is_needed(self) -> None:
        original = os.environ.get("HTTP_PROXY")
        os.environ["HTTP_PROXY"] = "http://offline.invalid:9"
        try:
            self.assertEqual(self.engine.run(COMMAND).state, RunState.LAUNCH_REQUESTED)
        finally:
            if original is None:
                os.environ.pop("HTTP_PROXY", None)
            else:
                os.environ["HTTP_PROXY"] = original

    def test_stop_prevents_actions(self) -> None:
        executor = LocalExecutor(self.engine.policy, stop_requested=lambda: True)
        with self.assertRaises(StopRequested):
            executor.execute(Action("find_newest_pdf", {"folder": self.downloads}), {})

    def test_untrusted_page_text_cannot_authorize_upload(self) -> None:
        policy = Policy((self.downloads,), (self.documents,))
        with self.assertRaises(PolicyDenied):
            policy.authorize(Action("upload_local_file", {"path": self.downloads / "newest.pdf"}, external_effect=True))

    def test_disallowed_path_is_blocked(self) -> None:
        policy = Policy((self.downloads,), (self.documents,))
        with self.assertRaises(PolicyDenied):
            policy.authorize(Action("copy_file", {"source": self.downloads / "newest.pdf", "destination": Path.cwd() / "nope.pdf"}))

    def test_reads_allowed_browser_status_with_mocked_network(self) -> None:
        engine = RelayEngine(
            self.downloads,
            self.documents,
            page_fetcher=lambda _url: "<html><body><h1>Heat Signal</h1><p>Status: Data loaded</p></body></html>",
        )
        result = engine.run("Open Heat-Signal and report the visible status")
        self.assertEqual(result.state, RunState.COMPLETED)
        self.assertIn("Status: Data loaded", result.events[-1].evidence)

    def test_browser_connectivity_failure_is_clear_and_does_not_retry(self) -> None:
        attempts = 0

        def offline(_url: str) -> str:
            nonlocal attempts
            attempts += 1
            raise OSError("network disabled")

        engine = RelayEngine(self.downloads, self.documents, page_fetcher=offline)
        result = engine.run("Open Heat-Signal and report the visible status")
        self.assertEqual(result.state, RunState.BLOCKED)
        self.assertIn("Connectivity is required", result.reason or "")
        self.assertEqual(attempts, 1)

    def test_browser_read_rejects_ungranted_site(self) -> None:
        policy = Policy((self.downloads,), (self.documents,))
        with self.assertRaises(PolicyDenied):
            policy.authorize(Action("browser_read_status", {"url": "https://example.invalid/status"}))

    def test_counts_pdfs_in_downloads_from_natural_command(self) -> None:
        result = self.engine.run("I just want you to identify how many PDFs are saved in my downloads folder")
        self.assertEqual(result.state, RunState.COMPLETED)
        self.assertIn("Counted 2 PDFs", result.events[-1].message)

    def test_finds_and_opens_oldest_pdf_from_natural_command(self) -> None:
        result = self.engine.run("Open my oldest PDF on my PC")
        self.assertEqual(result.state, RunState.LAUNCH_REQUESTED)
        self.assertEqual(self.opened, [(self.downloads / "old.pdf").resolve()])

    def test_finds_and_requests_launch_of_latest_picture_in_downloads(self) -> None:
        (self.downloads / "old.jpg").write_bytes(b"old picture")
        time.sleep(0.01)
        latest = self.downloads / "latest.png"
        latest.write_bytes(b"latest picture")

        result = self.engine.run("Open the latest picture in my Downloads folder")

        self.assertEqual(result.state, RunState.LAUNCH_REQUESTED)
        self.assertEqual(self.opened, [latest.resolve()])
        self.assertEqual(result.events[-1].message, "Requested Windows default-app launch: latest.png")
        self.assertIn("target exists and Windows accepted", result.events[-1].evidence)

    def test_default_app_launch_error_is_not_reported_as_completed(self) -> None:
        def unavailable_viewer(_path: Path) -> None:
            raise OSError("No default viewer is configured")

        engine = RelayEngine(self.downloads, self.documents, opener=unavailable_viewer)
        result = engine.run("Open my oldest PDF on my PC")

        self.assertEqual(result.state, RunState.FAILED)
        self.assertIn("Windows could not launch old.pdf", result.reason or "")
        self.assertEqual(result.events[-1].message, "Run failed")

    def test_opens_an_approved_folder_from_natural_command(self) -> None:
        result = self.engine.run("Open my Downloads folder")
        self.assertEqual(result.state, RunState.LAUNCH_REQUESTED)
        self.assertEqual(len(self.opened), 1)
        self.assertTrue(self.opened[0].samefile(self.downloads))

    def test_open_path_never_escapes_an_explicit_file_scope(self) -> None:
        policy = Policy((self.downloads,), (self.documents,))
        with self.assertRaises(PolicyDenied):
            policy.authorize(Action("open_path", {"path": Path.cwd()}))

    def test_form_submission_remains_outside_a_standing_read_grant(self) -> None:
        policy = Policy((self.downloads,), (self.documents,))
        with self.assertRaises(PolicyDenied):
            policy.authorize(Action("browser_fill_form", {"url": "https://perumal100.github.io/test"}, external_effect=True))

    def test_settings_round_trip_and_scoped_policy(self) -> None:
        settings_file = Path(self.temp.name) / "settings.json"
        settings = RelaySettings.defaults(self.downloads, self.documents)
        settings.save(settings_file)
        restored = RelaySettings.load(settings_file, RelaySettings.defaults(Path("missing"), Path("missing")))
        self.assertEqual(restored.allowed_sites, ["perumal100.github.io"])
        self.assertEqual(restored.policy().writable_roots, (self.documents,))

    def test_engine_uses_the_configured_folder_scopes(self) -> None:
        alternate_downloads = Path(self.temp.name) / "ApprovedDownloads"
        alternate_documents = Path(self.temp.name) / "ApprovedDocuments"
        alternate_downloads.mkdir()
        alternate_documents.mkdir()
        (alternate_downloads / "daily.pdf").write_bytes(b"daily")
        settings = RelaySettings.defaults(alternate_downloads, alternate_documents)
        result = RelayEngine(self.downloads, self.documents, opener=self.opened.append, settings=settings).run(COMMAND)
        self.assertEqual(result.state, RunState.LAUNCH_REQUESTED)
        self.assertTrue((alternate_documents / "daily.pdf").exists())

    def test_history_is_local_and_redacts_secrets(self) -> None:
        history = RunHistory(Path(self.temp.name) / "history.jsonl")
        engine = RelayEngine(self.downloads, self.documents, opener=self.opened.append, history=history)
        engine.run(COMMAND + " token=secret-value")
        record = history.recent()[0]
        self.assertIn("token=[redacted]", str(record["command"]))
        self.assertNotIn("secret-value", str(record))

    def test_timeout_is_reconciled_before_any_retry(self) -> None:
        attempts = 0

        def uncertain_action() -> str:
            nonlocal attempts
            attempts += 1
            raise TimeoutError("result unknown")

        result = retry_after_reconciliation(uncertain_action, lambda: "already completed")
        self.assertEqual(result.value, "already completed")
        self.assertTrue(result.recovered_after_timeout)
        self.assertEqual(attempts, 1)

    def test_timeout_retries_only_when_no_prior_completion_is_found(self) -> None:
        attempts = 0

        def eventually_works() -> str:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise TimeoutError("result unknown")
            return "completed now"

        result = retry_after_reconciliation(eventually_works, lambda: None)
        self.assertEqual(result.value, "completed now")
        self.assertEqual(result.attempts, 2)

    def test_browser_handoff_uses_a_separate_local_profile(self) -> None:
        profile = BrowserProfile(Path(self.temp.name) / "profile")
        handoff = profile.handoff_for_authentication("https://example.test/login", "sign in directly")
        self.assertTrue(handoff.profile_path.exists())
        self.assertEqual(handoff.reason, "sign in directly")

    def test_configured_local_model_extension_has_no_executor_access(self) -> None:
        class LocalProvider:
            def plan(self, _command: str) -> list[Action]:
                return [Action("browser_read_status", {"url": "https://perumal100.github.io/Heat-Signal/"})]

        plan = PlannerRouter(local_model=LocalProvider()).plan("use my local model", self.downloads, self.documents)
        self.assertEqual(plan[0].kind, "browser_read_status")

    def test_modern_local_ui_service_exposes_only_local_scopes(self) -> None:
        service = RelayService(Path(self.temp.name) / "settings.json")
        snapshot = service.snapshot()
        self.assertIn("downloads", snapshot["folders"])
        self.assertEqual(snapshot["sites"], ["perumal100.github.io"])
        self.assertIn(b"Speak naturally", _ui_bytes())
        self.assertIn(b'id="preview"', _ui_bytes())

    def test_selected_picture_has_a_scoped_in_app_preview(self) -> None:
        picture = self.downloads / "latest.png"
        picture_bytes = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000b49444154789c636000020000050001a5f645400000000049454e44ae426082")
        picture.write_bytes(picture_bytes)
        settings_path = Path(self.temp.name) / "preview-settings.json"
        RelaySettings.defaults(self.downloads, self.documents).save(settings_path)
        service = RelayService(settings_path)
        service.engine.opener = self.opened.append
        result = service.run("Open the latest picture in my Downloads")
        self.assertEqual(result["state"], "launch_requested")
        self.assertEqual(result["preview_type"], "image/png")
        self.assertEqual(self.opened, [picture.resolve()])

        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        try:
            connection.request("GET", result["preview_url"])
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Content-Type"), "image/png")
            self.assertEqual(response.read(), picture_bytes)

            connection.request("GET", result["preview_url"], headers={"Origin": "https://untrusted.example"})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()

            original_stat = picture.stat()
            replacement = self.downloads / "replacement.png"
            replacement.write_bytes(b"x" * len(picture_bytes))
            os.utime(replacement, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            replacement.replace(picture)
            self.assertEqual(picture.stat().st_size, original_stat.st_size)
            self.assertEqual(picture.stat().st_mtime_ns, original_stat.st_mtime_ns)
            self.assertNotEqual(picture.stat().st_ino, original_stat.st_ino)
            connection.request("GET", result["preview_url"])
            response = connection.getresponse()
            self.assertEqual(response.status, 409)
            response.read()

            picture.unlink()
            connection.request("GET", result["preview_url"])
            response = connection.getresponse()
            self.assertEqual(response.status, 404)
            response.read()
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_verified_pdf_copy_has_a_pdf_preview(self) -> None:
        settings_path = Path(self.temp.name) / "pdf-preview-settings.json"
        RelaySettings.defaults(self.downloads, self.documents).save(settings_path)
        service = RelayService(settings_path)
        service.engine.opener = self.opened.append
        result = service.run(COMMAND)
        self.assertEqual(result["state"], "launch_requested")
        self.assertEqual(result["preview_type"], "application/pdf")
        self.assertTrue(result["preview_url"].startswith("/api/preview/"))
        self.assertEqual(result["preview_name"], "newest.pdf")

    def test_local_api_rejects_other_websites_before_running_tasks(self) -> None:
        service = RelayService(Path(self.temp.name) / "server-settings.json")
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        try:
            connection.request(
                "POST", "/api/run", body=json.dumps({"command": "Open my Downloads folder"}),
                headers={"Content-Type": "application/json", "Origin": "https://untrusted.example"},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))
            response.read()
            self.assertEqual(service.history.recent(), [])

            connection.request("GET", "/api/snapshot", headers={"Origin": "https://untrusted.example"})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()

            connection.request("GET", "/api/snapshot", headers={"Host": "untrusted.example"})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()

            local_origin = f"http://127.0.0.1:{server.server_port}"
            connection.request(
                "POST", "/api/run", body=json.dumps({"command": "How many PDFs are in my Downloads folder?"}),
                headers={"Content-Type": "application/json", "Origin": local_origin},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Access-Control-Allow-Origin"), local_origin)
            self.assertEqual(json.loads(response.read())["state"], "completed")
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_local_api_allows_only_its_own_ui_and_chrome_extensions(self) -> None:
        self.assertTrue(_allowed_origin("http://127.0.0.1:8721", 8721))
        self.assertTrue(_allowed_origin("chrome-extension://" + "a" * 32, 8721))
        self.assertFalse(_allowed_origin("https://untrusted.example", 8721))
        self.assertFalse(_allowed_origin("null", 8721))
        self.assertFalse(_allowed_origin("http://127.0.0.1:8722", 8721))

    def test_data_directory_override_is_explicit(self) -> None:
        original = os.environ.get("RELAYPILOT_DATA_DIR")
        os.environ["RELAYPILOT_DATA_DIR"] = self.temp.name
        try:
            self.assertEqual(default_settings_path(), Path(self.temp.name) / "settings.json")
        finally:
            if original is None:
                os.environ.pop("RELAYPILOT_DATA_DIR", None)
            else:
                os.environ["RELAYPILOT_DATA_DIR"] = original

    def test_legacy_settings_gain_new_routine_actions_once(self) -> None:
        settings_file = Path(self.temp.name) / "legacy-settings.json"
        settings_file.write_text(
            json.dumps({"downloads": str(self.downloads), "documents": str(self.documents), "allowed_actions": ["find_newest_pdf"]}),
            encoding="utf-8",
        )
        restored = RelaySettings.load(settings_file, RelaySettings.defaults(self.downloads, self.documents))
        self.assertEqual(restored.schema_version, 3)
        self.assertIn("count_pdfs", restored.allowed_actions)
        self.assertIn("find_newest_image", restored.allowed_actions)
        self.assertIn(str(self.documents), restored.readable_folders)

    def test_version_two_settings_gain_only_the_new_image_action(self) -> None:
        settings_file = Path(self.temp.name) / "v2-settings.json"
        settings_file.write_text(
            json.dumps(
                {
                    "downloads": str(self.downloads),
                    "documents": str(self.documents),
                    "readable_folders": [str(self.downloads), str(self.documents)],
                    "allowed_actions": ["find_newest_pdf"],
                    "schema_version": 2,
                }
            ),
            encoding="utf-8",
        )
        restored = RelaySettings.load(settings_file, RelaySettings.defaults(self.downloads, self.documents))
        self.assertEqual(restored.schema_version, 3)
        self.assertEqual(set(restored.allowed_actions), {"find_newest_pdf", "find_newest_image"})

    def test_extension_has_active_tab_scope_not_unrestricted_site_access(self) -> None:
        manifest_path = Path(__file__).parents[1] / "extension" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIn("activeTab", manifest["permissions"])
        self.assertNotIn("<all_urls>", manifest.get("host_permissions", []))
        self.assertIn("http://127.0.0.1:8721/*", manifest["host_permissions"])

