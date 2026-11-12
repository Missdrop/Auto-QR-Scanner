import ctypes
import importlib
import struct
from pathlib import Path
from typing import Any

import psutil

from .secret_store import SecretStore


class ImageKeys:
    """
    Locate a read-only image configuration and verify it against the target image.
    """

    def __init__(self, path: Path) -> None:
        self._store = SecretStore(path)
        self._cached = self._store.load()

    @staticmethod
    def matches_string(read: Any, address: int, expected: str) -> bool:
        header = read(address, 32)
        encoded = expected.encode()
        if not header or struct.unpack_from("<Q", header, 16)[0] != len(encoded):
            return False
        capacity = struct.unpack_from("<Q", header, 24)[0]
        if capacity > 4096:
            return False
        if capacity <= 15:
            return header[: len(encoded)] == encoded
        pointer = struct.unpack_from("<Q", header)[0]
        return read(pointer, len(encoded)) == encoded

    @classmethod
    def locate(
        cls, image: bytes, base: int, read: Any, account: str, valid: Any
    ) -> int:
        position = -1
        while True:
            position = image.find(b"global_config", position + 1)
            if position < 0:
                break
            if image[position + 16 : position + 24] != struct.pack("<Q", 13):
                continue
            # Only follow bounded configuration pointers; never scan arbitrary keys.
            for back in range(0x100, 0x181, 8):
                pointer = cls.pointer(read, base + position + 16 - back)
                if not pointer:
                    continue
                for offset in range(0x30, 0xA1, 8):
                    configuration = cls.pointer(read, pointer + offset)
                    if not configuration:
                        continue
                    if not cls.matches_string(read, configuration + 0x48, account):
                        continue
                    value = read(configuration + 0x40, 4)
                    if value:
                        number = struct.unpack("<I", value)[0]
                        if valid(number):
                            return number
        raise ValueError("The image configuration could not be verified")

    @staticmethod
    def pointer(read: Any, address: int) -> int:
        value = read(address, 8)
        if value:
            pointer = struct.unpack("<Q", value)[0]
            if 0x10000 < pointer < 0x800000000000:
                return pointer
        return 0

    def resolve(self, media: Any, probe: bytes) -> tuple[str, int]:
        account = media.db.wxid

        def valid(number: int) -> bool:
            key, _ = media.derive_image_keys(number, account)
            return media._validate_key(key, probe)

        if self._cached.get("account") == account:
            try:
                number = int(self._cached["value"])
                if valid(number):
                    return media.derive_image_keys(number, account)
            except (ValueError, KeyError):
                pass
        module = importlib.import_module("wechatauto.db")
        for process in psutil.process_iter(["name", "cmdline"]):
            if (process.info["name"] or "").lower() != "weixin.exe":
                continue
            if any("--type=" in arg for arg in process.info["cmdline"] or []):
                continue
            image_info = module._find_weixin_module(process.pid)
            if not image_info:
                continue
            base, size, _ = image_info
            if not 0 < size <= 0x40000000:
                continue
            handle = module._k32.OpenProcess(0x410, False, process.pid)
            if not handle:
                continue
            try:

                def read(
                    address: int, length: int, handle: Any = handle
                ) -> bytes | None:
                    buffer = ctypes.create_string_buffer(length)
                    count = ctypes.c_size_t()
                    success = module._k32.ReadProcessMemory(
                        handle,
                        ctypes.c_void_p(address),
                        buffer,
                        length,
                        ctypes.byref(count),
                    )
                    return buffer.raw if success and count.value == length else None

                image = read(base, size)
                if image:
                    try:
                        number = self.locate(image, base, read, account, valid)
                    except ValueError:
                        continue
                    self._cached = {"account": account, "value": str(number)}
                    self._store.save(self._cached)
                    return media.derive_image_keys(number, account)
            finally:
                module._k32.CloseHandle(handle)
        raise ValueError("Cannot obtain a verified image key; keep WeChat logged in")
