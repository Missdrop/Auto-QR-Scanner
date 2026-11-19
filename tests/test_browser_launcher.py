import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from browser.launcher import main


class BrowserLauncherTest(unittest.TestCase):
    def test_scripts_are_installed_before_navigation_and_close_flushes_profile(self):
        events = []
        arguments = [
            "launcher",
            "--profile",
            "profile",
            "--scripts",
            "adapters",
            "--url",
            "https://example.com/",
        ]
        with (
            patch.object(sys, "argv", arguments),
            patch("browser.launcher.sync_playwright") as runtime,
            patch(
                "browser.launcher.Chromium.executable", return_value=Path("runtime.exe")
            ),
            patch("browser.launcher.BrowserScripts") as scripts,
        ):
            engine = runtime.return_value.__enter__.return_value.chromium
            context = engine.launch_persistent_context.return_value
            scripts.return_value.configure.side_effect = lambda context: events.append(
                "scripts"
            )
            context.pages[0].goto.side_effect = lambda *args, **kwargs: events.append(
                "navigate"
            )
            main()
            self.assertEqual(events, ["scripts", "navigate"])
            self.assertTrue(
                engine.launch_persistent_context.call_args.kwargs["chromium_sandbox"]
            )
            context.wait_for_event.assert_called_once_with("close", timeout=0)
            context.close.assert_called_once()

    def test_navigation_failure_still_closes_the_context(self):
        arguments = [
            "launcher",
            "--profile",
            "profile",
            "--scripts",
            "adapters",
            "--url",
            "https://example.com/",
        ]
        with (
            patch.object(sys, "argv", arguments),
            patch("browser.launcher.sync_playwright") as runtime,
            patch(
                "browser.launcher.Chromium.executable", return_value=Path("runtime.exe")
            ),
            patch("browser.launcher.BrowserScripts"),
        ):
            engine = runtime.return_value.__enter__.return_value.chromium
            context = engine.launch_persistent_context.return_value
            context.pages[0].goto.side_effect = RuntimeError("Navigation failed")
            with self.assertRaises(RuntimeError):
                main()
            context.close.assert_called_once()
