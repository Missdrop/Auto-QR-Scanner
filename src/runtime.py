import hashlib
import json
import os
import subprocess
import sys
from importlib.resources import files
from pathlib import Path


class Chromium:
    """
    Install and verify the Chromium revision supplied by the locked Playwright SDK.
    """

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = (
            directory or Path(__file__).resolve().parent.parent / ".runtimes"
        )

    @staticmethod
    def revision() -> str:
        metadata = files("playwright").joinpath("driver/package/browsers.json")
        browsers = json.loads(metadata.read_text(encoding="utf-8"))["browsers"]
        return next(
            browser["revision"] for browser in browsers if browser["name"] == "chromium"
        )

    @staticmethod
    def digest(path: Path) -> str:
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    def executable(self) -> Path:
        manifest_path = self.directory / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(
                "Run uv run python -m src.runtime to install Chromium"
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("revision") != self.revision():
            raise ValueError("Chromium changed; run uv run python -m src.runtime again")
        path = (self.directory / manifest["executable"]).resolve()
        if not path.is_relative_to(self.directory.resolve()) or not path.is_file():
            raise ValueError("The Chromium runtime path is invalid")
        if self.digest(path) != manifest["sha256"]:
            raise ValueError("Chromium verification failed; reinstall the runtime")
        return path

    def install(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        environment = {
            **os.environ,
            "PLAYWRIGHT_BROWSERS_PATH": str(self.directory.resolve()),
        }
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--no-shell", "chromium"],
            env=environment,
            check=True,
        )
        candidates = list(
            (self.directory / ("chromium-" + self.revision())).rglob("chrome.exe")
        )
        if len(candidates) != 1:
            raise ValueError("The downloaded Chromium executable is ambiguous")
        path = candidates[0]
        manifest = {
            "revision": self.revision(),
            "executable": str(path.relative_to(self.directory)),
            "sha256": self.digest(path),
        }
        (self.directory / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        self.executable()


if __name__ == "__main__":
    Chromium().install()
