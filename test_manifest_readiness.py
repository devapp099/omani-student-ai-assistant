"""Regression tests for fail-closed metadata readiness reporting."""
import csv
import tempfile
import unittest
from pathlib import Path
from manual_manifest import FIELDS
from manifest_readiness import readiness_report


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "books.csv"

    def write(self, rows):
        with self.path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def row(self, **changes):
        row = dict.fromkeys(FIELDS, "")
        row.update(grade="4", semester="1", subject="Test subject", title="Test title",
                   official_url="https://ict.moe.gov.om/book/",
                   download_status="downloaded", upload_status="uploaded",
                   local_filename="test.pdf", metadata_review="approved",
                   rights_status="permitted")
        row.update(changes)
        return row

    def test_empty_manifest_has_no_candidates(self):
        self.write([])
        report = readiness_report(self.path)
        self.assertEqual(report["counts"]["recorded"], 0)
        self.assertFalse(report["automatic_ingestion_allowed"])

    def test_candidate_still_requires_evidence_review(self):
        self.write([self.row()])
        report = readiness_report(self.path)
        self.assertEqual(report["counts"]["ready_for_human_evidence_review"], 1)
        self.assertFalse(report["automatic_ingestion_allowed"])

    def test_restricted_rights_block_candidate(self):
        self.write([self.row(rights_status="restricted")])
        self.assertEqual(readiness_report(self.path)["candidates"], [])

    def test_unreviewed_metadata_blocks_candidate(self):
        self.write([self.row(metadata_review="pending")])
        self.assertEqual(readiness_report(self.path)["candidates"], [])

    def test_invalid_grade_rejected(self):
        self.write([self.row(grade="13")])
        with self.assertRaises(ValueError):
            readiness_report(self.path)

    def test_formula_injection_rejected(self):
        self.write([self.row(title="=HYPERLINK(1)")])
        with self.assertRaises(ValueError):
            readiness_report(self.path)


if __name__ == "__main__":
    unittest.main()
