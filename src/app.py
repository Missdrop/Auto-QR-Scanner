from datetime import datetime
from pathlib import Path
from time import sleep
from uuid import uuid4

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from .conversation_search import ConversationSearch
from .history import History
from .message import ImageMessage
from .outcome import Outcome
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
    latest_incoming = Signal(object)
    platform_completed = Signal(object)

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
        self._image_directory = student_directory.parent / "images"
        self._conversation_search = ConversationSearch(
            student_directory.parent / "wechat"
        )
        self._student = Student(
            student_directory, self.student_notice.emit, self.platform_completed.emit
        )
        self._worker = Worker(scanner, history, self.completed.emit, self.notice.emit)
        self._connect_actions()
        window.show_student_status(self._student.status())
        for outcome in history.outcomes():
            window.show_outcome(outcome)

        for result in reversed(history.recent()):
            window.add_result(result)

    def _connect_actions(self) -> None:
        self._window.conversation_query_requested.connect(
            self._conversation_search.request
        )
        self._conversation_search.ready.connect(
            self._window.show_conversation_candidates
        )
        self._conversation_search.failed.connect(self.notice.emit)
        self.completed.connect(self._show_result)
        self.notice.connect(self._show_notice)
        self.student_notice.connect(self._show_student_notice)
        self.incoming.connect(self._submit_incoming)
        self.latest_incoming.connect(self._submit_incoming)
        self.platform_completed.connect(self._show_outcome)
        self._window.start_requested.connect(self._start_monitoring)
        self._window.latest_requested.connect(self._scan_latest)
        self._window.stop_requested.connect(self._wechat.stop)
        self._window.retry_requested.connect(self._submit_incoming)
        self._window.login_requested.connect(self._open_login)
        self._window.image_folder_requested.connect(self._open_image_folder)
        self._window.student_open_requested.connect(self._open_student)
        self._window.link_open_requested.connect(self._open_link)
        self._window.closing.connect(self.close)

    def _open_image_folder(self) -> None:
        self._image_directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self._image_directory.resolve()))
        )

    def _start_monitoring(self, groups: list[str]) -> None:
        try:
            self._wechat.start(
                groups,
                self.incoming.emit,
                self.notice.emit,
                download_originals=self._window.download_originals(),
            )
            self._window.set_monitoring(True)
        except ValueError as exception:
            self.notice.emit(str(exception))

    def _show_notice(self, message: str) -> None:
        self._window.show_status(message)
        if message.startswith("Monitoring stopped"):
            self._window.set_monitoring(False)

    def _scan_latest(self, groups: list[str]) -> None:
        try:
            self._wechat.start(
                groups,
                self.latest_incoming.emit,
                self.notice.emit,
                latest_only=True,
                download_originals=self._window.download_originals(),
            )
            self._window.set_monitoring(True)
        except ValueError as exception:
            self.notice.emit(str(exception))

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
        if result.codes:
            self._wechat.decoded(result.message.message_id)
        self._window.add_result(result)
        self._window.show_status(f"{result.status()}: {result.message.image_path.name}")
        if automatic:
            for code in result.codes:
                if Student.is_web_url(code.text):
                    previous = self._history.outcome(code.text)
                    if previous is None or previous.status in {
                        "error",
                        "login",
                        "cancelled",
                    }:
                        self._open_student(code.text)

    def _show_outcome(self, outcome: Outcome) -> None:
        self._history.save_outcome(outcome)
        self._window.show_outcome(outcome)

    def _show_student_notice(self, message: str) -> None:
        # Structured outcomes already display the precise translated result.
        if not message.startswith("Platform "):
            self._window.show_student_status(message)

    def _open_login(self) -> None:
        try:
            self._student.open()
        except (ValueError, OSError) as exception:
            self.student_notice.emit(str(exception))

    def _open_link(self, url: str) -> None:
        try:
            self._student.open_link(url)
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
        self._conversation_search.close()
        self._wechat.stop()
        while self._wechat.is_running():
            # The backend destructor queries native windows on the worker thread.
            # Keep responding to those queries until it has finished.
            QApplication.processEvents()
            sleep(0.01)
        self._wechat.close()
        self._worker.close()
        self._student.close()
