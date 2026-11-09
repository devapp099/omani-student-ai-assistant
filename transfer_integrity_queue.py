"""Read-only integrity follow-up queue for a curriculum transfer ledger.

This reports missing verification metadata; it does not approve or retrieve PDFs.
"""
import argparse
import json
import re
from pathlib import Path

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def integrity_queue(ledger):
    if not isinstance(ledger, dict) or not isinstance(ledger.get("records"), list):
        raise ValueError("ledger.records must be a list")
    queue = []
    for position, record in enumerate(ledger["records"], 1):
        if not isinstance(record, dict):
            continue
        if record.get("status") != "uploaded_verified":
            continue
        check = record.get("pdf_check")
        check = check if isinstance(check, dict) else {}
        missing = []
        digest = check.get("sha256")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            missing.append("sha256")
        if type(check.get("pages")) is not int or check["pages"] < 1:
            missing.append("pages")
        if type(check.get("bytes")) is not int or check["bytes"] < 1:
            missing.append("bytes")
        drive = record.get("drive_file")
        if not isinstance(drive, dict) or not isinstance(drive.get("id"), str) or not drive["id"]:
            missing.append("drive_file_id")
        if missing:
            queue.append({"source_id": str(record.get("id", "")),
                          "record_position": position, "missing": missing})
    return queue


def main():
    parser = argparse.ArgumentParser(description="List unverified PDF integrity fields without reading book text")
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    result = integrity_queue(json.loads(args.ledger.read_text(encoding="utf-8")))
    print(json.dumps({"needs_integrity_review": len(result), "records": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
