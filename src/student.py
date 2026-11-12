import hmac
import json
import secrets
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
    Receive student sessions from the companion extension over authenticated loopback.

    Login stays in the normal browser. QR results come from the existing AMS HTTPS
    endpoint. Session values use Windows DPAPI; passwords are never read.
    """

    def __init__(self, directory: Path, notify: Callable[[str], None]) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self._notify = notify
        self._browser = Browser()
        self._ams = Ams()
        self._processing = Lock()
        self._request_thread: Thread | None = None
        self._store = SecretStore(directory / "session.bin")
        self._session = self._store.load()
        self._lock = Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._key = self._load_key(directory / "pairing.key")
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

    def pairing_code(self) -> str:
        self.start()
        return f"{self.port}:{self._key}"

    def open(self, url: str = HOME_URL) -> None:
        if not self.is_student_url(url):
            raise ValueError("Only HTTPS XJTLU AMS student URLs can open automatically")
        self.start()
        with self._lock:
            student = dict(self._session)
        if url != HOME_URL and not student:
            self._notify("Login required: pair the browser companion and sign in")
            return

        if url != HOME_URL:
            state = self._ams.state(url)
            if not self._processing.acquire(blocking=False):
                self._notify(
                    "A student request is running; retry this record afterwards"
                )
                return
            self._notify("Student session available; waiting for the platform result")
            self._request_thread = Thread(
                target=self._process,
                args=(state, student["token"]),
                name="student-request",
                daemon=True,
            )
            self._request_thread.start()
            return
        self._notify("Complete student login in your normal paired browser")
        if not self._browser.open(url):
            self._notify("Cannot open the student page; check the installed browser")

    def _process(self, state: str, token: str) -> None:
        try:
            code, message = self._ams.process(state, token)
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
        except Exception as exception:
            self._notify(
                f"Cannot obtain a platform result: {type(exception).__name__}. "
                "Inspect the student login and retry manually."
            )
        finally:
            self._processing.release()

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

        if event == "ping":
            self._notify("Browser companion connected. " + self.status())
        elif event == "logout":
            with self._lock:
                self._store.save({})
                self._session = {}
            self._notify("Login required: student session expired or was cleared")
        elif event == "success":
            self._notify("The platform displayed its success page")
        elif event == "failure":
            self._notify("Platform did not confirm success; inspect the browser")
        else:
            raise ValueError("Unknown browser event")

    def _handler_type(self) -> type[BaseHTTPRequestHandler]:
        student = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self) -> None:
                super().setup()
                self.connection.settimeout(2)

            def do_OPTIONS(self) -> None:
                self.send_response(204)
                self._cors()
                self.end_headers()

            def do_POST(self) -> None:
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
                self._cors()
                self.end_headers()

            def _cors(self) -> None:
                origin = self.headers.get("Origin", "")
                if origin.startswith("chrome-extension://"):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header(
                        "Access-Control-Allow-Headers", "Authorization, Content-Type"
                    )
                    self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

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
        if self._request_thread is not None:
            self._request_thread.join(timeout=12)
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
