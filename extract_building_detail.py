#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的建物明細（房屋及停車位）。
策略：pdftotext -layout 文字解析，不依賴 pdfplumber（建物表格無邊框）。
"""
import subprocess, re, json, time
from pathlib import Path

ROOT = Path('/home/openclaw/.openclaw/workspace_coding/sunshine-search')
PDF_DIR = Path.home() / 'Downloads' / '廉政專刊'
OUT_FILE = ROOT / 'data' / 'building_detail.json'

def parse_num(s):
    if not s: return None
    s = str(s).strip().replace(',', '').replace(' ', '')
    try: return int(float(s))
    except: return None


def extract_from_pdf(pdf_path, pages_text=None):
    if pages_text is None:
        r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return {}
        pages_text = [p for p in r.stdout.split('\x0c') if p.strip()]

    # 建立人名列表
    all_people = set()
    for text in pages_text:
        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2:
                all_people.add(name)

    all_results = {}

    # 每次只處理一個建物頁面
    for pi, text in enumerate(pages_text):
        if '建物' not in text or ('房屋' not in text and '停車位' not in text):
            continue

        # 找建物區段
        idx = text.find('建物')
        end = len(text)
        for marker in ['船舶', '汽車', '航空器', '現金']:
            mi = text.find(marker, idx)
            if mi > 0 and mi < end:
                end = mi
        section = text[idx:end]
        lines = section.split('\n')

        # 建立所有地址行的索引
        addr_lines = []  # [(line_index, owner_name)]
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or len(stripped) < 10:
                continue
            if stripped.startswith('監察院') or stripped.startswith('廉'):
                continue
            # 必須有段+人名
            has_loc = bool(re.search(r'[段區市鄉鎮路街弄村]', stripped))
            if not has_loc:
                continue
            for name in all_people:
                if name in stripped:
                    addr_lines.append((i, name, stripped))
                    break

        # 對每個地址行，往前掃描找 area 和 price
        seen_people = set()
        for i, name, adr_line in addr_lines:
            # 去重：同一人同一個地址行可能出現多次（右側價格註記跨行）
            key = (name, i)
            if key in seen_people:
                continue
            seen_people.add(key)

            # Clean address (remove leading ★/numbers)
            address = re.sub(r'^[\d★\s,\*]+', '', adr_line).strip()
            
            # Extract rights
            rights_match = re.search(r'(全部|[\d,]+\s*分\s*之\s*[\d,]+|\d+\s*分之\s*\d+)', adr_line)
            rights = rights_match.group(0).replace(' ', '') if rights_match else ''

            # Find price: scan lines above the address (within 10 lines)
            # Price is always on the right-hand side, appears as large standalone number
            price = None
            notes = ''
            for j in range(max(0, i - 15), min(len(lines), i + 5)):
                l = lines[j].strip()
                n = parse_num(l)
                if n is not None and n >= 100:  # any price, even small amounts
                    # Skip small numbers that might just be area
                    if n >= 1000:
                        # Pick the lowest price (first one found)
                        if price is None:
                            price = n
                        elif n > price and n > 10000:
                            # If this is likely the real price (near the addr line)
                            if j >= i - 8 and j <= i + 2:
                                price = n
                # Notes: lines with parentheses annotations
                if re.search(r'[\(（]', l):
                    notes += ' '+ l if notes else l

            # Find area from lines above (usually a number like 56.72)
            area = None
            for j in range(max(0, i - 5), i):
                l = lines[j].strip()
                area_match = re.search(r'([\d,]+\.?\d*)', l)
                if area_match:
                    an = parse_num(area_match.group(1))
                    if an and 10 < an < 1000000:
                        area = an
                        break

            if name not in all_results:
                all_results[name] = []
            all_results[name].append({
                'address': address,
                'area': area,
                'rights': rights,
                'price': price,
                'notes': notes[:200],
            })

    return all_results


def main():
    issues = list(range(292, 320))
    all_data = {}

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
            with open(OUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            entry_count = sum(len(v) for v in result.values())
            print(f'  ✓ {len(result)} 人，{entry_count} 筆（{elapsed:.0f}s）')
        else:
            all_data[issue_key] = {}
            print(f'  - 無建物資料（{elapsed:.0f}s）')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    total = sum(sum(len(v) for v in all_data.values()) for v in all_data.values())
    print(f'\n完成：{len(all_data)} 期，{total} 筆建物記錄')
    print(f'寫入：{OUT_FILE}')


if __name__ == '__main__':
    print(f'PDF 目錄：{PDF_DIR}')
    print(f'輸出：{OUT_FILE}')
    print('=' * 40)
    main()