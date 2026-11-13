"""Offline checks for curriculum transfer manifest metadata; never reads PDF text."""
import json
import re
import unittest
from urllib.parse import urlsplit

PAGE = re.compile(r"/ar/manaheg/\\d+/show/([1-9]\\d*)/?$")
STATUSES = ("pending", "source_error", "excluded_wrong_source", "uploaded_verified")

def audit(data):
    if not isinstance(data.get("records"), list):
        raise ValueError("Missing records")
    ids, files, counts = set(), set(), {s: 0 for s in STATUSES}
    total, incomplete = 0, []
    for r in data["records"]:
        sid = str(r.get("id", ""))
        if not re.fullmatch(r"[1-9]\\d*", sid) or sid in ids:
            raise ValueError("Duplicate/invalid source ID")
        ids.add(sid)
        u = urlsplit(r.get("page", ""))
        match = PAGE.fullmatch(u.path)
        if (u.scheme != "https" or u.netloc != "home.moe.gov.om"
                or u.query or u.fragment or not match or match.group(1) != sid):
            raise ValueError("Untrusted or mismatched source page")
        status = r.get("status")
        if status not in counts:
            raise ValueError("Unknown status")
        counts[status] += 1
        check = r.get("pdf_check") or {}
        if "sha256" in check and not re.fullmatch(r"[a-f0-9]{64}", check["sha256"]):
            raise ValueError("Invalid SHA256")
        if status == "uploaded_verified":
            f = r.get("drive_file") or {}
            fid = f.get("id")
            if not fid or fid in files:
                raise ValueError("Duplicate/missing Drive file")
            files.add(fid)
            size = int(f.get("size") or 0)
            if size <= 0:
                raise ValueError("Invalid file size")
            if not check.get("bytes") or not check.get("pages"):
                incomplete.append(sid)
            elif int(check["bytes"]) != size or int(check["pages"]) <= 0:
                raise ValueError("PDF metadata mismatch")
            total += size
    summary = data.get("summary") or {}
    if (summary.get("catalog_pages") != len(ids)
            or summary.get("uploaded_verified") != len(files)
            or summary.get("bytes_uploaded") != total
            or any(summary.get("status_counts", {}).get(s, 0) != n for s, n in counts.items())):
        raise ValueError("Summary mismatch")
    return {"sources": len(ids), "drive_files": len(files),
            "bytes": total, "missing_pdf_checks": incomplete}

class ManifestAuditTests(unittest.TestCase):
    def sample(self):
        return {"records": [{"id": "12", "page": "https://home.moe.gov.om/ar/manaheg/1/show/12",
                "status": "uploaded_verified", "drive_file": {"id": "f", "size": "123"},
                "pdf_check": {"bytes": 123, "pages": 1}}],
                "summary": {"catalog_pages": 1, "uploaded_verified": 1,
                "bytes_uploaded": 123, "status_counts": {"uploaded_verified": 1}}}
    def test_valid(self):
        self.assertEqual(audit(self.sample())["drive_files"], 1)
    def test_missing_check_is_reported_not_invented(self):
        d = self.sample(); d["records"][0]["pdf_check"] = {}
        self.assertEqual(audit(d)["missing_pdf_checks"], ["12"])
    def test_duplicate(self):
        d = self.sample(); d["records"].append(dict(d["records"][0]))
        with self.assertRaises(ValueError): audit(d)
    def test_wrong_source(self):
        d = self.sample(); d["records"][0]["page"] += "?id=12"
        with self.assertRaises(ValueError): audit(d)
    def test_wrong_bytes(self):
        d = self.sample(); d["records"][0]["pdf_check"]["bytes"] = 1
        with self.assertRaises(ValueError): audit(d)
    def test_summary(self):
        d = self.sample(); d["summary"]["bytes_uploaded"] = 0
        with self.assertRaises(ValueError): audit(d)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("manifest", nargs="?")
    args = p.parse_args()
    if args.manifest:
        with open(args.manifest, encoding="utf-8") as handle:
            print(json.dumps(audit(json.load(handle)), ensure_ascii=False, indent=2))
    else:
        unittest.main(argv=["manifest_audit"])
