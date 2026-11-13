import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from threading import Event
from unittest.mock import Mock

from application.worker import Worker
from models.message import ImageMessage
from models.result import Code, ScanResult
from scanning.image_processor import ImageProcessor
from scanning.scanner import Scanner
from storage.history import History


class WorkerTest(unittest.TestCase):
    def test_success_does_not_skip_other_versions_of_the_same_message(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            messages = [
                ImageMessage("same", "Chat", root / "image.jpg", datetime.now(), kind)
                for kind in ("thumbnail", "original")
            ]
            scanner = Mock()
            scanner.scan.side_effect = [
                ScanResult(message, [Code("same-qr")]) for message in messages
            ]
            completed, results = Event(), []

            def receive(result, automatic):
                results.append(result)
                if len(results) == 2:
                    completed.set()

            worker = Worker(
                scanner, History(root / "history.sqlite3"), receive, self.fail
            )
            try:
                for message in messages:
                    worker.submit(message, True)
                self.assertTrue(completed.wait(3))
                self.assertEqual(scanner.scan.call_count, 2)
            finally:
                worker.close()

    def test_failed_image_is_recorded_and_worker_closes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history = History(root / "history.sqlite3")
            completed = Event()
            results = []

            def receive(result, automatic):
                results.append((result, automatic))
                completed.set()

            worker = Worker(Scanner(ImageProcessor()), history, receive, self.fail)
            try:
                message = ImageMessage(
                    "1", "Group", root / "missing.png", datetime.now()
                )
                self.assertTrue(worker.submit(message, True))
                self.assertTrue(completed.wait(5))
                self.assertTrue(results[0][1])
                self.assertEqual(history.recent()[0].status(), "Failed")
            finally:
                worker.close()
            self.assertFalse(worker._thread.is_alive())
