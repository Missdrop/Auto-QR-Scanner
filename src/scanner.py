from time import perf_counter

import zxingcpp

from .image_processor import ImageProcessor
from .message import ImageMessage
from .result import Code, ScanResult


class Scanner:
    """
    Decode QR values, including rotated and perspective-distorted symbols.
    """

    def __init__(self, image_processor: ImageProcessor) -> None:
        self._image_processor = image_processor

    def scan(self, message: ImageMessage) -> ScanResult:
        started = perf_counter()
        codes: dict[str, Code] = {}
        error = ""

        try:
            image = self._image_processor.load(message.image_path)
            for variant in self._image_processor.variants(image):
                decoded = zxingcpp.read_barcodes(
                    variant,
                    formats=zxingcpp.BarcodeFormats(zxingcpp.BarcodeFormat.QRCode),
                    try_rotate=True,
                    try_downscale=True,
                    try_invert=True,
                )
                for barcode in decoded:
                    codes.setdefault(barcode.text, Code(barcode.text))
        except (OSError, ValueError, RuntimeError) as exception:
            error = str(exception)

        elapsed_ms = (perf_counter() - started) * 1000
        return ScanResult(message, list(codes.values()), elapsed_ms, error)
