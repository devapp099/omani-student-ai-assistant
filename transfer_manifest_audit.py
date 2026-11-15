"""Offline checks for curriculum transfer manifest metadata; never reads PDF text."""
import json
import re
import unittest
from urllib.parse import urlsplit

PAGE = re.compile(r"/ar/manaheg/\d+/show/([1-9]\d*)/?$")
STATUSES = ("pending", "source_error", "excluded_wrong_source", "uploaded_verified")

def audit(data):
    if not isinstance(data.get("records"), list):
        raise ValueError("Missing records")
    ids, files, hashes, counts = set(), set(), set(), {s: 0 for s in STATUSES}
    total, incomplete, missing_sha256, missing_pdf_url = 0, [], [], []
    for r in data["records"]:
        sid = str(r.get("id", ""))
        if not re.fullmatch(r"[1-9]\d*", sid) or sid in ids:
            raise ValueError("Duplicate/invalid source ID")
        ids.add(sid)
        u = urlsplit(r.get("page", ""))
        match = PAGE.fullmatch(u.path)
        if (u.scheme != "https" or u.netloc != "home.moe.gov.om"
                or u.query or u.fragment or not match or match.group(1) != sid):
            raise ValueError("Untrusted or mismatched source page")
        pdf = r.get("pdf")
        if pdf:
            p = urlsplit(pdf)
            if (p.scheme != "https" or p.netloc != "home.moe.gov.om"
                    or not p.path.startswith("/images/manaheg/file/")
                    or not p.path.lower().endswith(".pdf")
                    or p.query or p.fragment or p.username or p.password
                    or any(segment in (".", "..") for segment in p.path.split("/"))
                    or "%" in p.path or "\\" in p.path):
                raise ValueError("Untrusted curriculum PDF URL")
        status = r.get("status")
        if status not in counts:
            raise ValueError("Unknown status")
        counts[status] += 1
        check = r.get("pdf_check") or {}
        if "sha256" in check and (not isinstance(check["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", check["sha256"])):
            raise ValueError("Invalid SHA256")
        if status == "uploaded_verified":
            if not pdf:
                missing_pdf_url.append(sid)
            if not check.get("sha256"):
                missing_sha256.append(sid)
            elif check["sha256"] in hashes:
                raise ValueError("Duplicate uploaded PDF SHA256")
            else:
                hashes.add(check["sha256"])
            f = r.get("drive_file") or {}
            fid = f.get("id")
            if not fid or fid in files:
                raise ValueError("Duplicate/missing Drive file")
            files.add(fid)
            if f.get("mime_type") != "application/pdf" or not str(f.get("title", "")).lower().endswith(".pdf"):
                raise ValueError("Uploaded file must be a PDF")
            # Do not silently route an uploaded book to a grade/term that
            # contradicts the official page breadcrumbs. Missing breadcrumbs
            # remain an evidence gap rather than a guessed classification.
            crumbs = r.get("crumbs") or []
            if crumbs and not isinstance(crumbs, list):
                raise ValueError("Invalid source breadcrumbs")
            if len(crumbs) >= 3:
                grades = ("الأول", "الثاني", "الثالث", "الرابع", "الخامس",
                          "السادس", "السابع", "الثامن", "التاسع", "العاشر",
                          "الحادي عشر", "الثاني عشر")
                grade_text = str(crumbs[0]).strip()
                term_text = str(crumbs[-1]).strip()
                expected_grade = next((i for i, name in enumerate(grades, 1)
                                       if grade_text == "الصف " + name), None)
                expected_term = (1 if term_text in ("الفصل الأول", "الفصل الاول")
                                 else 2 if term_text == "الفصل الثاني" else None)
                if expected_grade is not None and expected_term is not None:
                    expected_key = f"{expected_grade}:{expected_term}"
                    if f.get("folder_key") != expected_key:
                        raise ValueError("Uploaded folder contradicts official breadcrumbs")
            folder_key = f.get("folder_key")
            folder_map = data.get("folder_map")
            if folder_map is not None and (
                    not folder_key or folder_key not in folder_map
                    or f.get("parent_id") != folder_map[folder_key]):
                raise ValueError("Uploaded file folder does not match manifest")
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
            "bytes": total, "missing_pdf_checks": incomplete,
            "missing_sha256": missing_sha256,
            "missing_official_pdf_url": missing_pdf_url}


