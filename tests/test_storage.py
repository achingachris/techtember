import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from techtember.models import PageRecord
from techtember.storage import Storage


def make_record(url="https://example.com/post"):
    return PageRecord(
        url=url,
        canonical_url=url,
        title="Python cloud engineering",
        description="A technology article",
        author="Ada",
        published_at="2026-09-01",
        source="test",
        query="python",
        markdown="# Python cloud engineering\n\nTechnology article",
        technologies=["Python", "cloud"],
        topics=["technology"],
        relevance_score=0.8,
        content_hash="abc",
        fetched_at=datetime.now(timezone.utc).isoformat(),
        raw_json='{"ok": true}',
    )


class StorageTests(unittest.TestCase):
    def test_upsert_and_full_text_search(self):
        with tempfile.TemporaryDirectory() as directory:
            with Storage(Path(directory) / "test.db") as storage:
                storage.upsert(make_record())
                self.assertEqual(storage.count(), 1)
                rows = storage.search("Python cloud")
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["title"], "Python cloud engineering")
                self.assertEqual(rows[0]["technologies"], ["Python", "cloud"])

    def test_upsert_updates_same_canonical_url(self):
        with tempfile.TemporaryDirectory() as directory:
            with Storage(Path(directory) / "test.db") as storage:
                storage.upsert(make_record())
                updated = make_record()
                updated.title = "Updated Python article"
                storage.upsert(updated)
                self.assertEqual(storage.count(), 1)
                self.assertEqual(storage.list_pages()[0]["title"], "Updated Python article")


if __name__ == "__main__":
    unittest.main()

