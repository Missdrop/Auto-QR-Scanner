import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import zxingcpp

from models.message import ImageMessage
from scanning.image_processor import ImageProcessor
from scanning.scanner import Scanner


def make_code(text: str) -> np.ndarray:
    barcode = zxingcpp.create_barcode(text, zxingcpp.BarcodeFormat.QRCode)
    return np.asarray(barcode.to_image(scale=8))


class ScannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "photo.png"
        self.scanner = Scanner(ImageProcessor())

    def scan_image(self, image: np.ndarray):
        cv2.imencode(".png", image)[1].tofile(self.path)
        message = ImageMessage("test", "Test", self.path, datetime.now().astimezone())
        return self.scanner.scan(message)

    def test_rotated_code(self) -> None:
        image = np.rot90(make_code("https://example.com/qr"))
        result = self.scan_image(image)
        self.assertEqual(
            [code.text for code in result.codes], ["https://example.com/qr"]
        )
        self.assertEqual(result.error, "")

    def test_two_codes(self) -> None:
        first = make_code("first")
        second = make_code("second")
        canvas = np.full((600, 1000), 255, dtype=np.uint8)
        canvas[30 : 30 + first.shape[0], 30 : 30 + first.shape[1]] = first
        canvas[200 : 200 + second.shape[0], 600 : 600 + second.shape[1]] = second
        result = self.scan_image(canvas)
        self.assertEqual({code.text for code in result.codes}, {"first", "second"})

    def test_perspective_and_blur(self) -> None:
        image = make_code("photographed screen")
        height, width = image.shape
        source = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
        target = np.float32([[70, 40], [430, 75], [390, 430], [40, 390]])
        transform = cv2.getPerspectiveTransform(source, target)
        photo = cv2.warpPerspective(image, transform, (500, 500), borderValue=255)
        result = self.scan_image(cv2.GaussianBlur(photo, (3, 3), 0.6))
        self.assertEqual([code.text for code in result.codes], ["photographed screen"])

    def test_blank_image(self) -> None:
        result = self.scan_image(np.full((300, 300), 255, dtype=np.uint8))
        self.assertEqual(result.status(), "No QR code")

    def test_missing_file(self) -> None:
        message = ImageMessage("missing", "Test", self.path, datetime.now())
        result = self.scanner.scan(message)
        self.assertEqual(result.status(), "Failed")
        self.assertTrue(result.error)

    def test_invalid_file(self) -> None:
        self.path.write_bytes(b"not an image")
        message = ImageMessage("invalid", "Test", self.path, datetime.now())
        self.assertEqual(self.scanner.scan(message).status(), "Failed")

    def test_empty_file_is_reported_as_failure(self) -> None:
        self.path.write_bytes(b"")
        message = ImageMessage("empty", "Test", self.path, datetime.now())
        self.assertEqual(self.scanner.scan(message).status(), "Failed")

    def test_pixel_limit_is_enforced(self) -> None:
        self.scanner = Scanner(ImageProcessor(max_pixels=100))
        result = self.scan_image(make_code("too large"))
        self.assertEqual(result.status(), "Failed")
        self.assertIn("pixel limit", result.error)
