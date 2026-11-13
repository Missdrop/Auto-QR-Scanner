import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from wechat.cached_media import CachedMedia


class CachedMediaTest(unittest.TestCase):
    def setUp(self):
        self.media = object.__new__(CachedMedia)
        self.media._ffmpeg_exe = Mock(return_value="ffmpeg.exe")
        self.media._extract_hevc = Mock(return_value=b"video")

    def test_converter_is_hidden_and_returns_valid_image(self):
        def convert(arguments, **options):
            self.assertEqual(
                options["creationflags"], getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            self.assertTrue(options["capture_output"])
            self.assertEqual(options["timeout"], 30)
            Path(arguments[-1]).write_bytes(b"\xff\xd8\xffimage")
            return Mock(returncode=0)

        with patch("wechat.cached_media.subprocess.run", side_effect=convert) as run:
            self.assertEqual(self.media._wxgf_to_jpg(b"wxgf"), b"\xff\xd8\xffimage")
        run.assert_called_once()

    def test_failed_or_invalid_conversion_does_not_return_image(self):
        for response in [Mock(returncode=1), Mock(returncode=0)]:
            with patch("wechat.cached_media.subprocess.run", return_value=response):
                self.assertIsNone(self.media._wxgf_to_jpg(b"wxgf"))
        with patch(
            "wechat.cached_media.subprocess.run",
            side_effect=subprocess.TimeoutExpired("ffmpeg", 30),
        ):
            self.assertIsNone(self.media._wxgf_to_jpg(b"wxgf"))
