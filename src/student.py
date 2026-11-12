import hmac
import json
import secrets
from collections import deque
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import urlsplit

from .ams import Ams
from .browser import Browser
from .secret_store import SecretStore

HOME_URL = "https://ams.xjtlu.edu.cn/studenth5/"


class Student:
    """
    Receive sessions from the integrated login window over authenticated loopback.

    Login and authenticated QR requests run in the managed Chromium profile.
    Session metadata uses Windows DPAPI; passwords are never read.
    """

    def __init__(self, directory: Path, notify: Callable[[str], None]) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self._notify = notify
        self._browser = Browser(directory)
        self._ams = Ams()
        self._processing = Lock()
        self._queue_lock = Lock()
        self._pending: deque[tuple[str, str]] = deque()
        self._running = False
        self._closed = False
        self._request_thread: Thread | None = None
        self._store = SecretStore(directory / "session.bin")
        self._session = self._store.load()
        self._lock = Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._key = self._load_key(directory / "login.key")
        self.port = 52841

    @staticmethod
    def _load_key(path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="ascii").strip()
        key = secrets.token_urlsafe(32)
        path.write_text(key, encoding="ascii")
        return key

    def start(self, port: int = 52841) -> None:
        if self._server is not None:
            return
        self._server = ThreadingHTTPServer(("127.0.0.1", port), self._handler_type())
        self.port = self._server.server_address[1]
        self._thread = Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.2},
            name="student-bridge",
            daemon=True,
        )
        self._thread.start()

    def open(self, url: str = HOME_URL) -> None:
        if self._closed:
            raise ValueError("The student browser has been closed")
        if not self.is_student_url(url):
            raise ValueError("Only HTTPS XJTLU AMS student URLs can open automatically")
        self.start()
        if url == HOME_URL and self._processing.locked():
            self._notify("Wait for the Chromium request before opening Student login")
            return
        with self._lock:
            student = dict(self._session)
        if url != HOME_URL and not student:
            self._notify("Login required: open Student login and sign in")
            return

        if url != HOME_URL:
            state = self._ams.state(url)
            self._enqueue(state, student["token"])
            return
        self._notify(
            "Sign in using Chromium, then close its window to synchronize the session"
        )
        if not self._browser.open(url):
            self._notify("Cannot open the student page; check the installed browser")

    def _enqueue(self, state: str, token: str) -> None:
        with self._queue_lock:
            if len(self._pending) >= 64:
                self._notify("Student queue is full; retry this record manually")
                return
            self._pending.append((state, token))
            if self._running:
                self._notify("QR code queued for Chromium processing")
                return
            self._running = True
            self._processing.acquire()
            self._notify("Student session available; waiting for the platform result")
            self._request_thread = Thread(
                target=self._drain,
                name="student-request",
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
                state, token = self._pending.popleft()
            with self._lock:
                available = bool(self._session)
            if available:
                self._process(state, token)
            else:
                self._notify("Login required; retry pending records after signing in")

    def _process(self, state: str, token: str) -> None:
        try:
            code, message = self._browser.process(state)
            if code == 401:
                with self._lock:
                    current = self._session.get("token") == token
                    if current:
                        self._store.save({})
                        self._session = {}
                if current:
                    self._notify(
                        "Login required: student session expired or was cleared"
                    )
                else:
                    self._notify(
                        "The earlier session expired; retry with the new login"
                    )
            elif code == 0:
                self._notify("Platform confirmed successful processing: " + message)
            else:
                self._notify("Platform rejected the QR code: " + message)
        except RuntimeError as exception:
            self._notify(str(exception))
        except Exception as exception:
            self._notify(
                f"Cannot obtain a platform result: {type(exception).__name__}. "
                "Inspect the student login and retry manually."
            )

    @staticmethod
    def is_student_url(url: str) -> bool:
        try:
            parts = urlsplit(url)
        except ValueError:
            return False
        return (
            parts.scheme == "https"
            and parts.netloc == "ams.xjtlu.edu.cn"
            and parts.path == "/studenth5/"
        )

    def _receive(self, payload: dict[str, object]) -> None:
        event = payload.get("event")
        if event == "session":
            user_id = payload.get("userId")
            token = payload.get("token")
            if not isinstance(user_id, str) or not isinstance(token, str):
                raise ValueError("Invalid session fields")
            if not user_id or not token or len(token) > 16000:
                raise ValueError("Missing or excessive session fields")
            student = {"userId": user_id, "token": token}
            with self._lock:
                self._store.save(student)
                self._session = student
            self._notify("Student session available; platform validates it on use")
            return

        if event == "login-unavailable":
            self._notify("Close the student login window and reopen Student login")
        elif event == "logout":
            with self._lock:
                self._store.save({})
                self._session = {}
            self._notify("Login required: student session expired or was cleared")
        else:
            raise ValueError("Unknown browser event")

    def _handler_type(self) -> type[BaseHTTPRequestHandler]:
        student = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self) -> None:
                super().setup()
                self.connection.settimeout(2)

            def do_POST(self) -> None:
                if self.headers.get("Origin"):
                    self.send_error(403)
                    return
                if self.path != "/event":
                    self.send_error(404)
                    return
                authorization = self.headers.get("Authorization", "")
                if not hmac.compare_digest(authorization, "Bearer " + student._key):
                    self.send_error(403)
                    return
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 32768:
                        raise ValueError("Invalid request length")
                    payload = json.loads(self.rfile.read(size))
                    if not isinstance(payload, dict):
                        raise ValueError("Expected an object")
                    student._receive(payload)
                except (ValueError, OSError):
                    self.send_error(400)
                    return
                self.send_response(204)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                # Never log student tokens, request bodies or authenticated URLs.
                return

        return Handler

    def status(self) -> str:
        with self._lock:
            if self._session:
                return "Student session saved; platform validates it on use"
        return "Student login required"

    def close(self) -> None:
        self._closed = True
        with self._queue_lock:
            self._pending.clear()
        if self._request_thread is not None:
            self._request_thread.join(timeout=35)
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
