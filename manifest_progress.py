"""Summarize verified manual book manifest records without estimating missing books.

No PDFs are read or downloaded. Counts describe only recorded entries.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from manual_manifest import FIELDS, validate_manifest


def summarize(path):
    errors = validate_manifest(path)
    if errors:
        raise ValueError("\n".join(errors))
    groups = {(grade, semester): Counter() for grade in range(1, 13) for semester in (1, 2)}
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            counter = groups[(int(row["grade"]), int(row["semester"]))]
            counter["recorded"] += 1
            counter["downloaded"] += row["download_status"] == "downloaded"
            counter["uploaded"] += row["upload_status"] == "uploaded"
            counter["metadata_approved"] += row["metadata_review"] == "approved"
            counter["rights_permitted"] += row["rights_status"] == "permitted"
    return [
        {"grade": grade, "semester": semester,
         **{name: counts[name] for name in
            ("recorded", "downloaded", "uploaded", "metadata_approved", "rights_permitted")}}
        for (grade, semester), counts in sorted(groups.items())
    ]


def main():
    parser = argparse.ArgumentParser(description="Report recorded books; never infer missing book counts")
    parser.add_argument("--file", default="manual_books_manifest.csv")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        rows = summarize(args.file)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Manifest cannot be reported: {error}\n")
    if args.json:
        print(json.dumps({"scope": "recorded_entries_only", "coverage_unknown": True,
                          "by_grade_semester": rows}, ensure_ascii=False, indent=2))
    else:
        print("Grade,Semester,Recorded,Downloaded,Uploaded,Metadata approved,Rights permitted")
        for row in rows:
            print(",".join(str(row[key]) for key in
                           ("grade", "semester", "recorded", "downloaded", "uploaded",
                            "metadata_approved", "rights_permitted")))
        print("NOTE: Expected official book totals are unknown; zero does not mean no books exist.")


if __name__ == "__main__":
    main()
