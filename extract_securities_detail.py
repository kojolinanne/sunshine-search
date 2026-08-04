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

def parse_float_num(s):
    """Parse a number that may have decimals (e.g. nav, unit price)"""
    if not s: return None
    s = str(s).strip().replace(',', '').replace(' ', '')
    try: return float(s)
    except: return None


def _parse_stocks_from_text(text, person_name):
    """Fallback: parse stock rows from pdftotext layout when pdfplumber can't find tables.
    
    Stock row format in pdftotext:
        股票名          所有人             股數        面額10        新台幣總額
    e.g.: 台中銀          陳鴻源             4,945          10          49,450
    
    Rows may have blank lines between them.
    """
    results = []
    # Find stock section: "1.股票" or "股票（"
    stock_idx = text.find('股票')
    if stock_idx < 0:
        return results
    # Look for the stock header line and data after it
    stock_section = text[stock_idx:]
    
    # Pattern: 股票名 (spaces) 人名 (spaces) 股數 digits or comma (spaces) 面額 10 (spaces) 總額
    # Lines look like: "台泥控股         陳xx                  4,945           10                   49,450"
    # or multi-line name: "
    #                   大立光電           陳炳甫             3,000               10              30,000"
    for line in stock_section.split('\n'):
        line = line.strip()
        if not line or len(line) < 10:
            continue
        # Skip header lines and other non-data lines
        if any(kw in line for kw in ['股票', '有價證券', '名', '稱', '所', '有', '人', '股', '數', '票', '面', '價', '額', '總', '監察院公報', '專', '刊', '申報']):
            continue
        # Skip pure number lines and lines that look like page footers
        if re.match(r'^[\d\s,.-]+$', line):
            continue
        # Check if the line contains the person's name
        if person_name not in line:
            continue
        
        # Try to parse: name, shares, unit_price (10), total
        # Split by 2+ spaces (pdftotext layout format)
        parts = re.split(r'\s{2,}', line)
        if len(parts) < 2:
            continue
        
        # The last part should be the total amount (numbers)
        amount_part = None
        for p in reversed(parts):
            n = parse_num(p)
            if n is not None and n >= 100:
                amount_part = n
                break
        
        if amount_part is None:
            continue
        
        # Find shares: a number before the amount
        shares = None
        for p in reversed(parts[:-1]):
            n = parse_num(p)
            if n is not None and n > 0 and n != 10:  # skip the 10 unit price
                shares = n
                break
        
        # The name of the stock: everything before the shares
        person_idx = line.find(person_name)
        if person_idx < 0:
            continue
        stock_name = line[:person_idx].strip()
        # Clean up stock name (remove trailing spaces, merge if split)
        stock_name = re.sub(r'\s+', '', stock_name)
        if not stock_name:
            stock_name = '（未解析）'
        
        results.append({
            'name': stock_name,
            'shares': shares,
            'unit_price': 10,
            'currency': '新臺幣',
            'amount': amount_part,
        })
    
    return results


def _parse_funds_from_text(text, person_name):
    """Fallback: parse fund rows from pdftotext layout when pdfplumber can't find tables."""
    results = []
    # Find fund section: "受益憑證" or "基金" or "3."
    fund_idx = text.find('受益憑證')
    if fund_idx < 0:
        fund_idx = text.find('基金')
    if fund_idx < 0:
        return results
    fund_section = text[fund_idx:]
    
    for line in fund_section.split('\n'):
        line = line.strip()
        if not line or len(line) < 10:
            continue
        if person_name not in line:
            continue
        # Skip header lines
        if any(kw in line for kw in ['受益憑證', '基金', '名', '稱', '所', '有', '人', '受託', '單', '位', '數', '淨值', '票', '面', '總', '監察院', '廉價']):
            continue
        if re.match(r'^[\d\s,.-]+$', line):
            continue
        
        # Split by 2+ spaces
        parts = re.split(r'\s{2,}', line)
        if len(parts) < 3:
            continue
        
        # Find amount (last numeric)
        amount = None
        for p in reversed(parts):
            n = parse_num(p)
            if n is not None and n > 0:
                amount = n
                break
        if amount is None:
            continue
        
        # Find units (second-last numeric)
        units = None
        found_amount = False
        for p in reversed(parts):
            n = parse_num(p)
            if n is not None:
                if not found_amount:
                    found_amount = True
                    continue
                units = n
                break
        
        # Find nav (third-last numeric)
        nav = None
        found_units = False
        count = 0
        for p in reversed(parts):
            n = parse_float_num(p)
            if n is not None:
                count += 1
                if count == 3:
                    nav = n
                    break
        
        # Stock/fund name
        person_idx = line.find(person_name)
        if person_idx < 0:
            continue
        fund_name = line[:person_idx].strip()
        fund_name = re.sub(r'\s+', '', fund_name)
        if not fund_name:
            fund_name = '（未解析）'
        
        results.append({
            'name': fund_name,
            'units': units,
            'nav': nav,
            'currency': '新臺幣',
            'amount': amount,
        })
    
    return results

