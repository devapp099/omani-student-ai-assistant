"""Read-only upload checklist for manually collected books.

Counts only verified manifest rows; never reads PDFs, downloads URLs or grants rights.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from manual_manifest import validate_manifest


def upload_checklist(path):
    errors = validate_manifest(path)
    if errors:
        raise ValueError("\n".join(errors))
    counts = Counter()
    pending = []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for line, row in enumerate(csv.DictReader(handle), 2):
            counts["recorded"] += 1
            if row["download_status"] == "downloaded":
                counts["downloaded"] += 1
            if row["upload_status"] == "uploaded":
                counts["uploaded"] += 1
            if row["download_status"] == "downloaded" and row["upload_status"] == "not_uploaded":
                counts["awaiting_manual_upload"] += 1
                pending.append({"csv_line": line, "grade": row["grade"],
                                "semester": row["semester"], "local_filename": row["local_filename"]})
            if row["metadata_review"] != "approved":
                counts["metadata_review_needed"] += 1
            if row["rights_status"] != "permitted":
                counts["rights_review_needed"] += 1
    return {"scope": "recorded_entries_only", "official_coverage_unknown": True,
            "counts": {key: counts[key] for key in
                       ("recorded", "downloaded", "uploaded", "awaiting_manual_upload",
                        "metadata_review_needed", "rights_review_needed")},
            "awaiting_manual_upload": pending,
            "notice": "Rights status in CSV is self-reported; independent evidence review is required."}


def main():
    parser = argparse.ArgumentParser(description="Metadata-only manual upload checklist")
    parser.add_argument("--file", default="manual_books_manifest.csv")
    args = parser.parse_args()
    try:
        result = upload_checklist(args.file)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Invalid manifest: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
