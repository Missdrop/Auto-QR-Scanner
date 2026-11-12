import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Error, sync_playwright

from src.runtime import Chromium
from src.student_page import StudentPage


class StudentPageTest(unittest.TestCase):
    def test_navigation_to_login_never_sends_a_qr_request(self):
        page = Mock()
        page.url = "https://uim.xjtlu.edu.cn/esc-sso/login/page"
        self.assertEqual(StudentPage(Path("unused")).request(page, "code")[0], 401)
        page.evaluate.assert_not_called()

    def test_context_closes_when_a_request_fails(self):
        with (
            patch("src.student_page.sync_playwright") as runtime,
            patch(
                "src.student_page.Chromium.executable", return_value=Path("chrome.exe")
            ),
            patch.object(StudentPage, "request", side_effect=ValueError("failed")),
        ):
            chromium = runtime.return_value.__enter__.return_value.chromium
            context = chromium.launch_persistent_context.return_value
            context.pages = [Mock()]
            with self.assertRaises(ValueError):
                StudentPage(Path("unused")).process("code")
            context.close.assert_called_once()


@unittest.skipUnless(
    os.environ.get("QR_BROWSER_TESTS") == "1",
    "Enable QR_BROWSER_TESTS for real Chromium tests",
)
class ChromiumRequestTest(unittest.TestCase):
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

    def test_browser_requests_and_results_without_real_school_traffic(self):
        with tempfile.TemporaryDirectory() as directory, sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=Chromium().executable())
            try:
                context = browser.new_context()
                context.add_init_script(
                    "if (location.origin === 'https://ams.xjtlu.edu.cn') "
                    "localStorage.setItem('Token', 'test-token');"
                )
                page = context.new_page()
                requests = []
                scenario = {
                    "status": 200,
                    "body": json.dumps({"code": 0, "message": "Accepted"}),
                }

                def route(request):
                    url = urlsplit(request.request.url)
                    if url.netloc != "ams.xjtlu.edu.cn":
                        request.abort()
                    elif url.path == "/studentpc/checkIn":
                        request.fulfill(
                            content_type="text/html", body="<title>AMS fixture</title>"
                        )
                    elif url.path == "/xjtlu/sign/qRCodeSign":
                        requests.append(request.request)
                        request.fulfill(**scenario)
                    else:
                        request.abort()

                context.route("**/*", route)
                student = StudentPage(Path(directory))
                self.assertEqual(student.request(page, "a/b="), (0, "Accepted"))
                request = requests[-1]
                self.assertEqual(
                    parse_qs(urlsplit(request.url).query),
                    {"code": ["a/b="], "type": ["1"]},
                )
                self.assertEqual(request.headers["x-token"], "test-token")
                self.assertNotIn("test-token", request.url)

                scenario["body"] = json.dumps({"code": 1001, "message": "Expired"})
                self.assertEqual(student.request(page, "old-code"), (1001, "Expired"))
                scenario["status"] = 401
                self.assertEqual(student.request(page, "expired-login")[0], 401)
                scenario["status"] = 200
                for body in ("<html>Unavailable</html>", '{"code":true}', "x" * 65537):
                    scenario["body"] = body
                    with self.assertRaises(Error):
                        student.request(page, "invalid-response")

                # Remove the seeding script by using a separate empty context.
                empty = browser.new_context()
                empty.route("**/*", route)
                before = len(requests)
                self.assertEqual(
                    student.request(empty.new_page(), "logged-out")[0], 401
                )
                self.assertEqual(len(requests), before)
                empty.close()
                context.close()
            finally:
                browser.close()