def extract_from_pdf(pdf_path, pages_text=None):
    """萃取單一 PDF 的所有有價證券資料
    
    策略：
    1. 先用 pdftotext 快速取得全文（~3秒），建立人名→頁面索引
    2. 只在候選頁面用 pdfplumber 提取表格
    3. 對於 pdfplumber 無法抓到的表格，fallback 到 text-based parsing
    """
    # pdftotext 快速分頁（~3秒）
    if pages_text is None:
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

    # 找出所有包含證券資料的候選頁面（減少 pdfplumber 開啟次數）
    securities_page_indices = set()
    for pi, text in enumerate(pages_text):
        if '有價證券' in text or '股票' in text or '受益憑證' in text:
            securities_page_indices.add(pi)

    all_results = {}

    # 只用 pdfplumber 提取候選頁面（大幅降低記憶體使用）
    table_extracted = []  # pages where pdfplumber found tables
    if securities_page_indices:
        with pdfplumber.open(pdf_path) as pdf:
            for pi in securities_page_indices:
                if pi >= len(pdf.pages):
                    continue
                page = pdf.pages[pi]
                tables = page.extract_tables() or []

                for tbl in tables:
                    if not tbl or len(tbl) < 2:
                        continue
                    header = [str(v or '').strip() for v in tbl[0]]
                    hdr_str = ' '.join(header)

                    # 判斷是否為證券表格
                    is_stock = re.search(r'名.{0,3}稱.*所.{0,3}有.{0,3}人', hdr_str) and len(header) >= 4 and '受' not in hdr_str
                    is_fund = re.search(r'單.{0,3}位.{0,3}數|單位淨值', hdr_str) and '受' in hdr_str
                    if not is_stock and not is_fund:
                        continue

                    table_extracted.append(pi)

                    for row in tbl[1:]:
                        if not row:
                            continue
                        row_c = [str(v or '').strip() for v in row]
                        if all(v in ('', '本欄空白') for v in row_c):
                            continue
                        holder = row_c[1] if len(row_c) > 1 else ''
                        # 找到該 row 對應的申報人
                        matched_name = None
                        for name in name_to_all_pages:
                            if re.search(re.escape(name), holder):
                                matched_name = name
                                break
                        if not matched_name:
                            continue

                        entry = None
                        if is_stock:
                            entry = {
                                'name': re.sub(r'\s+', '', row_c[0]),
                                'shares': parse_num(row_c[2]) if len(row_c) > 2 else None,
                                'unit_price': parse_num(row_c[3]) if len(row_c) > 3 else None,
                                'currency': row_c[4] if len(row_c) > 4 else '新臺幣',
                                'amount': parse_num(row_c[-1]) if row_c[-1] else None,
                            }
                        elif is_fund:
                            entry = {
                                'name': re.sub(r'\s+', '', row_c[0]),
                                'units': parse_num(row_c[3]) if len(row_c) > 3 else None,
                                'nav': parse_num(row_c[4]) if len(row_c) > 4 else None,
                                'currency': row_c[5] if len(row_c) > 5 else '新臺幣',
                                'amount': parse_num(row_c[-1]) if row_c[-1] else None,
                            }

                        if entry is None:
                            continue

                        if matched_name not in all_results:
                            all_results[matched_name] = {'stock': [], 'bond': [], 'fund': []}
                        target = 'stock' if is_stock else 'fund'
                        all_results[matched_name][target].append(entry)

    # Text-based fallback：對 pdfplumber 沒抓到表格的 securities 頁 + 人名匹配
    
    # 先對每個申報人，找出他們在 securities 相關頁面的出現
    for person_name, page_set in name_to_all_pages.items():
        # skip if already extracted in this run
        if person_name in all_results:
            continue
        person_data = {'stock': [], 'bond': [], 'fund': []}

        for pi in page_set:
            page_txt = pages_text[pi] if pi < len(pages_text) else ''
            if person_name not in page_txt:
                continue

            # 只在有證券相關字眼的頁面做 text parsing
            if '有價證券' not in page_txt and '股票' not in page_txt and '受益憑證' not in page_txt:
                continue

            # Try text-based stock parsing
            stock_entries = _parse_stocks_from_text(page_txt, person_name)
            if stock_entries:
                person_data['stock'].extend(stock_entries)
            # Try text-based fund parsing
            fund_entries = _parse_funds_from_text(page_txt, person_name)
            if fund_entries:
                person_data['fund'].extend(fund_entries)

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