"""Fail-closed, metadata-only readiness report for manual curriculum imports.

This report is NOT permission to ingest copyrighted material.
"""
import argparse
import csv
import json
from pathlib import Path
from manual_manifest import validate_manifest


def readiness_report(path):
    errors = validate_manifest(path)
    if errors:
        raise ValueError("\n".join(errors))
    counts = {"recorded": 0, "metadata_ready": 0, "rights_claimed_permitted": 0,
              "ready_for_human_evidence_review": 0}
    candidates = []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for line, row in enumerate(csv.DictReader(handle), 2):
            counts["recorded"] += 1
            metadata = row["metadata_review"] == "approved"
            rights = row["rights_status"] == "permitted"
            if metadata:
                counts["metadata_ready"] += 1
            if rights:
                counts["rights_claimed_permitted"] += 1
            if metadata and rights and row["upload_status"] == "uploaded":
                counts["ready_for_human_evidence_review"] += 1
                candidates.append({"csv_line": line, "grade": row["grade"],
                                   "semester": row["semester"], "title": row["title"]})
    return {"counts": counts, "candidates": candidates,
            "automatic_ingestion_allowed": False,
            "notice": "CSV status is not evidence of copyright permission. Independently verify evidence and file integrity before ingestion."}


def main():
    parser = argparse.ArgumentParser(description="Read-only metadata readiness report")
    parser.add_argument("--file", default="manual_books_manifest.csv")
    args = parser.parse_args()
    try:
        report = readiness_report(args.file)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Invalid manifest: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
