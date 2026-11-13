import unittest

from browser.address_filter import AddressFilter


class AddressFilterTest(unittest.TestCase):
    def test_empty_filter_allows_web_addresses(self):
        addresses = AddressFilter(" \n\n")
        self.assertTrue(addresses.allows("https://example.com/qr"))
        self.assertTrue(addresses.allows("http://other.example:8080/"))

    def test_domain_is_exact_and_case_insensitive(self):
        addresses = AddressFilter("Example.com\nsecond.example")
        self.assertTrue(addresses.allows("https://EXAMPLE.com/path"))
        self.assertTrue(addresses.allows("http://second.example/"))
        for url in [
            "https://example.com.evil.com/",
            "https://sub.example.com/",
            "https://evil.com/?next=example.com",
            "https://example.com@evil.com/",
        ]:
            self.assertFalse(addresses.allows(url), url)

    def test_full_url_matches_scheme_port_and_path_prefix(self):
        addresses = AddressFilter("https://example.com/qr/\nhttp://localhost:8080/a")
        self.assertTrue(addresses.allows("https://example.com:443/qr/one?state=x"))
        self.assertTrue(addresses.allows("http://localhost:8080/abc"))
        for url in [
            "http://example.com/qr/",
            "https://example.com:8443/qr/",
            "https://example.com/other/",
            "http://localhost:8081/a",
            "https://example.com:0/qr/",
        ]:
            self.assertFalse(addresses.allows(url), url)

    def test_query_and_fragment_prefixes_are_preserved(self):
        addresses = AddressFilter("https://example.com/qr/#/?state=")
        self.assertTrue(addresses.allows("https://example.com/qr/#/?state=abc"))
        self.assertFalse(addresses.allows("https://example.com/qr/#/?other=abc"))

    def test_invalid_rules_fail_closed(self):
        for rule in [
            "*.example.com",
            "https://",
            "https://example.com:bad/",
            ".",
            "ftp://example.com",
            "example.com/path",
            "https://user@example.com/",
            "example.com\\evil",
            "example .com",
        ]:
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                AddressFilter(rule)

    def test_malformed_addresses_are_never_allowed(self):
        for url in [
            "file:///tmp/a",
            "javascript:alert(1)",
            "https://example.com:bad/",
            "https://example.com\\@evil.com/",
            "https://exam\nple.com/",
        ]:
            self.assertFalse(AddressFilter("").allows(url), url)
