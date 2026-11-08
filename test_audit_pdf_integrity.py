"""Regression tests for PDF metadata integrity checks."""
import unittest
from audit_pdf_integrity import audit


def record(size="120", check=None):
    return {
        "id": "10",
        "status": "uploaded_verified",
        "drive_file": {"mime_type": "application/pdf", "title": "book.pdf", "size": size},
        "pdf_check": check if check is not None else {
            "bytes": 120, "pages": 3, "sha256": "a" * 64,
        },
    }


class PDFIntegrityTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(audit({"records": [record()]}), ([], []))

    def test_fractional_size_rejected(self):
        errors, _ = audit({"records": [record(120.9)]})
        self.assertTrue(errors)

    def test_boolean_size_rejected(self):
        errors, _ = audit({"records": [
            record(True, {"bytes": 1, "pages": 1, "sha256": "a" * 64})
        ]})
        self.assertTrue(errors)

    def test_missing_check_warning(self):
        item = record()
        item.pop("pdf_check")
        _, warnings = audit({"records": [item]})
        self.assertEqual(len(warnings), 1)

    def test_boolean_page_count_rejected(self):
        errors, _ = audit({"records": [
            record(check={"bytes": 120, "pages": True, "sha256": "a" * 64})
        ]})
        self.assertTrue(errors)

    def test_pending_ignored(self):
        item = record()
        item["status"] = "pending"
        self.assertEqual(audit({"records": [item]}), ([], []))


if __name__ == "__main__":
    unittest.main()
