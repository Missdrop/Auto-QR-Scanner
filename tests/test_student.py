import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

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

    def test_wrong_pairing_key_cannot_write_session(self) -> None:
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

    def test_missing_login_does_not_open_a_code(self) -> None:
        self.student.start(port=0)
        with patch("src.student.webbrowser.open") as browser:
            self.student.open(HOME_URL + "#/?state=example")
            browser.assert_not_called()
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
            with self.assertRaises(ValueError):
                self.student.open(url)

    def test_invalid_event_is_rejected(self) -> None:
        with self.assertRaises(HTTPError) as failure:
            self.send({"event": "session", "token": 42})
        self.assertEqual(failure.exception.code, 400)

    def test_existing_state_is_preserved(self) -> None:
        result = Student._authenticated_url(
            HOME_URL + "#/?state=a%2Fb%3D&token=old",
            {"userId": "student", "token": "secret"},
        )
        query = parse_qs(urlsplit(result).fragment.partition("?")[2])
        self.assertEqual(query["state"], ["a/b="])
        self.assertEqual(query["token"], ["secret"])

    def test_platform_status_is_separate_from_session(self) -> None:
        self.student._receive(
            {"event": "session", "userId": "student", "token": "secret"}
        )
        self.assertNotIn("success page", self.messages[-1])
        self.student._receive({"event": "failure"})
        self.assertIn("did not confirm", self.messages[-1])
        self.student._receive({"event": "success"})
        self.assertIn("success page", self.messages[-1])
