from itertools import chain
from time import perf_counter

import cv2
import zxingcpp

from models.message import ImageMessage
from models.result import Code, ScanResult
from scanning.image_processor import ImageProcessor


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
        warning = ""

        try:
            image = self._image_processor.load(message.image_path)
            if max(image.shape[:2]) < 600:
                warning = "Low resolution; waiting for a clearer cached image"
            for variant in chain(
                self._image_processor.variants(image),
                self._image_processor.regions(image),
            ):
                decoded = zxingcpp.read_barcodes(
                    variant,
                    formats=zxingcpp.BarcodeFormats(zxingcpp.BarcodeFormat.QRCode),
                    try_rotate=True,
                    try_downscale=True,
                    try_invert=True,
                )
                for barcode in decoded:
                    codes.setdefault(barcode.text, Code(barcode.text))
                if codes or perf_counter() - started > 2:
                    break
        except (OSError, ValueError, RuntimeError, cv2.error) as exception:
            error = str(exception)

        elapsed_ms = (perf_counter() - started) * 1000
        return ScanResult(
            message, list(codes.values()), elapsed_ms, error, warning=warning
        )
