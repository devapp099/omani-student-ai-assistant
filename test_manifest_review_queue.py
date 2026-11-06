import csv
import tempfile
import unittest
from pathlib import Path
from manual_manifest import FIELDS
from manifest_review_queue import review_queue


class ReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "books.csv"

    def write(self, **overrides):
        row = dict.fromkeys(FIELDS, "")
        row.update(grade="7", semester="1", subject="Example subject", title="Example title",
                   official_url="https://ict.moe.gov.om/book/", school_year="2026-2027",
                   edition="1", download_status="not_downloaded", upload_status="not_uploaded",
                   metadata_review="approved", rights_status="permitted")
        row.update(overrides)
        with self.path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerow(row)

    def test_no_flags_for_complete_metadata(self):
        self.write()
        self.assertEqual(review_queue(self.path), [])

    def test_missing_review_fields_are_flagged(self):
        self.write(school_year="", edition="", metadata_review="pending", rights_status="unknown")
        reasons = review_queue(self.path)[0]["reasons"]
        self.assertIn("school_year_missing", reasons)
        self.assertIn("content_permission_not_recorded", reasons)

    def test_external_https_domain_needs_review(self):
        self.write(official_url="https://example.org/book")
        self.assertIn("source_domain_needs_verification", review_queue(self.path)[0]["reasons"])

    def test_uploaded_file_is_flagged_for_private_storage(self):
        self.write(download_status="downloaded", upload_status="uploaded", local_filename="book.pdf")
        self.assertIn("uploaded_file_requires_private_storage_review", review_queue(self.path)[0]["reasons"])

    def test_invalid_manifest_fails_closed(self):
        self.write(grade="13")
        with self.assertRaises(ValueError):
            review_queue(self.path)


if __name__ == "__main__":
    unittest.main()
