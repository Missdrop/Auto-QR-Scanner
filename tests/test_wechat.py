import tempfile
import unittest
from pathlib import Path
from queue import Empty
from unittest.mock import Mock, patch

from wechat.client import WeChat


class WeChatTest(unittest.TestCase):
    def test_database_events_are_delivered_and_process_is_closed(self):
        context = Mock()
        process = context.Process.return_value
        process.pid = 123
        process.is_alive.return_value = False
        image = Mock()
        context.Queue.return_value.get.side_effect = [
            ("notice", "Monitoring selected chats in the background"),
            ("image", image),
            ("finished", None),
        ]
        with patch("wechat.client.multiprocessing.get_context", return_value=context):
            self.wechat._run(["Chat"], self.received.append, self.notices.append)
        self.assertEqual(self.received, [image])
        self.assertIn("Monitoring selected chats in the background", self.notices)
        self.assertEqual(self.notices[-1], "Monitoring stopped")
        context.Event.return_value.set.assert_called_once()
        process.close.assert_called_once()
        context.Queue.return_value.close.assert_called_once()

    def test_background_crash_is_not_reported_as_a_normal_stop(self):
        context = Mock()
        process = context.Process.return_value
        process.pid = 123
        process.is_alive.return_value = False
        process.exitcode = 1
        context.Queue.return_value.get.side_effect = Empty
        with patch(
            "wechat.client.multiprocessing.get_context",
            return_value=context,
        ):
            self.wechat._run(["Chat"], self.received.append, self.notices.append)
        self.assertIn("exited unexpectedly", self.notices[-1])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.wechat = WeChat(self.root / "downloaded")
        self.received = []
        self.notices = []

    def test_empty_group_list_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.wechat.start(["  "], self.received.append, self.notices.append)

    def test_removed_original_source_is_rejected_before_monitoring(self) -> None:
        with self.assertRaises(ValueError):
            self.wechat.start(
                ["Chat"],
                self.received.append,
                self.notices.append,
                image_modes=["original"],
            )
        self.assertIsNone(self.wechat._thread)

    def test_close_waits_for_monitor_cleanup(self) -> None:
        thread = Mock()
        self.wechat._thread = thread
        self.wechat.close()
        self.assertTrue(self.wechat._stop.is_set())
        thread.join.assert_called_once_with()
