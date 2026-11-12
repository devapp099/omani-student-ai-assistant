"""Audit PDF transfer metadata without reading or storing textbook contents."""
import argparse
import json
import re
from pathlib import Path

SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def audit(data):
    errors, warnings = [], []
    for record in data.get("records", []):
        if record.get("status") != "uploaded_verified":
            continue
        source = record.get("id", "unknown")
        file = record.get("drive_file") or {}
        check = record.get("pdf_check") or {}
        raw_size = file.get("size")
        # int() silently truncates floats and accepts booleans; reject both.
        if type(raw_size) is int and raw_size > 0:
            size = raw_size
        elif isinstance(raw_size, str) and re.fullmatch(r"[0-9]+", raw_size):
            size = int(raw_size)
        else:
            size = 0
        if file.get("mime_type") != "application/pdf" or not str(file.get("title", "")).lower().endswith(".pdf"):
            errors.append(f"source {source}: invalid PDF metadata")
        if size <= 0:
            errors.append(f"source {source}: missing or invalid Drive file size")
        if not check:
            warnings.append(f"source {source}: PDF integrity check missing")
            continue
        if type(check.get("bytes")) is not int or check["bytes"] <= 0 or check["bytes"] != size:
            errors.append(f"source {source}: PDF byte count differs from Drive size")
        if type(check.get("pages")) is not int or check["pages"] <= 0:
            errors.append(f"source {source}: invalid PDF page count")
        if check.get("pages") == 1 and type(check.get("pages")) is int:
            warnings.append(f"source {source}: single-page PDF requires manual cover/content review")
        digest = check.get("sha256")
        if digest is None:
            warnings.append(f"source {source}: SHA256 missing")
        elif not isinstance(digest, str) or not SHA256.fullmatch(digest):
            errors.append(f"source {source}: invalid SHA256 format")
    return errors, warnings


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    errors, warnings = audit(json.loads(args.ledger.read_text(encoding="utf-8")))
    for line in errors:
        print("ERROR:", line)
    for line in warnings:
        print("WARNING:", line)
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    raise SystemExit(bool(errors))
