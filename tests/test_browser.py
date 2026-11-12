import unittest
from pathlib import Path
from unittest.mock import patch

from src.browser import Browser


class BrowserTest(unittest.TestCase):
    def setUp(self):
        runtime = patch(
            "src.browser.Chromium.executable", return_value=Path("runtime.exe")
        )
        runtime.start()
        self.addCleanup(runtime.stop)

    def test_login_process_does_not_receive_credentials_in_arguments(self):
        with patch("src.browser.subprocess.Popen") as start:
            browser = Browser(Path("data/student"))
            self.assertTrue(browser.open("https://ams.xjtlu.edu.cn/studenth5/"))
        arguments = start.call_args.args[0]
        self.assertIn("src.login", arguments)
        self.assertNotIn("token", " ".join(arguments))
        self.assertEqual(arguments[-1], str(Path("data/student")))

    def test_an_existing_login_window_is_reused(self):
        with patch("src.browser.subprocess.Popen") as start:
            start.return_value.poll.return_value = None
            browser = Browser(Path("data/student"))
            browser.open("https://ams.xjtlu.edu.cn/studenth5/")
            browser.open("https://ams.xjtlu.edu.cn/studenth5/")
        start.assert_called_once()
