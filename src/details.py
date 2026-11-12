from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .language import chinese
from .outcome import Outcome
from .result import ScanResult


class ImagePreview(QLabel):
    """
    Fit a selected image to the available area without changing its proportions.
    """

    def __init__(self) -> None:
        super().__init__("请选择一条记录")
        self._image = QPixmap()
        self._path: Path | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(180, 140)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

    def show_image(self, path: Path) -> None:
        if path == self._path:
            return
        self._path = path
        self._image = QPixmap(str(path))
        self.setToolTip(str(path))
        self._fit()

    def _fit(self) -> None:
        if self._image.isNull():
            self.clear()
            self.setText("图片不存在或无法预览")
            return
        self.setPixmap(
            self._image.scaled(
                self.contentsRect().size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._path is not None:
            self._fit()


class Details(QWidget):
    """
    Present separate scan fields and the corresponding image side by side.
    """

    def __init__(self) -> None:
        super().__init__()
        fields = QWidget()
        form = QFormLayout(fields)
        self._status = self._field(form, "识别状态")
        self.content = QPlainTextEdit()
        self.content.setReadOnly(True)
        self.content.setMaximumHeight(65)
        form.addRow("二维码内容", self.content)
        self._outcome = self._field(form, "扫码结果")
        self._code = self._field(form, "返回码")
        self._message = QPlainTextEdit()
        self._message.setReadOnly(True)
        self._message.setMaximumHeight(65)
        form.addRow("原始提示", self._message)
        self._warning = QLabel()
        self._warning.setWordWrap(True)
        form.addRow("识别提示", self._warning)

        image = QWidget()
        image_layout = QVBoxLayout(image)
        image_layout.addWidget(QLabel("图片"))
        self._preview = ImagePreview()
        image_layout.addWidget(self._preview, 1)
        self._filename = QLabel()
        self._filename.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._filename.setWordWrap(True)
        image_layout.addWidget(self._filename)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(fields)
        splitter.addWidget(image)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    @staticmethod
    def _field(form: QFormLayout, title: str) -> QLineEdit:
        field = QLineEdit()
        field.setReadOnly(True)
        form.addRow(title, field)
        return field

    def show_result(
        self, result: ScanResult, text: str, outcome: Outcome | None
    ) -> None:
        self._status.setText(chinese(result.status()))
        self.content.setPlainText(text)
        self._outcome.setText(outcome.label() if outcome else "未提交")
        self._code.setText(
            str(outcome.code) if outcome and outcome.code is not None else "—"
        )
        self._message.setPlainText(outcome.message if outcome else "")
        self._warning.setText(
            "\n".join(
                chinese(value) for value in (result.error, result.warning) if value
            )
        )
        self._filename.setText(result.message.image_path.name)
        self._filename.setToolTip(str(result.message.image_path))
        self._preview.show_image(result.message.image_path)
