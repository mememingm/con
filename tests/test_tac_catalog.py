import csv
import tempfile
import unittest
from pathlib import Path

from sms_console.tac_catalog import TacCatalog


class TacCatalogTests(unittest.TestCase):
    def write_csv(self, directory, rows):
        path = Path(directory) / 'tac.csv'
        with path.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['Brand', 'TAC', 'SPECS'])
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_csv_builds_unique_and_ambiguous_candidates_without_xlsx(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(tmp, [
                {'Brand': 'Acme', 'TAC': '12345678', 'SPECS': 'One'},
                {'Brand': 'Acme', 'TAC': '12345678', 'SPECS': 'One'},
                {'Brand': 'Other', 'TAC': '87654321', 'SPECS': 'Two'},
                {'Brand': 'Other2', 'TAC': '87654321', 'SPECS': 'Three'},
                {'Brand': 'Bad', 'TAC': '1234567', 'SPECS': 'Short'},
                {'Brand': 'Blank', 'TAC': '', 'SPECS': 'Blank'},
            ])
            catalog = TacCatalog.from_csv(path, source='fixture.csv', data_updated_at='fixture')

            matched = catalog.lookup('12345678')
            ambiguous = catalog.lookup('87654321')
            unknown = catalog.lookup('1234567')

        self.assertEqual(matched['model_status'], 'matched')
        self.assertEqual(len(matched['candidates']), 1)
        self.assertEqual(ambiguous['model_status'], 'ambiguous')
        self.assertEqual(len(ambiguous['candidates']), 2)
        self.assertEqual(unknown['model_status'], 'unknown')
        self.assertEqual(catalog.stats['valid_rows'], 4)
        self.assertEqual(catalog.stats['invalid_rows'], 2)
        self.assertEqual(catalog.source, 'fixture.csv')
        self.assertEqual(catalog.data_updated_at, 'fixture')
        self.assertTrue(catalog.data_version.startswith('sha256:'))

    def test_lookup_does_not_left_pad_short_tac(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(tmp, [
                {'Brand': 'Acme', 'TAC': '00123456', 'SPECS': 'Eight digits'},
            ])
            catalog = TacCatalog.from_csv(path)

        self.assertEqual(catalog.lookup('123456')['model_status'], 'unknown')
        self.assertEqual(catalog.lookup('00123456')['model_status'], 'matched')


if __name__ == '__main__':
    unittest.main()
