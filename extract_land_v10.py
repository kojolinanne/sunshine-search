#!/usr/bin/env python3
"""
land_detail 萃取 v10 - 修正 skip + 雙格式支援

問題：
1. clean() 會在中文之間加空格，導致 skip 檢查失效（"土地坐" 比對不到"土 地 坐 落"）
2. 兩種 entry 格式：
   A) 舊格式（len~120）：地址+面積+持分+時間+價格全在同一主行
   B) 新格式（len~79/111）：主行(地址+面積+持分)，附行(價格+日期)，各自剛好 79/111 chars

v10:
  1. 用 is_header_line(raw_line) 做 skip 檢查（移除空格再比對）
  2. 動態識別格式：根據 main_line 長度判斷格式
     - len ≥ 100：舊格式（用 col 80+ 找日期/價格）
     - len ≤ 90：新格式（main+follow pair，col mapping 同 v9）
  3. follow line 動態解析：price 在 col 55-65，date 在 col 80-124
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

def is_header_line(line):
    """檢查是否為 header/separator 行（不計入數據）"""
    raw = line.replace(' ', '').replace('\u3000', '')
    patterns = ['面積(', '權利範圍', '所有權', '取得價', '土地坐', '土地變動', '公尺)', '建物', '（二）', '（三）']
    for p in patterns:
        if p in raw[:12]: return True
    return False

def is_data_line(line):
    """檢查是否為有效數據行（非 header、非空白、非括號開頭）"""
    if not line.strip(): return False
    if is_header_line(line): return False
    lc = clean(line)
    if re.match(r'^[（（]', lc): return False
    if '本欄空白' in lc: return False
    return True

def is_addr_line(line):
    """檢查是否為地址行"""
    return any(k in line[:65] for k in ['段','路','街','市','區','縣','鄉','鎮','町','丁目'])

def parse_date_from_text(text):
    dm = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月', text)
    if not dm: return ''
    acq = dm.group(1) + '年' + dm.group(2) + '月'
    day_m = re.search(r'月\s*(\d{1,2})\s*日', text)
    if day_m: acq += '月' + day_m.group(1) + '日'
    return acq

def parse_entry_pair(main_line, follow_line, person_name):
    """解析一個 entry（main_line + follow_line）"""
    ln = len(main_line)
    loc = clean(main_line[:43])
    area = ''
    rights = ''

    if ln >= 100:
        # === 舊格式：全在同一行 ===
        # Area: col 60-75
        am = re.match(r'^([\d,]+(?:\.\d+)?)', clean(main_line[60:76]))
        if am: area = am.group(1)
        # Date: col 80-95
        acq = parse_date_from_text(main_line[78:100])
        # Price: col 95+
        price = ''
        for pm in reversed(re.findall(r'\b([0-9,]{5,})\b', main_line[95:])):
            pv = pm.replace(',', '')
            if len(pv) >= 5 and pv not in ['00000', '10000', '100000']:
                price = pm; break
        # Rights from follow_line
        if follow_line:
            full = main_line + ' ' + follow_line
        else:
            full = main_line
    else:
        # === 新格式：main + follow pair ===
        # Area: col 43-48
        am = re.match(r'^([\d,]+(?:\.\d+)?)', clean(main_line[43:49]))
        if am: area = am.group(1)
        # Rights: col 55-61
        rights_raw = clean(main_line[55:62])
        if rights_raw in ['全部', '本欄']:
            rights = rights_raw
        elif '分之' in rights_raw:
            # Full share pattern
            sm = re.search(r'(\d+)\s*分\s*之\s*(\d+)', rights_raw)
            if sm: rights = rights_raw
            else:
                more = clean(main_line[61:66])
                sm2 = re.match(r'^(\d+)', more)
                if sm2: rights = rights_raw + more
                else: rights = rights_raw
        acq = ''
        price = ''
        if follow_line:
            fl = follow_line
            fl_len = len(fl)
            # Price: col 55-62
            if fl_len >= 62:
                pm = re.match(r'^([\d,]+)', clean(fl[55:63]))
                if pm:
                    pv = pm.group(1).replace(',', '')
                    if len(pv) >= 4 and pv not in ['0000', '1000']:
                        price = pm.group(1)
            # Date: col 80-124
            if fl_len >= 124:
                acq = parse_date_from_text(fl[80:124])
            elif fl_len >= 80:
                acq = parse_date_from_text(fl[80:fl_len])
            # Rights from follow
            if not rights or len(re.findall(r'\d', rights)) < 2:
                sm_f = re.search(r'(\d+)\s*分\s*之\s*(\d+)', fl)
                if sm_f: rights = sm_f.group(1) + '分之' + sm_f.group(2)
                elif '全部' in fl: rights = '全部'
            # Reason from follow
            reason = ''
            for kw in ['買賣', '贈與', '繼承', '設定', '自拍', '建築', '交換', '補償']:
                if kw in fl: reason = kw; break
        else:
            reason = ''
    # Rights from full text (fallback)
    if follow_line:
        full_text = main_line + ' ' + follow_line
    else:
        full_text = main_line
    if not rights:
        sm = re.search(r'(\d+)\s*分\s*之\s*(\d+)', full_text)
        if sm: rights = sm.group(1) + '分之' + sm.group(2)
        elif '全部' in full_text: rights = '全部'

    # Reason
    reason = ''
    for kw in ['買賣', '贈與', '繼承', '設定', '自拍', '建築', '交換', '補償']:
        if kw in full_text: reason = kw; break

    holder = clean(main_line[76:]) if len(main_line) >= 76 else person_name

    return {
        'location': loc,
        'area': area,
        'rights': rights,
        'holder': holder or person_name,
        'acquisition_time': acq if 'acq' in dir() else '',
        'acquisition_reason': reason,
        'price': price if 'price' in dir() else '',
        'type': '土地'
    }

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

        lines = land_section.split('\n')
        data_lines = [ln for ln in lines if is_data_line(ln)]

        i = 0
        while i < len(data_lines):
            line = data_lines[i]

            if not is_addr_line(line):
                i += 1; continue

            # 收集 follow lines
            follow = []
            j = i + 1
            while j < len(data_lines) and j <= i + 2:
                nxt = data_lines[j]
                nxt_c = clean(nxt)
                # 另一個新地址（非截斷）→ 停止
                if is_addr_line(nxt) and j > i + 1:
                    break
                follow.append(nxt); j += 1

            follow_line = follow[0] if follow else None
            entry = parse_entry_pair(line, follow_line, person_name)

            if entry['location'] and len(entry['location']) >= 4:
                results.append(entry)

            i = j

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