def retrieval_ready_ids(data):
    """Fail closed: return only verified, complete, officially sourced PDF IDs.

    A catalog entry or pending download must never become retrievable by itself.
    """
    audit(data)
    return [str(r["id"]) for r in data["records"]
            if r["status"] == "uploaded_verified"
            and r.get("pdf")
            and (r.get("pdf_check") or {}).get("sha256")
            and (r.get("pdf_check") or {}).get("pages")
            and (r.get("pdf_check") or {}).get("bytes")]

class ManifestAuditTests(unittest.TestCase):
    def sample(self):
        return {"records": [{"id": "12", "page": "https://home.moe.gov.om/ar/manaheg/1/show/12",
                "status": "uploaded_verified", "drive_file": {"id": "f", "size": "123", "mime_type": "application/pdf", "title": "sample.pdf"},
                "pdf_check": {"bytes": 123, "pages": 1}}],
                "summary": {"catalog_pages": 1, "uploaded_verified": 1,
                "bytes_uploaded": 123, "status_counts": {"uploaded_verified": 1}}}

    def test_retrieval_denies_unverified_and_missing_provenance(self):
        d = self.sample()
        self.assertEqual(retrieval_ready_ids(d), [])
        d["records"][0]["pdf"] = "https://home.moe.gov.om/images/manaheg/file/a.pdf"
        self.assertEqual(retrieval_ready_ids(d), [])
        d["records"][0]["pdf_check"]["sha256"] = "a" * 64
        self.assertEqual(retrieval_ready_ids(d), ["12"])
        d["records"][0]["status"] = "pending"
        d["records"][0]["drive_file"] = None
        d["summary"]["uploaded_verified"] = 0
        d["summary"]["bytes_uploaded"] = 0
        d["summary"]["status_counts"] = {"pending": 1}
        self.assertEqual(retrieval_ready_ids(d), [])

    def test_retrieval_rejects_untrusted_pdf(self):
        d = self.sample()
        d["records"][0]["pdf"] = "https://evil.example/a.pdf"
        with self.assertRaises(ValueError):
            retrieval_ready_ids(d)

    def test_valid(self):
        self.assertEqual(audit(self.sample())["drive_files"], 1)
    def test_missing_check_is_reported_not_invented(self):
        d = self.sample(); d["records"][0]["pdf_check"] = {}
        self.assertEqual(audit(d)["missing_pdf_checks"], ["12"])
    def test_missing_sha256_is_reported_not_invented(self):
        self.assertEqual(audit(self.sample())["missing_sha256"], ["12"])
    def test_invalid_sha256_type_rejected(self):
        d = self.sample(); d["records"][0]["pdf_check"]["sha256"] = 123
        with self.assertRaises(ValueError): audit(d)
    def test_valid_sha256_not_reported(self):
        d = self.sample(); d["records"][0]["pdf_check"]["sha256"] = "a" * 64
        self.assertEqual(audit(d)["missing_sha256"], [])
    def test_missing_official_pdf_url_reported(self):
        self.assertEqual(audit(self.sample())["missing_official_pdf_url"], ["12"])
    def test_official_pdf_url_present(self):
        d = self.sample()
        d["records"][0]["pdf"] = "https://home.moe.gov.om/images/manaheg/file/a.pdf"
        self.assertEqual(audit(d)["missing_official_pdf_url"], [])
    def test_reject_uploaded_non_pdf_mime(self):
        d = self.sample(); d["records"][0]["drive_file"]["mime_type"] = "text/plain"
        with self.assertRaisesRegex(ValueError, "Uploaded file must be a PDF"): audit(d)
    def test_reject_uploaded_non_pdf_filename(self):
        d = self.sample(); d["records"][0]["drive_file"]["title"] = "sample.txt"
        with self.assertRaisesRegex(ValueError, "Uploaded file must be a PDF"): audit(d)
    def test_accept_pdf_case_insensitive_extension(self):
        d = self.sample(); d["records"][0]["drive_file"]["title"] = "sample.PDF"
        self.assertEqual(audit(d)["drive_files"], 1)
    def test_duplicate_uploaded_pdf_hash_rejected(self):
        d = self.sample()
        first = d["records"][0]
        first["pdf_check"]["sha256"] = "a" * 64
        second = json.loads(json.dumps(first))
        second["id"] = "13"
        second["page"] = "https://home.moe.gov.om/ar/manaheg/1/show/13"
        second["drive_file"]["id"] = "different-file"
        d["records"].append(second)
        d["summary"]["catalog_pages"] = 2
        d["summary"]["uploaded_verified"] = 2
        d["summary"]["bytes_uploaded"] = 246
        d["summary"]["status_counts"]["uploaded_verified"] = 2
        with self.assertRaisesRegex(ValueError, "Duplicate uploaded PDF SHA256"):
            audit(d)
    def test_different_uploaded_pdf_hashes_allowed(self):
        d = self.sample()
        first = d["records"][0]
        first["pdf_check"]["sha256"] = "a" * 64
        second = json.loads(json.dumps(first))
        second["id"] = "13"
        second["page"] = "https://home.moe.gov.om/ar/manaheg/1/show/13"
        second["drive_file"]["id"] = "different-file"
        second["pdf_check"]["sha256"] = "b" * 64
        d["records"].append(second)
        d["summary"]["catalog_pages"] = 2
        d["summary"]["uploaded_verified"] = 2
        d["summary"]["bytes_uploaded"] = 246
        d["summary"]["status_counts"]["uploaded_verified"] = 2
        self.assertEqual(audit(d)["drive_files"], 2)
    def test_duplicate(self):
        d = self.sample(); d["records"].append(dict(d["records"][0]))
        with self.assertRaises(ValueError): audit(d)
    def test_wrong_source(self):
        d = self.sample(); d["records"][0]["page"] += "?id=12"
        with self.assertRaises(ValueError): audit(d)
    def test_wrong_bytes(self):
        d = self.sample(); d["records"][0]["pdf_check"]["bytes"] = 1
        with self.assertRaises(ValueError): audit(d)
    def test_reject_external_pdf(self):
        d = self.sample()
        d["records"][0]["pdf"] = "https://evil.example/images/manaheg/file/a.pdf"
        with self.assertRaises(ValueError): audit(d)
    def test_reject_pdf_query(self):
        d = self.sample()
        d["records"][0]["pdf"] = "https://home.moe.gov.om/images/manaheg/file/a.pdf?download=1"
        with self.assertRaises(ValueError): audit(d)
    def test_reject_pdf_parent_traversal(self):
        d = self.sample()
        d["records"][0]["pdf"] = "https://home.moe.gov.om/images/manaheg/file/../other.pdf"
        with self.assertRaises(ValueError): audit(d)
    def test_reject_pdf_encoded_traversal(self):
        d = self.sample()
        d["records"][0]["pdf"] = "https://home.moe.gov.om/images/manaheg/file/%2e%2e/other.pdf"
        with self.assertRaises(ValueError): audit(d)
    def test_reject_pdf_backslash(self):
        d = self.sample()
        d["records"][0]["pdf"] = "https://home.moe.gov.om/images/manaheg/file/..\\\\other.pdf"
        with self.assertRaises(ValueError): audit(d)
    def test_reject_folder_mismatch(self):
        d = self.sample()
        d["folder_map"] = {"2:2": "expected"}
        d["records"][0]["drive_file"].update(folder_key="2:2", parent_id="wrong")
        with self.assertRaises(ValueError): audit(d)
    def test_reject_folder_contradicting_official_breadcrumbs(self):
        d = self.sample()
        d["records"][0]["crumbs"] = ["الصف السابع", "العلوم", "الفصل الثاني"]
        d["records"][0]["drive_file"]["folder_key"] = "7:1"
        with self.assertRaisesRegex(ValueError, "contradicts official breadcrumbs"):
            audit(d)

    def test_accept_folder_matching_official_breadcrumbs(self):
        d = self.sample()
        d["records"][0]["crumbs"] = ["الصف السابع", "العلوم", "الفصل الثاني"]
        d["records"][0]["drive_file"]["folder_key"] = "7:2"
        self.assertEqual(audit(d)["drive_files"], 1)

    def test_valid_folder_mapping(self):
        d = self.sample()
        d["folder_map"] = {"2:2": "expected"}
        d["records"][0]["drive_file"].update(folder_key="2:2", parent_id="expected")
        self.assertEqual(audit(d)["drive_files"], 1)
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
