import subprocess
import tempfile
from pathlib import Path

from wechatauto.media import MediaDownloader


class CachedMedia(MediaDownloader):
    """Decode cached images without opening a console for the converter."""

    def _wxgf_to_jpg(self, data: bytes) -> bytes | None:
        executable = self._ffmpeg_exe()
        hevc = self._extract_hevc(data)
        if not executable or not hevc:
            return None
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "image.hevc"
            destination = Path(directory) / "image.jpg"
            source.write_bytes(hevc)
            try:
                result = subprocess.run(
                    [
                        executable,
                        "-y",
                        "-v",
                        "error",
                        "-i",
                        str(source),
                        "-frames:v",
                        "1",
                        str(destination),
                    ],
                    capture_output=True,
                    timeout=30,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode == 0:
                    image = destination.read_bytes()
                    if image.startswith(b"\xff\xd8\xff"):
                        return image
            except (OSError, subprocess.SubprocessError):
                return None
        return None
