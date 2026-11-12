import contextlib
import hashlib
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from queue import Empty
from time import monotonic
from typing import Any
from uuid import uuid4

from .database_source import DatabasePhoto, DatabaseSource
from .message import ImageMessage
from .original_downloads import OriginalDownloads


class DatabaseReader:
    """
    Follow database watermarks and wait briefly for newly received image caches.
    """

    def __init__(
        self, images: Path, output: Any, stopped: Any, feedback: Any = None
    ) -> None:
        self._images = images
        self._output = output
        self._stopped = stopped
        self._feedback = feedback
        self._decoded: set[str] = set()
        self._versions: dict[str, str] = {}
        self._downloads: OriginalDownloads | None = None

    def acknowledgements(self) -> None:
        if self._feedback is None:
            return
        while True:
            try:
                self._decoded.add(self._feedback.get_nowait())
            except Empty:
                return

    def notice(self, message: str) -> None:
        self._output.put(("notice", message))

    def deliver(self, name: str, photo: DatabasePhoto) -> None:
        source = photo.download()
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if self._versions.get(photo.id) == digest:
            return
        self._versions[photo.id] = digest
        self._images.mkdir(parents=True, exist_ok=True)
        destination = self._images / (uuid4().hex + source.suffix)
        shutil.copyfile(source, destination)
        kind = getattr(photo, "image_kind", "unknown")
        message = ImageMessage(
            photo.id,
            name,
            destination,
            datetime.now().astimezone(),
            kind if isinstance(kind, str) else "unknown",
        )
        self._output.put(("image", message))

    def run(self, names: list[str], latest_only: bool) -> None:
        self.notice("Preparing background database access; WeChat can stay minimized")
        source = DatabaseSource(self._images.parent / "wechat", self._images)
        source.thumbnail_only = self._downloads is None
        users = {name: source.resolve(name) for name in names}
        sequences = {}
        pending: dict[str, tuple[str, DatabasePhoto, float]] = {}
        for name, user in users.items():
            rows = source.latest(user, 100 if latest_only else 1)
            sequences[user] = max(
                (int(photo.row["sort_seq"]) for photo in rows), default=0
            )
            if latest_only:
                photo = next(
                    (p for p in rows if p.type == "image" and p.attr == "friend"), None
                )
                if photo is None:
                    raise ValueError("No recent incoming image in the requested chat")
                if self._downloads is not None:
                    self._downloads.submit(photo.id, name, user, photo.row)
                    pending[user + ":" + photo.id] = (name, photo, monotonic() + 60)
                self.deliver(name, photo)
        if latest_only and not pending:
            return

        self.notice("Monitoring selected chats in the background")
        while not self._stopped.wait(0.3):
            self.acknowledgements()
            if self._downloads is not None:
                self._downloads.poll()
            for name, user in [] if latest_only else users.items():
                for photo in source.after(user, sequences[user]):
                    sequences[user] = max(sequences[user], int(photo.row["sort_seq"]))
                    if photo.type == "image" and photo.attr == "friend":
                        if len(pending) >= 64:
                            self.notice(
                                "Image cache queue is full; retry missed images"
                            )
                            continue
                        pending[user + ":" + photo.id] = (name, photo, monotonic() + 60)
                        if self._downloads is not None:
                            self._downloads.submit(photo.id, name, user, photo.row)
            for key, (name, photo, deadline) in list(pending.items()):
                if self._stopped.is_set():
                    return
                if photo.id in self._decoded:
                    if self._downloads is not None:
                        self._downloads.cancel(photo.id)
                    self._decoded.discard(photo.id)
                    self._versions.pop(photo.id, None)
                    del pending[key]
                    continue
                try:
                    self.deliver(name, photo)
                except FileNotFoundError:
                    if monotonic() < deadline:
                        continue
                    self.notice("Image is not cached; open it once in WeChat and retry")
                except Exception as exception:
                    self.notice(
                        f"Cannot decrypt cached image: {type(exception).__name__}"
                    )
                if monotonic() < deadline:
                    continue
                self._versions.pop(photo.id, None)
                del pending[key]
            if latest_only and not pending:
                return


def read_database(
    names: list[str],
    images: Path,
    latest_only: bool,
    output: Any,
    stopped: Any,
    feedback: Any = None,
    download_originals: bool = False,
) -> None:
    """
    Isolate dependency startup and keep third-party diagnostics out of IPC output.
    """
    logging.disable(logging.CRITICAL)
    with (
        open(os.devnull, "w") as sink,
        contextlib.redirect_stdout(sink),
        contextlib.redirect_stderr(sink),
    ):
        reader = DatabaseReader(images, output, stopped, feedback)
        if download_originals:
            reader._downloads = OriginalDownloads(
                images.parent / "wechat", images, reader.notice
            )
        try:
            reader.run(names, latest_only)
        except Exception as exception:
            output.put(
                ("error", f"Background access failed: {type(exception).__name__}")
            )
        finally:
            if reader._downloads is not None:
                reader._downloads.close()
            output.put(("finished", None))
