import unittest
from transfer_integrity_queue import integrity_queue


class IntegrityQueueTests(unittest.TestCase):
    def test_missing_evidence_is_reported_without_promoting_source(self):
        ledger = {"records": [
            {"id": "25", "status": "uploaded_verified", "drive_file": {"id": "a"}},
            {"id": "58", "status": "source_error"},
            {"id": "92", "status": "uploaded_verified", "drive_file": {"id": "b"},
             "pdf_check": {"bytes": 123, "pages": 89}},
        ]}
        self.assertEqual(integrity_queue(ledger), [
            {"source_id": "25", "record_position": 1, "missing": ["sha256", "pages", "bytes"]},
            {"source_id": "92", "record_position": 3, "missing": ["sha256"]},
        ])

    def test_verified_record_is_not_queued(self):
        ledger = {"records": [{"id": "1", "status": "uploaded_verified",
                              "drive_file": {"id": "x"},
                              "pdf_check": {"bytes": 20, "pages": 2, "sha256": "a" * 64}}]}
        self.assertEqual(integrity_queue(ledger), [])

    def test_invalid_types_are_not_accepted(self):
        ledger = {"records": [{"id": "1", "status": "uploaded_verified", "drive_file": {},
                              "pdf_check": {"bytes": True, "pages": True, "sha256": "A" * 64}}]}
        self.assertEqual(integrity_queue(ledger)[0]["missing"],
                         ["sha256", "pages", "bytes", "drive_file_id"])

    def test_invalid_ledger(self):
        with self.assertRaises(ValueError):
            integrity_queue({"records": {}})


if __name__ == "__main__":
    unittest.main()
