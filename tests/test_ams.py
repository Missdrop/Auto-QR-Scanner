import unittest
from unittest.mock import Mock

from src.ams import Ams, NoRedirect


class AmsTest(unittest.TestCase):
    def test_result_requires_an_explicit_integer_platform_code(self) -> None:
        self.assertEqual(
            Ams.result({"code": 1001, "message": "Expired"}), (1001, "Expired")
        )
        for value in ({}, {"code": True}, {"code": "0"}, [], None):
            with self.assertRaises(ValueError):
                Ams.result(value)
        self.assertEqual(Ams.result({"code": 0}), (0, "No platform message"))
        self.assertEqual(len(Ams.result({"code": 0, "message": "x" * 2000})[1]), 1000)

    def test_token_requests_do_not_follow_redirects(self) -> None:
        self.assertIsNone(
            NoRedirect().redirect_request(
                Mock(), Mock(), 302, "Found", Mock(), "https://other.test"
            )
        )

    def test_missing_or_duplicate_qr_states_are_rejected(self) -> None:
        for url in ("https://example.com/#/", "https://example.com/#/?state=a&state=b"):
            with self.assertRaises(ValueError):
                Ams.state(url)
