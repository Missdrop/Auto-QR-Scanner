import ctypes
import re
import struct
from collections.abc import Callable
from pathlib import Path
from time import monotonic, sleep

import psutil
import uiautomation
import win32api
import win32con
import win32gui
import win32process


class Section:
    """
    Translate file offsets and validate a PE section's access flags.
    """

    def __init__(self, offset: int, address: int, size: int, flags: int) -> None:
        self.offset = offset
        self.address = address
        self.size = size
        self.flags = flags

    def translate(self, offset: int) -> int | None:
        if self.offset <= offset < self.offset + self.size:
            return self.address + offset - self.offset
        return None


class QtAccess:
    """
    Temporarily enable the existing Qt accessibility provider in WeChat 4.2.

    A narrowly matched runtime flag is restored when monitoring stops. No DLL
    file, login data, chat database or system accessibility setting is changed.
    """

    def __init__(self) -> None:
        self._handle = None
        self._address = 0
        self._original = 0
        self._changed = False

    @staticmethod
    def sections(content: bytes) -> list[Section]:
        if len(content) < 64 or content[:2] != b"MZ":
            raise ValueError("Not a PE image")
        header = struct.unpack_from("<I", content, 60)[0]
        if header + 24 > len(content) or content[header : header + 4] != b"PE\0\0":
            raise ValueError("Invalid PE header")
        count = struct.unpack_from("<H", content, header + 6)[0]
        optional_size = struct.unpack_from("<H", content, header + 20)[0]
        start = header + 24 + optional_size
        if count > 96 or start + count * 40 > len(content):
            raise ValueError("Invalid PE section table")

        sections = []
        for index in range(count):
            position = start + index * 40
            address, size, offset = struct.unpack_from("<III", content, position + 12)
            flags = struct.unpack_from("<I", content, position + 36)[0]
            if offset + size > len(content):
                raise ValueError("PE section exceeds the image")
            sections.append(Section(offset, address, size, flags))
        return sections

    @staticmethod
    def _translate(sections: list[Section], offset: int) -> int | None:
        for section in sections:
            address = section.translate(offset)
            if address is not None:
                return address
        return None

    @classmethod
    def candidates(cls, content: bytes) -> list[int]:
        sections = cls.sections(content)
        category = content.find(b"qt.accessibility.core")
        category_address = cls._translate(sections, category)
        if category_address is None:
            return []

        # Require a real reference to Qt's accessibility category in executable code.
        references = []
        load_pattern = rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](.{4})"
        for match in re.finditer(load_pattern, content, re.DOTALL):
            instruction = cls._translate(sections, match.start())
            if instruction is None:
                continue
            displacement = struct.unpack("<i", match.group(1))[0]
            if instruction + 7 + displacement == category_address:
                references.append(instruction)
        if not references:
            return []

        pattern = rb"\x48\x85\xc9\x0f\x84....\x80\x3d(.{4})\x00\x0f\x84"
        candidates = []
        for match in re.finditer(pattern, content, re.DOTALL):
            instruction = cls._translate(sections, match.start())
            if instruction is None:
                continue
            target = instruction + 16 + struct.unpack("<i", match.group(1))[0]
            writable = any(
                section.flags & 0x80000000
                and section.address <= target < section.address + section.size
                for section in sections
            )
            executable = any(
                section.flags & 0x20000000
                and section.address <= instruction < section.address + section.size
                for section in sections
            )
            distance = min(abs(instruction - reference) for reference in references)
            if executable and writable and distance <= 0x20000:
                candidates.append((distance, target))
        candidates.sort()
        return list(dict.fromkeys(target for _, target in candidates))

    @staticmethod
    def _window() -> tuple[int, int]:
        candidates = []

        def inspect(handle: int, extra: object) -> None:
            if not win32gui.IsWindowVisible(handle):
                return
            title = win32gui.GetWindowText(handle)
            if title not in {"微信", "Weixin", "WeChat"}:
                return
            _, process_id = win32process.GetWindowThreadProcessId(handle)
            try:
                process = psutil.Process(process_id)
                if process.name().lower() == "weixin.exe":
                    candidates.append((handle, process_id))
            except psutil.Error:
                return

        win32gui.EnumWindows(inspect, None)
        if len(candidates) != 1:
            raise ValueError("Open exactly one logged-in WeChat main window")
        return candidates[0]

    @staticmethod
    def has_tree(window: int) -> bool:
        root = uiautomation.ControlFromHandle(window)
        if root is None:
            return False
        controls = [root, *root.GetChildren()]
        return any(
            control.ClassName.startswith("mmui::MainWindow") for control in controls
        )

    def enable(self, notify: Callable[[str], None]) -> None:
        window, process_id = self._window()
        if self.has_tree(window):
            return
        root = uiautomation.ControlFromHandle(window)
        if root is None:
            raise ValueError("Cannot inspect the WeChat window")
        names = [control.Name for control in root.GetChildren()]
        if any("登录" in name for name in names):
            raise ValueError("Log in to WeChat before monitoring")

        self._handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION
            | win32con.PROCESS_VM_READ
            | win32con.PROCESS_VM_WRITE
            | win32con.PROCESS_VM_OPERATION,
            False,
            process_id,
        )
        for module in win32process.EnumProcessModules(self._handle):
            path = Path(win32process.GetModuleFileNameEx(self._handle, module))
            if path.name.lower() == "weixin.dll":
                notify("Preparing temporary WeChat accessibility compatibility")
                for offset in self.candidates(path.read_bytes()):
                    self._address = module + offset
                    self._original = self._read()
                    if self._original not in {0, 1}:
                        continue
                    self._write(1)
                    self._changed = self._original != 1
                    deadline = monotonic() + 1
                    while monotonic() < deadline:
                        if self.has_tree(window):
                            return
                        sleep(0.1)
                    self._write(self._original)
                    self._changed = False
                break
        self.close()
        raise ValueError("WeChat accessibility compatibility could not be verified")

    def _read(self) -> int:
        if self._handle is None:
            raise RuntimeError("WeChat process is not open")
        value = ctypes.c_ubyte()
        count = ctypes.c_size_t()
        operation = ctypes.WinDLL("kernel32", use_last_error=True).ReadProcessMemory
        operation.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
        ]
        if not operation(
            int(self._handle),
            self._address,
            ctypes.byref(value),
            1,
            ctypes.byref(count),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if count.value != 1:
            raise OSError("Incomplete accessibility flag read")
        return value.value

    def _write(self, value: int) -> None:
        if self._handle is None:
            raise RuntimeError("WeChat process is not open")
        buffer = ctypes.c_ubyte(value)
        count = ctypes.c_size_t()
        operation = ctypes.WinDLL("kernel32", use_last_error=True).WriteProcessMemory
        operation.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
        ]
        if not operation(
            int(self._handle),
            self._address,
            ctypes.byref(buffer),
            1,
            ctypes.byref(count),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if count.value != 1:
            raise OSError("Incomplete accessibility flag write")

    def close(self) -> None:
        if self._handle is not None:
            try:
                if self._changed and self._read() == 1:
                    self._write(self._original)
            finally:
                self._handle.Close()
                self._handle = None
                self._changed = False
