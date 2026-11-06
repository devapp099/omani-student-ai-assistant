import tempfile
import unittest
from pathlib import Path
from curriculum import connect
from discovery import register_metadata, ROOT
from metadata_audit import audit

class MetadataAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "audit.db")
        register_metadata(self.db, ROOT / "discovered_books.csv")
    def tearDown(self):
        self.tmp.cleanup()
    def mutate(self, statement):
        with connect(self.db) as db:
            db.execute(statement)
    def test_pending_catalogue_not_ready(self):
        report = audit(self.db)
        self.assertEqual(report["books_checked"], 5)
        self.assertEqual(report["errors"], 0)
        self.assertFalse(report["safe_to_enable_content"])
    def test_missing_source_is_warning(self):
        self.mutate("UPDATE books SET url=NULL WHERE id=(SELECT min(id) FROM books)")
        self.assertIn("missing_book_url", [f["code"] for f in audit(self.db)["findings"]])
    def test_rejects_insecure_url(self):
        self.mutate("UPDATE books SET url='http://example.org/book' WHERE id=(SELECT min(id) FROM books)")
        self.assertIn("invalid_book_url", [f["code"] for f in audit(self.db)["findings"]])
    def test_permission_requires_review(self):
        self.mutate("UPDATE books SET rights_status='permitted' WHERE id=(SELECT min(id) FROM books)")
        self.assertIn("permission_without_review", [f["code"] for f in audit(self.db)["findings"]])
    def test_extraction_requires_both_approvals(self):
        self.mutate("UPDATE books SET extraction_status='completed' WHERE id=(SELECT min(id) FROM books)")
        self.assertIn("unsafe_extraction_state", [f["code"] for f in audit(self.db)["findings"]])
    def test_rejected_metadata_cannot_be_permitted(self):
        self.mutate("UPDATE books SET review_status='rejected',rights_status='permitted' WHERE id=(SELECT min(id) FROM books)")
        self.assertIn("rejected_but_permitted", [f["code"] for f in audit(self.db)["findings"]])
    def test_unknown_state_detected(self):
        self.mutate("UPDATE books SET review_status='unexpected' WHERE id=(SELECT min(id) FROM books)")
        self.assertIn("unknown_review_status", [f["code"] for f in audit(self.db)["findings"]])
    def test_read_only(self):
        before = audit(self.db)
        self.assertEqual(before, audit(self.db))

if __name__ == "__main__":
    unittest.main()
