import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

from src.student import HOME_URL, Student


class StudentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.messages = []
        self.student = Student(Path(tempfile.gettempdir()), self.messages.append)

    def test_only_exact_student_origin_is_accepted(self) -> None:
        self.assertTrue(Student.is_student_url(HOME_URL + "#/?state=example"))
        for url in [
            "http://ams.xjtlu.edu.cn/studenth5/",
            "https://ams.xjtlu.edu.cn.evil.test/studenth5/",
            "https://user@ams.xjtlu.edu.cn/studenth5/",
            "file:///studenth5/",
            "javascript:alert(1)",
        ]:
            self.assertFalse(Student.is_student_url(url))
            with self.assertRaises(ValueError):
                self.student.open(url)

    def test_login_required_does_not_navigate_code(self) -> None:
        page = Mock()
        page.url = HOME_URL
        page.evaluate.return_value = None
        self.student._page = page
        self.student._navigate(HOME_URL + "#/?state=expired")
        page.goto.assert_not_called()
        self.assertIn("Login required", self.messages[-1])

    def test_account_is_added_without_replacing_state(self) -> None:
        original = HOME_URL + "#/?state=a%2Fb%3D&token=old"
        url = Student._authenticated_url(
            original, {"userId": "student", "token": "secret"}
        )
        parameters = parse_qs(urlsplit(url).fragment.partition("?")[2])
        self.assertEqual(parameters["state"], ["a/b="])
        self.assertEqual(parameters["userId"], ["student"])
        self.assertEqual(parameters["token"], ["secret"])

    def test_expired_response_removes_persistent_session(self) -> None:
        response = Mock()
        response.url = "https://ams.xjtlu.edu.cn/xjtlu/example"
        response.request.resource_type = "xhr"
        response.json.return_value = {"code": 401}
        page = Mock()
        self.student._page = page
        self.student._on_response(response)
        self.assertIn("expired", self.messages[-1])
        self.assertIn("removeItem", page.evaluate.call_args[0][0])

    def test_non_json_response_cannot_report_success(self) -> None:
        response = Mock()
        response.url = HOME_URL
        response.request.resource_type = "xhr"
        response.json.side_effect = ValueError("not JSON")
        self.student._on_response(response)
        self.assertEqual(self.messages, [])
