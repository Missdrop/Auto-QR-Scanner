import unittest
from unittest.mock import patch

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from src.conversation_input import ConversationInput
from src.details import Details


class ConversationInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_selection_replaces_only_the_current_line(self):
        field = ConversationInput()
        field.setPlainText("First\nIC\nThird")
        cursor = field.textCursor()
        cursor.setPosition(8)
        field.setTextCursor(cursor)
        field._choose("ICS [unique@chatroom]")
        self.assertEqual(field.toPlainText(), "First\nICS [unique@chatroom]\nThird")
        field.close()

    def test_stale_results_do_not_replace_current_candidates(self):
        field = ConversationInput()
        field.setPlainText("latest")
        cursor = field.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        field.setTextCursor(cursor)
        with patch.object(field, "hasFocus", return_value=True):
            field.show_candidates("old", [{"username": "wrong"}])
        self.assertEqual(field._model.stringList(), [])
        field.close()

    def test_long_filename_cannot_expand_the_image_column(self):
        details = Details()
        details.resize(900, 280)
        details.show()
        self.application.processEvents()
        before = details._filename.parentWidget().width()
        details._filename.setText("very_long_filename" * 80 + ".jpg")
        self.application.processEvents()
        self.assertEqual(details._filename.parentWidget().width(), before)
        self.assertEqual(before, 300)
        details.close()
