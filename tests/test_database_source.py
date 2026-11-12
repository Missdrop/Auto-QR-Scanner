import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.database_source import DatabasePhoto, DatabaseSource


class DatabaseSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = object.__new__(DatabaseSource)
        self.source.db = Mock()
        self.source.db.wxid = "own-account"
        self.source.media = Mock()
        self.source._keys = Mock()

    def test_ambiguous_chat_names_are_rejected(self) -> None:
        self.source.db.search_contact.return_value = [
            {"username": "a", "nick_name": "Chat"},
            {"username": "b", "remark": "Chat"},
        ]
        with self.assertRaises(ValueError):
            self.source.resolve("Chat")

    def test_only_exact_chat_names_are_accepted(self) -> None:
        self.source.db.search_contact.return_value = [
            {"username": "a", "nick_name": "Chat extended"},
            {"username": "b", "remark": "Chat"},
        ]
        self.assertEqual(self.source.resolve("Chat"), "b")

    def test_self_and_unknown_senders_are_not_treated_as_friends(self) -> None:
        for sender, expected in [
            ("own-account", "self"),
            ("", "unknown"),
            ("other", "friend"),
        ]:
            row = {
                "type": "图片",
                "local_id": 1,
                "sort_seq": 2,
                "sender_username": sender,
            }
            self.assertEqual(DatabasePhoto(self.source, "chat", row).attr, expected)

    def test_cached_image_never_uses_the_foreground_download_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.jpg"
            image.write_bytes(b"photo")
            self.source.media._image_files.return_value = {"mid": (str(image), 5)}
            self.source.media._probe_ct.return_value = b"encrypted-probe"
            self.source._keys.resolve.return_value = ("verified-key", 7)
            self.source.media.download_image.return_value = str(image)
            row = {"local_id": 1, "shard": "message_0.db"}
            self.assertEqual(self.source.image("chat", row), image)
            self.source.media.download_image.assert_called_once_with(
                "chat",
                1,
                shard="message_0.db",
                tier="mid",
                aes_key="verified-key",
                xor_key=7,
            )
            self.source.media.download_image_original.assert_not_called()
            self.assertEqual(self.source.image_kind, "compressed")

    def test_uncached_images_report_a_retriable_error(self) -> None:
        self.source.media._image_files.return_value = {}
        with self.assertRaises(FileNotFoundError):
            self.source.image("chat", {"local_id": 1})
        self.source.media.download_image_original.assert_not_called()

    def test_thumbnail_mode_never_selects_an_existing_original(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "thumb.jpg"
            image.write_bytes(b"thumbnail")
            self.source.thumbnail_only = True
            self.source.media._image_files.return_value = {
                "thumb": (str(image), 9),
                "original": ("original.dat", 1000),
            }
            self.source.media._probe_ct.return_value = None
            self.source.media.download_image.return_value = str(image)
            self.source.image("chat", {"local_id": 1})
            self.source.media.download_image.assert_called_once_with(
                "chat", 1, shard=None, tier="thumb"
            )
            self.source.media._probe_ct.assert_called_once_with(str(image))
            self.source.media.download_image_original.assert_not_called()
            self.assertEqual(self.source.image_kind, "thumbnail")

    def test_selected_candidate_resolves_by_unique_identifier(self):
        self.source.db.search_contact.return_value = [
            {"username": "unique@chatroom", "nick_name": "Group"}
        ]
        self.assertEqual(
            self.source.resolve("Group [unique@chatroom]"), "unique@chatroom"
        )

    def test_removed_original_mode_is_rejected(self):
        self.source.media._image_files.return_value = {"thumb": ("thumb.dat", 100)}
        with self.assertRaises(ValueError):
            self.source.image("chat", {"local_id": 1}, "original")
        self.source.media.download_image.assert_not_called()

    def test_compressed_mode_uses_mid_cache_even_when_original_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "mid.jpg"
            image.write_bytes(b"photo")
            self.source.image_mode = "compressed"
            self.source.media._image_files.return_value = {
                "mid": (str(image), 5),
                "original": ("original.dat", 1000),
            }
            self.source.media._probe_ct.return_value = None
            self.source.media.download_image.return_value = str(image)
            self.source.image("chat", {"local_id": 1})
            self.source.media.download_image.assert_called_once_with(
                "chat", 1, shard=None, tier="mid"
            )
            self.assertEqual(self.source.image_kind, "compressed")
            self.source.media.download_image_original.assert_not_called()
