import csv
import tempfile
import unittest
from pathlib import Path
from evidence import validate, ROOT

class EvidenceTests(unittest.TestCase):
    def test_official_seed_is_valid_but_unapproved(self):
        result = validate(ROOT / "official_evidence.csv")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["pending"], 4)

    def test_reject_unofficial_url_and_invalid_grade(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            with (ROOT / "official_evidence.csv").open(encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames
                rows = list(reader)
            rows[0]["grade"] = "13"
            rows[0]["source_url"] = "https://example.com/"
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
            result = validate(path)
            self.assertTrue(any("invalid grade" in e for e in result["errors"]))
            self.assertTrue(any("invalid official source" in e for e in result["errors"]))

    def test_verified_requires_reviewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claimed.csv"
            with (ROOT / "official_evidence.csv").open(encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames
                rows = list(reader)
            rows[0]["evidence_status"] = "verified"
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
            self.assertTrue(any("reviewer attribution" in e for e in validate(path)["errors"]))

if __name__ == "__main__":
    unittest.main()
