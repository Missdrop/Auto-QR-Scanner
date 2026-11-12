import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.language import chinese
from src.original_downloads import (
    DownloadDiagnostics,
    OriginalDownloads,
    failure_notice,
)


class OriginalDownloadsTest(unittest.TestCase):
    def test_completed_download_returns_its_actual_saved_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "saved.jpg"
            image.write_bytes(b"photo")
            downloads = OriginalDownloads(root, root, self.fail)
            process = Mock()
            process.is_alive.return_value = False
            process.exitcode = 0
            results = Mock()
            results.get_nowait.return_value = str(image)
            downloads._process = process
            downloads._results = results
            downloads._active = "one"
            downloads.poll()
            self.assertEqual(downloads.take_completed(), [("one", image.resolve())])
            self.assertEqual(downloads.take_completed(), [])
            results.close.assert_called_once()

    def test_failure_category_does_not_keep_private_log_values(self) -> None:
        diagnostics = DownloadDiagnostics()
        record = logging.LogRecord(
            "wechatauto",
            logging.DEBUG,
            "",
            0,
            "没有出现新的预览窗 %s",
            ("private-chat-name",),
            None,
        )
        diagnostics.emit(record)
        self.assertEqual(diagnostics.code, 4)
        self.assertNotIn("private-chat-name", failure_notice(diagnostics.code))
        self.assertIn("图片窗口未打开", chinese(failure_notice(diagnostics.code)))

    def test_timeout_is_distinguished_from_a_completed_failure(self) -> None:
        notices = []
        downloads = OriginalDownloads(Path("unused"), Path("unused"), notices.append)
        process = Mock()
        process.is_alive.return_value = True
        process.exitcode = None
        downloads._process = process
        downloads._deadline = 0
        downloads.poll()
        self.assertFalse(downloads.last_success)
        self.assertEqual(notices, [failure_notice(7)])
        process.terminate.assert_called_once()

    def test_backend_failure_category_reaches_the_notice(self) -> None:
        notices = []
        downloads = OriginalDownloads(Path("unused"), Path("unused"), notices.append)
        process = Mock()
        process.is_alive.return_value = False
        process.exitcode = 3
        downloads._process = process
        downloads.poll()
        self.assertEqual(notices, [failure_notice(3)])
        process.terminate.assert_not_called()
