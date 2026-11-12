from .message import ImageMessage


class Code:
    """
    Hold the decoded text of one QR code.
    """

    def __init__(self, text: str) -> None:
        self.text = text


class ScanResult:
    """
    Associate decoded codes with their original image message.
    """

    def __init__(self, message: ImageMessage, codes: list[Code]) -> None:
        self.message = message
        self.codes = list(codes)
