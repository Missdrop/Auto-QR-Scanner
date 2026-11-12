import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .message import ImageMessage
from .result import Code, ScanResult


class History:
    """
    Store scan attempts and detect previously decoded values in local SQLite.

    Each operation owns its connection so worker and UI threads never share one.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY,
                    message_id TEXT NOT NULL,
                    chat_name TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    elapsed_ms REAL NOT NULL,
                    error TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS codes (
                    scan_id INTEGER NOT NULL REFERENCES scans(id),
                    text TEXT NOT NULL,
                    duplicate INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS codes_text ON codes(text);
            """)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, result: ScanResult) -> None:
        message = result.message

        with self._connect() as connection:
            # Serialize the lookup and insert to keep duplicate flags consistent.
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "INSERT INTO scans VALUES (NULL, ?, ?, ?, ?, ?, ?)",
                (
                    message.message_id,
                    message.chat_name,
                    str(message.image_path),
                    message.received_at.isoformat(),
                    result.elapsed_ms,
                    result.error,
                ),
            )
            result.record_id = cursor.lastrowid
            for code in result.codes:
                previous = connection.execute(
                    "SELECT 1 FROM codes WHERE text = ? LIMIT 1",
                    (code.text,),
                ).fetchone()
                code.duplicate = previous is not None
                connection.execute(
                    "INSERT INTO codes VALUES (?, ?, ?)",
                    (result.record_id, code.text, int(code.duplicate)),
                )

    def recent(self, limit: int = 500) -> list[ScanResult]:
        if limit < 1:
            raise ValueError("History limit must be positive")

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM scans ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            results = []
            for row in rows:
                code_rows = connection.execute(
                    "SELECT text, duplicate FROM codes WHERE scan_id = ?",
                    (row[0],),
                ).fetchall()
                message = ImageMessage(
                    row[1],
                    row[2],
                    Path(row[3]),
                    datetime.fromisoformat(row[4]),
                )
                codes = [Code(text, bool(duplicate)) for text, duplicate in code_rows]
                results.append(ScanResult(message, codes, row[5], row[6], row[0]))

        return results
