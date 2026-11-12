import contextlib
import logging
import multiprocessing
import os
from collections import deque
from collections.abc import Callable
from pathlib import Path
from queue import Empty
from time import monotonic
from typing import Any


class DownloadDiagnostics(logging.Handler):
    """Keep only a failure category, without retaining private backend messages."""

    def __init__(self) -> None:
        super().__init__()
        self.code = 1

    def emit(self, record: logging.LogRecord) -> None:
        template = str(record.msg)
        if "消息列表没渲染" in template or "可视区里没有图片气泡" in template:
            self.code = 3
        elif "没有出现新的预览窗" in template:
            self.code = 4
        elif "预览窗缩放键状态" in template or "那一档仍没出现" in template:
            self.code = 5
        elif "原图流程异常" in template:
            self.code = 6


def failure_notice(code: int | None) -> str:
    """Translate child process results into stable, non-sensitive notices."""
    return {
        2: "Original download failed: WeChat controls unavailable",
        3: "Original download failed: image message not visible",
        4: "Original download failed: image viewer did not open",
        5: "Original download failed: original file not received",
        6: "Original download failed: backend error",
        7: "Original download failed: timed out",
    }.get(code or 1, "Original download unavailable; open the image in WeChat")


def download_original(
    directory: Path,
    images: Path,
    name: str,
    user: str,
    row: dict,
    results: Any = None,
) -> None:
    """
    Fetch exactly one original through the authorized WeChat image viewer.
    """
    logging.disable(logging.CRITICAL)
    with (
        open(os.devnull, "w") as sink,
        contextlib.redirect_stdout(sink),
        contextlib.redirect_stderr(sink),
    ):
        import pythoncom

        from .database_source import DatabaseSource
        from .qt_access import QtAccess

        pythoncom.CoInitialize()
        access = QtAccess()
        diagnostics = DownloadDiagnostics()
        logger = logging.getLogger("wechatauto")
        try:
            source = DatabaseSource(directory, images)
            # Cached originals need neither focus nor accessibility compatibility.
            try:
                cached = source.image(user, row, "original")
                if results is not None:
                    results.put(str(cached))
                return
            except FileNotFoundError:
                pass
            try:
                access.enable(lambda message: None, restore=True)
            except ValueError:
                raise SystemExit(2) from None
            logger.handlers = [diagnostics]
            logger.propagate = False
            logger.setLevel(logging.DEBUG)
            logging.disable(logging.NOTSET)
            path = source.original(user, row, name)
            if path is None:
                raise SystemExit(diagnostics.code)
            if results is not None:
                results.put(str(path))
        except Exception:
            raise SystemExit(6) from None
        finally:
            logging.disable(logging.CRITICAL)
            logger.removeHandler(diagnostics)
            access.close()
            pythoncom.CoUninitialize()


class OriginalDownloads:
    """
    Serialize viewer downloads in a separate process while decoding continues.
    """

    def __init__(
        self,
        directory: Path,
        images: Path,
        notify: Callable[[str], None] | None = None,
    ) -> None:
        self._directory = directory
        self._images = images
        self._pending: deque[tuple[str, str, str, dict]] = deque()
        self._process: Any = None
        self._active = ""
        self._results: Any = None
        self._completed: deque[tuple[str, Path]] = deque()
        self._deadline = 0.0
        self._notify = notify or (lambda message: None)
        self.last_success: bool | None = None

    def submit(self, identifier: str, name: str, user: str, row: dict) -> None:
        if len(self._pending) < 64:
            self._pending.append((identifier, name, user, row))
        self.poll()

    def cancel(self, identifier: str) -> None:
        self._pending = deque(job for job in self._pending if job[0] != identifier)
        if self._active == identifier:
            self._finish()

    def _finish(self) -> None:
        if self._process is not None:
            if self._process.is_alive():
                self._process.terminate()
            self._process.join(timeout=2)
            self._process.close()
            self._process = None
            self._active = ""
            if self._results is not None:
                self._results.close()
                self._results.cancel_join_thread()
                self._results = None

    def take_completed(self) -> list[tuple[str, Path]]:
        completed = list(self._completed)
        self._completed.clear()
        return completed

    def poll(self) -> None:
        if self._process is not None:
            if self._process.is_alive() and monotonic() < self._deadline:
                return
            timed_out = self._process.is_alive()
            self.last_success = not timed_out and self._process.exitcode == 0
            if not self.last_success:
                code = 7 if timed_out else self._process.exitcode
                self._notify(failure_notice(code))
            elif self._results is not None:
                try:
                    path = Path(self._results.get_nowait()).resolve()
                    if path.is_relative_to(self._images.resolve()) and path.is_file():
                        self._completed.append((self._active, path))
                    else:
                        self.last_success = False
                        self._notify(failure_notice(5))
                except Empty:
                    self.last_success = False
                    self._notify(failure_notice(5))
            self._finish()
        if self._pending:
            identifier, name, user, row = self._pending.popleft()
            context = multiprocessing.get_context("spawn")
            self._results = context.Queue(maxsize=1)
            self._process = context.Process(
                target=download_original,
                args=(self._directory, self._images, name, user, row, self._results),
            )
            self._active = identifier
            self._deadline = monotonic() + 30
            self._process.start()

    def close(self) -> None:
        self._pending.clear()
        self._finish()
