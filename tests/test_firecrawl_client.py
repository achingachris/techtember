import unittest

from techtember.firecrawl_client import FirecrawlClient


class LegacyClient:
    def search(self, query, limit=None, **kwargs):
        return {"web": [{"url": "https://example.com", "title": "Example"}]}

    def scrape_url(self, url, formats=None):
        return {"markdown": "# Example", "metadata": {"sourceURL": url}}

    def map_url(self, url, search=None):
        return {"links": ["https://example.com/about"]}

    def crawl_url(self, url, limit=None, scrape_options=None):
        return {"data": [{"markdown": "# Example", "metadata": {"sourceURL": url}}]}


class FlakyClient:
    def __init__(self):
        self.calls = 0

    def search(self, query, limit=None, **kwargs):
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("temporary failure")
        return {"web": [{"url": "https://example.com/recovered"}]}


class AdapterTests(unittest.TestCase):
    def test_supports_legacy_named_sdk_methods(self):
        client = FirecrawlClient(client=LegacyClient())
        self.assertEqual(client.search("example")[0].url, "https://example.com")
        self.assertEqual(client.scrape("https://example.com").markdown, "# Example")
        self.assertEqual(client.map("https://example.com"), ["https://example.com/about"])
        self.assertEqual(len(client.crawl("https://example.com")), 1)

    def test_retries_transient_sdk_errors(self):
        fake = FlakyClient()
        client = FirecrawlClient(client=fake, max_retries=2, backoff_seconds=0)
        self.assertEqual(client.search("example")[0].url, "https://example.com/recovered")
        self.assertEqual(fake.calls, 3)


if __name__ == "__main__":
    unittest.main()
