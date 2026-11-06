import tempfile
import unittest
from pathlib import Path
from curriculum import init, add_book, connect
from discovery import register_metadata, ROOT
from coverage_report import coverage_report

class CoverageReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "catalog.db")
        register_metadata(self.db, ROOT / "discovered_books.csv")
    def tearDown(self):
        self.tmp.cleanup()
    def test_counts_are_not_completeness_claims(self):
        report = coverage_report(self.db)
        self.assertEqual(len(report["grades"]), 12)
        self.assertEqual(report["totals"]["catalogued_books"], 5)
        self.assertEqual(report["totals"]["grades_with_books"], 5)
        self.assertFalse(report["ready_for_student_answers"])
    def test_pending_is_not_approved(self):
        report = coverage_report(self.db)
        self.assertEqual(report["totals"]["metadata_approved"], 0)
        self.assertEqual(report["totals"]["content_permitted"], 0)
        self.assertEqual(report["totals"]["content_extracted"], 0)
    def test_missing_metadata_visible(self):
        report = coverage_report(self.db)
        self.assertEqual(sum(g["missing_academic_year"] for g in report["grades"]), 5)
    def test_empty_grades_are_visible(self):
        report = coverage_report(self.db)
        self.assertEqual(report["grades"][0]["catalogued_books"], 0)
    def test_read_only(self):
        before = coverage_report(self.db)
        coverage_report(self.db)
        self.assertEqual(before, coverage_report(self.db))
    def test_approved_metadata_does_not_imply_content_permission(self):
        with connect(self.db) as db:
            db.execute("UPDATE books SET review_status='approved' WHERE id=(SELECT min(id) FROM books)")
        report = coverage_report(self.db)
        self.assertEqual(report["totals"]["metadata_approved"], 1)
        self.assertEqual(report["totals"]["content_permitted"], 0)

if __name__ == "__main__":
    unittest.main()
