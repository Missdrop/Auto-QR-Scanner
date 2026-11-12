import tempfile
import unittest
from pathlib import Path

from src.history import History
from src.outcome import Outcome


class OutcomeTest(unittest.TestCase):
    def test_platform_results_are_not_confused_with_decoding(self):
        cases = [
            (0, "OK", "签到成功"),
            (1001, "The QR code has expired", "二维码已过期"),
            (1002, "This is not your course", "不是我的课"),
            (1003, "You have already signed in", "已签到"),
            (401, "Expired", "需要重新登录"),
            (999, "Unknown platform error", "扫码未通过"),
        ]
        for code, message, label in cases:
            self.assertEqual(Outcome("qr", "result", code, message).label(), label)
        self.assertEqual(Outcome("qr", "queued").label(), "等待扫码")
        self.assertNotEqual(Outcome("qr", "error").label(), "签到成功")

    def test_results_survive_restart_and_interrupted_work_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.sqlite3"
            history = History(path)
            history.save_outcome(Outcome("one", "result", 1001, "Expired"))
            history.save_outcome(Outcome("two", "processing"))
            loaded = {value.url: value for value in History(path).outcomes()}
            self.assertEqual(loaded["one"].label(), "二维码已过期")
            self.assertEqual(loaded["two"].status, "cancelled")
