import importlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import zstandard


class LoginStorage:
    """
    Read only AMS session entries from the application's dedicated Chrome profile.
    """

    PREFIX = b"_https://ams.xjtlu.edu.cn\x00"

    def __init__(self, profile: Path) -> None:
        self._database = profile / "Default/LocalStorage"
        self._directory = profile / "Default/Local Storage/leveldb"

    @staticmethod
    def text(value: bytes) -> str:
        if not value:
            return ""
        if value[0] == 1:
            return value[1:].decode("latin-1")
        if value[0] == 0:
            return value[1:].decode("utf-16-le")
        raise ValueError("Unknown Chromium storage string encoding")

    @classmethod
    def select(cls, records: Any) -> dict[str, str]:
        latest: dict[str, Any] = {}
        for entry in records:
            row = entry.record
            if not row.key.startswith(cls.PREFIX):
                continue
            key = cls.text(row.key[len(cls.PREFIX) :])
            if key not in {"Token", "userInfo"}:
                continue
            if key not in latest or row.sequence_number > latest[key].sequence_number:
                latest[key] = row
        return {
            key: cls.text(row.value)
            for key, row in latest.items()
            if int(row.record_type) == 1
        }

    def session(self) -> dict[str, str] | None:
        values = self._sqlite() if self._database.is_file() else self._leveldb()
        return self._session(values)

    def _sqlite(self) -> dict[str, str]:
        # Chromium holds an exclusive lock while running. Retry after it closes;
        # an unavailable database must never be interpreted as a logout.
        if self._database.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("The managed login database exceeded its size limit")
        connection = sqlite3.connect(
            self._database.resolve().as_uri() + "?mode=ro", uri=True, timeout=1
        )
        try:
            rows = connection.execute(
                "SELECT key, value, value_compression_type FROM map_entries "
                "JOIN maps ON map_id = row_id WHERE storage_key = ? "
                "AND key IN (?, ?)",
                (b"https://ams.xjtlu.edu.cn/", b"\x01Token", b"\x01userInfo"),
            )
            values = {}
            for key, value, compression in rows:
                if len(value) > 65536:
                    raise ValueError("The managed session value is too large")
                if compression == 1:
                    size = zstandard.frame_content_size(value)
                    if (
                        size
                        not in {
                            zstandard.CONTENTSIZE_UNKNOWN,
                            zstandard.CONTENTSIZE_ERROR,
                        }
                        and size > 65536
                    ):
                        raise ValueError("The decoded session value is too large")
                    value = zstandard.ZstdDecompressor().decompress(
                        value, max_output_size=65536
                    )
                elif compression != 0:
                    raise ValueError("Unknown Chromium storage compression")
                if len(value) > 65536:
                    raise ValueError("The decoded session value is too large")
                values[self.text(key)] = self.text(value)
            return values
        finally:
            connection.close()

    def _leveldb(self) -> dict[str, str]:
        if not self._directory.is_dir():
            return {}
        module = importlib.import_module("dfindexeddb.leveldb.record")
        with tempfile.TemporaryDirectory(prefix="autoqr-login-") as temporary:
            copied = []
            total = 0
            for source in self._directory.iterdir():
                if source.suffix not in {".log", ".ldb"}:
                    continue
                total += source.stat().st_size
                if total > 64 * 1024 * 1024:
                    raise ValueError(
                        "The managed login storage exceeded its size limit"
                    )
                target = Path(temporary) / source.name
                shutil.copyfile(source, target)
                copied.append(target)
            records = (
                record
                for target in copied
                for record in module.LevelDBRecord.FromFile(target)
            )
            values = self.select(records)
        return values

    @staticmethod
    def _session(values: dict[str, str]) -> dict[str, str] | None:
        if not values.get("Token") or not values.get("userInfo"):
            return None
        account = json.loads(values["userInfo"])
        if not isinstance(account, dict):
            raise ValueError("Invalid AMS account reference")
        token = values["Token"]
        try:
            decoded = json.loads(token)
            if isinstance(decoded, str):
                token = decoded
        except ValueError:
            pass
        user_id = account.get("userId") or account.get("sourceId")
        if not user_id or not token:
            return None
        return {"userId": str(user_id), "token": token}
