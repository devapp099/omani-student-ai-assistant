"""Metadata-only Omani curriculum inventory. No book downloading or scraping."""
import argparse
import csv
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS grades (id INTEGER PRIMARY KEY CHECK(id BETWEEN 1 AND 12));
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
  kind TEXT, verification TEXT, rights_status TEXT NOT NULL DEFAULT 'unknown', notes TEXT
);
CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY, name_ar TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY,
  grade_id INTEGER NOT NULL REFERENCES grades(id),
  subject_id INTEGER NOT NULL REFERENCES subjects(id),
  source_id TEXT REFERENCES sources(id),
  title TEXT NOT NULL, academic_year TEXT,
  semester INTEGER CHECK(semester IN (1,2) OR semester IS NULL),
  book_type TEXT, edition TEXT, url TEXT,
  rights_status TEXT NOT NULL DEFAULT 'unknown',
  extraction_status TEXT NOT NULL DEFAULT 'not_started',
  review_status TEXT NOT NULL DEFAULT 'pending',
  sha256 TEXT,
  UNIQUE(grade_id,subject_id,title,academic_year,semester,book_type,edition)
);
CREATE TABLE IF NOT EXISTS units (
  id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id),
  sequence INTEGER NOT NULL, title TEXT NOT NULL, UNIQUE(book_id,sequence)
);
CREATE TABLE IF NOT EXISTS lessons (
  id INTEGER PRIMARY KEY, unit_id INTEGER NOT NULL REFERENCES units(id),
  sequence INTEGER NOT NULL, title TEXT NOT NULL,
  page_start INTEGER, page_end INTEGER,
  CHECK(page_end IS NULL OR page_start IS NULL OR page_end>=page_start),
  UNIQUE(unit_id,sequence)
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY, lesson_id INTEGER NOT NULL REFERENCES lessons(id),
  page_start INTEGER, page_end INTEGER,
  text TEXT NOT NULL, sha256 TEXT NOT NULL,
  review_status TEXT NOT NULL DEFAULT 'pending',
  CHECK(page_end IS NULL OR page_start IS NULL OR page_end>=page_start)
);
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY, entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL,
  decision TEXT NOT NULL, reviewer TEXT, reviewed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS import_jobs (
  id INTEGER PRIMARY KEY, source_id TEXT REFERENCES sources(id),
  state TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, error TEXT
);
CREATE INDEX IF NOT EXISTS idx_books_grade_subject ON books(grade_id,subject_id);
CREATE INDEX IF NOT EXISTS idx_chunks_lesson ON chunks(lesson_id);
"""

def connect(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init(path):
    with connect(path) as db:
        db.executescript(DDL)
        db.executemany("INSERT OR IGNORE INTO grades(id) VALUES (?)", [(i,) for i in range(1,13)])
        with (ROOT / "sources.csv").open(encoding="utf-8-sig", newline="") as source_file:
            for r in csv.DictReader(source_file):
                if urlsplit(r["url"]).scheme != "https":
                    raise ValueError("HTTPS source required")
                db.execute(
                    """INSERT INTO sources(id,name,url,kind,verification,notes)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,url=excluded.url,kind=excluded.kind,
                    verification=excluded.verification,notes=excluded.notes""",
                    (r["source_id"],r["name"],r["url"],r["type"],r["verification"],r["notes"])
                )

def add_book(path, data):
    if any(not data.get(k) for k in ("grade", "subject", "title")):
        raise ValueError("Missing grade, subject or title")
    grade = int(data["grade"])
    if not 1 <= grade <= 12:
        raise ValueError("Grade must be 1..12")
    if data.get("url") and urlsplit(data["url"]).scheme != "https":
        raise ValueError("HTTPS book URL required")
    with connect(path) as db:
        subject = data["subject"].strip()
        title = data["title"].strip()
        db.execute("INSERT OR IGNORE INTO subjects(name_ar) VALUES(?)", (subject,))
        sid = db.execute("SELECT id FROM subjects WHERE name_ar=?", (subject,)).fetchone()[0]
        existing = db.execute(
            """SELECT 1 FROM books WHERE grade_id=? AND subject_id=? AND title=?
            AND academic_year IS ? AND semester IS ? AND book_type IS ? AND edition IS ?""",
            (grade, sid, title, data.get("academic_year"), data.get("semester"),
             data.get("book_type"), data.get("edition"))
        ).fetchone()
        if existing:
            raise sqlite3.IntegrityError("Duplicate book metadata")
        db.execute(
            """INSERT INTO books(grade_id,subject_id,source_id,title,academic_year,
            semester,book_type,edition,url) VALUES(?,?,?,?,?,?,?,?,?)""",
            (grade,sid,data.get("source_id"),title,data.get("academic_year"),
             data.get("semester"),data.get("book_type"),data.get("edition"),data.get("url"))
        )

def report(path):
    with connect(path) as db:
        return {
            "grades": db.execute("SELECT count(*) FROM grades").fetchone()[0],
            "sources": db.execute("SELECT count(*) FROM sources").fetchone()[0],
            "books": db.execute("SELECT count(*) FROM books").fetchone()[0],
            "approved_books": db.execute(
                "SELECT count(*) FROM books WHERE rights_status='permitted' AND review_status='approved'"
            ).fetchone()[0],
            "chunks": db.execute("SELECT count(*) FROM chunks").fetchone()[0]
        }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "report", "add-book"])
    parser.add_argument("--db", default=str(ROOT / "curriculum.sqlite3"))
    parser.add_argument("--json", help="JSON metadata file for add-book")
    args = parser.parse_args()
    if args.command == "init":
        init(args.db)
        print("Initialized:", args.db)
    elif args.command == "report":
        print(json.dumps(report(args.db), ensure_ascii=False, indent=2))
    else:
        if not args.json:
            parser.error("--json required")
        add_book(args.db, json.loads(Path(args.json).read_text(encoding="utf-8")))
        print("Book metadata added")

if __name__ == "__main__":
    main()
