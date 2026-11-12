from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from .ams import Ams
from .runtime import Chromium


class StudentPage:
    """
    Process a QR state inside Chromium using its own saved AMS login.
    """

    def __init__(self, directory: Path) -> None:
        self._profile = directory / "chromium"
        self._script = Path(__file__).with_name("student_request.js")

    def process(self, state: str) -> tuple[int, str]:
        with sync_playwright() as runtime:
            context = runtime.chromium.launch_persistent_context(
                self._profile.resolve(),
                executable_path=Chromium().executable(),
                headless=True,
                ignore_default_args=["--enable-automation"],
                timeout=15000,
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                return self.request(page, state)
            finally:
                context.close()

    def request(self, page: Page, state: str) -> tuple[int, str]:
        page.goto(
            "https://ams.xjtlu.edu.cn/studentpc/checkIn",
            wait_until="domcontentloaded",
            timeout=15000,
        )
        if not page.url.startswith("https://ams.xjtlu.edu.cn/"):
            return 401, "Student login required"
        result = page.evaluate(self._script.read_text(encoding="utf-8"), state)
        return Ams.result(result)
