import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch

import cv2
import numpy as np
import zxingcpp
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

from src.app import App
from src.history import History
from src.image_processor import ImageProcessor
from src.message import ImageMessage
from src.outcome import Outcome
from src.result import Code, ScanResult
from src.scanner import Scanner
from src.student import Student
from src.wechat import WeChat
from src.window import Window


class AppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        start = Student.start
        bridge = patch.object(
            Student,
            "start",
            autospec=True,
            side_effect=lambda student: start(student, 0),
        )
        bridge.start()
        self.addCleanup(bridge.stop)

    def test_local_image_reaches_window_without_opening_browser(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
            window = Window(settings)
            history = History(root / "history.sqlite3")
            controller = App(
                WeChat(root / "images"),
                Scanner(ImageProcessor()),
                history,
                window,
                root / "profile",
            )
            try:
                self.assertIsNone(controller._student._server)
                barcode = zxingcpp.create_barcode(
                    "https://example.com", zxingcpp.BarcodeFormat.QRCode
                )
                path = root / "image.png"
                cv2.imencode(".png", np.asarray(barcode.to_image(scale=5)))[1].tofile(
                    path
                )
                with patch.object(controller._student, "open") as open_browser:
                    window.files_requested.emit([path])
                    deadline = time.monotonic() + 5
                    while not window._records and time.monotonic() < deadline:
                        self.application.processEvents()
                        time.sleep(0.01)
                    self.assertEqual(len(window._records), 1)
                    self.assertEqual(window._records[0][1], "https://example.com")
                    open_browser.assert_not_called()
                window._table.selectRow(0)
                self.assertIn("https://example.com", window._details.toPlainText())
                # Native backend cleanup can depend on the GUI handling a query.
                released = Event()
                monitor = Thread(target=lambda: released.wait(2), daemon=True)
                controller._wechat._thread = monitor
                monitor.start()
                QTimer.singleShot(0, released.set)
                controller.close()
                self.assertTrue(released.is_set())
                self.assertFalse(monitor.is_alive())
            finally:
                controller.close()
                window.close()

    def test_result_column_is_chinese_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            window = Window(
                QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
            )
            history = History(root / "history.sqlite3")
            controller = App(
                WeChat(root / "images"),
                Scanner(ImageProcessor()),
                history,
                window,
                root / "student",
            )
            try:
                url = "https://ams.xjtlu.edu.cn/studenth5/#/?state=example"
                result = ScanResult(
                    ImageMessage("one", "Chat", root / "image.png", datetime.now()),
                    [Code(url)],
                )
                history.save(result)
                controller._show_result(result, False)
                controller.platform_completed.emit(
                    Outcome(url, "result", 1001, "Expired")
                )
                self.assertEqual(window.windowTitle(), "Auto QR Scanner")
                self.assertEqual(
                    window._table.horizontalHeaderItem(5).text(), "扫码结果"
                )
                self.assertEqual(window._table.item(0, 5).text(), "二维码已过期")
                controller._show_student_notice(
                    "Platform rejected the QR code: Expired"
                )
                self.assertEqual(window._student_status.text(), "二维码已过期")
                self.assertEqual(
                    History(root / "history.sqlite3").outcome(url).code, 1001
                )
            finally:
                controller.close()
                window.close()
