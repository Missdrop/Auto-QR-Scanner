import struct
import unittest
from unittest.mock import Mock

from src.qt_access import QtAccess


def image(writable: bool = True) -> bytes:
    content = bytearray(0x800)
    content[:2] = b"MZ"
    struct.pack_into("<I", content, 60, 0x80)
    content[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", content, 0x86, 3)
    for index, (address, offset, flags) in enumerate(
        [
            (0x1000, 0x200, 0x20000000),
            (0x2000, 0x400, 0),
            (0x3000, 0x600, 0x80000000 if writable else 0),
        ]
    ):
        position = 0x98 + index * 40
        struct.pack_into("<IIII", content, position + 8, 0x200, address, 0x200, offset)
        struct.pack_into("<I", content, position + 36, flags)
    content[0x400:0x415] = b"qt.accessibility.core"
    content[0x220:0x227] = b"\x48\x8d\x0d" + struct.pack("<i", 0x2000 - 0x1027)
    content[0x240:0x254] = (
        b"\x48\x85\xc9\x0f\x84\0\0\0\0\x80\x3d"
        + struct.pack("<i", 0x3000 - 0x1050)
        + b"\0\x0f\x84\0\0"
    )
    return bytes(content)


class QtAccessTest(unittest.TestCase):
    def test_finds_only_a_writable_accessibility_flag(self) -> None:
        self.assertEqual(QtAccess.candidates(image()), [0x3000])
        self.assertEqual(QtAccess.candidates(image(False)), [])

    def test_rejects_unrelated_code_without_the_category_reference(self) -> None:
        content = image().replace(b"qt.accessibility.core", b"unrelated.category.xx")
        self.assertEqual(QtAccess.candidates(content), [])

    def test_rejects_malformed_images(self) -> None:
        for content in [b"", b"MZ", b"MZ" + b"\xff" * 100]:
            with self.assertRaises(ValueError):
                QtAccess.candidates(content)

    def test_close_restores_owned_runtime_change(self) -> None:
        access = QtAccess()
        handle = Mock()
        access._handle = handle
        access._changed = True
        access._original = 0
        access._read = Mock(return_value=1)
        access._write = Mock()
        access.close()
        access._write.assert_called_once_with(0)
        handle.Close.assert_called_once()
        self.assertIsNone(access._handle)

    def test_close_does_not_override_a_state_changed_elsewhere(self) -> None:
        access = QtAccess()
        access._handle = Mock()
        access._changed = True
        access._read = Mock(return_value=0)
        access._write = Mock()
        access.close()
        access._write.assert_not_called()
