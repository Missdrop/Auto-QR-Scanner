import contextlib
import hashlib
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from .database_source import DatabasePhoto, DatabaseSource
from .message import ImageMessage


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
        self._versions: dict[str, str] = {}
        self._image_mode: str | None = None
        self._image_modes: list[str] | None = None

    def notice(self, message: str) -> None:
        self._output.put(("notice", message))

    def deliver(self, name: str, photo: DatabasePhoto) -> None:
        if self._image_modes is not None:
            for mode in self._image_modes:
                try:
                    source = photo.download(mode)
                except FileNotFoundError:
                    continue
                self._deliver_source(name, photo, source, photo.id + ":" + mode)
            return
        self._deliver_source(name, photo, photo.download(), photo.id)

    def _complete(self, photo: DatabasePhoto) -> bool:
        return self._image_modes is not None and all(
            photo.id + ":" + mode in self._versions for mode in self._image_modes
        )

    def _forget(self, photo: DatabasePhoto) -> None:
        self._versions.pop(photo.id, None)
        for mode in self._image_modes or []:
            self._versions.pop(photo.id + ":" + mode, None)

    def _deliver_source(
        self, name: str, photo: DatabasePhoto, source: Path, key: str
    ) -> None:
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if self._versions.get(key) == digest:
            return
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
        # A failed copy or delivery must remain eligible for retry.
        self._versions[key] = digest

    def run(self, names: list[str], latest_only: bool) -> None:
        self.notice("Preparing background database access; WeChat can stay minimized")
        source = DatabaseSource(self._images.parent / "wechat", self._images)
        source.image_mode = self._image_mode or "thumbnail"
        source.thumbnail_only = source.image_mode == "thumbnail"
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
                if self._image_mode == "compressed" or self._image_modes is not None:
                    pending[user + ":" + photo.id] = (name, photo, monotonic() + 60)
                self.deliver(name, photo)
        if latest_only and not pending:
            return

        self.notice("Monitoring selected chats in the background")
        while not self._stopped.wait(0.3):
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
            for key, (name, photo, deadline) in list(pending.items()):
                if self._stopped.is_set():
                    return
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
                if self._complete(photo):
                    self._forget(photo)
                    del pending[key]
                    continue
                if monotonic() < deadline:
                    continue
                if self._image_modes is not None:
                    self.notice(
                        "Selected image versions are not cached; "
                        "open the image in WeChat and retry"
                    )
                self._forget(photo)
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
    image_mode: str | None = None,
    image_modes: list[str] | None = None,
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
        reader._image_mode = image_mode
        reader._image_modes = image_modes
        try:
            reader.run(names, latest_only)
        except Exception as exception:
            output.put(
                ("error", f"Background access failed: {type(exception).__name__}")
            )
        finally:
            output.put(("finished", None))
