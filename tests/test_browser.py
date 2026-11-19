import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.base import AdapterResult
from browser.client import Browser


class BrowserTest(unittest.TestCase):
    def test_local_scripts_use_a_managed_browser_without_credentials_in_arguments(self):
        with (
            patch(
                "browser.client.BrowserScripts.paths", return_value=[Path("browser.js")]
            ),
            patch("browser.client.subprocess.Popen") as start,
        ):
            Browser(Path("data/session")).open("https://example.com/")
        arguments = start.call_args.args[0]
        self.assertIn("browser.launcher", arguments)
        self.assertIn(str(Path("data/session/chromium").resolve()), arguments)
        self.assertNotIn("token", " ".join(arguments))

    def setUp(self):
        scripts = patch("browser.client.BrowserScripts.paths", return_value=[])
        scripts.start()
        self.addCleanup(scripts.stop)
        runtime = patch(
            "browser.client.Chromium.executable",
            return_value=Path("runtime.exe"),
        )
        runtime.start()
        self.addCleanup(runtime.stop)

    def test_login_process_does_not_receive_credentials_in_arguments(self):
        with patch("browser.client.subprocess.Popen") as start:
            browser = Browser(Path("data/session"))
            self.assertTrue(browser.open("https://example.com/qr/"))
        arguments = start.call_args.args[0]
        self.assertEqual(arguments[0], "runtime.exe")
        self.assertNotIn("token", " ".join(arguments))
        self.assertEqual(arguments[-1], "https://example.com/qr/")
        self.assertIn(
            "--user-data-dir=" + str(Path("data/session/chromium").resolve()), arguments
        )

    def test_repeated_windows_share_the_same_persistent_profile(self):
        with patch("browser.client.subprocess.Popen") as start:
            start.return_value.poll.return_value = None
            browser = Browser(Path("data/session"))
            browser.open()
            browser.open()
        self.assertEqual(start.call_count, 2)
        self.assertEqual(start.call_args_list[0].args, start.call_args_list[1].args)

    def test_active_login_cannot_share_its_profile_with_qr_processing(self):
        with patch("browser.client.subprocess.Popen") as start:
            start.return_value.poll.return_value = None
            browser = Browser(Path("data/session"))
            browser.open("https://example.com/qr/")
            with self.assertRaisesRegex(RuntimeError, "Close the built-in browser"):
                browser.process("https://example.com/qr", object())

    def test_qr_processing_delegates_to_chromium_without_a_token_argument(self):
        with patch("browser.client.BrowserPage") as page:
            result = AdapterResult("Custom result", "Description")
            page.return_value.process.return_value = result
            browser = Browser(Path("data/session"))
            self.assertEqual(
                browser.process("https://example.com/qr", object()), result
            )
        self.assertEqual(
            page.return_value.process.call_args.args[0], "https://example.com/qr"
        )
