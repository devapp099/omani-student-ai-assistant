"""Create a blank, reviewable manual-download manifest; never download books."""
import argparse
import csv
import unicodedata
from pathlib import Path
from manifest_cell_safety import suspicious_cells
from retrieval_gate import _secure

FIELDS = ("grade", "semester", "subject", "book_type", "title", "official_url",
          "school_year", "edition", "download_status", "upload_status",
          "metadata_review", "rights_status", "local_filename", "notes")
STATUSES = {"not_downloaded", "downloaded"}
UPLOADS = {"not_uploaded", "uploaded"}
REVIEWS = {"pending", "approved", "rejected"}
RIGHTS = {"unknown", "permitted", "restricted"}


def blank_manifest(path):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing manifest: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
    return path


def validate_manifest(path):
    errors = []
    seen = set()
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != list(FIELDS):
            return ["CSV header does not match expected manifest schema"]
        for line, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                errors.append(f"line {line}: malformed column count")
                continue
            for field in suspicious_cells(row):
                errors.append(f"line {line}: spreadsheet formula-like value in {field}")
            # Detect duplicate entries without assuming book titles are globally unique.
            identity = tuple(row[field].strip().casefold() for field in
                             ("grade", "semester", "subject", "book_type", "title", "official_url"))
            if identity in seen:
                errors.append(f"line {line}: duplicate book entry")
            seen.add(identity)
            if row["grade"] not in {str(i) for i in range(1, 13)}:
                errors.append(f"line {line}: invalid grade")
            if row["semester"] not in {"1", "2"}:
                errors.append(f"line {line}: invalid semester")
            if not row["title"].strip() or not row["subject"].strip():
                errors.append(f"line {line}: missing verified title or subject")
            if not _secure(row["official_url"]):
                errors.append(f"line {line}: official URL must be HTTPS")
            if row["download_status"] not in STATUSES:
                errors.append(f"line {line}: invalid download status")
            if row["upload_status"] not in UPLOADS:
                errors.append(f"line {line}: invalid upload status")
            if row["metadata_review"] not in REVIEWS:
                errors.append(f"line {line}: invalid review status")
            if row["rights_status"] not in RIGHTS:
                errors.append(f"line {line}: invalid rights status")
            filename = row["local_filename"]
            if filename and (filename in {".", ".."} or "/" in filename or "\\" in filename):
                errors.append(f"line {line}: local filename must not contain paths")
            if filename and (any(ord(c) < 32 or ord(c) == 127 or unicodedata.category(c) == "Cf" for c in filename)
                             or filename != filename.strip() or filename.endswith((".", " "))):
                errors.append(f"line {line}: unsafe local filename")
            if row["upload_status"] == "uploaded" and not filename:
                errors.append(f"line {line}: uploaded book requires local filename")
            if row["upload_status"] == "uploaded" and row["download_status"] != "downloaded":
                errors.append(f"line {line}: upload cannot precede download")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Manual book manifest; no PDF downloads or textbook storage")
    parser.add_argument("command", choices=["init", "check"])
    parser.add_argument("--file", default="manual_books_manifest.csv")
    args = parser.parse_args()
    if args.command == "init":
        print(blank_manifest(args.file))
    else:
        errors = validate_manifest(args.file)
        for error in errors:
            print(error)
        print(f"{len(errors)} issue(s)")
        if errors:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
