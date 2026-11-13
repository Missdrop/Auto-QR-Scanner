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
from src.wechat import WeChat
from src.window import Window


class AppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

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
                barcode = zxingcpp.create_barcode(
                    "https://example.com", zxingcpp.BarcodeFormat.QRCode
                )
                path = root / "image.png"
                cv2.imencode(".png", np.asarray(barcode.to_image(scale=5)))[1].tofile(
                    path
                )
                with patch.object(controller._session, "open") as open_browser:
                    controller._scan_files([path])
                    deadline = time.monotonic() + 5
                    while not window._records and time.monotonic() < deadline:
                        self.application.processEvents()
                        time.sleep(0.01)
                    self.assertEqual(len(window._records), 1)
                    self.assertEqual(window._records[0][1], "https://example.com")
                    open_browser.assert_not_called()
                window._table.selectRow(0)
                self.assertIn(
                    "https://example.com", window._details.content.toPlainText()
                )
                self.assertFalse(window._details._preview.pixmap().isNull())
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
                root / "session",
            )
            try:
                url = "https://example.com/qr/#/?state=example"
                result = ScanResult(
                    ImageMessage("one", "Chat", root / "image.png", datetime.now()),
                    [Code(url)],
                )
                history.save(result)
                controller._show_result(result, False)
                controller.platform_completed.emit(
                    Outcome(url, "result", 1001, "Expired")
                )
                window._table.selectRow(0)
                self.assertEqual(window._details._code.text(), "1001")
                self.assertEqual(window._details._outcome.text(), "二维码已过期")
                self.assertEqual(window.windowTitle(), "Auto QR Scanner")
                self.assertEqual(
                    window._table.horizontalHeaderItem(5).text(), "扫码结果"
                )
                self.assertEqual(window._table.item(0, 5).text(), "二维码已过期")
                controller._show_session_notice(
                    "Platform rejected the QR code: Expired"
                )
                self.assertEqual(window._session_status.text(), "二维码已过期")
                self.assertEqual(
                    History(root / "history.sqlite3").outcome(url).code, 1001
                )
            finally:
                controller.close()
                window.close()

    def test_another_image_version_does_not_replay_a_failed_request(self):
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
                root / "profile",
            )
            url = "https://example.com/qr"
            result = ScanResult(
                ImageMessage("one", "Chat", root / "image.jpg", datetime.now()),
                [Code(url)],
            )
            try:
                for status in ["error", "login", "cancelled", "queued", "result"]:
                    history.save_outcome(Outcome(url, status))
                    with patch.object(controller._session, "open") as open_browser:
                        controller._show_result(result, True)
                        open_browser.assert_not_called()
                with patch.object(controller._session, "open") as open_browser:
                    controller._open_session(url)
                    open_browser.assert_called_once_with(url)
            finally:
                controller.close()
                window.close()

    def test_image_modes_can_be_combined_and_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(
                str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat
            )
            settings.setValue("image_mode", "original")
            settings.setValue("image_modes", ["original"])
            settings.setValue("image_defaults_updated", True)
            window = Window(settings)
            self.assertTrue(window.automatic_open())
            self.assertEqual(window.image_modes(), ["thumbnail", "compressed"])
            self.assertNotIn("original", window._image_modes)
            window._image_modes["thumbnail"].setChecked(False)
            self.assertEqual(window.image_modes(), ["compressed"])
            window.close()
            restored = Window(settings)
            self.assertEqual(restored.image_modes(), ["compressed"])
            restored.close()

    def test_empty_saved_sources_restore_usable_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(
                str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat
            )
            settings.setValue("image_defaults_updated", True)
            settings.setValue("image_modes", [])
            window = Window(settings)
            try:
                self.assertEqual(window.image_modes(), ["thumbnail", "compressed"])
                self.assertEqual(set(window._image_modes), {"thumbnail", "compressed"})
            finally:
                window.close()

    def test_address_filter_blocks_automatic_requests_and_persists(self):
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
            allowed = "https://example.com/qr/one"
            blocked = "https://other.example/qr"
            result = ScanResult(
                ImageMessage("one", "Chat", root / "image.jpg", datetime.now()),
                [Code(allowed), Code(blocked)],
            )
            try:
                window._addresses.setPlainText("https://example.com/qr/")
                with patch.object(controller._session, "open") as open_browser:
                    controller._show_result(result, True)
                    open_browser.assert_called_once_with(allowed)
                self.assertEqual(history.outcome(blocked).status, "filtered")
                self.assertEqual(history.outcome(blocked).label(), "已被地址过滤")
                window._addresses.clear()
                with patch.object(controller._session, "open") as open_browser:
                    controller._show_result(result, True)
                    self.assertEqual(open_browser.call_count, 2)
                history.save_outcome(Outcome(blocked, "result", 0))
                window._addresses.setPlainText("example.com")
                with patch.object(controller._session, "open"):
                    controller._show_result(result, True)
                self.assertEqual(history.outcome(blocked).code, 0)
                window._addresses.setPlainText("https://")
                with patch.object(controller._wechat, "start") as start:
                    controller._start_monitoring(["Chat"])
                    start.assert_not_called()
                window._addresses.setPlainText("example.com\nsecond.example")
            finally:
                controller.close()
                window.close()
            restored = Window(settings)
            self.assertTrue(restored.address_filter().allows("https://second.example/"))
            self.assertFalse(restored.address_filter().allows("https://other.example/"))
            restored.close()
