"""Read-only, evidence-aware curriculum inventory health report."""
import argparse
import json
from pathlib import Path
from curriculum import connect

ROOT = Path(__file__).resolve().parent

def coverage_report(db_path):
    with connect(db_path) as db:
        grades = []
        for grade in range(1, 13):
            rows = db.execute(
                """SELECT b.review_status, b.rights_status, b.extraction_status,
                          b.url, b.academic_year, b.edition
                   FROM books b WHERE b.grade_id=?""", (grade,)
            ).fetchall()
            grades.append({
                "grade": grade,
                "catalogued_books": len(rows),
                "metadata_approved": sum(r[0] == "approved" for r in rows),
                "content_permitted": sum(r[0] == "approved" and r[1] == "permitted" for r in rows),
                "content_extracted": sum(r[0] == "approved" and r[1] == "permitted" and r[2] == "completed" for r in rows),
                "missing_source_url": sum(not r[3] for r in rows),
                "missing_academic_year": sum(not r[4] for r in rows),
                "missing_edition": sum(not r[5] for r in rows),
            })
    return {
        "scope": "metadata inventory only; no textbook text examined",
        "grades": grades,
        "totals": {
            "catalogued_books": sum(g["catalogued_books"] for g in grades),
            "grades_with_books": sum(g["catalogued_books"] > 0 for g in grades),
            "metadata_approved": sum(g["metadata_approved"] for g in grades),
            "content_permitted": sum(g["content_permitted"] for g in grades),
            "content_extracted": sum(g["content_extracted"] for g in grades),
        },
        "ready_for_student_answers": False,
        "note": "Metadata counts are not curriculum completeness. No official expected book counts are asserted.",
    }

def main():
    parser = argparse.ArgumentParser(description="Audit coverage of local metadata inventory")
    parser.add_argument("--db", default=str(ROOT / "curriculum.sqlite3"))
    args = parser.parse_args()
    print(json.dumps(coverage_report(args.db), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
