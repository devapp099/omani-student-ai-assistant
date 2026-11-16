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
    seen_drive_ids = {}
    seen_hashes = {}
    for record in manifest.get("records", []):
        if record.get("status") != "uploaded_verified":
            continue
        verified += 1
        check = record.get("pdf_check") or {}
        drive = record.get("drive_file") or {}
        missing = []
        source_id = str(record.get('id', ''))
        if type(check.get("bytes")) is not int or check["bytes"] <= 0:
            missing.append("pdf_bytes")
        if type(check.get("pages")) is not int or check["pages"] <= 0:
            missing.append("pdf_pages")
        if not isinstance(check.get("sha256"), str) or not SHA256.fullmatch(check["sha256"]):
            missing.append("sha256")
        digest = check.get("sha256")
        if isinstance(digest, str) and SHA256.fullmatch(digest):
            digest = digest.lower()
            if digest in seen_hashes:
                missing.append("duplicate_pdf_sha256_with_source_" + seen_hashes[digest])
            else:
                seen_hashes[digest] = source_id
        drive_id = drive.get("id")
        if not drive_id:
            missing.append("drive_file_id")
        elif drive_id in seen_drive_ids:
            missing.append("duplicate_drive_file_id_with_source_" + seen_drive_ids[drive_id])
        else:
            seen_drive_ids[drive_id] = source_id
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
