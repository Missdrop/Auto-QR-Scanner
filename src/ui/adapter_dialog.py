from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class AdapterDialog(QDialog):
    """Display metadata supplied by local adapters without rendering HTML."""

    def __init__(self, parent: QWidget, rows: list[dict[str, str]]) -> None:
        super().__init__(parent)
        self.setWindowTitle("网站适配器")
        self.resize(850, 330)
        self._rows = rows
        layout = QVBoxLayout(self)
        loaded = sum(row["status"] == "loaded" for row in rows)
        layout.addWidget(QLabel(f"已加载 {loaded} 个适配器；修改文件后需重启程序。"))
        if not rows:
            layout.addWidget(QLabel("未发现适配器，网页二维码将作为普通链接打开。"))
        self.table = QTableWidget(len(rows), 4)
        self.table.setHorizontalHeaderLabels(["名称", "版本", "说明", "状态"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for index, row in enumerate(rows):
            status = (
                "已加载" if row["status"] == "loaded" else "加载失败：" + row["error"]
            )
            for column, value in enumerate(
                [
                    row["name"],
                    row["version"] or "未提供",
                    row["description"] or "未提供",
                    status,
                ]
            ):
                self.table.setItem(index, column, QTableWidgetItem(value))
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        for column in (0, 1, 3):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        self._details = QPlainTextEdit()
        self._details.setReadOnly(True)
        self._details.setMaximumHeight(110)
        layout.addWidget(self._details)
        self.table.currentCellChanged.connect(lambda row, *_: self._show_details(row))
        if rows:
            self.table.selectRow(0)
            self._show_details(0)

    def _show_details(self, index: int) -> None:
        if 0 <= index < len(self._rows):
            row = self._rows[index]
            self._details.setPlainText(
                f"名称：{row['name']}\n版本：{row['version'] or '未提供'}\n"
                f"说明：{row['description'] or '未提供'}\n文件：{row['path']}"
            )
