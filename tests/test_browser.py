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
        self.assertEqual(arguments[0], "runtime.exe")
        self.assertNotIn("token", " ".join(arguments))
        self.assertEqual(arguments[-1], "https://ams.xjtlu.edu.cn/studenth5/")
        self.assertIn(
            "--user-data-dir=" + str(Path("data/student/chromium").resolve()), arguments
        )

    def test_repeated_windows_share_the_same_persistent_profile(self):
        with patch("src.browser.subprocess.Popen") as start:
            start.return_value.poll.return_value = None
            browser = Browser(Path("data/student"))
            browser.open()
            browser.open()
        self.assertEqual(start.call_count, 2)
        self.assertEqual(start.call_args_list[0].args, start.call_args_list[1].args)

    def test_active_login_cannot_share_its_profile_with_qr_processing(self):
        with patch("src.browser.subprocess.Popen") as start:
            start.return_value.poll.return_value = None
            browser = Browser(Path("data/student"))
            browser.open("https://ams.xjtlu.edu.cn/studenth5/")
            with self.assertRaisesRegex(RuntimeError, "Close the built-in browser"):
                browser.process("example")

    def test_qr_processing_delegates_to_chromium_without_a_token_argument(self):
        with patch("src.browser.StudentPage") as page:
            page.return_value.process.return_value = (1001, "Expired")
            browser = Browser(Path("data/student"))
            self.assertEqual(browser.process("example"), (1001, "Expired"))
        page.return_value.process.assert_called_once_with("example")
