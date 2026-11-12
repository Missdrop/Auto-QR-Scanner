import json
from email.message import Message
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


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
    Use the existing AMS QR endpoint over HTTPS and return its explicit result.
    """

    @staticmethod
    def state(url: str) -> str:
        query = urlsplit(url).fragment.partition("?")[2]
        values = parse_qs(query, max_num_fields=16).get("state", [])
        if len(values) != 1 or not 1 <= len(values[0]) <= 512:
            raise ValueError("The AMS QR URL has no valid state")
        return values[0]

    def process(self, state: str, token: str) -> tuple[int, str]:
        query = urlencode({"code": state, "type": 1})
        request = Request(
            "https://ams.xjtlu.edu.cn/xjtlu/sign/qRCodeSign?" + query,
            headers={"X-Token": token},
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=10) as response:
                content = response.read(65537)
        except HTTPError as exception:
            code = exception.code
            exception.close()
            if code in {301, 302, 303, 307, 308, 401, 403}:
                return 401, "Student login required"
            raise
        if len(content) > 65536:
            raise ValueError("The AMS response exceeded the size limit")
        result = json.loads(content)
        if not isinstance(result, dict) or type(result.get("code")) is not int:
            raise ValueError("The AMS response has no result code")
        message = result.get("message")
        if not isinstance(message, str):
            message = "No platform message"
        return result["code"], message[:1000]
