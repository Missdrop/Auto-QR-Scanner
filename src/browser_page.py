from pathlib import Path

from playwright.sync_api import sync_playwright

from .runtime import Chromium
from .website_adapters import WebsiteAdapter


class BrowserPage:
    """
    Run a trusted local adapter using the persistent Chromium profile.
    """

    def __init__(self, directory: Path) -> None:
        self._profile = directory / "chromium"

    def process(self, url: str, adapter: WebsiteAdapter) -> tuple[int, str]:
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
                result = adapter.process(page, url)
                if (
                    not isinstance(result, tuple)
                    or len(result) != 2
                    or type(result[0]) is not int
                    or not isinstance(result[1], str)
                ):
                    raise ValueError("Invalid website adapter result")
                return result[0], result[1][:1000]
            finally:
                context.close()
