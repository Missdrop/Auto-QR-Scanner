import importlib
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from .message import ImageMessage


class WeChat:
    """
    Keep UI Automation on its own thread and emit only new incoming images.

    Free wxauto4 monitors one group by polling. A separately installed wxautox4
    backend can use its multi-window listener. Client compatibility is required.
    """

    def __init__(self, image_directory: Path) -> None:
        self._image_directory = image_directory
        self._stop = Event()
        self._thread: Thread | None = None
        self._seen: set[str] = set()

    def start(
        self,
        chat_names: list[str],
        receive: Callable[[ImageMessage], None],
        notify: Callable[[str], None],
    ) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise ValueError("Monitoring is already running")
        names = list(dict.fromkeys(name.strip() for name in chat_names if name.strip()))
        if not names:
            raise ValueError("Enter at least one exact group name")

        self._stop.clear()
        self._seen.clear()
        self._thread = Thread(
            target=self._run,
            args=(names, receive, notify),
            name="wechat-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def close(self) -> None:
        self.stop()
        if self._thread is not None:
            # Finish the monitor's finally block before the desktop process exits.
            self._thread.join()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(
        self,
        names: list[str],
        receive: Callable[[ImageMessage], None],
        notify: Callable[[str], None],
    ) -> None:
        client: Any = None
        com: Any = None
        accessibility: Any = None
        stopped_message = "Monitoring stopped"
        try:
            com = importlib.import_module("pythoncom")
            com.CoInitialize()
            from .qt_access import QtAccess

            accessibility = QtAccess()
            accessibility.enable(notify)
            module = self._load_backend()
            # WeChat 4.2 exposes virtual controls without native window handles.
            # Keep the existing window size instead of resizing a virtual control.
            client = module.WeChat(resize=False, ads=False, start_listener=False)
            if module.__name__ == "wxautox4":
                self._listen(client, names, receive, notify)
            else:
                self._poll(client, names, receive, notify)
        except Exception as exception:
            reason = f"{type(exception).__name__}: {exception}"
            stopped_message = (
                f"Monitoring stopped: {reason}. Check WeChat login, "
                "client compatibility and the optional backend."
            )
        finally:
            if client is not None and hasattr(client, "StopListening"):
                try:
                    client.StopListening()
                except Exception:
                    pass
            if accessibility is not None:
                try:
                    accessibility.close()
                except OSError:
                    stopped_message += "; could not restore accessibility state"
            if com is not None:
                com.CoUninitialize()
            notify(stopped_message)

    @staticmethod
    def _load_backend() -> Any:
        try:
            return importlib.import_module("wxautox4")
        except ModuleNotFoundError as exception:
            if exception.name != "wxautox4":
                raise
        return importlib.import_module("wxauto4")

    def _listen(
        self,
        client: Any,
        names: list[str],
        receive: Callable[[ImageMessage], None],
        notify: Callable[[str], None],
    ) -> None:
        for name in names:

            def on_message(message: Any, chat: Any, group: str = name) -> None:
                if not self._stop.is_set():
                    self._receive(message, group, receive, notify)

            response = client.AddListenChat(nickname=name, callback=on_message)
            if response is None or not bool(response):
                raise RuntimeError("Cannot attach group listener")
        client.StartListening()
        notify("Monitoring selected groups")
        self._stop.wait()

    def _poll(
        self,
        client: Any,
        names: list[str],
        receive: Callable[[ImageMessage], None],
        notify: Callable[[str], None],
    ) -> None:
        if len(names) != 1:
            raise ValueError("The free backend supports one group at a time")
        name = names[0]
        client.ChatWith(name, exact=True)
        info = client.ChatInfo()
        if info.get("chat_name") != name or info.get("chat_type") != "group":
            raise ValueError("Selected chat is not the requested group")

        # Snapshot visible messages before monitoring; never process old history.
        for message in client.GetAllMessage():
            self._seen.add(name + ":" + str(message.id))
        notify("Monitoring group; keep the selected WeChat chat open")
        while not self._stop.wait(0.3):
            if client.ChatInfo().get("chat_name") != name:
                raise RuntimeError("The active WeChat chat changed; restart monitoring")
            for message in client.GetAllMessage():
                self._receive(message, name, receive, notify)

    def _receive(
        self,
        message: Any,
        group: str,
        receive: Callable[[ImageMessage], None],
        notify: Callable[[str], None],
    ) -> None:
        message_id = str(message.id)
        key = group + ":" + message_id
        if key in self._seen:
            return
        self._seen.add(key)
        if message.attr != "friend" or message.type != "image":
            return
        received_at = datetime.now().astimezone()

        try:
            source = Path(message.download())
            if not source.is_file():
                raise ValueError("Downloaded image is missing")
            self._image_directory.mkdir(parents=True, exist_ok=True)
            destination = self._image_directory / (uuid4().hex + source.suffix)
            shutil.copyfile(source, destination)
            receive(ImageMessage(message_id, group, destination, received_at))
        except Exception as exception:
            notify(f"Cannot retrieve group image: {type(exception).__name__}")
