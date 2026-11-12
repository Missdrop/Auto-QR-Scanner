import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from threading import Event

from src.history import History
from src.image_processor import ImageProcessor
from src.message import ImageMessage
from src.scanner import Scanner
from src.worker import Worker


class WorkerTest(unittest.TestCase):
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
