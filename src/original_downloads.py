import contextlib
import logging
import multiprocessing
import os
from collections import deque
from collections.abc import Callable
from pathlib import Path
from time import monotonic
from typing import Any


def download_original(
    directory: Path, images: Path, name: str, user: str, row: dict
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
        try:
            source = DatabaseSource(directory, images)
            try:
                access.enable(lambda message: None)
            except ValueError:
                # An original already on disk needs no visible main window.
                pass
            if source.original(user, row, name) is None:
                raise SystemExit(1)
        except Exception:
            raise SystemExit(1) from None
        finally:
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

    def poll(self) -> None:
        if self._process is not None:
            if self._process.is_alive() and monotonic() < self._deadline:
                return
            self.last_success = self._process.exitcode == 0
            if not self.last_success:
                self._notify("Original download unavailable; open the image in WeChat")
            self._finish()
        if self._pending:
            identifier, name, user, row = self._pending.popleft()
            context = multiprocessing.get_context("spawn")
            self._process = context.Process(
                target=download_original,
                args=(self._directory, self._images, name, user, row),
            )
            self._active = identifier
            self._deadline = monotonic() + 30
            self._process.start()

    def close(self) -> None:
        self._pending.clear()
        self._finish()
