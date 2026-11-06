"""Generate a human review queue from manual book metadata only.

This tool never fetches URLs, opens PDFs, or decides legal permissions.
"""
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlsplit

from manual_manifest import validate_manifest


def review_queue(path):
    issues = validate_manifest(path)
    if issues:
        raise ValueError("\n".join(issues))
    output = []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        for number, row in enumerate(csv.DictReader(stream), 2):
            reasons = []
            host = (urlsplit(row["official_url"]).hostname or "").lower()
            if host not in {"ict.moe.gov.om", "moe.gov.om"} and not host.endswith(".moe.gov.om"):
                reasons.append("source_domain_needs_verification")
            if not row["school_year"].strip():
                reasons.append("school_year_missing")
            if not row["edition"].strip():
                reasons.append("edition_missing")
            if row["metadata_review"] != "approved":
                reasons.append("metadata_not_approved")
            if row["rights_status"] != "permitted":
                reasons.append("content_permission_not_recorded")
            if row["upload_status"] == "uploaded":
                reasons.append("uploaded_file_requires_private_storage_review")
            if reasons:
                output.append({"csv_line": number, "grade": row["grade"],
                               "semester": row["semester"], "title": row["title"],
                               "reasons": reasons})
    return output


def main():
    parser = argparse.ArgumentParser(description="Review metadata without downloading textbooks")
    parser.add_argument("--file", default="manual_books_manifest.csv")
    args = parser.parse_args()
    try:
        result = review_queue(args.file)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Cannot audit manifest: {exc}\n")
    print(json.dumps({"review_queue": result, "count": len(result),
                      "note": "Flags are not legal authorization or proof of official book coverage"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
