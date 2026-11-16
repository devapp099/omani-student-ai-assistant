"""Read-only evidence gaps for previously transferred curriculum PDFs.

No textbook contents are read, fetched, indexed, or published. A Drive record
is not proof of the underlying file's integrity or copyright permissions.
"""
import argparse
import json
import re
from pathlib import Path

SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")


def evidence_report(manifest):
    gaps = []
    verified = 0
    for record in manifest.get("records", []):
        if record.get("status") != "uploaded_verified":
            continue
        verified += 1
        check = record.get("pdf_check") or {}
        drive = record.get("drive_file") or {}
        missing = []
        if type(check.get("bytes")) is not int or check["bytes"] <= 0:
            missing.append("pdf_bytes")
        if type(check.get("pages")) is not int or check["pages"] <= 0:
            missing.append("pdf_pages")
        if not isinstance(check.get("sha256"), str) or not SHA256.fullmatch(check["sha256"]):
            missing.append("sha256")
        if not drive.get("id"):
            missing.append("drive_file_id")
        if not drive.get("parent_id"):
            missing.append("drive_parent_id")
        try:
            drive_bytes = int(drive.get("size"))
        except (TypeError, ValueError):
            drive_bytes = None
        if drive_bytes is None or drive_bytes <= 0:
            missing.append("drive_bytes")
        elif type(check.get("bytes")) is int and check["bytes"] > 0 and drive_bytes != check["bytes"]:
            missing.append("size_mismatch")
        if missing:
            gaps.append({"source_id": str(record.get("id", "")), "issues": missing})
    return {"uploaded_records": verified, "evidence_complete": verified - len(gaps),
            "needs_review": gaps, "automatic_reverification": False,
            "notice": "Do not infer missing hashes or pages; verify original PDF bytes before updating the private manifest."}


def main():
    parser = argparse.ArgumentParser(description="Read-only transferred PDF evidence audit")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    print(json.dumps(evidence_report(json.loads(args.manifest.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
