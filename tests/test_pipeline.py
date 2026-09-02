import tempfile
import unittest
from pathlib import Path

from techtember.models import FetchedPage, SearchHit
from techtember.pipeline import TechtemberPipeline
from techtember.storage import Storage


class FakeClient:
    def search(self, query, limit=10, include_domains=None):
        return [
            SearchHit(
                url="https://example.com/python",
                title="Python engineering",
                description="Technology news",
            )
        ]

    def scrape(self, url):
        return FetchedPage(
            url=url,
            markdown="# Python engineering\n\nTechnology news for developers.",
            metadata={"title": "Python engineering"},
            raw={"source": "fake"},
        )


class PipelineTests(unittest.TestCase):
    def test_discover_scrapes_and_stores_hits(self):
        with tempfile.TemporaryDirectory() as directory:
            with Storage(Path(directory) / "test.db") as storage:
                pipeline = TechtemberPipeline(
                    client=FakeClient(),
                    storage=storage,
                    terms=["python", "technology"],
                )
                summary = pipeline.discover(["python"], limit=1)
                self.assertEqual(summary.discovered, 1)
                self.assertEqual(summary.fetched, 1)
                self.assertEqual(summary.stored, 1)
                self.assertEqual(storage.count(), 1)

    def test_excluded_domains_are_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            with Storage(Path(directory) / "test.db") as storage:
                pipeline = TechtemberPipeline(
                    client=FakeClient(),
                    storage=storage,
                    terms=["python"],
                    exclude_domains=["example.com"],
                )
                summary = pipeline.discover(["python"], limit=1)
                self.assertEqual(summary.stored, 0)
                self.assertEqual(summary.skipped, 1)


if __name__ == "__main__":
    unittest.main()

