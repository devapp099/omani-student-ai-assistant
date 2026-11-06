"""Safe, read-only book metadata search. No textbook content is stored or returned."""
import argparse
import json
import sqlite3
from pathlib import Path

from curriculum import connect

ROOT = Path(__file__).resolve().parent

def find_books(db_path, grade=None, subject=None, query=None, semester=None, limit=50):
    if grade is not None and (not isinstance(grade, int) or not 1 <= grade <= 12):
        raise ValueError("grade must be between 1 and 12")
    if semester is not None and semester not in (1, 2):
        raise ValueError("semester must be 1 or 2")
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if query is not None and len(query) > 200:
        raise ValueError("query is too long")
    if subject is not None and len(subject) > 200:
        raise ValueError("subject is too long")
    clauses = []
    params = []
    if grade is not None:
        clauses.append("b.grade_id=?")
        params.append(grade)
    if semester is not None:
        clauses.append("b.semester=?")
        params.append(semester)
    if subject:
        clauses.append("instr(lower(s.name_ar),lower(?))>0")
        params.append(subject)
    if query:
        clauses.append("instr(lower(b.title),lower(?))>0")
        params.append(query)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    sql = ("""SELECT b.id, b.grade_id, s.name_ar, b.title, b.semester,
              b.academic_year, b.edition, b.url, b.review_status,
              b.rights_status, b.extraction_status
              FROM books b JOIN subjects s ON b.subject_id=s.id"""
           + where + " ORDER BY b.grade_id, s.name_ar, b.title, b.id LIMIT ?")
    params.append(limit)
    with connect(db_path) as db:
        rows = db.execute(sql, params).fetchall()
    results = []
    for r in rows:
        results.append({
            "id": r[0], "grade": r[1], "subject": r[2], "title": r[3],
            "semester": r[4], "academic_year": r[5], "edition": r[6],
            "source_url": r[7],
            "metadata_review": r[8], "content_rights": r[9],
            "extraction_status": r[10],
            "content_available": r[8] == "approved" and r[9] == "permitted"
                                   and r[10] == "completed",
        })
    return results

def main():
    parser = argparse.ArgumentParser(description="Search local curriculum book metadata")
    parser.add_argument("--db", default=str(ROOT / "curriculum.sqlite3"))
    parser.add_argument("--grade", type=int)
    parser.add_argument("--semester", type=int)
    parser.add_argument("--subject")
    parser.add_argument("--query")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    try:
        results = find_books(args.db, grade=args.grade, semester=args.semester,
                             subject=args.subject, query=args.query, limit=args.limit)
    except (ValueError, sqlite3.Error) as exc:
        parser.error(str(exc))
    print(json.dumps({"count": len(results), "books": results},
                     ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
