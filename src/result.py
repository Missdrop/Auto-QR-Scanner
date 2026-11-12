from .message import ImageMessage


class Code:
    """
    Hold one decoded QR value and its duplicate status.
    """

    def __init__(self, text: str, duplicate: bool = False) -> None:
        self.text = text
        self.duplicate = duplicate


class ScanResult:
    """
    Keep source, decoded values, duration and an optional failure together.
    """

    def __init__(
        self,
        message: ImageMessage,
        codes: list[Code],
        elapsed_ms: float = 0,
        error: str = "",
        record_id: int | None = None,
    ) -> None:
        self.message = message
        self.codes = list(codes)
        self.elapsed_ms = elapsed_ms
        self.error = error
        self.record_id = record_id

    def status(self) -> str:
        if self.error:
            return "Failed"
        if not self.codes:
            return "No QR code"
        if all(code.duplicate for code in self.codes):
            return "Duplicate"
        return "Decoded"
