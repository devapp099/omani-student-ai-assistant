"""Audit transfer ledger metadata only; no PDF reading or download."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

STATUSES = {"pending", "uploaded_verified", "source_error", "excluded_wrong_source"}


def audit(data):
    errors = []
    rows = data.get("records")
    if not isinstance(rows, list):
        return ["records must be a list"]
    source_ids, drive_ids, counts, total_bytes = set(), set(), Counter(), 0
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
        drive, pdf = row.get("drive_file"), row.get("pdf_check")
        if status == "uploaded_verified":
            if not isinstance(drive, dict) or not isinstance(pdf, dict):
                errors.append(f"record {index}: missing upload PDF verification")
                continue
            file_id = drive.get("id")
            if not isinstance(file_id, str) or not file_id:
                errors.append(f"record {index}: missing Drive file ID")
            elif file_id in drive_ids:
                errors.append(f"record {index}: duplicate Drive file ID")
            drive_ids.add(file_id)
            try:
                size = int(drive.get("size", ""))
                if size <= 0 or type(pdf.get("bytes")) is not int or size != pdf["bytes"]:
                    raise ValueError()
                total_bytes += size
            except (ValueError, TypeError):
                errors.append(f"record {index}: PDF size mismatch")
            if type(pdf.get("pages")) is not int or pdf["pages"] < 1:
                errors.append(f"record {index}: invalid PDF page count")
        elif drive is not None:
            errors.append(f"record {index}: non-uploaded source has Drive file")
        if isinstance(pdf, dict) and "sha256" in pdf and not (
            isinstance(pdf["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", pdf["sha256"])
        ):
            errors.append(f"record {index}: invalid SHA256")
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
