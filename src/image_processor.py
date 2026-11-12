from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np
from cv2.typing import MatLike

Image = MatLike


class ImageProcessor:
    """
    Load bounded images and lazily produce alternatives for photographed codes.
    """

    def __init__(self, max_pixels: int = 24_000_000) -> None:
        self._max_pixels = max_pixels

    def load(self, image_path: Path) -> Image:
        # imdecode supports Windows paths containing non-ASCII characters.
        if image_path.stat().st_size > 40_000_000:
            raise ValueError("Image file exceeds 40 MB")

        encoded = np.fromfile(image_path, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Cannot decode image file")
        if image.shape[0] * image.shape[1] > self._max_pixels:
            raise ValueError("Image exceeds the pixel limit")

        return image

    def variants(self, image: Image) -> Iterator[Image]:
        # Decode the original first; most clear photos need no enhancement.
        yield image
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        yield gray

        # Limit working resolution so retries cannot grow without bound.
        scale = min(2.0, 2200 / max(gray.shape))
        resized = cv2.resize(gray, None, fx=scale, fy=scale)
        yield resized
        enhanced = cv2.createCLAHE(clipLimit=2.0).apply(resized)
        yield enhanced
        yield cv2.adaptiveThreshold(
            enhanced,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            41,
            7,
        )

        # Gentle smoothing can reduce interference from photographed screens.
        yield cv2.GaussianBlur(resized, (3, 3), 0)
        yield 255 - resized

    def regions(self, image: Image) -> Iterator[Image]:
        # Crop before enlarging: a small projected symbol otherwise remains tiny
        # when the entire classroom photo reaches the working-resolution limit.
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        for top in (0.0, 0.2, 0.4):
            for left in (0.0, 0.2, 0.4):
                crop = gray[
                    int(height * top) : int(height * (top + 0.6)),
                    int(width * left) : int(width * (left + 0.6)),
                ]
                if not crop.size:
                    continue
                scale = min(6.0, 1400 / max(crop.shape))
                enlarged = cv2.resize(
                    crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
                )
                yield enlarged
                smooth = cv2.GaussianBlur(enlarged, (0, 0), 1.2)
                yield cv2.addWeighted(enlarged, 1.8, smooth, -0.8, 0)
