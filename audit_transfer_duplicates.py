"""Detect conflicting Drive file IDs and duplicate PDF fingerprints in a transfer ledger.

Metadata only: never reads or stores textbook contents. A repeated fingerprint is
reported for human review, not automatically removed or reclassified.
"""
import argparse
import json
import re
from pathlib import Path

SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def audit(records):
    errors, warnings = [], []
    file_ids, hashes = {}, {}
    for record in records:
        if record.get("status") != "uploaded_verified":
            continue
        source = str(record.get("id", "unknown"))
        drive = record.get("drive_file") or {}
        file_id = drive.get("id")
        if not isinstance(file_id, str) or not file_id.strip():
            errors.append(f"source {source}: missing Drive file ID")
        elif file_id in file_ids:
            errors.append(f"sources {file_ids[file_id]} and {source}: same Drive file ID")
        else:
            file_ids[file_id] = source
        digest = (record.get("pdf_check") or {}).get("sha256")
        if digest is None:
            continue  # Missing digests are handled by the PDF integrity audit.
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            errors.append(f"source {source}: invalid SHA256")
        elif digest in hashes:
            warnings.append(f"sources {hashes[digest]} and {source}: same SHA256; review source labels")
        else:
            hashes[digest] = source
    return errors, warnings


def self_test():
    def row(source, file_id, digest=None, status="uploaded_verified"):
        return {"id": source, "status": status, "drive_file": {"id": file_id},
                "pdf_check": {"sha256": digest} if digest is not None else {}}
    h = "a" * 64
    assert audit([row(1, "A", h), row(2, "B", "b" * 64)]) == ([], [])
    assert len(audit([row(1, "A"), row(2, "A")])[0]) == 1
    assert len(audit([row(1, "A", h), row(2, "B", h)])[1]) == 1
    assert audit([row(1, "A", h), row(2, "A", h, "pending")]) == ([], [])
    assert len(audit([row(1, "", "not-a-hash")])[0]) == 2
    print("5 duplicate-audit self-tests passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        if args.ledger is None:
            parser.error("ledger is required unless --self-test is used")
        data = json.loads(args.ledger.read_text(encoding="utf-8"))
        errors, warnings = audit(data["records"])
        for item in errors:
            print("ERROR:", item)
        for item in warnings:
            print("WARNING:", item)
        print(f"{len(errors)} errors, {len(warnings)} warnings")
        raise SystemExit(bool(errors))
