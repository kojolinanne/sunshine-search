#!/usr/bin/env python3
"""
Regenerate declarations.json with full_text included for full-text search (including stock names).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / 'data'
DECL_FILE = DATA / 'declarations.json'
MARKER = '公\n職\n人\n員\n財\n產\n申\n報\n表'
MARKER_ALT = '公\n\n職\n\n人\n\n員\n\n財\n\n產\n\n申\n\n報\n\n表'

def main():
    # Load existing declarations
    with open(DECL_FILE, encoding='utf-8') as f:
        decl = json.load(f)

    # Load all issue full_texts once, indexed by filename
    issue_texts = {}
    for p in DATA.glob('issue_*.json'):
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
        issue_texts[p.name] = data['full_text']

    # Group declarations by source_file
    from collections import defaultdict
    by_source = defaultdict(list)
    for rec in decl['records']:
        by_source[rec['source_file']].append(rec)

    # Attach full_text to each record
    modified = 0
    for src_file, records in by_source.items():
        if src_file not in issue_texts:
            print(f"WARNING: {src_file} not found, skipping {len(records)} records")
            continue

        full_text = issue_texts[src_file]
        # Normalize double-newline-separated characters to single-newline
        # (some issues use 雙行距 markers like '公\n\n職\n\n人\n\n員...')
        normalized = re.sub(r'\n+', '\n', full_text)
        sections = normalized.split(MARKER)
        # sections[0] is empty (before first marker), sections[1..] are actual declarations

        for rec in records:
            seq = rec['sequence']
            if seq < len(sections) and sections[seq]:
                rec['full_text'] = MARKER + sections[seq]  # Include marker for context
                modified += 1
            else:
                rec['full_text'] = ''
                print(f"  WARNING: seq {seq} out of range for {src_file} ({rec['name']})")

    # Save updated declarations
    tmp = DECL_FILE.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(decl, f, ensure_ascii=False, indent=2)
    tmp.rename(DECL_FILE)

    print(f"Done. Updated {modified}/{len(decl['records'])} records.")
    import os
    size = os.path.getsize(DECL_FILE)
    print(f"File size: {size/1024/1024:.1f} MB")

if __name__ == '__main__':
    main()