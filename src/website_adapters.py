from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from .adapter import WebsiteAdapter


class WebsiteAdapters:
    """Load trusted local adapters; no website implementations ship in Git."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._adapters: list[WebsiteAdapter] | None = None
        self._information: list[dict[str, str]] = []

    def information(self) -> list[dict[str, str]]:
        self._load()
        return [dict(row) for row in self._information]

    def find(self, url: str) -> WebsiteAdapter | None:
        self._load()
        if any(row["status"] == "error" for row in self._information):
            raise ValueError("Cannot load website adapter; check adapter.py")
        try:
            return next(
                (adapter for adapter in self._adapters or [] if adapter.matches(url)),
                None,
            )
        except Exception:
            raise ValueError("Website adapter matching failed") from None

    def _load(self) -> None:
        if self._adapters is None:
            adapters = []
            for index, path in enumerate(sorted(self._directory.glob("*/adapter.py"))):
                row = {
                    "name": path.parent.name,
                    "version": "",
                    "description": "",
                    "path": str(path.resolve()),
                    "status": "error",
                    "error": "",
                }
                try:
                    spec = spec_from_file_location(
                        f"local_website_adapter_{index}", path
                    )
                    if spec is None or spec.loader is None:
                        raise ValueError("Cannot load adapter")
                    module = module_from_spec(spec)
                    spec.loader.exec_module(module)
                    adapter = module.Adapter()
                    if not isinstance(adapter, WebsiteAdapter):
                        raise ValueError("Adapter must inherit WebsiteAdapter")
                    for key in ("version", "description"):
                        value = getattr(adapter, key, row[key])
                        if isinstance(value, str):
                            row[key] = value[:1000]
                    adapters.append(adapter)
                    row["status"] = "loaded"
                except Exception as exception:
                    row["error"] = type(exception).__name__
                self._information.append(row)
            self._adapters = adapters
