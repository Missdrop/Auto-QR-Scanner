from PySide6.QtCore import QStringListModel, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QCompleter, QPlainTextEdit


class ConversationInput(QPlainTextEdit):
    """
    Complete the current conversation line using background database matches.
    """

    query_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._inserting = False
        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(
            QCompleter.CompletionMode.UnfilteredPopupCompletion
        )
        self._completer.activated.connect(self._choose)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._query)
        self.textChanged.connect(self._changed)

    def _changed(self) -> None:
        if not self._inserting:
            self._timer.start()

    def _query(self) -> None:
        text = self.textCursor().block().text().strip()
        if text and self.isEnabled():
            self.query_requested.emit(text)
        else:
            self._completer.popup().hide()

    def show_candidates(self, query: str, rows: list) -> None:
        if query != self.textCursor().block().text().strip() or not self.hasFocus():
            return
        labels = []
        for row in rows:
            name = row.get("remark") or row.get("nick_name") or row["username"]
            labels.append(f"{name} [{row['username']}]")
        self._model.setStringList(labels)
        if labels and self.isEnabled():
            self._completer.setCompletionPrefix(query)
            self._completer.complete(self.cursorRect())
        else:
            self._completer.popup().hide()

    def _choose(self, label: str) -> None:
        self._inserting = True
        self._timer.stop()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
        )
        cursor.insertText(label)
        self.setTextCursor(cursor)
        self._inserting = False
        self._completer.popup().hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._completer.popup().isVisible() and event.key() in {
            Qt.Key.Key_Enter,
            Qt.Key.Key_Return,
            Qt.Key.Key_Escape,
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
        }:
            event.ignore()
            return
        super().keyPressEvent(event)
