from email.message import Message
from typing import Any
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request


class NoRedirect(HTTPRedirectHandler):
    """
    Never forward a student token to a redirect destination.
    """

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> None:
        return None


class Ams:
    """
    Validate QR states and the explicit platform result returned by Chromium.
    """

    @staticmethod
    def state(url: str) -> str:
        query = urlsplit(url).fragment.partition("?")[2]
        values = parse_qs(query, max_num_fields=16).get("state", [])
        if len(values) != 1 or not 1 <= len(values[0]) <= 512:
            raise ValueError("The AMS QR URL has no valid state")
        return values[0]

    @staticmethod
    def result(result: object) -> tuple[int, str]:
        if not isinstance(result, dict) or type(result.get("code")) is not int:
            raise ValueError("The AMS response has no result code")
        message = result.get("message")
        if not isinstance(message, str):
            message = "No platform message"
        return result["code"], message[:1000]
