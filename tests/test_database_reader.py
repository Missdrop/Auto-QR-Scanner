import tempfile
import unittest
from pathlib import Path
from queue import Queue
from unittest.mock import Mock, patch

from src.database_reader import DatabaseReader


class DatabaseReaderTest(unittest.TestCase):
    def test_new_cached_version_is_delivered_but_identical_bytes_are_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            thumb, original = root / "thumb.jpg", root / "original.jpg"
            thumb.write_bytes(b"small-photo")
            original.write_bytes(b"full-photo")
            photo = Mock()
            photo.id, photo.type, photo.attr = "image", "image", "friend"
            photo.row = {"sort_seq": 2}
            photo.download.side_effect = [thumb, original, original]
            old = Mock()
            old.row = {"sort_seq": 1}
            source = Mock()
            source.resolve.return_value = "chat-user"
            source.latest.return_value = [old]
            source.after.side_effect = [[photo], [], []]
            stopped, output = Mock(), Mock()
            stopped.wait.side_effect = [False, False, False, True]
            stopped.is_set.return_value = False
            reader = DatabaseReader(root / "images", output, stopped)
            with patch("src.database_reader.DatabaseSource", return_value=source):
                reader.run(["chat"], False)
            images = [
                call.args[0][1]
                for call in output.put.call_args_list
                if call.args[0][0] == "image"
            ]
            self.assertEqual(
                [image.image_path.read_bytes() for image in images],
                [b"small-photo", b"full-photo"],
            )

    def test_download_starts_before_decode_and_success_skips_original_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            thumb = root / "thumb.jpg"
            thumb.write_bytes(b"small-photo")
            photo = Mock()
            photo.id, photo.type, photo.attr = "image", "image", "friend"
            photo.row = {"sort_seq": 2}
            photo.download.return_value = thumb
            source = Mock()
            source.resolve.return_value = "chat-user"
            source.latest.return_value = [photo]
            feedback, output, stopped = Queue(), Mock(), Mock()
            stopped.wait.return_value = False
            stopped.is_set.return_value = False
            reader = DatabaseReader(root / "images", output, stopped, feedback)
            reader._downloads = Mock()

            def receive(event):
                if event[0] == "image":
                    reader._downloads.submit.assert_called_once()
                    feedback.put(event[1].message_id)

            output.put.side_effect = receive
            with patch("src.database_reader.DatabaseSource", return_value=source):
                reader.run(["chat"], True)
            photo.download.assert_called_once()
            reader._downloads.cancel.assert_called_once_with("image")

    def test_new_images_wait_for_cache_without_replaying_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "cached.jpg"
            image.write_bytes(b"photo")
            old = Mock()
            old.row = {"sort_seq": 100}
            new = Mock()
            new.row = {"sort_seq": 101}
            new.id = "new"
            new.type = "image"
            new.attr = "friend"
            new.download.side_effect = [FileNotFoundError(), image]
            source = Mock()
            source.resolve.return_value = "chat-user"
            source.latest.return_value = [old]
            source.after.side_effect = [[new], []]
            output = Mock()
            stopped = Mock()
            stopped.wait.side_effect = [False, False, True]
            stopped.is_set.return_value = False
            reader = DatabaseReader(root / "images", output, stopped)
            with patch("src.database_reader.DatabaseSource", return_value=source):
                reader.run(["Chat"], False)
            delivered = [
                call.args[0][1]
                for call in output.put.call_args_list
                if call.args[0][0] == "image"
            ]
            self.assertEqual(len(delivered), 1)
            self.assertEqual(delivered[0].image_path.read_bytes(), b"photo")
            old.download.assert_not_called()
            source.after.assert_any_call("chat-user", 100)
            source.after.assert_any_call("chat-user", 101)

    def test_latest_mode_does_not_require_a_visible_window(self) -> None:
        source = Mock()
        source.resolve.return_value = "chat-user"
        photo = Mock()
        photo.type, photo.attr = "image", "friend"
        photo.row = {"sort_seq": 1}
        source.latest.return_value = [photo]
        reader = DatabaseReader(Path("unused/images"), Mock(), Mock())
        with (
            patch("src.database_reader.DatabaseSource", return_value=source),
            patch.object(reader, "deliver") as deliver,
        ):
            reader.run(["Chat"], True)
        deliver.assert_called_once_with("Chat", photo)
        source.after.assert_not_called()
