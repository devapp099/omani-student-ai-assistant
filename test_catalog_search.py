import tempfile
import unittest
from pathlib import Path

from curriculum import init, add_book
from discovery import register_metadata, ROOT
from catalog_search import find_books

class BookSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "search.db")
        register_metadata(self.db, ROOT / "discovered_books.csv")
    def tearDown(self):
        self.tmp.cleanup()
    def test_find_by_grade(self):
        rows = find_books(self.db, grade=7)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["grade"], 7)
        self.assertIn("ict.moe.gov.om", rows[0]["source_url"])
    def test_find_by_subject_and_title(self):
        rows = find_books(self.db, subject="تقنية", query="العاشر")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["grade"], 10)
    def test_metadata_not_content(self):
        rows = find_books(self.db)
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r["metadata_review"] == "pending" for r in rows))
        self.assertTrue(all(r["content_rights"] == "unknown" for r in rows))
        self.assertTrue(all(r["content_available"] is False for r in rows))
        self.assertTrue(all("text" not in r and "chunks" not in r for r in rows))
    def test_invalid_filters(self):
        with self.assertRaises(ValueError): find_books(self.db, grade=13)
        with self.assertRaises(ValueError): find_books(self.db, semester=3)
        with self.assertRaises(ValueError): find_books(self.db, limit=0)
    def test_sql_injection_is_inert(self):
        self.assertEqual(find_books(self.db, query="' OR 1=1 --"), [])
        self.assertEqual(len(find_books(self.db)), 5)
    def test_limit_and_empty_result(self):
        self.assertEqual(len(find_books(self.db,limit=2)),2)
        self.assertEqual(find_books(self.db,grade=1),[])
    def test_no_data_writes(self):
        before = find_books(self.db)
        find_books(self.db, query="تقنية")
        self.assertEqual(before,find_books(self.db))

if __name__ == "__main__":
    unittest.main()
