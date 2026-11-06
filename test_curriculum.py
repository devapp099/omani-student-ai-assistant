import tempfile
import unittest
import sqlite3
from pathlib import Path
from curriculum import init, report, add_book

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "test.db")
        init(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_seed_and_idempotency(self):
        init(self.db)
        self.assertEqual(report(self.db)["grades"], 12)
        self.assertEqual(report(self.db)["sources"], 6)
        self.assertEqual(report(self.db)["books"], 0)

    def test_grade_validation(self):
        with self.assertRaises(ValueError):
            add_book(self.db, {"grade":13,"subject":"تجربة","title":"تجربة"})

    def test_book_metadata_and_no_automatic_approval(self):
        add_book(self.db, {"grade":5,"subject":"تجربة","title":"كتاب تجريبي"})
        self.assertEqual(report(self.db)["books"], 1)
        self.assertEqual(report(self.db)["approved_books"], 0)

    def test_duplicate_rejected(self):
        book = {"grade":5,"subject":"تجربة","title":"كتاب تجريبي"}
        add_book(self.db, book)
        with self.assertRaises(sqlite3.IntegrityError):
            add_book(self.db, book)

    def test_http_rejected(self):
        with self.assertRaises(ValueError):
            add_book(self.db, {"grade":1,"subject":"تجربة","title":"تجربة","url":"http://example.com/book.pdf"})

if __name__ == "__main__":
    unittest.main()
