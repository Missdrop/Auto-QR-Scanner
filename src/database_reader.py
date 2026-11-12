import contextlib
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

    def __init__(self, images: Path, output: Any, stopped: Any) -> None:
        self._images = images
        self._output = output
        self._stopped = stopped

    def notice(self, message: str) -> None:
        self._output.put(("notice", message))

    def deliver(self, name: str, photo: DatabasePhoto) -> None:
        source = photo.download()
        self._images.mkdir(parents=True, exist_ok=True)
        destination = self._images / (uuid4().hex + source.suffix)
        shutil.copyfile(source, destination)
        message = ImageMessage(photo.id, name, destination, datetime.now().astimezone())
        self._output.put(("image", message))

    def run(self, names: list[str], latest_only: bool) -> None:
        self.notice("Preparing background database access; WeChat can stay minimized")
        source = DatabaseSource(self._images.parent / "wechat", self._images)
        users = {name: source.resolve(name) for name in names}
        sequences = {}
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
                self.deliver(name, photo)
        if latest_only:
            return

        self.notice("Monitoring selected chats in the background")
        pending: dict[str, tuple[str, DatabasePhoto, float]] = {}
        while not self._stopped.wait(0.3):
            for name, user in users.items():
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
                del pending[key]


def read_database(
    names: list[str], images: Path, latest_only: bool, output: Any, stopped: Any
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
        reader = DatabaseReader(images, output, stopped)
        try:
            reader.run(names, latest_only)
        except Exception as exception:
            output.put(
                ("error", f"Background access failed: {type(exception).__name__}")
            )
        finally:
            output.put(("finished", None))
