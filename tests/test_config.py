import json
import tempfile
import unittest
from pathlib import Path

from techtember.config import load_settings


class ConfigTests(unittest.TestCase):
    def test_platform_terms_and_sites_are_loaded(self):
        config = {
            "search_terms": [
                {"name": "X search", "platform": "x", "query": "AI launch"},
                {"name": "Google search", "platform": "google", "query": "AI news"},
            ],
            "crawl_sites": [
                {
                    "name": "Tech blog",
                    "url": "https://example.com/blog",
                    "limit": 5,
                    "include_paths": ["/blog/*"],
                    "max_depth": 1,
                },
                {"url": "https://example.org", "enabled": False},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seeds.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            settings = load_settings(path)

        self.assertEqual([seed.platform for seed in settings.search_seeds], ["x", "google"])
        self.assertEqual(settings.search_seeds[0].include_domains, ["x.com", "twitter.com"])
        self.assertEqual(settings.crawl_sites[0].name, "Tech blog")
        self.assertEqual(settings.crawl_sites[0].limit, 5)
        self.assertEqual(settings.crawl_sites[0].include_paths, ["/blog/*"])
        self.assertEqual(settings.crawl_sites[0].max_depth, 1)
        self.assertFalse(settings.crawl_sites[1].enabled)


if __name__ == "__main__":
    unittest.main()
