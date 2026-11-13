"""Compare official curriculum source IDs with a local transfer manifest.

No book text or PDF bytes are read, downloaded, or stored.
The official snapshot must be independently verified before use.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

SOURCE_PATH = re.compile(r"/ar/manaheg/\d+/show/(\d+)(?:[/?#]|$)")


def source_id(value):
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return str(value)
    if isinstance(value, str):
        value = value.strip()
        if DIGITS.fullmatch(value):
            return str(int(value))
        try:
            parsed = urlsplit(value)
            if (parsed.scheme == 'https' and parsed.hostname == 'home.moe.gov.om'
                    and parsed.username is None and parsed.password is None
                    and parsed.port is None):
                match = SOURCE_PATH.fullmatch(parsed.path)
                if match:
                    return str(int(match.group(1)))
        except ValueError:
            pass
    raise ValueError(f"Invalid or untrusted source identifier: {value!r}")

def compare(manifest, official_ids):
    records = manifest['records']
    if not isinstance(records, list):
        raise ValueError('records must be a list')
    old = [source_id(r['id']) for r in records]
    new = [source_id(i) for i in official_ids]
    if len(set(old)) != len(old) or len(set(new)) != len(new):
        raise ValueError('Duplicate source identifiers; review input before comparing')
    old_set, new_set = set(old), set(new)
    return {'manifest_count': len(old), 'official_count': len(new),
            'new_source_ids': sorted(new_set - old_set, key=int),
            'missing_from_official_snapshot': sorted(old_set - new_set, key=int),
            'shared_count': len(old_set & new_set),
            'warning': 'ID differences do not establish PDF availability, edition, or grade/semester.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('official_snapshot', type=Path,
                        help='Verified JSON array of official source IDs or official page URLs')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    snapshot = json.loads(args.official_snapshot.read_text(encoding='utf-8'))
    if not isinstance(snapshot, list):
        parser.error('official_snapshot must be a JSON array')
    print(json.dumps(compare(manifest, snapshot), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
