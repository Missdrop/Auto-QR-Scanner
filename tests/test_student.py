import json
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.ams import Ams
from src.student import HOME_URL, Student


class StudentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.messages = []
        self.student = Student(Path(self.directory.name), self.messages.append)
        self.addCleanup(self.student.close)

    def send(self, payload, key=None):
        self.student.start(port=0)
        request = Request(
            f"http://127.0.0.1:{self.student.port}/event",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": "Bearer " + (key or self.student._key),
                "Content-Type": "application/json",
            },
        )
        return urlopen(request, timeout=2)

    def test_wrong_login_key_cannot_write_session(self) -> None:
        with self.assertRaises(HTTPError) as failure:
            self.send(
                {"event": "session", "userId": "student", "token": "secret"}, "wrong"
            )
        self.assertEqual(failure.exception.code, 403)
        self.assertEqual(self.student._session, {})

    def test_session_is_encrypted_and_survives_restart(self) -> None:
        with self.send(
            {"event": "session", "userId": "student", "token": "secret"}
        ) as response:
            self.assertEqual(response.status, 204)
        stored = Path(self.directory.name) / "session.bin"
        self.assertNotIn(b"secret", stored.read_bytes())
        other = Student(Path(self.directory.name), self.messages.append)
        self.assertEqual(other._session["userId"], "student")
        self.assertEqual(other._key, self.student._key)

    def test_logout_clears_the_saved_session(self) -> None:
        self.student._receive(
            {"event": "session", "userId": "student", "token": "secret"}
        )
        with self.send({"event": "logout"}):
            pass
        self.assertEqual(self.student._session, {})
        self.assertIn("Login required", self.messages[-1])
        restored = Student(Path(self.directory.name), self.messages.append)
        self.assertEqual(restored._session, {})

    def test_browser_profile_is_authoritative_without_exported_session(self) -> None:
        with patch.object(
            self.student._browser, "process", return_value=(401, "Expired")
        ) as browser:
            self.student.open(HOME_URL + "#/?state=example")
            self.student._request_thread.join(timeout=1)
            browser.assert_called_once_with("example")
        self.assertIn("Login required", self.messages[-1])

    def test_only_exact_student_origin_is_accepted(self) -> None:
        self.assertTrue(Student.is_student_url(HOME_URL + "#/?state=example"))
        for url in [
            "http://ams.xjtlu.edu.cn/studenth5/",
            "https://[",
            "https://ams.xjtlu.edu.cn.evil.test/studenth5/",
            "https://user@ams.xjtlu.edu.cn/studenth5/",
            "javascript:alert(1)",
        ]:
            self.assertFalse(Student.is_student_url(url))
        for url in (
            "javascript:alert(1)",
            "https://[",
            "https://user@host/path",
            "file:///x",
        ):
            with self.assertRaises(ValueError):
                self.student.open(url)

    def test_generic_web_links_open_in_the_persistent_browser(self):
        with patch.object(self.student._browser, "open", return_value=True) as browser:
            self.student.open("https://example.com/qr")
            browser.assert_called_once_with("https://example.com/qr")
        self.assertIsNone(self.student._server)

    def test_browser_button_opens_blank_page_without_a_login_workflow(self):
        with patch.object(self.student._browser, "open", return_value=True) as browser:
            self.student.open()
            browser.assert_called_once_with("about:blank")

    def test_invalid_event_is_rejected(self) -> None:
        with self.assertRaises(HTTPError) as failure:
            self.send({"event": "session", "token": 42})
        self.assertEqual(failure.exception.code, 400)

    def test_existing_state_is_preserved(self) -> None:
        result = Ams.state(HOME_URL + "#/?state=a%2Fb%3D&token=old")
        self.assertEqual(result, "a/b=")

    def test_expired_qr_result_reaches_the_desktop(self) -> None:
        self.student.start(port=0)
        self.student._receive(
            {"event": "session", "userId": "student", "token": "secret"}
        )
        with patch.object(
            self.student._browser, "process", return_value=(1001, "Expired")
        ):
            self.student.open(HOME_URL + "#/?state=old-code")
            self.student._request_thread.join(timeout=1)
        self.assertIn("Platform rejected", self.messages[-1])
        self.assertIn("Expired", self.messages[-1])

    def test_platform_unauthorized_response_clears_the_session(self) -> None:
        self.student.start(port=0)
        self.student._receive(
            {"event": "session", "userId": "student", "token": "secret"}
        )
        with patch.object(
            self.student._browser, "process", return_value=(401, "Expired")
        ):
            self.student.open(HOME_URL + "#/?state=old-code")
            self.student._request_thread.join(timeout=1)
        self.assertEqual(self.student._session, {})
        self.assertIn("Login required", self.messages[-1])

    def test_old_request_cannot_clear_a_refreshed_session(self) -> None:
        self.student.start(port=0)
        self.student._receive({"event": "session", "userId": "student", "token": "old"})

        def refresh_during_request(state):
            self.student._receive(
                {"event": "session", "userId": "student", "token": "new"}
            )
            return 401, "Expired"

        with patch.object(
            self.student._browser, "process", side_effect=refresh_during_request
        ):
            self.student.open(HOME_URL + "#/?state=old-code")
            self.student._request_thread.join(timeout=1)
        self.assertEqual(self.student._session["token"], "new")

    def test_platform_status_is_separate_from_session(self) -> None:
        self.student._receive(
            {"event": "session", "userId": "student", "token": "secret"}
        )
        self.assertNotIn("success page", self.messages[-1])
        with self.assertRaises(ValueError):
            self.student._receive({"event": "success"})

    def test_consecutive_codes_are_processed_in_order_without_dropping_them(self):
        self.student.start(port=0)
        self.student._receive(
            {"event": "session", "userId": "student", "token": "secret"}
        )
        started, released = Event(), Event()
        states = []

        def process(state):
            states.append(state)
            if state == "first":
                started.set()
                released.wait(2)
            return 1001, "Expired"

        with patch.object(self.student._browser, "process", side_effect=process):
            try:
                self.student.open(HOME_URL + "#/?state=first")
                self.assertTrue(started.wait(1))
                self.student.open(HOME_URL + "#/?state=second")
                self.student.open(HOME_URL + "#/?state=third")
                self.assertIn("queued", self.messages[-1])
            finally:
                released.set()
                self.student._request_thread.join(timeout=2)
        self.assertEqual(states, ["first", "second", "third"])
