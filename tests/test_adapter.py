import unittest
from unittest.mock import Mock

from adapters.base import AdapterResult, WebsiteAdapter


class AdapterTest(unittest.TestCase):
    def test_missing_extraction_method_prevents_instantiation(self):
        class Incomplete(WebsiteAdapter):
            def matches(self, url):
                return True

            def process(self, page, url):
                return {}

            def get_result(self, response):
                return "Example"

        with self.assertRaises(TypeError):
            Incomplete()

    def test_default_execution_shares_one_response_without_repeating_request(self):
        response = {"result": "Custom wording", "details": "Original description"}
        calls = []

        class Example(WebsiteAdapter):
            def matches(self, url):
                return True

            def process(self, page, url):
                calls.append("process")
                return response

            def get_result(self, value):
                self_result = value is response
                calls.append(self_result)
                return value["result"]

            def get_details(self, value):
                calls.append(value is response)
                return value["details"]

        result = Example().execute(Mock(), "https://example.com/qr")
        self.assertEqual(calls, ["process", True, True])
        self.assertEqual(result.result, "Custom wording")
        self.assertEqual(result.details, "Original description")

    def test_invalid_presentation_fields_are_rejected(self):
        for result, description in [("", ""), ("x" * 201, ""), ("ok", "x" * 4001)]:
            with self.assertRaises(ValueError):
                AdapterResult(result, description)
