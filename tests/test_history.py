import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

from src.history import History
from src.message import ImageMessage
from src.result import Code, ScanResult


class HistoryTest(unittest.TestCase):
    def test_existing_records_keep_details_without_inventing_adapter_results(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.sqlite3"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    "CREATE TABLE outcomes (url TEXT PRIMARY KEY, status TEXT, "
                    "code INTEGER, message TEXT)"
                )
                connection.execute(
                    "INSERT INTO outcomes VALUES (?, ?, ?, ?)",
                    ("qr", "result", 0, "Existing details"),
                )
                connection.commit()
            history = History(path)
            old = history.outcome("qr")
            self.assertEqual(old.details, "Existing details")
            self.assertEqual(old.result, "")
            self.assertEqual(old.label(), "已处理")

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "history.sqlite3"
        self.history = History(self.path)

    def result(self, text: str) -> ScanResult:
        message = ImageMessage(
            "1", "Group", Path("photo.png"), datetime.now().astimezone()
        )
        return ScanResult(message, [Code(text)], 12.5)

    def test_duplicate_survives_restart(self) -> None:
        first = self.result("https://example.com/?name='test'")
        self.history.save(first)
        self.assertFalse(first.codes[0].duplicate)

        history = History(self.path)
        second = self.result(first.codes[0].text)
        history.save(second)
        self.assertTrue(second.codes[0].duplicate)
        records = history.recent()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].status(), "Duplicate")
        self.assertEqual(records[0].message.chat_name, "Group")
        self.assertEqual(records[1].elapsed_ms, 12.5)

    def test_failed_attempt_is_preserved(self) -> None:
        result = self.result("unused")
        result.codes = []
        result.error = "Cannot decode image file"
        self.history.save(result)
        self.assertEqual(self.history.recent()[0].error, result.error)

    def test_limit(self) -> None:
        self.history.save(self.result("first"))
        self.history.save(self.result("second"))
        self.assertEqual(len(self.history.recent(1)), 1)
        with self.assertRaises(ValueError):
            self.history.recent(0)

    def test_actual_image_kind_survives_restart_and_old_records_stay_unknown(self):
        result = self.result("original")
        result.message.image_kind = "original"
        self.history.save(result)
        self.assertEqual(History(self.path).recent()[0].message.image_kind, "original")
        self.history.save(self.result("legacy"))
        self.assertEqual(History(self.path).recent()[0].message.image_kind, "unknown")
