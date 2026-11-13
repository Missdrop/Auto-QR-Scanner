from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QCloseEvent, QIcon
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

from browser.address_filter import AddressFilter
from models.outcome import Outcome
from models.result import ScanResult
from ui.adapter_dialog import AdapterDialog
from ui.conversation_input import ConversationInput
from ui.details import Details
from ui.language import chinese


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
    adapters_requested = Signal()
    image_folder_requested = Signal()
    session_open_requested = Signal(str)
    link_open_requested = Signal(str)
    conversation_query_requested = Signal(str)
    closing = Signal()

    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self._records: list[tuple[ScanResult, str]] = []
        self._outcomes: dict[str, Outcome] = {}
        self._settings = (
            settings if settings is not None else QSettings("AutoQRScanner", "Desktop")
        )
        self.setWindowTitle("Auto QR Scanner")
        self.setWindowIcon(
            QIcon(str(Path(__file__).resolve().parents[2] / "assets/logo.ico"))
        )
        self.resize(1240, 920)

        self._groups = ConversationInput()
        self._groups.query_requested.connect(self.conversation_query_requested.emit)
        self._groups.setPlaceholderText(
            "输入群名或联系人选择候选，每行一个；也可直接填写精确名称"
        )
        self._groups.setPlainText(str(self._settings.value("groups", "")))
        self._groups.setMaximumHeight(100)
        self._addresses = QPlainTextEdit()
        self._addresses.setPlaceholderText(
            "每行一个域名或完整网址前缀，例如 example.com 或 https://example.com/qr/；留白允许所有网址"
        )
        self._addresses.setPlainText(str(self._settings.value("address_filter", "")))
        self._addresses.setMaximumHeight(65)
        self._automatic = QCheckBox("识别后自动扫码")
        self._automatic.setChecked(True)
        self._image_modes: dict[str, QCheckBox] = {}
        descriptions = {
            "thumbnail": (
                "缩略图：速度快、清晰度低。实测各场景均可获取，"
                "不受是否选中会话、免打扰或前后台影响。\n"
                "具体情况请自行测试；最保险的是将微信置于前台并打开监听会话。"
            ),
            "compressed": (
                "压缩图：更清晰。实测需在微信中选中监听会话，"
                "免打扰和前后台状态未影响结果；仅读取已有缓存。\n"
                "具体情况请自行测试；最保险的是将微信置于前台并打开监听会话。"
            ),
        }
        # Apply the revised defaults once, then preserve subsequent user choices.
        if not self._settings.value("image_defaults_updated", False, type=bool):
            self._settings.setValue("image_modes", ["thumbnail", "compressed"])
            self._settings.setValue("image_defaults_updated", True)
        saved = self._settings.value("image_modes", None)
        if isinstance(saved, list):
            selected = [str(mode) for mode in saved]
        elif isinstance(saved, str):
            selected = [saved]
        else:
            legacy_mode = self._settings.value("image_mode", None)
            selected = (
                [str(legacy_mode)]
                if legacy_mode is not None
                else ["thumbnail", "compressed"]
            )
        selected = [mode for mode in selected if mode in descriptions]
        if not selected:
            selected = ["thumbnail", "compressed"]
        for mode, description in descriptions.items():
            button = QCheckBox(description)
            self._image_modes[mode] = button
            button.setChecked(mode in selected)
        self._status = QLabel("就绪")
        self._session_status = QLabel("")
        self._session_status.setWordWrap(True)
        self._table = self._create_table()
        self._details = Details()
        self.setCentralWidget(self._create_layout())

    def _create_table(self) -> QTableWidget:
        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(
            [
                "收到时间",
                "会话",
                "识别状态",
                "二维码内容",
                "识别耗时（毫秒）",
                "扫码结果",
                "图片类型",
            ]
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for column in (2, 4, 5, 6):
            table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        table.itemSelectionChanged.connect(self._show_selection)
        table.setWordWrap(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)
        table.setColumnWidth(1, 175)
        table.setColumnWidth(0, 150)
        return table

    def _create_layout(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        heading = QLabel("Auto QR Scanner")
        heading.setObjectName("heading")
        layout.addWidget(heading)
        subtitle = QLabel("后台读取图片，识别二维码并使用内置浏览器处理链接。")
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)
        inputs = QHBoxLayout()
        inputs.setSpacing(16)
        for title, field in [
            ("微信会话", self._groups),
            ("地址过滤", self._addresses),
        ]:
            column = QVBoxLayout()
            label = QLabel(title)
            label.setObjectName("section")
            column.addWidget(label)
            field.setFixedHeight(82)
            column.addWidget(field)
            inputs.addLayout(column, 1)
        layout.addLayout(inputs)

        controls = QHBoxLayout()
        self._start = self._button("开始监听", self._request_start, controls)
        self._start.setObjectName("primary")
        self._latest = self._button(
            "扫描最近图片",
            lambda: self.latest_requested.emit(self._groups.toPlainText().splitlines()),
            controls,
        )
        self._stop = self._button("停止", self.stop_requested.emit, controls)
        self._stop.setEnabled(False)
        self._button("打开内置浏览器", self.login_requested.emit, controls)
        self._button("查看适配器", self.adapters_requested.emit, controls)
        self._button("打开图片文件夹", self.image_folder_requested.emit, controls)
        layout.addLayout(controls)
        options = QHBoxLayout()
        options.addWidget(self._automatic)
        options.addStretch()
        for mode, button in self._image_modes.items():
            button.setToolTip(button.text())
            button.setText("使用缩略图" if mode == "thumbnail" else "使用压缩图")
            options.addWidget(button)
        hint = QLabel("实测压缩图需选中会话（详情见悬停提示）")
        hint.setObjectName("muted")
        options.addWidget(hint)
        layout.addLayout(options)
        cache_hint = QLabel("请自行测试；最保险的是将微信置于前台，并打开监听会话。")
        cache_hint.setObjectName("muted")
        cache_hint.setWordWrap(True)
        layout.addWidget(cache_hint)
        layout.addWidget(self._session_status)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._table)
        splitter.addWidget(self._details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self._button("复制内容", self._copy_content, actions)
        self._button("打开链接", self._open_link, actions)
        self._button("重新扫码", self._open_session, actions)
        self._button("重新识别并处理", self._retry, actions)
        layout.addLayout(actions)
        layout.addWidget(self._status)
        self._status.setObjectName("status")
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

    def show_adapters(self, rows: list[dict[str, str]]) -> None:
        if hasattr(self, "_adapter_dialog"):
            self._adapter_dialog.show()
            self._adapter_dialog.raise_()
            return
        self._adapter_dialog = AdapterDialog(self, rows)
        self._adapter_dialog.show()

    def address_filter(self) -> AddressFilter:
        return AddressFilter(self._addresses.toPlainText())

    def show_conversation_candidates(self, query: str, rows: list) -> None:
        self._groups.show_candidates(query, rows)

    def image_modes(self) -> list[str]:
        return [
            mode for mode, button in self._image_modes.items() if button.isChecked()
        ]

    def set_monitoring(self, running: bool) -> None:
        self._start.setEnabled(not running)
        self._latest.setEnabled(not running)
        self._stop.setEnabled(running)
        self._groups.setEnabled(not running)
        for button in self._image_modes.values():
            button.setEnabled(not running)

    def show_status(self, message: str) -> None:
        self._status.setText(chinese(message))

    def show_session_status(self, message: str) -> None:
        self._session_status.setText(chinese(message))

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
                self._outcomes[text].label() if text in self._outcomes else "未打开",
                {"thumbnail": "缩略图", "original": "原图", "compressed": "压缩图"}.get(
                    result.message.image_kind, "未知"
                ),
            ]
            for column, value in enumerate(columns):
                self._table.setItem(0, column, QTableWidgetItem(value))
        # History stays durable in SQLite; cap the visible table for responsiveness.
        while len(self._records) > 2000:
            self._records.pop()
            self._table.removeRow(self._table.rowCount() - 1)

    def show_outcome(self, outcome: Outcome) -> None:
        self._outcomes[outcome.url] = outcome
        self._session_status.setText(outcome.label())
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
        self.link_open_requested.emit(selected[1])

    def _open_session(self) -> None:
        selected = self._selection()
        if selected is not None and selected[1]:
            self.session_open_requested.emit(selected[1])

    def _retry(self) -> None:
        selected = self._selection()
        if selected is not None:
            self.retry_requested.emit(selected[0].message)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._settings.setValue("address_filter", self._addresses.toPlainText())
        self._settings.setValue("image_modes", self.image_modes())
        self._settings.setValue("groups", self._groups.toPlainText())
        self.closing.emit()
        event.accept()
