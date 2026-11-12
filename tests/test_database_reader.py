import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.database_reader import DatabaseReader


class DatabaseReaderTest(unittest.TestCase):
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
