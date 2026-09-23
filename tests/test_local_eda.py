"""Execute every local EDA cell with real Parquet samples and edge cases."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / 'training/eda_local_merrec_professional.ipynb'


class LocalEdaTests(unittest.TestCase):
    def run_notebook(self, table, exact=False, save_figures=False):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as directory:
            folder = Path(directory)
            data = folder / 'input'
            data.mkdir()
            pq.write_table(table, data / 'sample.parquet')
            namespace = {'__name__': '__main__'}
            notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
            log = io.StringIO()
            count = 0
            try:
                figure_patch = contextlib.nullcontext() if save_figures else patch.object(plt, 'savefig')
                with patch.dict(os.environ, {'MERREC_EDA_DATA': str(data), 'MERREC_EDA_OUTPUT': str(folder / 'output')}), contextlib.redirect_stdout(log), patch.object(plt, 'show'), figure_patch:
                    for index, cell in enumerate(notebook['cells']):
                        if cell['cell_type'] != 'code':
                            continue
                        try:
                            exec(compile(''.join(cell['source']), f'{NOTEBOOK.name}:cell-{index}', 'exec'), namespace)
                            if index == 3 and exact:
                                namespace['USE_EXACT_DISTINCT'] = True
                                namespace['RUN_EXACT_DUPLICATE'] = True
                        except Exception as error:
                            self.fail(f'Cell {index} failed: {error}\n{log.getvalue()[-3000:]}')
                        count += 1
                self.assertEqual(count, 39)
                summary = json.loads((folder / 'output/eda_summary.json').read_text(encoding='utf-8'))
                self.assertEqual(summary['rows'], table.num_rows)
                self.assertEqual(int(namespace['event_counts']['count'].sum()), table.num_rows)
                self.assertTrue((folder / 'output/tables/00_master_summary.csv').is_file())
                if save_figures:
                    self.assertGreaterEqual(len(list((folder / 'output/figures').glob('*.png'))), 20)
                return namespace
            finally:
                if 'con' in namespace:
                    namespace['con'].close()
                plt.close('all')

    def test_real_parquet_sample(self):
        files = sorted((ROOT / 'data/raw/20230501').glob('*.parquet'))
        if not files:
            self.skipTest('Local MerRec Parquet not available')
        batch = next(pq.ParquetFile(files[0]).iter_batches(batch_size=20000))
        result = self.run_notebook(pa.Table.from_batches([batch]), save_figures=True)
        self.assertIsNotNone(result['price_stats'])
        self.assertEqual(result['invalid_times'], 0)

    def test_duplicate_null_price_and_session_boundaries(self):
        # Same session id across users must not create cross-user transitions.
        rows = [
            {'user_id': 1, 'item_id': 10, 'event_id': 'item_view', 'stime': 1683000000000, 'session_id': 's', 'price': None, 'c0_name': None, 'sequence_id': 'a', 'sequence_length': None},
            {'user_id': 1, 'item_id': 10, 'event_id': 'buy_comp', 'stime': 1683000001000, 'session_id': 's', 'price': None, 'c0_name': None, 'sequence_id': 'a', 'sequence_length': None},
            {'user_id': 2, 'item_id': 20, 'event_id': 'item_like', 'stime': 1683000002000, 'session_id': 's', 'price': None, 'c0_name': None, 'sequence_id': 'b', 'sequence_length': None},
            {'user_id': None, 'item_id': None, 'event_id': None, 'stime': None, 'session_id': None, 'price': None, 'c0_name': None, 'sequence_id': None, 'sequence_length': None},
        ]
        rows.append(dict(rows[0]))
        result = self.run_notebook(pa.Table.from_pylist(rows), exact=True)
        self.assertEqual(result['exact_dup'], 1)
        self.assertEqual(result['pair_count'], 2)
        self.assertEqual(result['sparsity'], 0.5)
        self.assertIsNone(result['price_stats'])
        self.assertIsNone(result['seq_stats'])
        self.assertNotIn('item_like', result['trans_pct'].columns)
        self.assertEqual(result['overview']['min_time'][:10], '2023-05-02')

    def test_optional_columns_absent_and_invalid_times(self):
        table = pa.table({'user_id': [1,2], 'item_id': [10,20], 'event_id': ['item_view','buy_comp'], 'stime': ['invalid',None]})
        result = self.run_notebook(table)
        self.assertIsNone(result['overview']['sessions'])
        self.assertIsNone(result['peak_hour'])
        self.assertIsNone(result['trans_pct'])
        self.assertEqual(result['invalid_times'], 2)

    def test_all_null_keys(self):
        table = pa.table({'user_id': pa.array([None], pa.int64()), 'item_id': pa.array([None], pa.int64()), 'event_id': pa.array([None], pa.string()), 'stime': pa.array([None], pa.timestamp('us'))})
        result = self.run_notebook(table)
        self.assertIsNone(result['sparsity'])
        self.assertEqual(result['user_stats']['entities'], 0)


if __name__ == '__main__':
    unittest.main()
