import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.wechat import WeChat


class WeChatTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.wechat = WeChat(self.root / "downloaded")
        self.received = []
        self.notices = []

    def message(self, message_id="1", attr="friend", kind="image"):
        message = Mock()
        message.id = message_id
        message.attr = attr
        message.type = kind
        return message

    def test_incoming_image_is_copied_once(self) -> None:
        original = self.root / "photo.png"
        original.write_bytes(b"image content")
        message = self.message()
        message.download.return_value = original
        for _ in range(2):
            self.wechat._receive(
                message, "Group", self.received.append, self.notices.append
            )
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0].image_path.read_bytes(), b"image content")
        self.assertEqual(self.received[0].chat_name, "Group")
        self.assertEqual(message.download.call_count, 1)

    def test_self_and_text_messages_are_ignored(self) -> None:
        for message in [self.message("1", "self"), self.message("2", kind="text")]:
            self.wechat._receive(
                message, "Group", self.received.append, self.notices.append
            )
            message.download.assert_not_called()
        self.assertEqual(self.received, [])

    def test_download_failure_is_visible(self) -> None:
        message = self.message()
        message.download.side_effect = OSError("unavailable")
        self.wechat._receive(
            message, "Group", self.received.append, self.notices.append
        )
        self.assertEqual(self.received, [])
        self.assertIn("Cannot retrieve", self.notices[-1])

    def test_empty_group_list_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.wechat.start(["  "], self.received.append, self.notices.append)

    def test_polling_skips_baseline_and_checks_group(self) -> None:
        client = Mock()
        client.ChatInfo.return_value = {"chat_name": "Group", "chat_type": "group"}
        old = self.message("old")
        client.GetAllMessage.return_value = [old]
        self.wechat._stop.set()
        self.wechat._poll(client, ["Group"], self.received.append, self.notices.append)
        self.assertIn("Group:old", self.wechat._seen)
        self.assertEqual(self.received, [])

    def test_free_backend_polls_even_when_listener_api_exists(self) -> None:
        module = Mock()
        module.__name__ = "wxauto4"
        client = module.WeChat.return_value
        events = []
        access = Mock()
        access.close.side_effect = lambda: events.append("restored")
        com = Mock()
        com.CoUninitialize.side_effect = lambda: events.append("uninitialized")

        with (
            patch("src.qt_access.QtAccess", return_value=access),
            patch("src.wechat.importlib.import_module", return_value=com),
            patch.object(self.wechat, "_load_backend", return_value=module),
            patch.object(self.wechat, "_poll") as poll,
            patch.object(self.wechat, "_listen") as listen,
        ):
            self.wechat._run(["Group"], self.received.append, self.notices.append)

        module.WeChat.assert_called_once_with(
            resize=False, ads=False, start_listener=False
        )
        poll.assert_called_once()
        listen.assert_not_called()
        client.StopListening.assert_called_once()
        self.assertEqual(events, ["restored", "uninitialized"])

    def test_failed_initialization_restores_accessibility(self) -> None:
        module = Mock()
        module.WeChat.side_effect = OSError("Window unavailable")
        access = Mock()
        with (
            patch("src.qt_access.QtAccess", return_value=access),
            patch("src.wechat.importlib.import_module"),
            patch.object(self.wechat, "_load_backend", return_value=module),
        ):
            self.wechat._run(["Group"], self.received.append, self.notices.append)

        access.close.assert_called_once()
        self.assertIn("Window unavailable", self.notices[-1])

    def test_close_waits_for_monitor_cleanup(self) -> None:
        thread = Mock()
        self.wechat._thread = thread
        self.wechat.close()
        self.assertTrue(self.wechat._stop.is_set())
        thread.join.assert_called_once_with()
