import csv
import tempfile
import unittest
from pathlib import Path
from discovery import ROOT,check_catalog,register_metadata
from curriculum import report

class DiscoveryTests(unittest.TestCase):
    def test_catalog_has_five_rows(self):
        self.assertEqual(len(check_catalog(ROOT/'discovered_books.csv')),5)
    def test_register_idempotent_and_unapproved(self):
        with tempfile.TemporaryDirectory() as d:
            db=str(Path(d)/'books.sqlite3')
            self.assertEqual(register_metadata(db,ROOT/'discovered_books.csv'),5)
            self.assertEqual(register_metadata(db,ROOT/'discovered_books.csv'),0)
            r=report(db)
            self.assertEqual((r['books'],r['approved_books'],r['chunks']),(5,0,0))
    def test_reject_unofficial_domain(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'catalog.csv'
            with (ROOT/'discovered_books.csv').open(encoding='utf-8',newline='') as f:
                source=csv.DictReader(f);fields=source.fieldnames;rows=list(source)
            rows[0]['source_url']='https://ict.moe.gov.om.evil.example/book/'
            with target.open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
            with self.assertRaisesRegex(ValueError,'untrusted'):
                check_catalog(target)
    def test_reject_claimed_rights(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'catalog.csv'
            with (ROOT/'discovered_books.csv').open(encoding='utf-8',newline='') as f:
                source=csv.DictReader(f);fields=source.fieldnames;rows=list(source)
            rows[0]['rights_status']='permitted'
            with target.open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
            with self.assertRaisesRegex(ValueError,'written authorization'):
                check_catalog(target)
if __name__=='__main__': unittest.main()
