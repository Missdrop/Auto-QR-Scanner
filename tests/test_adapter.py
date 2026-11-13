import unittest
from unittest.mock import Mock

from adapters.base import AdapterResult, WebsiteAdapter


class AdapterTest(unittest.TestCase):
    def test_missing_processing_method_prevents_instantiation(self):
        class Incomplete(WebsiteAdapter):
            def matches(self, url):
                return True

        with self.assertRaises(TypeError):
            Incomplete()

    def test_adapter_returns_its_result_directly(self):
        page = Mock()

        class Example(WebsiteAdapter):
            def matches(self, url):
                return True

            def process(self, page, url):
                page.goto(url)
                return AdapterResult(result="Custom wording", details=page.title())

        page.title.return_value = "Original description"
        result = Example().process(page, "https://example.com/qr")
        page.goto.assert_called_once_with("https://example.com/qr")
        self.assertEqual(result.result, "Custom wording")
        self.assertEqual(result.details, "Original description")
        self.assertEqual(AdapterResult("Opened").details, "")

    def test_invalid_presentation_fields_are_rejected(self):
        for result, details in [
            ("", ""),
            ("   ", ""),
            ("x" * 201, ""),
            ("ok", "x" * 4001),
            (None, ""),
            ("ok", None),
        ]:
            with self.subTest(result=result, details=details):
                with self.assertRaises(ValueError):
                    AdapterResult(result, details)
