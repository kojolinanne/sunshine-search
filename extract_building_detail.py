#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的建物明細（房屋及停車位）。
策略：pdftotext layout → address-name-based 關聯式解析。
建物格式：每個建物以地址行（含 段 + 所有權人姓名）為 anchor，上下合併金額/面積資訊。
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

    # Build person → page index
    person_pages = {}
    for pi, text in enumerate(pages_text):
        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2:
                person_pages.setdefault(name, set()).add(pi)

    # Expand to all pages where name appears
    name_to_all = {}
    for name, pages in person_pages.items():
        name_to_all[name] = set(pages)
    for pi, text in enumerate(pages_text):
        for name in person_pages:
            if name in text:
                name_to_all.setdefault(name, set()).add(pi)

    all_results = {}

    for person_name, page_set in name_to_all.items():
        entries = []
        for pi in page_set:
            page_lines = pages_text[pi].split('\n')
            page_r = _parse_building_page(page_lines, person_name)
            if page_r:
                entries.extend(page_r)
        if entries:
            all_results[person_name] = entries

    return all_results


def _is_building_page(lines):
    """Check if this page contains a building section."""
    text = '\n'.join(lines[:10])
    return '建物' in text and ('房屋' in text or '停車位' in text)


def _is_address_anchor(line, person_name):
    """Check if a line is a building entry anchor (address + owner name)."""
    return (person_name in line and 
            re.search(r'[段區鎮市鄉路街弄]', line) and
            not any(kw in line for kw in ['健全', '建議', '建築']))

def _parse_building_page(page_lines, person_name):
    """Parse building entries from one page for one person."""
    if not _is_building_page(page_lines):
        return []
    if person_name not in '\n'.join(page_lines):
        return []

    # Find building section boundaries
    bldg_start = None
    for i, line in enumerate(page_lines):
        if '建物' in line and ('房屋' in line or '停車位' in line):
            bldg_start = i
            break
    if bldg_start is None:
        return []

    bldg_end = len(page_lines)
    for marker in ['船舶', '航空器', '現金', '存款', '有價證券']:
        for j in range(bldg_start + 2, len(page_lines)):
            if marker in page_lines[j] and not re.search(r'(名|稱|股|基|債|申報)', page_lines[j]):
                bldg_end = min(bldg_end, j)
                break

    lines = page_lines[bldg_start:bldg_end]
    # Strip leading empty lines and footer
    while lines and not lines[-1].strip():
        lines.pop()

    results = []

    for i, line in enumerate(lines):
        if not _is_address_anchor(line, person_name):
            continue

        entry = {}

        # --- Address: extract from the anchor line ---
        # The address is in the left portion, before the rights/owner columns
        # Strip ★ prefix and trailing whitespace/numbers after address
        raw = line.strip()
        # Remove leading ★ and digits
        raw = re.sub(r'^[\d★\s,]+', '', raw)
        # Extract address (before owner name)
        name_pos = raw.find(person_name)
        if name_pos < 0:
            continue
        addr_part = raw[:name_pos].strip()
        # Remove area numbers from end of address
        addr_part = re.sub(r'\s*[\d,\.]+\s*$', '', addr_part)
        addr_part = re.sub(r'\s+全部$', '', addr_part).strip()
        if not addr_part:
            continue
        entry['address'] = addr_part

        # --- Rights: find "全部" or "N分之N" in the anchor line ---
        rights = ''
        r_match = re.search(
            r'(全部|[\d,]+分\s*之\s*[\d,]+|\d+\s*分\s*之\s*\d+|[\d,]+\s*分之\s*[\d,]+)',
            raw
        )
        if r_match:
            rights = r_match.group(1).replace(' ', '')
        entry['rights'] = rights

        # --- Area: look in lines above the anchor ---
        area = None
        for j in range(i - 1, max(i - 12, 0), -1):
            prev = lines[j].strip()
            # Try to find a number in the area column (~char 27-42)
            # The area is typically a standalone number near the left side
            # Match: and loose strings
            nums = re.findall(r'(?<!\d)(\d{1,4}(?:[.,]\d{1,2})?)(?!\d)', prev)
            for n_str in nums:
                n = parse_num(n_str)
                if n is not None and 3 < n < 100000:
                    # Check it's not a rights denominator (too small)
                    # Check it's not "附屬建物總面積" description (text nearby)
                    if '積' in prev or '附屬' in prev or '總面':
                        # Could be area info
                        area = n
                        break
                    if n < 10:
                        continue  # too small for main area
                    # For numbers that don't appear to be rights
                    # Verify not a price
                    p_match = re.search(r'[\d,]+', prev)
                    if p_match and len(p_match.group().replace(',', '')) >= 6:
                        continue  # looks like a price
                    area = n
                    break
            if area is not None:
                break

        # If still no area, try broader search for standalone numbers
        if area is None:
            for j in range(i - 1, max(i - 15, 0), -1):
                prev = lines[j].strip()
                parts = prev.split()
                for p in parts:
                    n = parse_num(p)
                    if n and 10 < n < 50000:
                        # heuristically check if standalone
                        if re.match(r'^\s*[×\d,\s\.]+\s*$', prev):
                            area = n
                            break
                if area:
                    break

        entry['area'] = area

        # --- Price: scan above AND below for large numbers ---
        price = None
        # First scan above (price often appears as a right-aligned number before the address)
        for j in range(i, max(i - 20, 0), -1):
            prev = lines[j]
            # Look for standalone large number in the rightmost column
            right_part = prev[80:].strip() if len(prev) > 80 else prev.strip()
            n = parse_num(right_part.replace(' ', ''))
            if n is not None and n > 10000 and n < 1000000000:
                price = n
                break
            # Also check left/middle for standalone prices
            # Sometimes pdftotext splits the line with costs on the left
            stripped = prev.strip()
            # Check if the whole line is a number
            nn = parse_num(stripped.replace(')', '').replace('(', ''))
            if nn is not None and nn > 10000 and nn < 1000000000:
                # Verify it's not "(超過五年)" which is 0
                if not re.search(r'超過五年|監察院', stripped):
                    price = nn
                    break
    
        # If still no price, look below
        if price is None:
            for j in range(i + 1, min(i + 20, len(lines))):
                curr = lines[j]
                right_part = curr[80:].strip() if len(curr) > 80 else curr.strip()
                n = parse_num(right_part)
                if n is not None and n > 10000 and n < 1000000000:
                    price = n
                    break
                # Check full line
                stripped = curr.strip()
                nn = parse_num(stripped)
                if nn is not None and nn > 10000 and nn < 1000000000:
                    if not re.search(r'超過五年|監察院', stripped):
                        price = nn
                        break

        entry['price'] = price
        results.append(entry)

    return results


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
            print(f'  ✓ {len(result)} 人，{entry_count} 筆建物（{elapsed:.0f}s）')
        else:
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