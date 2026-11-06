"""Fail-closed, metadata-only retrieval eligibility gate; never returns textbook text."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from curriculum import connect

ROOT = Path(__file__).resolve().parent

def _secure(url):
    if not isinstance(url, str) or any(char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\" for char in url):
        return False  # Reject whitespace/control characters before urlsplit normalizes them.
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and bool(u.hostname) and not (u.username or u.password)
                and (u.port is None or 1 <= u.port <= 65535))
    except ValueError:
        return False

def eligible_chunks(db_path, book_id, limit=50):
    if type(book_id) is not int or book_id < 1:
        raise ValueError("positive integer book_id required")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    with connect(db_path) as db:
        book = db.execute("SELECT review_status,rights_status,extraction_status,url FROM books WHERE id=?", (book_id,)).fetchone()
        if not book or book[:3] != ("approved", "permitted", "completed") or not _secure(book[3]):
            return []
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='book_review_events'").fetchone():
            return []
        events = db.execute("SELECT decision,evidence_url FROM book_review_events WHERE book_id=? ORDER BY id", (book_id,)).fetchall()
        permission = False
        for decision, evidence_url in events:
            if decision not in ("restrict_content", "reject_metadata", "permit_content"):
                return []  # Unknown audit events must not silently preserve access.
            if decision in ("restrict_content", "reject_metadata"):
                permission = False
            elif decision == "permit_content":
                permission = _secure(evidence_url)
        if not permission:
            return []
        rows = db.execute("""SELECT c.id,c.page_start,c.page_end FROM chunks c
            JOIN lessons l ON c.lesson_id=l.id JOIN units u ON l.unit_id=u.id
            WHERE u.book_id=? AND c.review_status='approved'
            AND c.page_start >= 1 AND c.page_end >= c.page_start
            ORDER BY u.sequence,l.sequence,c.id LIMIT ?""", (book_id,limit)).fetchall()
        return [{"chunk_id":r[0],"page_start":r[1],"page_end":r[2]} for r in rows]

def main():
    p = argparse.ArgumentParser(description="Check approved chunk IDs; no textbook content returned")
    p.add_argument("--db", default=str(ROOT / "curriculum.sqlite3"))
    p.add_argument("--book-id", type=int, required=True)
    p.add_argument("--limit", type=int, default=50)
    a = p.parse_args()
    rows = eligible_chunks(a.db, a.book_id, a.limit)
    print(json.dumps({"book_id":a.book_id,"eligible_chunk_count":len(rows),"chunks":rows}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
