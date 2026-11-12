import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

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
