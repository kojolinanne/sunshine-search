#!/usr/bin/env python3
"""從單一廉政專刊 PDF 萃取文字並更新 data/。"""
import argparse
import re
import sys
from pathlib import Path

from extract_all import process_pdf, rebuild_index, write_issue

PDF_RE = re.compile(r'廉政專刊第(\d+)期\.pdf$')

def parse_args():
    parser = argparse.ArgumentParser(description='更新單一期別的廉政專刊搜尋資料')
    parser.add_argument('pdf', type=Path, help='PDF 路徑，例如 ~/Downloads/廉政專刊第320期.pdf')
    parser.add_argument('--issue', type=int, help='手動指定期數，預設由檔名解析')
    return parser.parse_args()

def infer_issue(pdf_path, issue):
    if issue is not None:
        return issue

    match = PDF_RE.search(pdf_path.name)
    if not match:
        raise ValueError('無法從檔名解析期數，請使用 --issue 指定')
    return int(match.group(1))

def main():
    args = parse_args()
    pdf_path = args.pdf.expanduser()
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    issue = infer_issue(pdf_path, args.issue)
    data = process_pdf(pdf_path, issue)
    output_path = write_issue(data)
    issues, index_path = rebuild_index()

    from build_statistics import main as build_statistics
    build_statistics()

    print(f"輸出：{output_path}", file=sys.stderr)
    print(f"索引：{index_path}", file=sys.stderr)
    print(f"共 {len(issues)} 期，總 {sum(d['total_chars'] for d in issues):,} 字", file=sys.stderr)

if __name__ == '__main__':
    main()
