"""Offline tests for strict ministry URL and encrypted PDF transfer rejection."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
from types import SimpleNamespace

from verify_transfer_candidate import preflight


class CandidateSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = Path(self.tmp.name) / "candidate.pdf"
        self.pdf.write_bytes(b"%PDF-" + b"X" * 200)
        self.manifest = {
            "folder_map": {"6:1": "private-folder"},
            "records": [{
                "id": "500", "status": "pending",
                "crumbs": ["الصف السادس", "العلوم", "الفصل الأول"],
                "pdf": "https://home.moe.gov.om/images/manaheg/file/Book615664.pdf",
            }],
        }

    def test_rejects_encoded_path_traversal(self):
        self.manifest["records"][0]["pdf"] = (
            "https://home.moe.gov.om/images/manaheg/file/%2e%2e/Book615664.pdf"
        )
        with self.assertRaisesRegex(ValueError, "untrusted"):
            preflight(self.manifest, "500", self.pdf)

    def test_rejects_unexpected_subdirectory(self):
        self.manifest["records"][0]["pdf"] = (
            "https://home.moe.gov.om/images/manaheg/file/other/Book615664.pdf"
        )
        with self.assertRaisesRegex(ValueError, "untrusted"):
            preflight(self.manifest, "500", self.pdf)

    def test_rejects_encrypted_pdf(self):
        fake_pypdf = SimpleNamespace(PdfReader=lambda *a, **kw: SimpleNamespace(is_encrypted=True))
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            with self.assertRaisesRegex(ValueError, "Encrypted"):
                preflight(self.manifest, "500", self.pdf)

    def test_allows_canonical_path_to_reach_structural_validation(self):
        fake_reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(mediabox=(0, 0, 1, 1))])
        with patch.dict(sys.modules, {"pypdf": SimpleNamespace(PdfReader=lambda *a, **kw: fake_reader)}):
            result = preflight(self.manifest, "500", self.pdf)
        self.assertEqual(result["pages"], 1)
        self.assertFalse(result["approved_for_upload"])


if __name__ == "__main__":
    unittest.main()
