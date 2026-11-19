from pathlib import Path

from playwright.sync_api import BrowserContext


class BrowserScripts:
    """Load optional page initialization from trusted local adapter folders."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or (
            Path(__file__).resolve().parents[2] / "website_adapters"
        )

    def paths(self) -> list[Path]:
        return sorted(self.directory.glob("*/browser.js"))

    def configure(self, context: BrowserContext) -> None:
        for path in self.paths():
            if path.stat().st_size > 256 * 1024:
                raise ValueError("Browser initialization script is too large")
            context.add_init_script(path=path)
