"""Explicit, auditable curriculum book review. Never grants permissions automatically."""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from curriculum import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS book_review_events (
 id INTEGER PRIMARY KEY,
 book_id INTEGER NOT NULL REFERENCES books(id),
 decision TEXT NOT NULL CHECK(decision IN ('verify_metadata','reject_metadata','permit_content','restrict_content')),
 reviewer TEXT NOT NULL,
 evidence_url TEXT NOT NULL,
 note TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_events_book ON book_review_events(book_id);
"""

def apply_decision(db_path, book_id, decision, reviewer, evidence_url, note):
    if decision not in ('verify_metadata', 'reject_metadata', 'permit_content', 'restrict_content'):
        raise ValueError('Unsupported decision')
    if not isinstance(book_id, int) or book_id < 1:
        raise ValueError('Valid book ID required')
    if not reviewer or not reviewer.strip() or not note or not note.strip():
        raise ValueError('Reviewer and justification are mandatory')
    parsed = urlsplit(evidence_url)
    if parsed.scheme != 'https' or not parsed.hostname:
        raise ValueError('HTTPS evidence URL required')
    if decision == 'permit_content' and ('permission' not in note.lower() and 'إذن' not in note):
        raise ValueError('Content permission must mention explicit permission in the note')
    with connect(db_path) as db:
        db.executescript(SCHEMA)
        row = db.execute('SELECT id, review_status, rights_status FROM books WHERE id=?', (book_id,)).fetchone()
        if row is None:
            raise ValueError('Book does not exist')
        if decision == 'verify_metadata':
            db.execute("UPDATE books SET review_status='approved' WHERE id=?", (book_id,))
        elif decision == 'reject_metadata':
            db.execute("UPDATE books SET review_status='rejected', rights_status='unknown' WHERE id=?", (book_id,))
        elif decision == 'permit_content':
            if row[1] != 'approved':
                raise ValueError('Metadata must be independently approved before content permission')
            db.execute("UPDATE books SET rights_status='permitted' WHERE id=?", (book_id,))
        elif decision == 'restrict_content':
            db.execute("UPDATE books SET rights_status='restricted' WHERE id=?", (book_id,))
        db.execute("""INSERT INTO book_review_events(book_id,decision,reviewer,evidence_url,note,created_at)
                   VALUES(?,?,?,?,?,?)""",
                   (book_id, decision, reviewer.strip(), evidence_url, note.strip(),
                    datetime.now(timezone.utc).isoformat()))
    return {'book_id': book_id, 'decision': decision}

def review_report(db_path):
    with connect(db_path) as db:
        db.executescript(SCHEMA)
        return {
          'pending_metadata': db.execute("SELECT count(*) FROM books WHERE review_status='pending'").fetchone()[0],
          'approved_metadata': db.execute("SELECT count(*) FROM books WHERE review_status='approved'").fetchone()[0],
          'permitted_content': db.execute("SELECT count(*) FROM books WHERE rights_status='permitted' AND review_status='approved'").fetchone()[0],
          'review_events': db.execute("SELECT count(*) FROM book_review_events").fetchone()[0]
        }

def main():
    p = argparse.ArgumentParser(description='Audit book metadata and content permissions')
    p.add_argument('command', choices=['report','review'])
    p.add_argument('--db', default=str(Path(__file__).resolve().parent / 'curriculum.sqlite3'))
    p.add_argument('--book-id', type=int)
    p.add_argument('--decision', choices=['verify_metadata','reject_metadata','permit_content','restrict_content'])
    p.add_argument('--reviewer')
    p.add_argument('--evidence-url')
    p.add_argument('--note')
    a = p.parse_args()
    if a.command == 'report':
        value = review_report(a.db)
    else:
        if not all((a.book_id,a.decision,a.reviewer,a.evidence_url,a.note)):
            p.error('review requires --book-id, --decision, --reviewer, --evidence-url and --note')
        value = apply_decision(a.db,a.book_id,a.decision,a.reviewer,a.evidence_url,a.note)
    print(json.dumps(value, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
