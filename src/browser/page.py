from pathlib import Path

from playwright.sync_api import sync_playwright

from adapters.base import AdapterResult
from adapters.registry import WebsiteAdapter
from browser.runtime import Chromium


class BrowserPage:
    """
    Run a trusted local adapter using the persistent Chromium profile.
    """

    def __init__(self, directory: Path) -> None:
        self._profile = directory / "chromium"

    def process(self, url: str, adapter: WebsiteAdapter) -> AdapterResult:
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
                if not isinstance(result, AdapterResult):
                    raise ValueError("Invalid website adapter result")
                return AdapterResult(result.result, result.details)
            finally:
                context.close()
