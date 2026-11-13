from collections import deque
from collections.abc import Callable
from pathlib import Path
from threading import Lock, Thread

from adapters.registry import WebsiteAdapter, WebsiteAdapters
from browser.address_filter import AddressFilter
from browser.client import Browser
from models.outcome import Outcome


class BrowserSession:
    """Use a persistent browser profile and optional private website adapters."""

    def __init__(
        self,
        directory: Path,
        notify: Callable[[str], None],
        outcome: Callable[[Outcome], None] | None = None,
    ) -> None:
        self._notify = notify
        self._outcome = outcome or (lambda result: None)
        self._browser = Browser(directory)
        self._adapters = WebsiteAdapters(
            Path(__file__).resolve().parents[2] / "website_adapters"
        )
        self._processing = Lock()
        self._queue_lock = Lock()
        self._pending: deque[tuple[str, WebsiteAdapter]] = deque()
        self._running = False
        self._closed = False
        self._request_thread: Thread | None = None

    def open(self, url: str | None = None) -> None:
        if self._closed:
            raise ValueError("The browser has been closed")
        if url is not None and not self.is_web_url(url):
            raise ValueError("Only HTTP or HTTPS links can open in the browser")
        adapter = self._adapters.find(url) if url is not None else None
        if adapter is not None and url is not None:
            self._enqueue(url, adapter)
            return
        if self._processing.locked():
            self._notify("Wait for the Chromium request before opening browser window")
            return
        if not self._browser.open(url or "about:blank"):
            self._notify("Cannot open the browser")
        elif url is not None:
            self._outcome(Outcome(url, "opened"))

    def open_link(self, url: str) -> None:
        if self._closed or not self.is_web_url(url):
            raise ValueError("Only HTTP or HTTPS links can open in the browser")
        if self._processing.locked():
            self._notify("Wait for the Chromium request before opening browser window")
            return
        self._browser.open(url)

    def _enqueue(self, url: str, adapter: WebsiteAdapter) -> None:
        with self._queue_lock:
            if len(self._pending) >= 64:
                self._outcome(Outcome(url, "error", details="Queue is full"))
                self._notify("Browser queue is full; retry manually")
                return
            self._pending.append((url, adapter))
            self._outcome(Outcome(url, "queued"))
            if self._running:
                self._notify("QR code queued for Chromium processing")
                return
            self._running = True
            self._processing.acquire()
            self._notify("Browser session available; waiting for the platform result")
            self._request_thread = Thread(
                target=self._drain,
                name="session-request",
                daemon=True,
            )
            self._request_thread.start()

    def _drain(self) -> None:
        while True:
            with self._queue_lock:
                if not self._pending:
                    self._running = False
                    self._processing.release()
                    return
                url, adapter = self._pending.popleft()
            self._outcome(Outcome(url, "processing"))
            self._process(url, adapter)

    def _process(self, url: str, adapter: WebsiteAdapter) -> None:
        try:
            result = self._browser.process(url, adapter)
            self._outcome(Outcome(url, "result", result.result, result.details))
        except Exception as exception:
            message = (
                str(exception)
                if isinstance(exception, RuntimeError)
                else type(exception).__name__
            )
            self._outcome(Outcome(url, "error", details=message))
            self._notify(message)

    @staticmethod
    def is_web_url(url: str) -> bool:
        return AddressFilter("").allows(url)

    def status(self) -> str:
        return ""

    def adapter_information(self) -> list[dict[str, str]]:
        return self._adapters.information()

    def close(self) -> None:
        self._closed = True
        with self._queue_lock:
            for url, _ in self._pending:
                self._outcome(Outcome(url, "cancelled"))
            self._pending.clear()
        if self._request_thread is not None:
            self._request_thread.join(timeout=35)
