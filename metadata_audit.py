"""Read-only integrity audit for local book metadata and review states."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from curriculum import connect

ROOT = Path(__file__).resolve().parent

def audit(db_path):
    findings = []
    with connect(db_path) as db:
        rows = db.execute("""
            SELECT b.id, b.grade_id, b.source_id, b.url, b.review_status,
                   b.rights_status, b.extraction_status, b.title,
                   s.id, s.url
            FROM books b LEFT JOIN sources s ON b.source_id=s.id
            ORDER BY b.id
        """).fetchall()
    for (book_id, grade, source_id, url, review, rights, extraction,
         title, linked_source_id, source_url) in rows:
        def flag(code, severity, message):
            findings.append({"book_id": book_id, "code": code,
                             "severity": severity, "message": message})
        if not isinstance(grade, int) or not 1 <= grade <= 12:
            flag("invalid_grade", "error", "Grade outside 1–12")
        if not title or not title.strip():
            flag("missing_title", "error", "Book title missing")
        if source_id and not linked_source_id:
            flag("missing_source_record", "error", "Source ID has no matching record")
        if not url:
            flag("missing_book_url", "warning", "No book source URL")
        else:
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                flag("invalid_book_url", "error", "Book URL must be HTTPS with no credentials")
        if source_url:
            parsed = urlsplit(source_url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                flag("invalid_source_url", "error", "Source URL must be HTTPS with no credentials")
        if review not in ("pending", "approved", "rejected"):
            flag("unknown_review_status", "error", "Unexpected review status")
        if rights not in ("unknown", "permitted", "restricted"):
            flag("unknown_rights_status", "error", "Unexpected rights status")
        if review == "rejected" and rights == "permitted":
            flag("rejected_but_permitted", "error", "Rejected metadata cannot grant content permission")
        if extraction == "completed" and not (review == "approved" and rights == "permitted"):
            flag("unsafe_extraction_state", "error", "Extraction completed without both approvals")
        if rights == "permitted" and review != "approved":
            flag("permission_without_review", "error", "Permission requires approved metadata")
    return {
        "scope": "metadata and state integrity only; no textbook content examined",
        "books_checked": len(rows),
        "errors": sum(f["severity"] == "error" for f in findings),
        "warnings": sum(f["severity"] == "warning" for f in findings),
        "findings": findings,
        "safe_to_enable_content": bool(rows) and not findings and all(
            r[4] == "approved" and r[5] == "permitted" and r[6] == "completed"
            for r in rows
        ),
    }

def main():
    parser = argparse.ArgumentParser(description="Audit book metadata integrity without modifying records")
    parser.add_argument("--db", default=str(ROOT / "curriculum.sqlite3"))
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on errors")
    args = parser.parse_args()
    result = audit(args.db)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.strict and result["errors"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
