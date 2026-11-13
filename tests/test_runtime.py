import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from browser.runtime import Chromium


class ChromiumTest(unittest.TestCase):
    def test_runtime_is_verified_and_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "chrome.exe"
            executable.write_bytes(b"test-runtime")
            manifest = {
                "revision": "1",
                "executable": "chrome.exe",
                "sha256": Chromium.digest(executable),
            }
            (root / "manifest.json").write_text(json.dumps(manifest))
            with patch.object(Chromium, "revision", return_value="1"):
                self.assertEqual(Chromium(root).executable(), executable)
                executable.write_bytes(b"modified")
                with self.assertRaises(ValueError):
                    Chromium(root).executable()

    def test_manifest_cannot_reference_an_external_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {
                "revision": "1",
                "executable": "../outside.exe",
                "sha256": "invalid",
            }
            (root / "manifest.json").write_text(json.dumps(manifest))
            with patch.object(Chromium, "revision", return_value="1"):
                with self.assertRaises(ValueError):
                    Chromium(root).executable()
