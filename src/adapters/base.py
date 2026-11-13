from abc import ABC, abstractmethod

from playwright.sync_api import Page


class AdapterResult:
    """Describe a website result using text chosen entirely by the adapter."""

    def __init__(self, result: str, details: str = "") -> None:
        if not isinstance(result, str) or not result.strip() or len(result) > 200:
            raise ValueError("Invalid adapter result text")
        if not isinstance(details, str) or len(details) > 4000:
            raise ValueError("Invalid adapter details")
        self.result = result
        self.details = details


class WebsiteAdapter(ABC):
    """Match website links and process them using the saved browser session."""

    version = ""
    description = ""

    @abstractmethod
    def matches(self, url: str) -> bool:
        """Return whether this adapter handles the URL."""
        raise NotImplementedError

    @abstractmethod
    def process(self, page: Page, url: str) -> AdapterResult:
        """Process the website once and return its result text and details."""
        raise NotImplementedError
