from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


def apply_theme(application: QApplication) -> None:
    """Apply one consistent palette to windows, dialogs and completion popups."""
    application.setStyle("Fusion")
    application.setFont(QFont("Microsoft YaHei UI", 10))
    check_icon = (Path(__file__).resolve().parents[2] / "assets/check.svg").as_posix()
    application.setStyleSheet(
        """
        QWidget { background: #111827; color: #e5eaf3; }
        QLabel { background: transparent; }
        QLabel#heading { font-size: 23px; font-weight: 600; color: #f8fafc; }
        QLabel#muted { color: #94a3b8; font-size: 12px; }
        QLabel#section { color: #cbd5e1; font-weight: 600; }
        QLabel#status { color: #93c5fd; padding: 7px 10px;
            background: #192338; border-radius: 6px; }
        QPlainTextEdit, QLineEdit { background: #1b2537; color: #e5eaf3;
            border: 1px solid #334155; border-radius: 7px; padding: 7px;
            selection-background-color: #2563eb; }
        QPlainTextEdit:focus, QLineEdit:focus { border: 1px solid #60a5fa; }
        QPushButton { background: #243249; border: 1px solid #3b4b63;
            border-radius: 7px; padding: 8px 12px; min-height: 19px; }
        QPushButton:hover { background: #30425e; border-color: #64748b; }
        QPushButton:pressed { background: #17253b; }
        QPushButton#primary { background: #2563eb; border-color: #3b82f6;
            color: white; font-weight: 600; }
        QPushButton#primary:hover { background: #3b82f6; }
        QPushButton:disabled { background: #192235; color: #64748b;
            border-color: #29364c; }
        QCheckBox { spacing: 8px; background: transparent; }
        QCheckBox::indicator { width: 18px; height: 18px;
            border: 2px solid #71839d; border-radius: 4px; background: #1b2537; }
        QCheckBox::indicator:hover { border-color: #93c5fd; }
        QCheckBox::indicator:checked { background: #2563eb; border-color: #60a5fa;
            image: url("__CHECK_ICON__"); }
        QCheckBox::indicator:disabled { background: #192235; border-color: #3b4b63; }
        QCheckBox::indicator:checked:disabled { background: #334b70; }
        QTableWidget, QListView { background: #172134;
            alternate-background-color: #1b273b; border: 1px solid #334155;
            border-radius: 7px; selection-background-color: #284c7c; }
        QTableWidget::item { padding: 7px; border-bottom: 1px solid #26334a; }
        QTableWidget::item:selected, QListView::item:selected {
            background: #284c7c; color: #f8fafc; }
        QHeaderView::section { background: #223047; color: #bdcbe0;
            border: none; padding: 9px; font-weight: 600; }
        QSplitter::handle { background: #334155; height: 2px; }
        QScrollBar:vertical { background: #172134; width: 10px; }
        QScrollBar::handle:vertical { background: #475569;
            min-height: 25px; border-radius: 4px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QToolTip { background: #243249; color: #f1f5f9;
            border: 1px solid #475569; padding: 6px; }
    """.replace("__CHECK_ICON__", check_icon)
    )
