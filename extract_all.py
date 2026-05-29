#!/usr/bin/env python3
"""從 Downloads 內的廉政專刊 PDF 萃取文字並更新 data/。"""
import json
import re
import subprocess
import sys
from pathlib import Path

PDF_RE = re.compile(r'^廉政專刊第(\d+)期\.pdf$')
ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / 'data'
DOWNLOAD_DIR = Path.home() / 'Downloads'

def extract_text(pdf_path):
    result = subprocess.run(
        ['pdftotext', '-enc', 'UTF-8', str(pdf_path), '-'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f'pdftotext failed: {pdf_path}')
    return result.stdout

def clean_text(text):
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if line:
            cleaned.append(line)
    return '\n'.join(cleaned)

def process_pdf(pdf_path, issue_num):
    print(f"  處理中：第{issue_num}期...", file=sys.stderr)
    text = extract_text(pdf_path)
    cleaned = clean_text(text)
    preview = '\n'.join(cleaned.split('\n')[:30])
    print(f"    完成，{len(cleaned):,} 字", file=sys.stderr)
    return {
        "issue": issue_num,
        "total_chars": len(cleaned),
        "preview": preview,
        "full_text": cleaned
    }

def discover_pdfs():
    pdfs = {}
    for path in DOWNLOAD_DIR.glob('廉政專刊第*期.pdf'):
        match = PDF_RE.match(path.name)
        if match:
            pdfs[int(match.group(1))] = path
    return pdfs

def write_issue(data):
    output_path = DATA_DIR / f'issue_{data["issue"]}.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return output_path

def load_issue(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    return {
        "issue": int(data["issue"]),
        "total_chars": int(data["total_chars"]),
        "preview": data["preview"],
        "full_text": data["full_text"],
    }

def rebuild_index():
    issues = []
    for path in DATA_DIR.glob('issue_*.json'):
        data = load_issue(path)
        issues.append({
            "issue": data["issue"],
            "total_chars": data["total_chars"],
            "preview": data["preview"],
        })

    issues.sort(key=lambda item: item["issue"], reverse=True)
    index_path = DATA_DIR / 'index.json'
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(issues, f, ensure_ascii=False, indent=2)
    return issues, index_path

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = discover_pdfs()

    if not pdfs:
        print(f"Downloads 未找到 {PDF_RE.pattern} 格式的 PDF，僅重建 index.json。", file=sys.stderr)

    for issue, pdf_path in sorted(pdfs.items(), reverse=True):
        data = process_pdf(pdf_path, issue)
        output_path = write_issue(data)
        print(f"    輸出：{output_path.name}", file=sys.stderr)

    issues, index_path = rebuild_index()
    print(f"\n完成！索引輸出到：{index_path}", file=sys.stderr)
    print(f"共 {len(issues)} 期，總 {sum(d['total_chars'] for d in issues):,} 字", file=sys.stderr)

    from build_statistics import main as build_statistics
    build_statistics()

if __name__ == '__main__':
    main()
