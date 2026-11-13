import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from models.message import ImageMessage
from models.outcome import Outcome
from models.result import Code, ScanResult


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
                CREATE TABLE IF NOT EXISTS outcomes (
                    url TEXT PRIMARY KEY, status TEXT NOT NULL,
                    code INTEGER, message TEXT NOT NULL
                );
                UPDATE outcomes SET status = 'cancelled'
                    WHERE status IN ('queued', 'processing');
            """)

        with self._connect() as connection:
            outcome_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(outcomes)")
            }
            if "result" not in outcome_columns:
                connection.execute(
                    "ALTER TABLE outcomes ADD COLUMN result TEXT NOT NULL DEFAULT ''"
                )

        with self._connect() as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(scans)")}
            if "warning" not in columns:
                connection.execute(
                    "ALTER TABLE scans ADD COLUMN warning TEXT NOT NULL DEFAULT ''"
                )
            if "image_kind" not in columns:
                connection.execute(
                    "ALTER TABLE scans ADD COLUMN image_kind TEXT "
                    "NOT NULL DEFAULT 'unknown'"
                )

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
                "INSERT INTO scans VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    message.message_id,
                    message.chat_name,
                    str(message.image_path),
                    message.received_at.isoformat(),
                    result.elapsed_ms,
                    result.error,
                    result.warning,
                    message.image_kind,
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
                    row[8],
                )
                codes = [Code(text, bool(duplicate)) for text, duplicate in code_rows]
                results.append(
                    ScanResult(message, codes, row[5], row[6], row[0], row[7])
                )

        return results

    def save_outcome(self, outcome: Outcome) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO outcomes (url, status, code, message, result) "
                "VALUES (?, ?, NULL, ?, ?) ON CONFLICT(url) "
                "DO UPDATE SET status=excluded.status, code=NULL, "
                "result=excluded.result, "
                "message=excluded.message",
                (outcome.url, outcome.status, outcome.details, outcome.result),
            )

    def outcomes(self) -> list[Outcome]:
        with self._connect() as connection:
            return [
                Outcome(*row)
                for row in connection.execute(
                    "SELECT url, status, result, message FROM outcomes"
                )
            ]

    def outcome(self, url: str) -> Outcome | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT url, status, result, message FROM outcomes WHERE url = ?",
                (url,),
            ).fetchone()
        return Outcome(*row) if row else None
