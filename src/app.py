from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from .history import History
from .message import ImageMessage
from .result import ScanResult
from .scanner import Scanner
from .student import Student
from .wechat import WeChat
from .window import Window
from .worker import Worker


class App(QObject):
    """
    Connect desktop actions to monitoring, scanning and the student browser.
    """

    completed = Signal(object, bool)
    notice = Signal(str)
    student_notice = Signal(str)
    incoming = Signal(object)

    def __init__(
        self,
        wechat: WeChat,
        scanner: Scanner,
        history: History,
        window: Window,
        student_directory: Path,
    ) -> None:
        super().__init__()
        self._closed = False
        self._wechat = wechat
        self._history = history
        self._window = window
        self._student = Student(student_directory, self.student_notice.emit)
        self._worker = Worker(scanner, history, self.completed.emit, self.notice.emit)
        self._connect_actions()
        window.show_student_status(self._student.status())

        for result in reversed(history.recent()):
            window.add_result(result)

    def _connect_actions(self) -> None:
        self.completed.connect(self._show_result)
        self.notice.connect(self._show_notice)
        self.student_notice.connect(self._window.show_student_status)
        self.incoming.connect(self._submit_incoming)
        self._window.start_requested.connect(self._start_monitoring)
        self._window.stop_requested.connect(self._wechat.stop)
        self._window.files_requested.connect(self._scan_files)
        self._window.retry_requested.connect(self._worker.submit)
        self._window.login_requested.connect(self._open_login)
        self._window.pairing_requested.connect(self._copy_pairing_code)
        self._window.student_open_requested.connect(self._open_student)
        self._window.closing.connect(self.close)

    def _start_monitoring(self, groups: list[str]) -> None:
        try:
            self._wechat.start(groups, self.incoming.emit, self.notice.emit)
            self._window.set_monitoring(True)
        except ValueError as exception:
            self.notice.emit(str(exception))

    def _show_notice(self, message: str) -> None:
        self._window.show_status(message)
        if message.startswith("Monitoring stopped"):
            self._window.set_monitoring(False)

    def _scan_files(self, paths: list[Path]) -> None:
        for path in paths:
            message = ImageMessage(
                uuid4().hex,
                "Local image",
                path.resolve(),
                datetime.now().astimezone(),
            )
            if not self._worker.submit(message):
                break

    def _submit_incoming(self, message: ImageMessage) -> None:
        self._worker.submit(message, self._window.automatic_open())

    def _show_result(self, result: ScanResult, automatic: bool) -> None:
        self._window.add_result(result)
        self._window.show_status(f"{result.status()}: {result.message.image_path.name}")
        if automatic:
            for code in result.codes:
                if not code.duplicate and Student.is_student_url(code.text):
                    self._open_student(code.text)

    def _copy_pairing_code(self) -> None:
        try:
            QApplication.clipboard().setText(self._student.pairing_code())
            self.student_notice.emit(
                "Pairing code copied; paste it into the companion popup"
            )
        except OSError:
            self.student_notice.emit(
                "Cannot start the local bridge; close other app instances"
            )

    def _open_login(self) -> None:
        try:
            self._student.open()
        except (ValueError, OSError) as exception:
            self.student_notice.emit(str(exception))

    def _open_student(self, url: str) -> None:
        try:
            self._student.open(url)
        except (ValueError, OSError) as exception:
            self.student_notice.emit(str(exception))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._wechat.close()
        self._worker.close()
        self._student.close()
