import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from src.passive_chat import PassiveChat, Photo


class PassiveChatTest(unittest.TestCase):
    def row(self, outgoing=False):
        image = np.full((250, 720, 3), 30, np.uint8)
        left = 440 if outgoing else 90
        image[15:235, left : left + 160] = (180, 110, 50)
        avatar = 655 if outgoing else 15
        image[15:65, avatar : avatar + 50] = 210
        return image

    def test_photo_location_excludes_avatar(self):
        self.assertEqual(Photo.locate(self.row()), (90, 15, 160, 220))

    def test_empty_row_is_rejected(self):
        with self.assertRaises(ValueError):
            Photo.locate(np.full((250, 720, 3), 30, np.uint8))

    def test_direction_detection_never_clicks_the_avatar(self):
        with tempfile.TemporaryDirectory() as directory:
            for outgoing in (False, True):
                control = Mock()
                control.Name = "图片"
                image = self.row(outgoing)

                def capture(path, image=image):
                    cv2.imencode(".png", image)[1].tofile(path)
                    return True

                control.CaptureToImage.side_effect = capture
                photo = Photo(control, Mock(), Path(directory))
                self.assertEqual(photo.attr, "self" if outgoing else "friend")
                control.Click.assert_not_called()
                control.RightClick.assert_not_called()
                control.DoubleClick.assert_not_called()

    def test_snapshot_only_reads_message_identifiers(self):
        reader = object.__new__(PassiveChat)
        reader._client = Mock()
        reader._directory = Path("unused")
        reader._notify = None
        reader._messages = Mock()
        row = Mock()
        row.Name = "图片"
        row.GetRuntimeId.return_value = (1, 2, 3)
        reader._messages.GetChildren.return_value = [row]
        photo = reader.messages()[0]
        self.assertEqual(photo.id, "(1, 2, 3)")
        row.CaptureToImage.assert_not_called()
        row.Click.assert_not_called()
        reader._client.GetAllMessage.assert_not_called()

    def test_viewer_is_closed_after_save_failure(self):
        control = Mock()
        control.Name = "图片"
        photo = Photo(control, Mock(), Path("unused"))
        photo._bounds = (90, 15, 160, 220)
        photo._path = Path("unused/photo.png")
        viewer = Mock()
        viewer.save.side_effect = OSError("Save failed")
        with patch("wxauto4.ui.component.WeChatImage", return_value=viewer):
            self.assertEqual(photo.download(), photo._path)
        control.DoubleClick.assert_called_once_with(x=170, y=125)
        control.RightClick.assert_not_called()
        viewer.close.assert_called_once()
