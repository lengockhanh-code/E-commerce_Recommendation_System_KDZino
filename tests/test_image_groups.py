import csv
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import resolve_images_to_sql as app


class GroupTests(unittest.TestCase):
    def test_shared_search_null_resume_and_retry(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            fields = ['item_id', 'name', 'brand_name', 'c0_name', 'c1_name', 'c2_name', 'color']
            rows = []
            for i, name in enumerate(['A', ' a ', 'missing', 'missing', 'error', 'error', 'A'], 1):
                rows.append(dict(item_id=i, name=name, brand_name='Brand', c0_name='Home',
                                 c1_name='Decor', c2_name='Art', color='red'))
            rows.append(dict(rows[0], item_id=8, color='blue'))
            for part, subset in enumerate([rows[:4], rows[4:]], 1):
                with (root / f'product_catalog_part_{part:03}.csv').open('w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(subset)
            args = ['resolver', '--input-dir', str(root), '--db', str(root/'test.db'),
                    '--sql', str(root/'test.sql'), '--workers', '2']

            def fake(row, args):
                name = row['name'].strip().lower()
                if name == 'missing':
                    return (None, 'no_match', 0.0, None, None)
                if name == 'error':
                    return (None, 'error', 0.0, None, 'timeout')
                return ("https://example.com/a'b.jpg", 'ok', 90.0, None, None)

            with patch.object(sys, 'argv', args), patch.object(app, 'resolve', side_effect=fake) as search:
                app.main()
                self.assertEqual(search.call_count, 4)
            with sqlite3.connect(':memory:') as con:
                con.executescript((root/'test.sql').read_text(encoding='utf-8'))
                self.assertEqual(con.execute('SELECT COUNT(*) FROM product_images').fetchone()[0], 8)
                self.assertEqual(con.execute('SELECT COUNT(*) FROM product_images WHERE image_url IS NULL').fetchone()[0], 4)
                urls = con.execute('SELECT image_url FROM product_images WHERE item_id IN (1,2,7)').fetchall()
                self.assertEqual(len(set(urls)), 1)
            with patch.object(sys, 'argv', args), patch.object(app, 'resolve', return_value=('https://example.com/retry.jpg', 'ok', 90.0, None, None)) as search:
                app.main()
                self.assertEqual(search.call_count, 1)
            with patch.object(sys, 'argv', args), patch.object(app, 'resolve') as search:
                app.main()
                search.assert_not_called()

    def test_key_preserves_model_and_category_differences(self):
        from argparse import Namespace
        args = Namespace(min_score=55, max_results=10)
        self.assertNotEqual(app.group_key({'name':'AB-12'}, args), app.group_key({'name':'AB 12'}, args))
        self.assertNotEqual(app.group_key({'name':'áo'}, args), app.group_key({'name':'ao'}, args))
        self.assertNotEqual(app.group_key({'name':'A','c2_name':'X'}, args), app.group_key({'name':'A','c2_name':'Y'}, args))


if __name__ == '__main__':
    unittest.main()
