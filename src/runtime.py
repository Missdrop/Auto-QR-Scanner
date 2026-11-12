import argparse
import base64
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen


class Chromium:
    """
    Install a pinned unbranded Chromium build from the official snapshot archive.
    """

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = (
            directory or Path(__file__).resolve().parent.parent / ".runtimes"
        )

    @staticmethod
    def revision() -> str:
        metadata = Path(__file__).with_name("chromium.json")
        return json.loads(metadata.read_text(encoding="utf-8"))["revision"]

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
        metadata = json.loads(Path(__file__).with_name("chromium.json").read_text())
        destination = self.directory / ("chromium-" + self.revision())
        destination.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.directory) as temporary:
            archive = Path(temporary) / "chromium.zip"
            checksum = hashlib.md5()
            size = 0
            progress = -1
            with (
                urlopen(metadata["url"], timeout=30) as response,
                archive.open("wb") as stream,
            ):
                while block := response.read(1024 * 1024):
                    stream.write(block)
                    checksum.update(block)
                    size += len(block)
                    if size > metadata["size"]:
                        raise ValueError("Chromium download exceeded its declared size")
                    current = size * 10 // metadata["size"]
                    if current != progress:
                        print(f"Downloading Chromium: {current * 10}%", flush=True)
                        progress = current
            expected = base64.b64decode(metadata["md5"])
            if size != metadata["size"] or checksum.digest() != expected:
                raise ValueError("Chromium archive verification failed")
            with zipfile.ZipFile(archive) as package:
                total = 0
                for member in package.infolist():
                    target = (destination / member.filename).resolve()
                    if not target.is_relative_to(destination.resolve()):
                        raise ValueError("Chromium archive contains an unsafe path")
                    total += member.file_size
                    if total > 2 * 1024**3:
                        raise ValueError(
                            "Chromium archive expands beyond its size limit"
                        )
                package.extractall(destination)
        candidates = list(destination.rglob("chrome.exe"))
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensure", action="store_true")
    arguments = parser.parse_args()
    runtime = Chromium()
    if arguments.ensure:
        try:
            runtime.executable()
        except (OSError, ValueError, KeyError):
            runtime.install()
    else:
        runtime.install()
