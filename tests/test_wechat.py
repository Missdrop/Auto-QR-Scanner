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
        reader = Mock()
        reader.name.return_value = "Group"
        reader.messages.return_value = [old]
        self.wechat._stop.set()
        with patch("src.passive_chat.PassiveChat", return_value=reader):
            self.wechat._poll(
                client, ["Group"], self.received.append, self.notices.append
            )
        self.assertIn("Group:old", self.wechat._seen)
        self.assertEqual(self.received, [])
        client.GetAllMessage.assert_not_called()
        client.ChatInfo.assert_not_called()

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
            self.wechat._run_ui(["Group"], self.received.append, self.notices.append)

        module.WeChat.assert_called_once_with(
            resize=False, ads=False, start_listener=False
        )
        poll.assert_called_once()
        listen.assert_not_called()
        client.StopListening.assert_called_once()
        self.assertEqual(events, ["restored", "uninitialized"])

    def test_passive_poll_receives_new_images_without_backend_parsing(self) -> None:
        source = self.root / "incoming.png"
        source.write_bytes(b"photo")
        old = self.message("old")
        new = self.message("new")
        new.download.return_value = source
        reader = Mock()
        reader.name.return_value = "Group"
        reader.is_foreground.return_value = True
        reader.messages.side_effect = [[old], [old, new]]
        client = Mock()
        with (
            patch("src.passive_chat.PassiveChat", return_value=reader),
            patch.object(self.wechat._stop, "wait", side_effect=[False, True]),
        ):
            self.wechat._poll(
                client, ["Group"], self.received.append, self.notices.append
            )
        self.assertEqual([message.message_id for message in self.received], ["new"])
        old.download.assert_not_called()
        client.GetAllMessage.assert_not_called()
        client.ChatInfo.assert_not_called()

    def test_passive_poll_does_not_capture_when_wechat_is_covered(self) -> None:
        reader = Mock()
        reader.name.return_value = "Group"
        reader.is_foreground.return_value = False
        reader.messages.return_value = []
        with (
            patch("src.passive_chat.PassiveChat", return_value=reader),
            patch.object(self.wechat._stop, "wait", side_effect=[False, True]),
        ):
            self.wechat._poll(
                Mock(), ["Group"], self.received.append, self.notices.append
            )
        reader.messages.assert_called_once()
        self.assertEqual(self.received, [])
        self.assertIn("paused", self.notices[-1])

    def test_latest_image_mode_reads_one_old_incoming_image(self) -> None:
        source = self.root / "latest.png"
        source.write_bytes(b"photo")
        older = self.message("older")
        latest = self.message("latest")
        latest.download.return_value = source
        outgoing = self.message("outgoing", "self")
        reader = Mock()
        reader.name.return_value = "Chat"
        reader.is_foreground.return_value = True
        reader.messages.return_value = [older, latest, outgoing]
        with patch("src.passive_chat.PassiveChat", return_value=reader):
            self.wechat._poll(
                Mock(),
                ["Chat"],
                self.received.append,
                self.notices.append,
                latest_only=True,
            )
        self.assertEqual([message.message_id for message in self.received], ["latest"])
        older.download.assert_not_called()
        outgoing.download.assert_not_called()

    def test_failed_initialization_restores_accessibility(self) -> None:
        module = Mock()
        module.WeChat.side_effect = OSError("Window unavailable")
        access = Mock()
        with (
            patch("src.qt_access.QtAccess", return_value=access),
            patch("src.wechat.importlib.import_module"),
            patch.object(self.wechat, "_load_backend", return_value=module),
        ):
            self.wechat._run_ui(["Group"], self.received.append, self.notices.append)

        access.close.assert_called_once()
        self.assertIn("Window unavailable", self.notices[-1])

    def test_close_waits_for_monitor_cleanup(self) -> None:
        thread = Mock()
        self.wechat._thread = thread
        self.wechat.close()
        self.assertTrue(self.wechat._stop.is_set())
        thread.join.assert_called_once_with()

    def test_background_stop_can_terminate_a_slow_database_startup(self) -> None:
        context = Mock()
        process = context.Process.return_value
        process.pid = 123
        process.is_alive.return_value = True
        self.wechat._stop.set()
        with patch("src.wechat.multiprocessing.get_context", return_value=context):
            self.wechat._run(["Chat"], self.received.append, self.notices.append)
        process.terminate.assert_called_once()
        context.Event.return_value.set.assert_called_once()
        self.assertEqual(context.Queue.return_value.close.call_count, 2)
        self.assertEqual(self.notices[-1], "Monitoring stopped")
