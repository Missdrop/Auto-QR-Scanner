import json
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from src.ams import Ams, NoRedirect


class AmsTest(unittest.TestCase):
    def test_qr_request_uses_https_and_a_token_header(self) -> None:
        response = Mock()
        response.read.return_value = json.dumps(
            {"code": 1001, "message": "Expired"}
        ).encode()
        opener = Mock()
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        with patch("src.ams.build_opener", return_value=opener):
            self.assertEqual(Ams().process("a/b=", "secret"), (1001, "Expired"))
        request = opener.open.call_args.args[0]
        self.assertEqual(urlsplit(request.full_url).scheme, "https")
        self.assertEqual(
            parse_qs(urlsplit(request.full_url).query),
            {
                "code": ["a/b="],
                "type": ["1"],
            },
        )
        self.assertEqual(request.get_header("X-token"), "secret")
        self.assertNotIn("secret", request.full_url)
        opener.open.assert_called_once_with(request, timeout=10)

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
