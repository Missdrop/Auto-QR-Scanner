from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Protocol

from playwright.sync_api import Page


class WebsiteAdapter(Protocol):
    def matches(self, url: str) -> bool: ...

    def process(self, page: Page, url: str) -> tuple[int, str]: ...


class WebsiteAdapters:
    """Load trusted local adapters; no website implementations ship in Git."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._adapters: list[WebsiteAdapter] | None = None

    def find(self, url: str) -> WebsiteAdapter | None:
        if self._adapters is None:
            adapters = []
            for index, path in enumerate(sorted(self._directory.glob("*/adapter.py"))):
                try:
                    spec = spec_from_file_location(
                        f"local_website_adapter_{index}", path
                    )
                    if spec is None or spec.loader is None:
                        raise ValueError("Cannot load adapter")
                    module = module_from_spec(spec)
                    spec.loader.exec_module(module)
                    adapter = module.Adapter()
                    if not callable(adapter.matches) or not callable(adapter.process):
                        raise ValueError("Missing adapter methods")
                    adapters.append(adapter)
                except Exception:
                    raise ValueError(
                        "Cannot load website adapter; check adapter.py"
                    ) from None
            self._adapters = adapters
        try:
            return next(
                (adapter for adapter in self._adapters if adapter.matches(url)), None
            )
        except Exception:
            raise ValueError("Website adapter matching failed") from None
