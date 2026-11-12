import tempfile
import unittest
from pathlib import Path
from queue import Queue
from unittest.mock import Mock, patch

from src.database_reader import DatabaseReader


class DatabaseReaderTest(unittest.TestCase):
    def test_viewer_saved_original_is_delivered_without_a_wechat_cache_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "saved.jpg"
            original.write_bytes(b"viewer-saved-original")
            photo = Mock()
            photo.id, photo.type, photo.attr = "one", "image", "friend"
            photo.row = {"sort_seq": 1}
            photo.download.side_effect = FileNotFoundError
            source = Mock()
            source.resolve.return_value = "user"
            source.latest.return_value = [photo]
            stopped, output = Mock(), Mock()
            stopped.wait.return_value = False
            stopped.is_set.return_value = False
            reader = DatabaseReader(root / "images", output, stopped)
            reader._image_modes = ["original"]
            reader._downloads = Mock()
            reader._downloads.take_completed.return_value = [("one", original)]
            with patch("src.database_reader.DatabaseSource", return_value=source):
                reader.run(["Chat"], True)
            images = [
                call.args[0][1]
                for call in output.put.call_args_list
                if call.args[0][0] == "image"
            ]
            self.assertEqual(len(images), 1)
            self.assertEqual(images[0].image_kind, "original")
            self.assertEqual(images[0].image_path.read_bytes(), original.read_bytes())
            self.assertEqual(reader._versions, {})

    def test_failed_copy_is_retried_instead_of_marked_delivered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "photo.jpg"
            image.write_bytes(b"image")
            photo = Mock()
            photo.id = "one"
            output = Mock()
            reader = DatabaseReader(root / "images", output, Mock())
            with patch("src.database_reader.shutil.copyfile", side_effect=OSError):
                with self.assertRaises(OSError):
                    reader._deliver_source("Chat", photo, image, "one:original")
            reader._deliver_source("Chat", photo, image, "one:original")
            output.put.assert_called_once()

    def test_finished_versions_are_released(self):
        reader = DatabaseReader(Path("unused"), Mock(), Mock())
        reader._image_modes = ["thumbnail", "original"]
        reader._versions = {
            "one:thumbnail": "a",
            "one:original": "b",
            "two:original": "c",
        }
        photo = Mock()
        photo.id = "one"
        reader._forget(photo)
        self.assertEqual(reader._versions, {"two:original": "c"})

    def test_missing_selected_version_is_reported_when_wait_expires(self):
        photo = Mock()
        photo.id, photo.type, photo.attr = "one", "image", "friend"
        photo.row = {"sort_seq": 1}
        photo.download.side_effect = FileNotFoundError
        source = Mock()
        source.resolve.return_value = "user"
        source.latest.return_value = [photo]
        stopped, output = Mock(), Mock()
        stopped.wait.return_value = False
        stopped.is_set.return_value = False
        reader = DatabaseReader(Path("unused/images"), output, stopped)
        reader._image_modes = ["original"]
        with (
            patch("src.database_reader.DatabaseSource", return_value=source),
            patch("src.database_reader.monotonic", side_effect=[0, 61]),
        ):
            reader.run(["Chat"], True)
        notices = [call.args[0][1] for call in output.put.call_args_list]
        self.assertTrue(any("Selected image versions" in notice for notice in notices))

    def test_every_selected_version_is_emitted_even_after_success_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            thumb, original = root / "thumb.jpg", root / "original.jpg"
            thumb.write_bytes(b"thumbnail")
            original.write_bytes(b"original")
            photo = Mock()
            photo.id = "one"
            feedback, output = Queue(), Mock()
            reader = DatabaseReader(root / "images", output, Mock(), feedback)
            reader._image_modes = ["thumbnail", "original"]

            def download(mode):
                photo.image_kind = mode
                return thumb if mode == "thumbnail" else original

            photo.download.side_effect = download
            reader.deliver("Chat", photo)
            feedback.put("one")
            reader.deliver("Chat", photo)
            images = [call.args[0][1] for call in output.put.call_args_list]
            self.assertEqual(
                [value.image_kind for value in images], ["thumbnail", "original"]
            )
            self.assertTrue(reader._complete(photo))

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

    def test_download_starts_before_decode_and_success_does_not_cancel_it(self):
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
            stopped.wait.side_effect = [False, True]
            stopped.is_set.return_value = False
            reader = DatabaseReader(root / "images", output, stopped, feedback)
            reader._downloads = Mock()
            reader._downloads.take_completed.return_value = []

            def receive(event):
                if event[0] == "image":
                    reader._downloads.submit.assert_called_once()
                    feedback.put(event[1].message_id)

            output.put.side_effect = receive
            with patch("src.database_reader.DatabaseSource", return_value=source):
                reader.run(["chat"], True)
            self.assertEqual(photo.download.call_count, 2)
            reader._downloads.cancel.assert_not_called()

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
