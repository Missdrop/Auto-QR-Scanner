import ctypes
import json
from ctypes import wintypes
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


class SecretStore:
    """
    Protect a local session session with Windows user-bound DPAPI encryption.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @staticmethod
    def _transform(value: bytes, decrypt: bool) -> bytes:
        buffer = ctypes.create_string_buffer(value)
        source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        destination = Blob()
        library = ctypes.WinDLL("crypt32", use_last_error=True)
        operation = library.CryptUnprotectData if decrypt else library.CryptProtectData
        if not operation(
            ctypes.byref(source), None, None, None, None, 1, ctypes.byref(destination)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(destination.data, destination.size)
        finally:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.LocalFree.argtypes = [ctypes.c_void_p]
            kernel.LocalFree(destination.data)

    def save(self, session: dict[str, str]) -> None:
        encoded = json.dumps(session).encode("utf-8")
        encrypted = self._transform(encoded, False)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_bytes(encrypted)
        temporary.replace(self._path)

    def load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            decoded = self._transform(self._path.read_bytes(), True)
            value = json.loads(decoded)
            if isinstance(value, dict):
                return value
        except (OSError, ValueError):
            pass
        return {}
