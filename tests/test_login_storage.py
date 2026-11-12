import json
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

import zstandard

from src.login_storage import LoginStorage


def varint(number):
    result = bytearray()
    while number >= 128:
        result.append((number & 127) | 128)
        number >>= 7
    result.append(number)
    return bytes(result)


def write_log(path, sequence, entries):
    payload = struct.pack("<QI", sequence, len(entries))
    for key, value in entries:
        payload += bytes([0 if value is None else 1]) + varint(len(key)) + key
        if value is not None:
            payload += varint(len(value)) + value
    checksum = 0xFFFFFFFF
    for value in b"\x01" + payload:
        checksum ^= value
        for _ in range(8):
            checksum = (checksum >> 1) ^ (0x82F63B78 if checksum & 1 else 0)
    checksum ^= 0xFFFFFFFF
    checksum = (((checksum >> 15) | (checksum << 17)) + 0xA282EAD8) & 0xFFFFFFFF
    path.write_bytes(struct.pack("<IHB", checksum, len(payload), 1) + payload)


class LoginStorageTest(unittest.TestCase):
    def test_sqlite_compressed_session_is_filtered_and_logout_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / "Default").mkdir()
            connection = sqlite3.connect(profile / "Default/LocalStorage")
            connection.executescript(
                "CREATE TABLE maps(row_id INTEGER, storage_key BLOB);"
                "CREATE TABLE map_entries(map_id INTEGER, key BLOB, value BLOB, "
                "value_compression_type INTEGER);"
            )
            connection.executemany(
                "INSERT INTO maps VALUES (?, ?)",
                [(1, b"https://ams.xjtlu.edu.cn/"), (2, b"https://other.test/")],
            )
            compressed = zstandard.ZstdCompressor().compress(
                b'\x01{"sourceId":"student"}'
            )
            connection.executemany(
                "INSERT INTO map_entries VALUES (?, ?, ?, ?)",
                [
                    (1, b"\x01Token", b"\x01example-token", 0),
                    (1, b"\x01userInfo", compressed, 1),
                    (2, b"\x01Token", b"\x01other-token", 0),
                ],
            )
            connection.commit()
            storage = LoginStorage(profile)
            self.assertEqual(
                storage.session(), {"userId": "student", "token": "example-token"}
            )
            connection.execute("DELETE FROM map_entries WHERE map_id = 1")
            connection.commit()
            self.assertIsNone(storage.session())
            connection.close()

    def test_actual_leveldb_log_decodes_only_the_managed_ams_session(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            data = profile / "Default/Local Storage/leveldb"
            data.mkdir(parents=True)
            prefix = LoginStorage.PREFIX
            write_log(
                data / "000001.log",
                1,
                [
                    (prefix + b"\x01Token", b'\x01"example-token"'),
                    (prefix + b"\x01userInfo", b'\x01{"sourceId":"student"}'),
                    (b"_https://other.test\0\x01Token", b"\x01other-token"),
                ],
            )
            storage = LoginStorage(profile)
            self.assertEqual(
                storage.session(), {"userId": "student", "token": "example-token"}
            )
            write_log(data / "000002.log", 3, [(prefix + b"\x01Token", None)])
            self.assertIsNone(storage.session())

    def test_utf16_chromium_strings_are_decoded(self):
        value = json.dumps({"name": "测试"}, ensure_ascii=False)
        self.assertEqual(LoginStorage.text(b"\0" + value.encode("utf-16-le")), value)
