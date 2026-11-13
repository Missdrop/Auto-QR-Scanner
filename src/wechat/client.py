import multiprocessing
from collections.abc import Callable
from pathlib import Path
from queue import Empty
from threading import Event, Thread

from models.message import ImageMessage


class WeChat:
    """
    Isolate database access in a cancellable process and emit incoming images.
    """

    def __init__(self, image_directory: Path) -> None:
        self._image_directory = image_directory
        self._stop = Event()
        self._thread: Thread | None = None

    def start(
        self,
        chat_names: list[str],
        receive: Callable[[ImageMessage], None],
        notify: Callable[[str], None],
        latest_only: bool = False,
        image_mode: str | None = None,
        image_modes: list[str] | None = None,
    ) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise ValueError("Monitoring is already running")
        names = list(dict.fromkeys(name.strip() for name in chat_names if name.strip()))
        if not names:
            raise ValueError("Enter at least one exact group name")

        self._image_mode = image_mode or "thumbnail"
        self._image_modes = image_modes
        if image_modes is not None and (
            not image_modes
            or any(mode not in {"thumbnail", "compressed"} for mode in image_modes)
        ):
            raise ValueError("Select at least one valid image source")
        if self._image_mode not in {"thumbnail", "compressed"}:
            raise ValueError("Unknown image source mode")
        self._stop.clear()
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
        from wechat.database_reader import read_database

        context = multiprocessing.get_context("spawn")
        output = context.Queue(maxsize=128)
        stopped = context.Event()
        process = context.Process(
            target=read_database,
            args=(
                names,
                self._image_directory,
                latest_only,
                output,
                stopped,
                None,
                getattr(self, "_image_mode", None),
                getattr(self, "_image_modes", None),
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
                        if process.exitcode not in {None, 0}:
                            stopped_message = (
                                "Monitoring stopped: "
                                "Background process exited unexpectedly"
                            )
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
            notify(stopped_message)
