import contextlib
import importlib
import logging
import multiprocessing
import os
from pathlib import Path
from queue import Empty, Full
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal


def contact_candidates(database: Any, query: str) -> list[dict]:
    """Match display-name prefixes before limiting results, treating input literally."""
    if not query:
        return []
    connection = database._contact_conn()
    if connection is None:
        raise RuntimeError("Contact database unavailable")
    try:
        rows = connection.execute(
            "SELECT username, nick_name, remark FROM contact "
            "WHERE substr(COALESCE(NULLIF(remark, ''), NULLIF(nick_name, ''), "
            "username), 1, ?) = ? COLLATE NOCASE "
            "ORDER BY COALESCE(NULLIF(remark, ''), NULLIF(nick_name, ''), "
            "username) COLLATE NOCASE, username LIMIT 50",
            (len(query), query),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def search_contacts(directory: Path, requests: Any, results: Any) -> None:
    """
    Search only local contact data, without creating a WeChat UI driver.
    """
    logging.disable(logging.CRITICAL)
    with (
        open(os.devnull, "w") as sink,
        contextlib.redirect_stdout(sink),
        contextlib.redirect_stderr(sink),
    ):
        directory.mkdir(parents=True, exist_ok=True)
        database = None
        while True:
            query = requests.get()
            if query is None:
                return
            try:
                if database is None:
                    module = importlib.import_module("wechatauto.db")
                    database = module.WeChatDB(workdir=str(directory))
                rows = contact_candidates(database, query)
                results.put((query, rows, ""))
            except Exception as exception:
                results.put((query, [], type(exception).__name__))


class ConversationSearch(QObject):
    """
    Keep contact lookup in a reusable process so typing never blocks the GUI.
    """

    ready = Signal(str, list)
    failed = Signal(str)

    def __init__(self, directory: Path) -> None:
        super().__init__()
        self._directory = directory
        self._closed = False
        self._process: Any = None
        self._requests: Any = None
        self._results: Any = None
        self._pending_query: str | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._receive)

    def request(self, query: str) -> None:
        if self._closed:
            return
        self._pending_query = query
        if self._process is None:
            context = multiprocessing.get_context("spawn")
            self._requests = context.Queue(maxsize=1)
            self._results = context.Queue(maxsize=4)
            self._process = context.Process(
                target=search_contacts,
                args=(self._directory, self._requests, self._results),
                daemon=True,
            )
            self._process.start()
            self._timer.start()
        self._send_pending()

    def _send_pending(self) -> None:
        if self._pending_query is not None:
            try:
                self._requests.put_nowait(self._pending_query)
                self._pending_query = None
            except Full:
                pass

    def _receive(self) -> None:
        if self._closed:
            return
        self._send_pending()
        while True:
            try:
                query, rows, error = self._results.get_nowait()
            except Empty:
                return
            self.ready.emit(query, rows)
            if error:
                self.failed.emit(
                    "Conversation suggestions unavailable; enter a name manually"
                )

    def close(self) -> None:
        self._closed = True
        self._timer.stop()
        if self._process is not None:
            self._process.terminate()
            self._process.join(timeout=2)
            self._process.close()
            self._process = None
            for queue in (self._requests, self._results):
                queue.close()
                queue.cancel_join_thread()
