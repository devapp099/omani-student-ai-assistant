"""Audit transfer ledger metadata only; no PDF reading or download."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

STATUSES = {"pending", "uploaded_verified", "source_error", "excluded_wrong_source"}


def _official_url(value, path_pattern):
    parts = urlsplit(value)
    return (
        parts.scheme == "https"
        and parts.netloc == "home.moe.gov.om"
        and re.fullmatch(path_pattern, parts.path) is not None
        and not parts.query and not parts.fragment
    )


def audit(data):
    errors = []
    rows = data.get("records")
    if not isinstance(rows, list):
        return ["records must be a list"]
    source_ids, drive_ids, uploaded_hashes, counts, total_bytes = set(), set(), set(), Counter(), 0
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            errors.append(f"record {index}: not an object")
            continue
        source = str(row.get("id", ""))
        if not source.isascii() or not source.isdecimal() or int(source or 0) < 1:
            errors.append(f"record {index}: invalid source id")
        elif source in source_ids:
            errors.append(f"record {index}: duplicate source id")
        source_ids.add(source)
        status = row.get("status")
        if status not in STATUSES:
            errors.append(f"record {index}: invalid status")
            continue
        counts[status] += 1
        # Metadata-only allowlist: never trust arbitrary retrieval URLs.
        if status in {"pending", "uploaded_verified", "excluded_wrong_source"}:
            page_url = row.get("page")
            pdf_url = row.get("pdf")
            if not isinstance(page_url, str) or not _official_url(page_url, r"/ar/manaheg/\d+/show/\d+"):
                errors.append(f"record {index}: invalid official source page URL")
            elif page_url.rsplit("/", 1)[-1] != source:
                errors.append(f"record {index}: source page ID mismatch")
            if not isinstance(pdf_url, str) or not _official_url(pdf_url, r"/images/manaheg/file/[A-Za-z0-9_-]+\.pdf"):
                errors.append(f"record {index}: invalid official PDF URL")
        drive, pdf = row.get("drive_file"), row.get("pdf_check")
        if status == "uploaded_verified":
            if not isinstance(drive, dict):
                errors.append(f"record {index}: missing Drive file metadata")
                continue
            if not isinstance(pdf, dict):
                errors.append(f"record {index}: missing upload PDF verification")
                pdf = {}
            if drive.get("mime_type") != "application/pdf":
                errors.append(f"record {index}: Drive file is not a PDF")
            if not isinstance(drive.get("title"), str) or not drive["title"].lower().endswith(".pdf"):
                errors.append(f"record {index}: Drive filename must end in .pdf")
            if drive.get("shared") is not False:
                errors.append(f"record {index}: Drive file privacy is not confirmed")
            folder_key = drive.get("folder_key")
            folder_map = data.get("folder_map")
            if folder_key is not None or drive.get("parent_id") is not None:
                if not isinstance(folder_map, dict) or folder_key not in folder_map:
                    errors.append(f"record {index}: unknown destination folder")
                elif drive.get("parent_id") != folder_map[folder_key]:
                    errors.append(f"record {index}: destination parent folder mismatch")
            file_id = drive.get("id")
            if not isinstance(file_id, str) or not file_id:
                errors.append(f"record {index}: missing Drive file ID")
            elif file_id in drive_ids:
                errors.append(f"record {index}: duplicate Drive file ID")
            drive_ids.add(file_id)
            try:
                size = int(drive.get("size", ""))
                if size <= 0:
                    raise ValueError()
                total_bytes += size
                if type(pdf.get("bytes")) is not int or size != pdf["bytes"]:
                    errors.append(f"record {index}: PDF size mismatch")
            except (ValueError, TypeError):
                errors.append(f"record {index}: invalid Drive file size")
            if type(pdf.get("pages")) is not int or pdf["pages"] < 1:
                errors.append(f"record {index}: invalid PDF page count")
        elif drive is not None:
            errors.append(f"record {index}: non-uploaded source has Drive file")
        if isinstance(pdf, dict) and "sha256" in pdf and not (
            isinstance(pdf["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", pdf["sha256"])
        ):
            errors.append(f"record {index}: invalid SHA256")
        if status == "uploaded_verified" and isinstance(pdf, dict):
            digest = pdf.get("sha256")
            if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
                if digest in uploaded_hashes:
                    errors.append(f"record {index}: duplicate uploaded PDF SHA256")
                uploaded_hashes.add(digest)
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return errors + ["summary must be an object"]
    if summary.get("catalog_pages") != len(rows):
        errors.append("summary catalog_pages mismatch")
    if summary.get("uploaded_verified") != counts["uploaded_verified"]:
        errors.append("summary uploaded_verified mismatch")
    if summary.get("bytes_uploaded") != total_bytes:
        errors.append("summary bytes_uploaded mismatch")
    if summary.get("status_counts") != dict(counts):
        errors.append("summary status_counts mismatch")
    return errors



def _trusted_edition_evidence(value):
    """Require canonical HTTPS evidence on the exact official ICT host."""
    if not isinstance(value, str):
        return False
    parts = urlsplit(value)
    return (
        parts.scheme == "https"
        and parts.netloc == "ict.moe.gov.om"
        and parts.path.startswith("/")
        and parts.path != "/"
        and not parts.query
        and not parts.fragment
    )

def eligible_for_retrieval(record):
    """Fail closed: uploaded PDF metadata alone never authorizes text retrieval."""
    if not isinstance(record, dict) or record.get("status") != "uploaded_verified":
        return False
    edition = record.get("edition_review")
    rights = record.get("retrieval_rights")
    return (
        isinstance(edition, dict)
        and edition.get("status") == "verified_current"
        and isinstance(edition.get("evidence_url"), str)
        and _trusted_edition_evidence(edition["evidence_url"])
        and isinstance(rights, dict)
        and rights.get("status") == "permission_verified"
        and isinstance(rights.get("evidence"), str)
        and bool(rights["evidence"].strip())
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit transfer ledger without opening books")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    issues = audit(json.loads(args.file.read_text(encoding="utf-8")))
    for issue in issues:
        print(issue)
    print(f"{len(issues)} issue(s)")
    if issues:
        raise SystemExit(1)
