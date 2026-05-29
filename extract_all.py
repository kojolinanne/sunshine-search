#!/usr/bin/env python3
"""從廉政專刊 PDF 萃取文字 - 處理全部 20 期"""
import subprocess, json, sys
from pathlib import Path

def extract_text(pdf_path):
    result = subprocess.run(
        ['pdftotext', '-enc', 'UTF-8', str(pdf_path), '-'],
        capture_output=True, text=True
    )
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

if __name__ == '__main__':
    download_dir = Path.home() / 'Downloads'
    results = []
    
    # 第300-319期（由大到小）
    for issue in range(319, 299, -1):
        pdf = download_dir / f'廉政專刊第{issue}期.pdf'
        if pdf.exists():
            data = process_pdf(pdf, issue)
            results.append(data)
        else:
            print(f"  找不到：{pdf.name}", file=sys.stderr)
    
    # 輸出 JSON
    output_path = Path(__file__).parent / 'data' / 'issues.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n完成！輸出到：{output_path}", file=sys.stderr)
    print(f"共 {len(results)} 期，總 {sum(d['total_chars'] for d in results):,} 字", file=sys.stderr)
