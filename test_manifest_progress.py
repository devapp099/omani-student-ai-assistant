"""Tests for accurate manual collection progress, without fabricated book totals."""
import csv
import tempfile
import unittest
from pathlib import Path

from manual_manifest import FIELDS
from manifest_progress import summarize


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "manifest.csv"

    def write(self, rows):
        with self.path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def row(self, **changes):
        result = dict.fromkeys(FIELDS, "")
        result.update(grade="7", semester="1", subject="Verified subject",
                      title="Verified title", official_url="https://ict.moe.gov.om/book/",
                      download_status="not_downloaded", upload_status="not_uploaded",
                      metadata_review="pending", rights_status="unknown")
        result.update(changes)
        return result

    def test_blank_manifest_has_24_zero_groups(self):
        self.write([])
        result = summarize(self.path)
        self.assertEqual(len(result), 24)
        self.assertTrue(all(item["recorded"] == 0 for item in result))

    def test_separates_semesters_and_statuses(self):
        self.write([self.row(), self.row(semester="2", title="Another title",
                    download_status="downloaded", upload_status="uploaded",
                    local_filename="book.pdf", metadata_review="approved",
                    rights_status="permitted")])
        result = summarize(self.path)
        first = next(r for r in result if r["grade"] == 7 and r["semester"] == 1)
        second = next(r for r in result if r["grade"] == 7 and r["semester"] == 2)
        self.assertEqual((first["recorded"], first["uploaded"]), (1, 0))
        self.assertEqual((second["recorded"], second["uploaded"],
                          second["rights_permitted"]), (1, 1, 1))

    def test_invalid_manifest_fails_closed(self):
        self.write([self.row(grade="13")])
        with self.assertRaises(ValueError):
            summarize(self.path)

    def test_duplicate_records_fail_closed(self):
        self.write([self.row(), self.row()])
        with self.assertRaises(ValueError):
            summarize(self.path)


if __name__ == "__main__":
    unittest.main()
