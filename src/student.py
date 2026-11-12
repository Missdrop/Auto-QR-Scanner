import json
from collections.abc import Callable
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import BrowserContext, Page, Response, sync_playwright

HOME_URL = "https://ams.xjtlu.edu.cn/studenth5/"


class Student:
    """
    Own a persistent student browser on one dedicated thread.

    Credentials are entered on the university page. Session data stays in the
    private browser profile, including AMS sessionStorage restored after restart.
    """

    def __init__(self, profile_path: Path, notify: Callable[[str], None]) -> None:
        self._profile_path = profile_path
        self._notify = notify
        self._commands: Queue[str | None] = Queue(maxsize=100)
        self._thread: Thread | None = None
        self._stop = Event()
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._session_present = False

    def open(self, url: str = HOME_URL) -> None:
        if not self.is_student_url(url):
            raise ValueError("Only HTTPS XJTLU AMS student URLs can open automatically")
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = Thread(target=self._run, name="student-browser", daemon=True)
            self._thread.start()
        self._commands.put_nowait(url)

    @staticmethod
    def is_student_url(url: str) -> bool:
        parts = urlsplit(url)
        return (
            parts.scheme == "https"
            and parts.netloc == "ams.xjtlu.edu.cn"
            and parts.path == "/studenth5/"
        )

    def close(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=2)

    def _run(self) -> None:
        try:
            with sync_playwright() as playwright:
                self._profile_path.mkdir(parents=True, exist_ok=True)
                self._context = playwright.chromium.launch_persistent_context(
                    str(self._profile_path),
                    channel="msedge",
                    headless=False,
                    viewport={"width": 480, "height": 850},
                )
                self._context.add_init_script("""
                    if (location.origin === 'https://ams.xjtlu.edu.cn') {
                        const stored = localStorage.getItem('autoQrStudentSession');
                        if (stored && !sessionStorage.getItem('amsuserInfo')) {
                            sessionStorage.setItem('amsuserInfo', stored);
                        }
                    }
                """)
                self._page = self._context.pages[0]
                self._page.on("response", self._on_response)
                self._process_commands()
        except Exception:
            # Browser closure and missing Edge are recoverable through Login.
            self._notify(
                "Student browser unavailable. "
                "Close its window and try Student login again."
            )
        finally:
            if self._context is not None:
                try:
                    self._context.close()
                except Exception:
                    pass
            self._page = None
            self._context = None
            self._session_present = False
            while not self._commands.empty():
                self._commands.get_nowait()

    def _process_commands(self) -> None:
        while (
            not self._stop.is_set()
            and self._page is not None
            and not self._page.is_closed()
        ):
            try:
                url = self._commands.get_nowait()
            except Empty:
                self._page.wait_for_timeout(300)
                self._capture_session()
                continue

            if url is None:
                return
            self._navigate(url)

    def _capture_session(self) -> dict[str, object] | None:
        if self._page is None:
            return None
        if urlsplit(self._page.url).hostname != "ams.xjtlu.edu.cn":
            return None

        raw = self._page.evaluate("sessionStorage.getItem('amsuserInfo')")
        if not raw:
            return None
        try:
            student = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not student.get("token") or not student.get("userId"):
            return None

        self._page.evaluate(
            "value => localStorage.setItem('autoQrStudentSession', value)",
            raw,
        )
        if not self._session_present:
            self._session_present = True
            self._notify("Student session available; platform validates it on use")
        return student

    def _navigate(self, url: str) -> None:
        if self._page is None:
            return
        if self._page.url == "about:blank":
            self._page.goto(HOME_URL, wait_until="domcontentloaded", timeout=30000)

        student = self._capture_session()
        if url != HOME_URL and student is None:
            self._notify(
                "Login required: sign in with your student account, then Retry"
            )
            self._page.bring_to_front()
            return

        # AMS accepts the current user and token on its published QR route.
        if student is not None and url != HOME_URL:
            url = self._authenticated_url(url, student)
        self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        self._page.bring_to_front()
        if student is None:
            self._notify("Login required: complete student login in the browser")
        else:
            self._notify("Student session available; waiting for platform validation")

    @staticmethod
    def _authenticated_url(url: str, student: dict[str, object]) -> str:
        parts = urlsplit(url)
        route, _, query = parts.fragment.partition("?")
        parameters = dict(parse_qsl(query))
        parameters["userId"] = str(student["userId"])
        parameters["token"] = str(student["token"])
        fragment = route + "?" + urlencode(parameters)
        return urlunsplit(parts._replace(fragment=fragment))

    def _on_response(self, response: Response) -> None:
        if urlsplit(response.url).hostname != "ams.xjtlu.edu.cn":
            return
        if response.request.resource_type not in {"xhr", "fetch"}:
            return
        try:
            payload = response.json()
        except Exception:
            return
        if not isinstance(payload, dict):
            return

        if payload.get("code") == 401:
            if self._page is not None:
                self._page.evaluate("""
                    localStorage.removeItem('autoQrStudentSession');
                    sessionStorage.removeItem('amsuserInfo');
                """)
            self._session_present = False
            self._notify("Login required: student session expired")
            return

        details = payload.get("data")
        if isinstance(details, dict) and isinstance(details.get("checkInfo"), dict):
            check = details["checkInfo"]
            if check.get("code") == 0:
                self._notify("Platform confirmed successful processing")
            else:
                self._notify("Platform did not confirm success; inspect the browser")
