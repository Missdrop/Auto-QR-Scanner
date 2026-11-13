from datetime import datetime
from pathlib import Path
from time import sleep
from uuid import uuid4

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from application.worker import Worker
from browser.session import BrowserSession
from models.message import ImageMessage
from models.outcome import Outcome
from models.result import ScanResult
from scanning.scanner import Scanner
from storage.history import History
from ui.window import Window
from wechat.client import WeChat
from wechat.conversation_search import ConversationSearch


class App(QObject):
    """
    Connect desktop actions to monitoring, scanning and the session browser.
    """

    completed = Signal(object, bool)
    notice = Signal(str)
    session_notice = Signal(str)
    incoming = Signal(object)
    latest_incoming = Signal(object)
    platform_completed = Signal(object)

    def __init__(
        self,
        wechat: WeChat,
        scanner: Scanner,
        history: History,
        window: Window,
        session_directory: Path,
    ) -> None:
        super().__init__()
        self._closed = False
        self._wechat = wechat
        self._history = history
        self._window = window
        self._image_directory = session_directory.parent / "images"
        self._conversation_search = ConversationSearch(
            session_directory.parent / "wechat"
        )
        self._session = BrowserSession(
            session_directory, self.session_notice.emit, self.platform_completed.emit
        )
        self._worker = Worker(scanner, history, self.completed.emit, self.notice.emit)
        self._connect_actions()
        window.show_session_status(self._session.status())
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
        self.session_notice.connect(self._show_session_notice)
        self.incoming.connect(self._submit_incoming)
        self.latest_incoming.connect(self._submit_incoming)
        self.platform_completed.connect(self._show_outcome)
        self._window.start_requested.connect(self._start_monitoring)
        self._window.latest_requested.connect(self._scan_latest)
        self._window.stop_requested.connect(self._wechat.stop)
        self._window.retry_requested.connect(self._submit_incoming)
        self._window.login_requested.connect(self._open_login)
        self._window.adapters_requested.connect(self._show_adapters)
        self._window.image_folder_requested.connect(self._open_image_folder)
        self._window.session_open_requested.connect(self._open_session)
        self._window.link_open_requested.connect(self._open_link)
        self._window.closing.connect(self.close)

    def _open_image_folder(self) -> None:
        self._image_directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self._image_directory.resolve()))
        )

    def _show_adapters(self) -> None:
        self._window.show_adapters(self._session.adapter_information())

    def _start_monitoring(self, groups: list[str]) -> None:
        try:
            if self._window.automatic_open():
                self._window.address_filter()
            self._wechat.start(
                groups,
                self.incoming.emit,
                self.notice.emit,
                image_modes=self._window.image_modes(),
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
            if self._window.automatic_open():
                self._window.address_filter()
            self._wechat.start(
                groups,
                self.latest_incoming.emit,
                self.notice.emit,
                latest_only=True,
                image_modes=self._window.image_modes(),
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
        if self._closed:
            return
        self._worker.submit(message, self._window.automatic_open())

    def _show_result(self, result: ScanResult, automatic: bool) -> None:
        if self._closed:
            return
        self._window.add_result(result)
        self._window.show_status(f"{result.status()}: {result.message.image_path.name}")
        if automatic:
            try:
                addresses = self._window.address_filter()
            except ValueError as exception:
                self.notice.emit(str(exception))
                return
            for code in result.codes:
                if BrowserSession.is_web_url(code.text):
                    previous = self._history.outcome(code.text)
                    if not addresses.allows(code.text):
                        if previous is None or previous.status == "filtered":
                            self._show_outcome(Outcome(code.text, "filtered"))
                        continue
                    # Another image version must not replay an uncertain request.
                    # Existing attempts can be retried explicitly from the record.
                    if previous is None or previous.status == "filtered":
                        self._open_session(code.text)

    def _show_outcome(self, outcome: Outcome) -> None:
        self._history.save_outcome(outcome)
        self._window.show_outcome(outcome)

    def _show_session_notice(self, message: str) -> None:
        # Structured outcomes already display the precise translated result.
        if not message.startswith("Platform "):
            self._window.show_session_status(message)

    def _open_login(self) -> None:
        try:
            self._session.open()
        except (ValueError, OSError) as exception:
            self.session_notice.emit(str(exception))

    def _open_link(self, url: str) -> None:
        try:
            self._session.open_link(url)
        except (ValueError, OSError) as exception:
            self.session_notice.emit(str(exception))

    def _open_session(self, url: str) -> None:
        try:
            self._session.open(url)
        except (ValueError, OSError) as exception:
            self.session_notice.emit(str(exception))

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
        self._session.close()
