"""Validate official curriculum evidence metadata without downloading copyrighted books."""
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
REQUIRED = {"evidence_id", "grade", "subject", "title", "academic_year", "semester", "source_url", "evidence_status", "rights_status"}
STATUSES = {"needs_manual_review", "verified", "rejected"}
RIGHTS = {"unknown", "permitted", "restricted"}

def validate(path):
    errors = []
    rows = []
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            return {"total": 0, "errors": ["Missing columns: " + ", ".join(sorted(missing))], "by_grade": {}, "pending": 0}
        seen = set()
        for index, row in enumerate(reader, 2):
            rows.append(row)
            rid = row["evidence_id"].strip()
            if not rid or rid in seen:
                errors.append(f"line {index}: duplicate or empty evidence_id")
            seen.add(rid)
            try:
                grade = int(row["grade"])
                if not 1 <= grade <= 12:
                    raise ValueError()
            except ValueError:
                errors.append(f"line {index}: invalid grade")
            semester = row["semester"].strip()
            if semester and semester not in {"1", "2"}:
                errors.append(f"line {index}: invalid semester")
            if not row["subject"].strip() or not row["title"].strip():
                errors.append(f"line {index}: missing subject or title")
            url = urlsplit(row["source_url"].strip())
            if url.scheme != "https" or not url.netloc or url.hostname != "ict.moe.gov.om":
                errors.append(f"line {index}: invalid official source URL")
            if row["evidence_status"] not in STATUSES:
                errors.append(f"line {index}: invalid evidence_status")
            if row["rights_status"] not in RIGHTS:
                errors.append(f"line {index}: invalid rights_status")
            if row["evidence_status"] == "verified" and not row.get("reviewer", "").strip():
                errors.append(f"line {index}: verified row needs reviewer attribution")
    grades = {}
    for row in rows:
        grade = row["grade"]
        grades[grade] = grades.get(grade, 0) + 1
    return {"total": len(rows), "errors": errors, "by_grade": grades,
            "pending": sum(r["evidence_status"] == "needs_manual_review" for r in rows)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(ROOT / "official_evidence.csv"))
    args = parser.parse_args()
    result = validate(args.csv)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["errors"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
