import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb
from scripts.similar_products import fetch_similar
from scripts import recommendation_engine as engine


class SimilarProductsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "catalog.parquet"
        with duckdb.connect() as con:
            con.execute("CREATE TABLE products(item_id VARCHAR, name VARCHAR, brand VARCHAR, category0 VARCHAR, category1 VARCHAR, category2 VARCHAR, price DOUBLE)")
            con.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", [
                ("seed", "Bmx oldschool V handlebars", "Others Follow", "Sports", "Outdoors", "Biking Equipment", 39),
                ("good", "BMX handlebar", None, "Sports", "Outdoors", "Biking Equipment", 40),
                ("tires", "BMX oldschool tires", "Others Follow", "Sports", "Outdoors", "Biking Equipment", 39),
                ("stem", "BMX handlebar neck stem", None, "Sports", "Outdoors", "Biking Equipment", 39),
                ("pad", "BMX sleeping pad", "Others Follow", "Sports", "Outdoors", "Camping", 39),
                ("tennis", "Tennis rackets", "Others Follow", "Sports", "Tennis", "Rackets", 39),
                ("substring", "Bmx handlebars", None, "Other", "Outdoors", "Biking Equipment", 39),
                ("missing", "BMX handlebars", None, "Sports", "Outdoors", None, 39),
                ("generic", "new black large", None, "Sports", "Outdoors", "Biking Equipment", 39),
            ])
            con.sql("SELECT * FROM products").write_parquet(str(self.path))

    def test_same_type_and_full_category_path_without_backfill(self):
        rows = fetch_similar("seed", 12, self.path)
        self.assertEqual([r["item_id"] for r in rows], ["good"])
        self.assertEqual(rows, fetch_similar("seed", 12, self.path))

    def test_unknown_id_and_sql_input_do_not_return_random_products(self):
        for item_id in ("absent", "seed' OR 1=1 --", "missing", "generic"):
            with self.subTest(item_id=item_id):
                self.assertEqual(fetch_similar(item_id, 12, self.path), [])

    def test_invalid_limit_and_missing_dependency(self):
        with self.assertRaises(ValueError):
            fetch_similar("seed", 0, self.path)
        with self.assertRaises(duckdb.IOException):
            fetch_similar("seed", 12, self.path.parent / "absent.parquet")

    def test_detail_fallback_uses_strict_catalog_policy(self):
        with patch.dict("os.environ", {"MERREC_CATALOG_PATH": str(self.path)}), patch.object(engine, "attach_product_images", side_effect=lambda items, dsn: items):
            result = engine.get_recommendations_parquet("product_detail", "seed", 12)
        self.assertEqual([p["id"] for p in result["items"]], ["good"])
        self.assertEqual(result["model_name"], "catalog_similar_v2")


if __name__ == "__main__":
    unittest.main()
