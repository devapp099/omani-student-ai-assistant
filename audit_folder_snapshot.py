"""Audit a Drive folder snapshot without trusting filenames as curriculum evidence.

Input: ledger JSON and snapshot JSON mapping folder keys (e.g. "4:1") to
arrays of Google Drive metadata. This never reads or indexes PDF contents.
"""
import argparse
import json
from pathlib import Path


def audit(ledger, snapshot):
    folders = ledger.get("folder_map", {})
    registered = {}
    ledger_errors = []
    for rec in ledger.get("records", []):
        if rec.get("status") == "uploaded_verified":
            item = rec.get("drive_file") or {}
            if item.get("id"):
                if item["id"] in registered:
                    ledger_errors.append(f"duplicate registered Drive ID: {item['id']}")
                else:
                    registered[item["id"]] = (str(rec.get("id")), item)
    seen = set()
    errors, pending_review, verified = ledger_errors, [], []
    for folder_key, items in snapshot.items():
        if folder_key not in folders:
            errors.append(f"unknown folder key: {folder_key}")
            continue
        if not isinstance(items, list):
            errors.append(f"invalid listing: {folder_key}")
            continue
        for item in items:
            if not isinstance(item, dict):
                errors.append(f"invalid file metadata in {folder_key}")
                continue
            fid = item.get("id")
            if not isinstance(fid, str) or not fid:
                errors.append(f"missing file ID in {folder_key}")
                continue
            if fid in seen:
                errors.append(f"duplicate file ID in snapshot: {fid}")
                continue
            seen.add(fid)
            if item.get("mime_type", item.get("mimeType")) != "application/pdf":
                continue
            size = item.get("size")
            if isinstance(size, bool) or not str(size).isdigit() or int(size) < 1:
                errors.append(f"invalid PDF size: {fid}")
                continue
            if fid not in registered:
                pending_review.append({"id": fid, "folder_key": folder_key,
                                       "name": item.get("title", item.get("name", "")),
                                       "reason": "unregistered; do not index"})
                continue
            source, saved = registered[fid]
            problems = []
            if saved.get("folder_key") != folder_key:
                problems.append(f"source {source}: wrong folder for {fid}")
            if str(saved.get("size")) != str(size):
                problems.append(f"source {source}: size mismatch for {fid}")
            if saved.get("parent_id") != folders[folder_key]:
                problems.append(f"source {source}: ledger parent mismatch for {fid}")
            if problems:
                errors.extend(problems)
            else:
                verified.append(source)
    # Only report missing files in folders actually included in this snapshot.
    # Partial inventories must not imply that other registered files vanished.
    covered = {key for key, items in snapshot.items()
               if key in folders and isinstance(items, list)}
    missing = {fid for fid, (_, item) in registered.items()
               if item.get("folder_key") in covered and fid not in seen}
    return {"errors": errors, "unregistered": pending_review,
            "matched_registered": sorted(verified, key=int),
            "registered_not_seen": sorted(missing)}


def self_test():
    ledger = {"folder_map": {"2:1": "folder-A", "4:1": "folder-B"},
              "records": [{"id": "25", "status": "uploaded_verified",
                           "drive_file": {"id": "pdf1", "size": "123",
                                          "folder_key": "2:1", "parent_id": "folder-A"}}]}
    a = {"id": "pdf1", "mime_type": "application/pdf", "size": "123"}
    b = {"id": "pdf2", "mime_type": "application/pdf", "size": "15106"}
    assert audit(ledger, {"2:1": [a]})["matched_registered"] == ["25"]
    assert len(audit(ledger, {"2:1": [a, b]})["unregistered"]) == 1
    assert audit(ledger, {"4:1": [a]})["errors"]
    assert audit(ledger, {"4:1": [a]})["matched_registered"] == []
    assert audit(ledger, {"2:1": [a, a]})["errors"]
    assert audit(ledger, {"2:1": [dict(a, size="124")]})["errors"]
    assert audit(ledger, {"2:1": [dict(a, size="124")]})["matched_registered"] == []
    assert audit(ledger, {"2:1": [dict(a, size=True)]})["errors"]
    assert audit(ledger, {"2:1": []})["registered_not_seen"] == ["pdf1"]
    assert audit(ledger, {"unknown": []})["errors"]
    duplicate_ledger = dict(ledger, records=ledger["records"] * 2)
    assert any("duplicate registered Drive ID" in e for e in audit(duplicate_ledger, {"2:1": [a]})["errors"])
    assert audit(ledger, {})["registered_not_seen"] == []
    assert audit(ledger, {"4:1": []})["registered_not_seen"] == []
    assert any("invalid file metadata" in e for e in audit(ledger, {"2:1": [None]})["errors"])
    assert any("invalid file metadata" in e for e in audit(ledger, {"2:1": ["bad"]})["errors"])
    print("15 folder snapshot assertions passed")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("ledger", nargs="?", type=Path)
    p.add_argument("snapshot", nargs="?", type=Path)
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
    else:
        if not args.ledger or not args.snapshot:
            p.error("ledger and snapshot required")
        result = audit(json.loads(args.ledger.read_text(encoding="utf-8")),
                       json.loads(args.snapshot.read_text(encoding="utf-8")))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(bool(result["errors"]))
