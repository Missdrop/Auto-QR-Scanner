import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from playwright.sync_api import sync_playwright

from src.browser_page import BrowserPage
from src.runtime import Chromium


class BrowserPageTest(unittest.TestCase):
    def test_invalid_adapter_result_closes_the_browser_context(self):
        context = Mock()
        context.pages = [Mock()]
        adapter = Mock()
        adapter.execute.return_value = (True, "Invalid result")
        with (
            patch("src.browser_page.sync_playwright") as runtime,
            patch(
                "src.browser_page.Chromium.executable", return_value=Path("runtime.exe")
            ),
        ):
            engine = runtime.return_value.__enter__.return_value.chromium
            engine.launch_persistent_context.return_value = context
            with self.assertRaisesRegex(ValueError, "Invalid website adapter result"):
                BrowserPage(Path("unused")).process("https://example.com/", adapter)
        context.close.assert_called_once()


@unittest.skipUnless(os.environ.get("QR_BROWSER_TESTS") == "1", "Enable browser tests")
class BrowserProfileTest(unittest.TestCase):
    def test_profile_keeps_cookie_and_token_after_browser_restart(self):
        with tempfile.TemporaryDirectory() as directory, sync_playwright() as runtime:
            for first in (True, False):
                context = runtime.chromium.launch_persistent_context(
                    directory,
                    executable_path=Chromium().executable(),
                    headless=True,
                )
                try:
                    context.route(
                        "**/*",
                        lambda route: route.fulfill(
                            content_type="text/html",
                            body="<title>Profile fixture</title>",
                        ),
                    )
                    page = context.pages[0]
                    page.goto("https://example.test/")
                    if first:
                        page.evaluate("localStorage.setItem('Token', 'fixture-token')")
                        context.add_cookies(
                            [
                                {
                                    "name": "fixture",
                                    "value": "saved",
                                    "domain": "example.test",
                                    "path": "/",
                                    "secure": True,
                                    "expires": 4102444800,
                                }
                            ]
                        )
                    else:
                        self.assertTrue(
                            page.evaluate(
                                "localStorage.getItem('Token') === 'fixture-token'"
                            )
                        )
                        self.assertTrue(
                            any(
                                cookie["name"] == "fixture"
                                for cookie in context.cookies()
                            )
                        )
                finally:
                    context.close()
