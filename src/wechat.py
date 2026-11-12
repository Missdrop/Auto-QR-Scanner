import importlib
import multiprocessing
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from queue import Empty
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from .message import ImageMessage


class WeChat:
    """
    Isolate database access in a cancellable process and emit incoming images.
    """

    def __init__(self, image_directory: Path) -> None:
        self._image_directory = image_directory
        self._stop = Event()
        self._thread: Thread | None = None
        self._seen: set[str] = set()
        self._feedback: Any = None

    def decoded(self, message_id: str) -> None:
        if self._feedback is not None:
            try:
                self._feedback.put_nowait(message_id)
            except (OSError, ValueError):
                pass

    def start(
        self,
        chat_names: list[str],
        receive: Callable[[ImageMessage], None],
        notify: Callable[[str], None],
        latest_only: bool = False,
        download_originals: bool = False,
    ) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise ValueError("Monitoring is already running")
        names = list(dict.fromkeys(name.strip() for name in chat_names if name.strip()))
        if not names:
            raise ValueError("Enter at least one exact group name")

        self._stop.clear()
        self._download_originals = download_originals
        self._seen.clear()
        self._thread = Thread(
            target=self._run,
            args=(names, receive, notify, latest_only),
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
        latest_only: bool = False,
    ) -> None:
        from .database_reader import read_database

        context = multiprocessing.get_context("spawn")
        output = context.Queue(maxsize=128)
        self._feedback = context.Queue()
        stopped = context.Event()
        process = context.Process(
            target=read_database,
            args=(
                names,
                self._image_directory,
                latest_only,
                output,
                stopped,
                self._feedback,
                getattr(self, "_download_originals", False),
            ),
            name="wechat-database",
            daemon=False,
        )
        stopped_message = "Monitoring stopped"
        try:
            process.start()
            while not self._stop.is_set():
                try:
                    event, value = output.get(timeout=0.2)
                except Empty:
                    if not process.is_alive():
                        break
                    continue
                if event == "image":
                    receive(value)
                elif event == "error":
                    stopped_message = "Monitoring stopped: " + value
                elif event == "notice":
                    notify(value)
                elif event == "finished":
                    break
        except Exception as exception:
            stopped_message = f"Monitoring stopped: {type(exception).__name__}"
        finally:
            stopped.set()
            if process.pid is not None:
                process.join(timeout=4)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                process.close()
            output.close()
            output.cancel_join_thread()
            self._feedback.close()
            self._feedback.cancel_join_thread()
            self._feedback = None
            notify(stopped_message)

    def _run_ui(
        self,
        names: list[str],
        receive: Callable[[ImageMessage], None],
        notify: Callable[[str], None],
        latest_only: bool = False,
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
            if module.__name__ == "wxautox4" and not latest_only:
                self._listen(client, names, receive, notify)
            else:
                self._poll(client, names, receive, notify, latest_only)
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
        latest_only: bool = False,
    ) -> None:
        if len(names) != 1:
            raise ValueError("The free backend supports one group at a time")
        name = names[0]
        client.ChatWith(name, exact=True)
        from .passive_chat import PassiveChat

        reader = PassiveChat(client, self._image_directory, notify)
        if reader.name() != name:
            raise ValueError("Selected chat is not the requested conversation")

        if latest_only:
            if not reader.is_foreground():
                raise ValueError("Bring the requested conversation to the foreground")
            for message in reversed(reader.messages()):
                if message.type == "image" and message.attr == "friend":
                    self._receive(message, name, receive, notify)
                    return
            raise ValueError("No visible incoming image in this conversation")

        # Snapshot identifiers only: backend message constructors may click avatars.
        for message in reader.messages():
            self._seen.add(name + ":" + message.id)
        notify("Monitoring conversation; keep WeChat visible and in the foreground")
        paused = False
        while not self._stop.wait(0.3):
            if reader.name() != name:
                raise RuntimeError("The active WeChat chat changed; restart monitoring")
            if not reader.is_foreground():
                if not paused:
                    notify(
                        "Monitoring paused; bring the selected chat to the foreground"
                    )
                paused = True
                continue
            if paused:
                notify("Monitoring conversation; WeChat is in the foreground")
                paused = False
            for message in reader.messages():
                if self._stop.is_set():
                    break
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
        if message.type != "image":
            return
        received_at = datetime.now().astimezone()

        try:
            if message.attr != "friend":
                return
            source = Path(message.download())
            if not source.is_file():
                raise ValueError("Downloaded image is missing")
            self._image_directory.mkdir(parents=True, exist_ok=True)
            destination = self._image_directory / (uuid4().hex + source.suffix)
            shutil.copyfile(source, destination)
            receive(ImageMessage(message_id, group, destination, received_at))
        except Exception as exception:
            notify(f"Cannot retrieve group image: {type(exception).__name__}")
