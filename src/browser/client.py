import subprocess
from pathlib import Path
from threading import Thread

from adapters.base import AdapterResult
from adapters.registry import WebsiteAdapter
from browser.page import BrowserPage
from browser.runtime import Chromium


class Browser:
    """
    Open links with the application's persistent Chromium profile.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._process: subprocess.Popen | None = None

    def open(self, url: str = "about:blank") -> bool:
        active = self._process is not None and self._process.poll() is None
        profile = (self._directory / "chromium").resolve()
        profile.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(
            [
                str(Chromium().executable()),
                "--new-window",
                "--user-data-dir=" + str(profile),
                "--no-first-run",
                "--no-default-browser-check",
                url,
            ],
            cwd=Path(__file__).resolve().parents[2],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if active:
            # Chromium forwards this navigation to the existing profile owner.
            # Keep tracking that owner rather than the short-lived launcher.
            Thread(target=process.wait, name="browser-launcher", daemon=True).start()
        else:
            self._process = process
        return True

    def process(self, url: str, adapter: WebsiteAdapter) -> AdapterResult:
        if self._process is not None and self._process.poll() is None:
            raise RuntimeError(
                "Close the built-in browser before background processing"
            )
        return BrowserPage(self._directory).process(url, adapter)
