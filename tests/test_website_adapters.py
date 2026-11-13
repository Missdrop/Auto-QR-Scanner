import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

from adapters.base import AdapterResult
from adapters.registry import WebsiteAdapters
from browser.session import BrowserSession


class WebsiteAdaptersTest(unittest.TestCase):
    def test_adapter_information_includes_metadata_and_load_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good, bad = root / "good", root / "bad"
            good.mkdir()
            bad.mkdir()
            (good / "adapter.py").write_text(
                "from adapters.base import WebsiteAdapter, AdapterResult\n"
                "class Adapter(WebsiteAdapter):\n"
                "    name = 'Example adapter'\n"
                "    version = '1.0'\n"
                "    description = 'Example description'\n"
                "    def matches(self, url): return True\n"
                "    def process(self, page, url): return {}\n"
                "    def get_result(self, response): return 'Completed'\n"
                "    def get_details(self, response): return 'Accepted'\n"
            )
            (bad / "adapter.py").write_text("raise ValueError('private data')")
            registry = WebsiteAdapters(root)
            rows = registry.information()
            self.assertEqual(rows[0]["status"], "error")
            self.assertEqual(rows[0]["error"], "ValueError")
            self.assertEqual(rows[1]["name"], "good")
            self.assertEqual(rows[1]["version"], "1.0")
            self.assertEqual(rows[1]["description"], "Example description")
            self.assertEqual(rows[1]["status"], "loaded")
            rows[1]["name"] = "Changed"
            self.assertEqual(registry.information()[1]["name"], "good")

    def test_adapter_failure_does_not_drop_the_next_queued_url(self):
        with tempfile.TemporaryDirectory() as directory:
            outcomes = []
            session = BrowserSession(
                Path(directory), lambda message: None, outcomes.append
            )
            started, released = Event(), Event()

            def process(url, adapter):
                if url.endswith("first"):
                    started.set()
                    released.wait(2)
                    raise ValueError("Synthetic failure")
                return AdapterResult("Completed", "Accepted")

            try:
                with (
                    patch.object(session._adapters, "find", return_value=Mock()),
                    patch.object(session._browser, "process", side_effect=process),
                ):
                    session.open("https://example.com/first")
                    self.assertTrue(started.wait(1))
                    session.open("https://example.com/second")
                    released.set()
                    session._request_thread.join(timeout=3)
                final = {item.url: item for item in outcomes}
                self.assertEqual(final["https://example.com/first"].status, "error")
                self.assertEqual(
                    final["https://example.com/second"].result, "Completed"
                )
            finally:
                released.set()
                session.close()

    def test_local_adapter_loading_and_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(WebsiteAdapters(root).find("https://example.com/"))
            site = root / "example"
            site.mkdir()
            (site / "adapter.py").write_text(
                "from urllib.parse import urlsplit\n"
                "from adapters.base import WebsiteAdapter, AdapterResult\n"
                "class Adapter(WebsiteAdapter):\n"
                "    def matches(self, url):\n"
                "        return urlsplit(url).hostname == 'example.com'\n"
                "    def process(self, page, url):\n"
                "        return {}\n"
                "    def get_result(self, response): return 'Completed'\n"
                "    def get_details(self, response): return 'Accepted'\n"
            )
            registry = WebsiteAdapters(root)
            adapter = registry.find("https://example.com/path")
            self.assertIsNotNone(adapter)
            self.assertIsNone(registry.find("https://other.example/"))

    def test_invalid_adapter_reports_a_generic_error(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "broken"
            site.mkdir()
            (site / "adapter.py").write_text("raise RuntimeError('private detail')")
            with self.assertRaisesRegex(ValueError, "Cannot load website adapter"):
                WebsiteAdapters(Path(directory)).find("https://example.com/")

    def test_browser_session_uses_adapter_without_exported_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            outcomes = []
            session = BrowserSession(
                Path(directory), lambda message: None, outcomes.append
            )
            adapter = Mock()
            try:
                with (
                    patch.object(session._adapters, "find", return_value=adapter),
                    patch.object(
                        session._browser,
                        "process",
                        return_value=AdapterResult("Custom result", "Accepted"),
                    ) as process,
                ):
                    session.open("https://example.com/qr")
                    session._request_thread.join(timeout=2)
                    process.assert_called_once_with("https://example.com/qr", adapter)
                self.assertEqual(outcomes[-1].label(), "Custom result")
                self.assertFalse((Path(directory) / "session.bin").exists())
                self.assertFalse((Path(directory) / "login.key").exists())
            finally:
                session.close()

    def test_unmatched_links_open_normally_and_manual_links_bypass_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            outcomes = []
            session = BrowserSession(
                Path(directory), lambda message: None, outcomes.append
            )
            try:
                with (
                    patch.object(session._adapters, "find", return_value=None) as find,
                    patch.object(
                        session._browser, "open", return_value=True
                    ) as navigate,
                ):
                    session.open("https://example.com/qr")
                    session.open_link("https://example.com/other")
                    self.assertEqual(navigate.call_count, 2)
                    find.assert_called_once()
                self.assertEqual(outcomes[-1].status, "opened")
            finally:
                session.close()
