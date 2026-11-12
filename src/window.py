from collections.abc import Callable

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .details import Details
from .language import chinese
from .outcome import Outcome
from .result import ScanResult


class Window(QMainWindow):
    """
    Display group controls, scan history and the selected decoded value.

    Long-running work is delegated through signals and never runs in widgets.
    """

    start_requested = Signal(list)
    latest_requested = Signal(list)
    stop_requested = Signal()
    retry_requested = Signal(object)
    login_requested = Signal()
    image_folder_requested = Signal()
    student_open_requested = Signal(str)
    closing = Signal()

    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self._records: list[tuple[ScanResult, str]] = []
        self._outcomes: dict[str, Outcome] = {}
        self._settings = (
            settings if settings is not None else QSettings("AutoQRScanner", "Desktop")
        )
        self.setWindowTitle("Auto QR Scanner")
        self.resize(1180, 760)

        self._groups = QPlainTextEdit()
        self._groups.setPlaceholderText("填写精确群名或联系人名称，每行一个")
        self._groups.setPlainText(str(self._settings.value("groups", "")))
        self._groups.setMaximumHeight(100)
        self._automatic = QCheckBox("识别后自动扫码")
        self._automatic.setChecked(True)
        self._originals = QCheckBox(
            "使用原图（分辨率高，但会短暂打开微信图片窗口，取消勾选则只扫描缩略图）"
        )
        self._originals.setChecked(True)
        self._status = QLabel("就绪")
        self._student_status = QLabel("")
        self._student_status.setWordWrap(True)
        self._table = self._create_table()
        self._details = Details()
        self.setCentralWidget(self._create_layout())

    def _create_table(self) -> QTableWidget:
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(
            [
                "收到时间",
                "会话",
                "识别状态",
                "二维码内容",
                "识别耗时（毫秒）",
                "扫码结果",
            ]
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for column in (2, 4, 5):
            table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        table.itemSelectionChanged.connect(self._show_selection)
        table.setWordWrap(False)
        return table

    def _create_layout(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("微信会话"))
        layout.addWidget(self._groups)

        controls = QHBoxLayout()
        self._start = self._button("开始监听", self._request_start, controls)
        self._latest = self._button(
            "扫描最近图片",
            lambda: self.latest_requested.emit(self._groups.toPlainText().splitlines()),
            controls,
        )
        self._stop = self._button("停止", self.stop_requested.emit, controls)
        self._stop.setEnabled(False)
        self._button("打开内置浏览器", self.login_requested.emit, controls)
        self._button("打开图片文件夹", self.image_folder_requested.emit, controls)
        layout.addLayout(controls)
        layout.addWidget(self._automatic)
        layout.addWidget(self._originals)
        layout.addWidget(self._student_status)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._table)
        splitter.addWidget(self._details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        actions = QHBoxLayout()
        self._button("复制内容", self._copy_content, actions)
        self._button("打开链接", self._open_link, actions)
        self._button("在内置浏览器扫码", self._open_student, actions)
        self._button("重新识别并处理", self._retry, actions)
        layout.addLayout(actions)
        layout.addWidget(self._status)
        return widget

    @staticmethod
    def _button(
        text: str,
        callback: Callable[[], object],
        layout: QHBoxLayout,
    ) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _request_start(self) -> None:
        groups = self._groups.toPlainText()
        self._settings.setValue("groups", groups)
        self.start_requested.emit(groups.splitlines())

    def automatic_open(self) -> bool:
        return self._automatic.isChecked()

    def download_originals(self) -> bool:
        return self._originals.isChecked()

    def set_monitoring(self, running: bool) -> None:
        self._start.setEnabled(not running)
        self._latest.setEnabled(not running)
        self._stop.setEnabled(running)
        self._groups.setEnabled(not running)

    def show_status(self, message: str) -> None:
        self._status.setText(chinese(message))

    def show_student_status(self, message: str) -> None:
        self._student_status.setText(chinese(message))

    def add_result(self, result: ScanResult) -> None:
        values = [code.text for code in result.codes] or [""]
        for text in values:
            self._records.insert(0, (result, text))
            self._table.insertRow(0)
            columns = [
                result.message.received_at.strftime("%m-%d %H:%M:%S"),
                result.message.chat_name,
                (
                    "未识别（低分辨率）"
                    if not result.codes and result.warning
                    else chinese(result.status())
                ),
                text,
                f"{result.elapsed_ms:.0f}",
                self._outcomes[text].label() if text in self._outcomes else "未提交",
            ]
            for column, value in enumerate(columns):
                self._table.setItem(0, column, QTableWidgetItem(value))
        # History stays durable in SQLite; cap the visible table for responsiveness.
        while len(self._records) > 2000:
            self._records.pop()
            self._table.removeRow(self._table.rowCount() - 1)

    def show_outcome(self, outcome: Outcome) -> None:
        self._outcomes[outcome.url] = outcome
        self._student_status.setText(outcome.label())
        for row, (_, text) in enumerate(self._records):
            if text == outcome.url:
                self._table.setItem(row, 5, QTableWidgetItem(outcome.label()))
        self._show_selection()

    def _selection(self) -> tuple[ScanResult, str] | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._records):
            return None
        return self._records[row]

    def _show_selection(self) -> None:
        selected = self._selection()
        if selected is None:
            return
        result, text = selected
        self._details.show_result(result, text, self._outcomes.get(text))

    def _copy_content(self) -> None:
        selected = self._selection()
        if selected is not None:
            QApplication.clipboard().setText(selected[1])

    def _open_link(self) -> None:
        selected = self._selection()
        if selected is None:
            return
        self.student_open_requested.emit(selected[1])

    def _open_student(self) -> None:
        selected = self._selection()
        if selected is not None and selected[1]:
            self.student_open_requested.emit(selected[1])

    def _retry(self) -> None:
        selected = self._selection()
        if selected is not None:
            self.retry_requested.emit(selected[0].message)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._settings.setValue("groups", self._groups.toPlainText())
        self.closing.emit()
        event.accept()
