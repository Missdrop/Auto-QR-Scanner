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
    """Separate website interaction from interpretation of its response."""

    version = ""
    description = ""

    @abstractmethod
    def matches(self, url: str) -> bool:
        """Return whether this adapter handles the URL."""
        raise NotImplementedError

    @abstractmethod
    def process(self, page: Page, url: str) -> object:
        """Perform website processing once and return its raw response."""
        raise NotImplementedError

    @abstractmethod
    def get_result(self, response: object) -> str:
        """Extract the result text from the original response."""
        raise NotImplementedError

    @abstractmethod
    def get_details(self, response: object) -> str:
        """Extract details from the same response."""
        raise NotImplementedError

    def execute(self, page: Page, url: str) -> AdapterResult:
        response = self.process(page, url)
        return AdapterResult(self.get_result(response), self.get_details(response))
