import subprocess
import sys
from pathlib import Path

from .runtime import Chromium
from .student_page import StudentPage


class Browser:
    """
    Run the managed persistent Chromium login window.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._process: subprocess.Popen | None = None

    def open(self, url: str) -> bool:
        if self._process is not None and self._process.poll() is None:
            return True
        Chromium().executable()
        self._process = subprocess.Popen(
            [sys.executable, "-m", "src.login", "--data", str(self._directory)],
            cwd=Path(__file__).resolve().parent.parent,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    def process(self, state: str) -> tuple[int, str]:
        if self._process is not None and self._process.poll() is None:
            raise RuntimeError("Close Student login before processing a QR code")
        return StudentPage(self._directory).process(state)
