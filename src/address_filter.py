from urllib.parse import SplitResult, urlsplit, urlunsplit


class AddressRule:
    """Match an exact host, optionally constrained by a URL prefix and port."""

    def __init__(self, text: str) -> None:
        self._scheme = "://" in text
        self._parts = urlsplit(text if self._scheme else "//" + text)
        parts = self._parts
        if (
            (self._scheme and parts.scheme not in {"http", "https"})
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or any(character.isspace() for character in text)
            or "\\" in text
            or "*" in parts.netloc
            or (not self._scheme and (parts.path or parts.query or parts.fragment))
        ):
            raise ValueError("Invalid address filter")
        self._host = parts.hostname.encode("idna").decode().lower().rstrip(".")
        if not self._host or ".." in self._host:
            raise ValueError("Invalid address filter")
        self._port = parts.port
        self._prefix = self._suffix(parts)

    @staticmethod
    def _suffix(parts: SplitResult) -> str:
        return urlunsplit(("", "", parts.path or "/", parts.query, parts.fragment))

    def matches(self, parts: SplitResult) -> bool:
        host = (parts.hostname or "").encode("idna").decode().lower().rstrip(".")
        if host != self._host:
            return False
        port = (
            parts.port
            if parts.port is not None
            else (443 if parts.scheme == "https" else 80)
        )
        if self._scheme:
            expected = (
                self._port
                if self._port is not None
                else (443 if self._parts.scheme == "https" else 80)
            )
            return (
                parts.scheme == self._parts.scheme
                and port == expected
                and self._suffix(parts).startswith(self._prefix)
            )
        return self._port is None or port == self._port


class AddressFilter:
    """Allow all web addresses when empty, otherwise allow any matching rule."""

    def __init__(self, text: str) -> None:
        try:
            self._rules = [
                AddressRule(line.strip()) for line in text.splitlines() if line.strip()
            ]
        except ValueError:
            raise ValueError("Invalid address filter") from None

    def allows(self, url: str) -> bool:
        try:
            if "\\" in url or any(character.isspace() for character in url):
                return False
            parts = urlsplit(url)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.hostname
                or parts.username is not None
                or parts.password is not None
            ):
                return False
            # Validate the port even when no rules restrict this URL.
            _ = parts.port
            return not self._rules or any(rule.matches(parts) for rule in self._rules)
        except ValueError:
            return False
