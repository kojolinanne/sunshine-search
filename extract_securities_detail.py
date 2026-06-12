#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的有價證券明細（股票、基金受益憑證）。
策略：pdftotext 快速建立人名→頁面索引，只萃取相關頁面。
每期約 30-60 秒，跑完 28 期預估 20-40 分鐘。
"""
import subprocess, pdfplumber, re, json, time
from pathlib import Path

ROOT = Path('/home/openclaw/.openclaw/workspace_coding/sunshine-search')
PDF_DIR = Path.home() / 'Downloads' / '廉政專刊'
OUT_FILE = ROOT / 'data' / 'securities_detail.json'

def parse_num(s):
    if not s: return None
    s = str(s).strip().replace(',', '').replace(' ', '')
    try: return int(float(s))
    except: return None

def extract_from_pdf(pdf_path):
    """萃取單一 PDF 的所有有價證券資料"""
    # pdftotext 快速分頁（~3秒）
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(f'    pdftotext 失敗: {r.stderr}')
        return {}
    pages_text = [p for p in r.stdout.split('\x0c') if p.strip()]

    # 建立「人名 → 出現頁面集合」
    person_pages = {}
    for pi, text in enumerate(pages_text):
        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2:
                person_pages.setdefault(name, set()).add(pi)
    
    # 展開：任何頁面有此人名字都加入（處理股票/基金頁沒有申報人姓名的情況）
    name_to_all_pages = {n: s.copy() for n, s in person_pages.items()}
    for pi, text in enumerate(pages_text):
        for name in person_pages:
            if name in text:
                name_to_all_pages[name].add(pi)

    all_results = {}

    with pdfplumber.open(pdf_path) as pdf:
        for person_name, page_set in name_to_all_pages.items():
            person_data = {'stock': [], 'bond': [], 'fund': []}

            for pi in page_set:
                if pi >= len(pdf.pages): continue
                page_text_pdftxt = pages_text[pi] if pi < len(pages_text) else ''
                if person_name not in page_text_pdftxt: continue

                page = pdf.pages[pi]
                tables = page.extract_tables() or []

                for tbl in tables:
                    if not tbl or len(tbl) < 2: continue
                    header = [str(v or '').strip() for v in tbl[0]]
                    hdr_str = ' '.join(header)

                    # 股票表格（沒有「受託投資機構」）
                    if re.search(r'名.{0,3}稱.*所.{0,3}有.{0,3}人', hdr_str) and len(header) >= 4 and '受' not in hdr_str:
                        for row in tbl[1:]:
                            if not row: continue
                            row_c = [str(v or '').strip() for v in row]
                            if all(v in ('', '本欄空白') for v in row_c): continue
                            holder = row_c[1] if len(row_c) > 1 else ''
                            if person_name not in holder: continue
                            person_data['stock'].append({
                                'name': re.sub(r'\s+', '', row_c[0]),
                                'shares': parse_num(row_c[2]) if len(row_c) > 2 else None,
                                'unit_price': parse_num(row_c[3]) if len(row_c) > 3 else None,
                                'currency': row_c[4] if len(row_c) > 4 else '新臺幣',
                                'amount': parse_num(row_c[-1]) if row_c[-1] else None,
                            })

                    # 基金表格（有「單位數/單位淨值」+「受託投資機構」）
                    elif re.search(r'單.{0,3}位.{0,3}數|單位淨值', hdr_str) and '受' in hdr_str:
                        for row in tbl[1:]:
                            if not row: continue
                            row_c = [str(v or '').strip() for v in row]
                            if all(v in ('', '本欄空白') for v in row_c): continue
                            holder = row_c[1] if len(row_c) > 1 else ''
                            if person_name not in holder: continue
                            person_data['fund'].append({
                                'name': re.sub(r'\s+', '', row_c[0]),
                                'units': parse_num(row_c[3]) if len(row_c) > 3 else None,
                                'nav': parse_num(row_c[4]) if len(row_c) > 4 else None,
                                'currency': row_c[5] if len(row_c) > 5 else '新臺幣',
                                'amount': parse_num(row_c[-1]) if row_c[-1] else None,
                            })

            if person_data['stock'] or person_data['fund']:
                all_results[person_name] = person_data

    # 合併跨列斷行（公司名被 pdftotext 切斷）
    for person, data in all_results.items():
        for k in data:
            merged = []
            for entry in data[k]:
                prev = merged[-1] if merged else None
                if (prev and all(prev.get(f) is None for f in ['amount', 'shares', 'units'])
                    and all(entry.get(f) is None for f in ['amount', 'shares', 'units'])):
                    prev['name'] += entry['name']
                else:
                    merged.append(entry)
            data[k] = merged

    return all_results

def main():
    issues = list(range(292, 320))  # 292-319
    all_data = {}

    # 讀取已存在的進度（支援中斷後重啟）
    if OUT_FILE.exists():
        try:
            with open(OUT_FILE, encoding='utf-8') as f:
                all_data = json.load(f)
            print(f'已讀取 {len(all_data)} 期歷史進度')
        except Exception:
            pass

    for issue_num in issues:
        issue_key = str(issue_num)
        if issue_key in all_data:
            print(f'第 {issue_num} 期：已有資料，跳過')
            continue

        pdf_path = PDF_DIR / f'廉政專刊第{issue_num}期.pdf'
        if not pdf_path.exists():
            print(f'第{issue_num}期：PDF 不存在，跳過')
            continue

        t0 = time.time()
        print(f'處理第 {issue_num} 期 ({pdf_path.stat().st_size/1024/1024:.1f}MB)...', flush=True)
        result = extract_from_pdf(pdf_path)
        elapsed = time.time() - t0

        if result:
            all_data[issue_key] = result
            # 每期處理完立即寫入（進度保存）
            with open(OUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            stock_total = sum(len(v['stock']) for v in result.values())
            fund_total = sum(len(v['fund']) for v in result.values())
            print(f'  ✓ {len(result)} 人，股票 {stock_total} 筆，基金 {fund_total} 筆（{elapsed:.0f}s）')
        else:
            print(f'  - 無有價證券資料（{elapsed:.0f}s）')

    # 最終寫入
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    total_stock = sum(sum(len(p['stock']) for p in v.values()) for v in all_data.values())
    total_fund = sum(sum(len(p['fund']) for p in v.values()) for v in all_data.values())
    print(f'\n完成：{len(all_data)} 期，股票 {total_stock} 筆記錄，基金 {total_fund} 筆記錄')
    print(f'寫入：{OUT_FILE}')

if __name__ == '__main__':
    print(f'PDF 目錄：{PDF_DIR}')
    print(f'輸出：{OUT_FILE}')
    print('=' * 40)
    main()