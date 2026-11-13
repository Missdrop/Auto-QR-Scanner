from collections.abc import Callable
from queue import Empty, Full, Queue
from threading import Event, Thread

from models.message import ImageMessage
from models.result import ScanResult
from scanning.scanner import Scanner
from storage.history import History


class Worker:
    """
    Process a bounded image queue without blocking the desktop event loop.
    """

    def __init__(
        self,
        scanner: Scanner,
        history: History,
        completed: Callable[[ScanResult, bool], None],
        notify: Callable[[str], None],
    ) -> None:
        self._scanner = scanner
        self._history = history
        self._completed = completed
        self._notify = notify
        self._queue: Queue[tuple[ImageMessage, bool]] = Queue(maxsize=64)
        self._stop = Event()
        self._thread = Thread(target=self._run, name="image-scanner", daemon=True)
        self._thread.start()

    def submit(self, message: ImageMessage, automatic: bool = False) -> bool:
        try:
            self._queue.put_nowait((message, automatic))
            return True
        except Full:
            self._notify("Scan queue is full; retry skipped images after it clears")
            return False

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                message, automatic = self._queue.get(timeout=0.2)
            except Empty:
                continue
            try:
                result = self._scanner.scan(message)
                self._history.save(result)
                self._completed(result, automatic)
            except Exception as exception:
                self._notify(f"Scan could not be recorded: {type(exception).__name__}")
            finally:
                self._queue.task_done()
