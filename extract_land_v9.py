#!/usr/bin/env python3
"""
land_detail 萃取 v9 - 精確 column mapping 版

PDF 兩欄佈局（pdftotext -layout 合併成一行）：
  Main line (len~79):  col  0-42 = location
                       col 43-47 = area
                       col 55-60 = rights ("X分之Y" 或 "全部")
                       col 76-79 = holder (姓名)
  Follow line (len~111): col 55-60 = price
                         col 110-123 = date

策略：
  1. 主行：取 col 0-42(location), 43-47(area), 55-60(rights)
  2. 附行：取 col 55-60(price), col 110-123(date)
  3. 每個 entry = main line + 1 follow line（固定 2 行）
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR = Path.home() / 'Downloads' / '廉政專刊'
OUT_FILE = Path(__file__).parent / 'data' / 'land_detail.json'
IN_BACKUP = Path(__file__).parent / 'data' / 'land_detail.json.bak'
ISSUES = list(range(292, 320))

def find_pdf(n):
    p = PDF_DIR / f'廉政專刊第{n}期.pdf'
    if p.exists(): return p
    alt = Path(__file__).parent / 'data' / f'issue_{n}.pdf'
    if alt.exists(): return alt
    return None

def clean(s):
    if not s: return ''
    return re.sub(r'\s+', ' ', s).strip()

def has_addr_kw(s):
    return any(k in s[:42] for k in ['段','路','街','市','區','縣','鄉','鎮','町','丁目'])

def parse_date_from_text(text, start=0, end=50):
    chunk = clean(text[start:start+end])
    dm = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月', chunk)
    if not dm: return ''
    acq = dm.group(1) + '年' + dm.group(2) + '月'
    day_m = re.search(r'月\s*(\d{1,2})\s*日', chunk)
    if day_m: acq += '月' + day_m.group(1) + '日'
    return acq

def parse_person_block(block_text, person_name):
    results = []

    land_starts = [m.start() for m in re.finditer(r'1\.土地', block_text)]
    if not land_starts: return results

    for li, land_start in enumerate(land_starts):
        section_chunk = block_text[land_start:]
        bldg_pos = section_chunk.find('2.建物')
        next_land_pos = section_chunk.find('1.土地', 20)
        if bldg_pos == -1:
            land_end = next_land_pos if next_land_pos != -1 else len(section_chunk)
        elif next_land_pos != -1 and next_land_pos < bldg_pos:
            land_end = next_land_pos
        else:
            land_end = bldg_pos

        land_section = section_chunk[:land_end]
        chg = land_section.rfind('土地變動情形')
        if chg != -1: land_section = land_section[:chg]

        pos = land_section.find('土地坐落')
        if pos != -1: land_section = land_section[pos + 4:]

        lines = land_section.split('\n')
        skip = ['面  積', '權利範圍', '所 有 權', '取 得 價', '土地坐',
                '土地變動', '公   尺', '建物', '（二）', '（三）']
        data_lines = []
        for ln in lines:
            lc = clean(ln)
            if not lc: continue
            if any(p in lc[:8] for p in skip): continue
            if re.match(r'^[（（]', lc): continue
            if '本欄空白' in lc: break
            data_lines.append(ln)

        # Process entries in PAIRS: main_line + follow_line
        i = 0
        while i < len(data_lines):
            main_line = data_lines[i]
            # Main line must have address keyword in col 0-42
            if not has_addr_kw(main_line):
                i += 1; continue

            loc = clean(main_line[:43])
            area_raw = clean(main_line[43:48])
            area = ''
            am = re.match(r'^([\d,]+(?:\.\d+)?)', area_raw)
            if am: area = am.group(1)

            # Rights: col 55-60
            rights_raw = clean(main_line[55:61])
            if not rights_raw:
                rights = ''
            elif rights_raw in ['全部']:
                rights = '全部'
            else:
                # Try to find X分之Y pattern in the raw string
                share_m = re.search(r'(\d+)\s*分\s*之\s*(\d+)', rights_raw)
                if share_m:
                    rights = rights_raw  # already has the full pattern
                else:
                    # Partial: might be "X分之" (needs "Y" from nearby context)
                    # Check if there's a digit right after the rights_raw zone
                    more = clean(main_line[60:65])
                    if more and re.match(r'^\d+$', more):
                        rights = rights_raw + more
                    else:
                        rights = rights_raw

            holder = clean(main_line[76:]) if len(main_line) >= 76 else ''

            # Default values
            price = ''
            acq = ''
            reason = ''

            # Follow line processing
            if i + 1 < len(data_lines):
                follow_line = data_lines[i + 1]
                fl_c = clean(follow_line)
                fl_len = len(follow_line)

                # Price: col 55-61 in follow line
                if fl_len >= 61:
                    price_raw = clean(follow_line[55:62])
                    pm = re.match(r'^([\d,]+)', price_raw)
                    if pm:
                        pv = pm.group(1).replace(',', '')
                        if len(pv) >= 4 and pv not in ['0000', '1000']:
                            price = pm.group(1)

                # Acq date: col 110-124
                if fl_len >= 124:
                    acq = parse_date_from_text(follow_line, 108, 18)
                elif fl_len >= 90:
                    # Try to find date elsewhere
                    acq = parse_date_from_text(follow_line, 80, 30)

                # Rights from follow line (if main line had "分之" without Y)
                if not rights or rights == '分之' or '分之' in rights and len(re.findall(r'\d+', rights)) < 2:
                    # Look for share pattern in follow line
                    share_m2 = re.search(r'(\d+)\s*分\s*之\s*(\d+)', fl_c)
                    if share_m2:
                        rights = share_m2.group(1) + '分之' + share_m2.group(2)
                    elif '全部' in fl_c:
                        rights = '全部'

                # Reason
                for kw in ['買賣', '贈與', '繼承', '設定', '自拍', '建築', '交換', '補償']:
                    if kw in fl_c: reason = kw; break

            # Reason from main line too
            if not reason:
                for kw in ['買賣', '贈與', '繼承', '設定', '自拍', '建築', '交換', '補償']:
                    if kw in main_line: reason = kw; break

            if loc and len(loc) >= 4:
                results.append({
                    'location': loc,
                    'area': area,
                    'rights': rights,
                    'holder': holder or person_name,
                    'acquisition_time': acq,
                    'acquisition_reason': reason,
                    'price': price,
                    'type': '土地'
                })

            i += 2  # Move by 2 (pair)

    return results

def extract_from_pdf(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                      capture_output=True, text=True, timeout=300)
    if r.returncode != 0: return {}
    full_text = r.stdout

    person_blocks = []
    for m in re.finditer(r'申報人姓名\s+([^\n]+)', full_text):
        raw = m.group(1).strip()
        name = re.split(r'\s{2,}', raw)[0].strip()
        name = re.sub(r'[○●◎]', '', name).strip()
        if name and len(name) >= 2:
            person_blocks.append((m.start(), name))
    person_blocks.sort()

    results = {}
    for pi, (p_start, p_name) in enumerate(person_blocks):
        block_end = person_blocks[pi + 1][0] if pi + 1 < len(person_blocks) else len(full_text)
        items = parse_person_block(full_text[p_start:block_end], p_name)
        if items:
            results[p_name] = {'land': items}

    return results

def main():
    if IN_BACKUP.exists():
        with open(IN_BACKUP, encoding='utf-8') as f:
            orig = json.load(f)
    else:
        orig = {}

    all_data = {str(n): {} for n in ISSUES}
    for k, v in orig.items():
        if k in all_data: all_data[k] = v

    for issue_num in ISSUES:
        issue_key = str(issue_num)
        if all_data[issue_key]:
            print(f'第 {issue_num} 期：已有 {len(all_data[issue_key])} 人，跳過')
            continue
        pdf_path = find_pdf(issue_num)
        if not pdf_path:
            print(f'第 {issue_num} 期：PDF 不存在')
            continue
        t0 = time.time()
        print(f'處理第 {issue_num} 期...', flush=True)
        result = extract_from_pdf(pdf_path)
        elapsed = time.time() - t0
        if result:
            all_data[issue_key] = result
            total_land = sum(len(v.get('land', [])) for v in result.values())
            print(f'  ✓ {len(result)} 人，土地 {total_land} 筆（{elapsed:.1f}s）')
        else:
            print(f'  - 無（{elapsed:.1f}s）')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    total = sum(len(v.get('land', [])) for d in all_data.values() for v in d.values())
    print(f'\n完成：{len(all_data)} 期，土地 {total} 筆 → {OUT_FILE}')

if __name__ == '__main__':
    main()