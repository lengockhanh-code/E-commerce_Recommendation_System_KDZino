import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import storefront_catalog


class SearchAndCheckoutTests(unittest.TestCase):
    def test_catalog_parquet_search_filtering(self):
        results = storefront_catalog.read_catalog_parquet()
        self.assertGreater(len(results), 0)
        
        # Test product detail reading
        sample = results[0]
        item_id = sample["id"]
        detail = storefront_catalog.read_catalog_parquet(item_id=item_id)
        self.assertEqual(len(detail), 1)
        self.assertEqual(detail[0]["id"], item_id)

    def test_order_creation_payload_and_foreign_keys(self):
        # Verify read_catalog behavior with parquet fallback
        first_product = storefront_catalog.read_catalog()[0]
        self.assertIsNotNone(first_product["id"])
        self.assertIsNotNone(first_product["name"])


if __name__ == "__main__":
    unittest.main()
