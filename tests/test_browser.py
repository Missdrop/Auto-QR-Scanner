import unittest
from pathlib import Path
from unittest.mock import patch

from src.browser import Browser


class BrowserTest(unittest.TestCase):
    def test_installed_chrome_receives_the_complete_url(self):
        url = "https://ams.xjtlu.edu.cn/studenth5/#/?state=test&token=example"
        executable = Path("C:/Chrome/chrome.exe")
        with (
            patch.object(Browser, "executable", return_value=executable),
            patch("src.browser.webbrowser.BackgroundBrowser") as chrome,
            patch("src.browser.webbrowser.open") as default,
        ):
            chrome.return_value.open.return_value = True
            self.assertTrue(Browser().open(url))
        chrome.assert_called_once_with(str(executable))
        chrome.return_value.open.assert_called_once_with(url, new=2)
        default.assert_not_called()

    def test_default_browser_failure_is_reported(self):
        with (
            patch.object(Browser, "executable", return_value=None),
            patch("src.browser.webbrowser.open", return_value=False),
        ):
            self.assertFalse(Browser().open("https://example.com"))
