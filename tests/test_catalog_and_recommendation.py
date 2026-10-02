import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

import duckdb
from scripts import storefront_catalog as catalog
from scripts import recommendation_engine as rec_engine
from scripts import sync_catalog_to_postgres as catalog_sync


class CatalogAndRecommendationTests(unittest.TestCase):
    def test_parquet_catalog_reading(self):
        # Verify read_catalog returns structured Product dictionaries from parquet catalog
        results = catalog.read_catalog_parquet()
        self.assertTrue(len(results) > 0)
        first = results[0]
        self.assertIn("id", first)
        self.assertIn("name", first)
        self.assertIn("price", first)
        self.assertIn("c0_name", first)

    def test_parquet_catalog_detail(self):
        sample_id = "86680698"
        results = catalog.read_catalog_parquet(item_id=sample_id)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["id"], sample_id)

    def test_recommendation_engine_parquet_fallback(self):
        res = rec_engine.get_recommendations_parquet(context="home", limit=6)
        self.assertEqual(res["context"], "home")
        self.assertEqual(len(res["items"]), 6)
        self.assertIn("request_id", res)
        self.assertEqual(res["model_name"], "parquet_baseline_v1")

    def test_recommendation_engine_deduplication(self):
        trigger_id = "86680698"
        res = rec_engine.get_recommendations_parquet(context="product_detail", trigger_item_id=trigger_id, limit=6)
        item_ids = [item["id"] for item in res["items"]]
        self.assertNotIn(trigger_id, item_ids)

    def test_clean_string_and_float_helpers(self):
        self.assertIsNone(catalog_sync.clean_str("__UNK__"))
        self.assertIsNone(catalog_sync.clean_str("nan"))
        self.assertEqual(catalog_sync.clean_str(" Nike "), "Nike")
        self.assertEqual(catalog_sync.clean_float(19.99), 19.99)
        self.assertIsNone(catalog_sync.clean_float(-5.0))


if __name__ == "__main__":
    unittest.main()
