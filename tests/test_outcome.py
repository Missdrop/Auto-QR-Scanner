import tempfile
import unittest
from pathlib import Path

from src.history import History
from src.outcome import Outcome


class OutcomeTest(unittest.TestCase):
    def test_platform_results_are_not_confused_with_decoding(self):
        for label in ["Custom result", "Pending review", "Completed"]:
            outcome = Outcome("qr", "result", label, "Adapter description")
            self.assertEqual(outcome.label(), label)
            self.assertIn("Adapter description", outcome.detail())
        self.assertEqual(Outcome("qr", "queued").label(), "等待扫码")
        self.assertNotEqual(Outcome("qr", "error").label(), "处理成功")

    def test_results_survive_restart_and_interrupted_work_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.sqlite3"
            history = History(path)
            history.save_outcome(
                Outcome("one", "result", "Custom result", "Description")
            )
            history.save_outcome(Outcome("two", "processing"))
            loaded = {value.url: value for value in History(path).outcomes()}
            self.assertEqual(loaded["one"].label(), "Custom result")
            self.assertEqual(loaded["two"].status, "cancelled")
