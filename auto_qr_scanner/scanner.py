from auto_qr_scanner.image_processor import ImageProcessor


class Scanner:
    """
    Coordinate image preparation and QR decoding.

    Decoding and retry strategies are not implemented yet.
    """

    def __init__(self, image_processor: ImageProcessor) -> None:
        self._image_processor = image_processor
