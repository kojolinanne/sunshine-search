#!/usr/bin/env python3
"""從廉政專刊 PDF 萃取文字並輸出 JSON"""
import subprocess, json, re, sys
from pathlib import Path

def extract_text(pdf_path):
    """用 pdftotext 萃文字"""
    result = subprocess.run(
        ['pdftotext', '-enc', 'UTF-8', pdf_path, '-'],
        capture_output=True, text=True
    )
    return result.stdout

def clean_text(text):
    """簡單清理：移除行首/行尾多餘空白"""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if line:
            cleaned.append(line)
    return '\n'.join(cleaned)

def chunk_by_pages(raw_text, pages_info, page_size=50):
    """將文字依頁數分塊"""
    # 簡單分塊：每 N 行為一塊
    lines = raw_text.split('\n')
    chunks = []
    for i in range(0, len(lines), page_size):
        chunk_text = '\n'.join(lines[i:i+page_size])
        chunks.append({
            "chunk_id": i // page_size + 1,
            "text": chunk_text,
            "start_line": i
        })
    return chunks

def process_pdf(pdf_path, issue_num):
    text = extract_text(pdf_path)
    cleaned = clean_text(text)
    
    # 簡單取前 50 行作為摘要預覽
    preview = '\n'.join(cleaned.split('\n')[:30])
    
    return {
        "issue": issue_num,
        "total_chars": len(cleaned),
        "preview": preview,
        "full_text": cleaned  # 全文（搜尋用）
    }

if __name__ == '__main__':
    import os
    
    download_dir = Path.home() / 'Downloads'
    results = []
    
    # 處理第300-319期（先處理3期測試）
    for issue in [319, 318, 317]:
        pdf = download_dir / f'廉政專刊第{issue}期.pdf'
        if pdf.exists():
            print(f"處理中：第{issue}期...", file=sys.stderr)
            data = process_pdf(str(pdf), issue)
            results.append(data)
            print(f"  完成，字符數：{data['total_chars']:,}", file=sys.stderr)
        else:
            print(f"  找不到：{pdf}", file=sys.stderr)
    
    # 輸出 JSON
    output_path = Path(__file__).parent / 'data' / 'issues_sample.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"輸出：{output_path}", file=sys.stderr)
