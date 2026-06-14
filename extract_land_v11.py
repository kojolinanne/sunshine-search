#!/usr/bin/env python3
"""
land_detail 萃取 v11 - 修正：同一人多區塊（merge by name）

問題：同一個人的申報可能橫跨多個不連續文字區塊
  （PDF 分頁導致同一人出現兩次 `申報人姓名`）

v11：
  1. 收集所有 person markers（不 deduplicate）
  2. 每個 marker_start → next_marker_start = 一個 block
  3. 合併同名人（用 name 作為 key，append land sections）
  4. 每個 block 的 land section 用獨立的 parse_person_block call
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
    raw = line.replace(' ', '').replace('\u3000', '')
    patterns = ['面積(', '權利範圍', '所有權', '取得價', '土地坐', '土地變動', '公尺)', '建物', '（二）', '（三）']
    for p in patterns:
        if p in raw[:12]: return True
    return False

def is_data_line(line):
    if not line.strip(): return False
    if is_header_line(line): return False
    lc = clean(line)
    if re.match(r'^[（（]', lc): return False
    if '本欄空白' in lc: return False
    return True

def is_addr_line(line):
    return any(k in line[:65] for k in ['段','路','街','市','區','縣','鄉','鎮','町','丁目'])

def parse_date_from_text(text):
    dm = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月', text)
    if not dm: return ''
    acq = dm.group(1) + '年' + dm.group(2) + '月'
    day_m = re.search(r'月\s*(\d{1,2})\s*日', text)
    if day_m: acq += '月' + day_m.group(1) + '日'
    return acq

def parse_land_section(section_text, person_name):
    """解析一個 land section（傳入 section_chunk，不含 1.土地 標題）"""
    results = []
    chg = section_text.rfind('土地變動情形')
    if chg != -1: section_text = section_text[:chg]

    lines = section_text.split('\n')
    data_lines = [ln for ln in lines if is_data_line(ln)]

    i = 0
    while i < len(data_lines):
        line = data_lines[i]
        if not is_addr_line(line):
            i += 1; continue

        follow = []
        j = i + 1
        while j < len(data_lines) and j <= i + 2:
            nxt = data_lines[j]
            if is_addr_line(nxt) and j > i + 1:
                # Check if it's a continuation (starts with段( etc.)
                if nxt.lstrip()[:3] in ['段(', '路(', '市(', '區(']:
                    follow.append(nxt); j += 1; continue
                break
            follow.append(nxt); j += 1

        ln = len(line)
        loc = clean(line[:43])
        area = ''; rights = ''; price = ''; acq = ''

        if ln >= 100:
            # === 舊格式（全在同一行）===
            am = re.match(r'^([\d,]+(?:\.\d+)?)', clean(line[60:76]))
            if am: area = am.group(1)
            acq = parse_date_from_text(line[78:100])
            for pm in reversed(re.findall(r'\b([0-9,]{5,})\b', line[95:])):
                pv = pm.replace(',', '')
                if len(pv) >= 5 and pv not in ['00000', '10000', '100000']:
                    price = pm; break
        else:
            # === 新格式（main + follow pair）===
            am = re.match(r'^([\d,]+(?:\.\d+)?)', clean(line[43:49]))
            if am: area = am.group(1)
            # Rights: col 55-61
            rights_raw = clean(line[55:62])
            if rights_raw in ['全部']: rights = rights_raw
            else:
                sm = re.search(r'(\d+)\s*分\s*之\s*(\d+)', rights_raw)
                if sm: rights = rights_raw
                else:
                    more = clean(line[61:67])
                    sm2 = re.match(r'^(\d+)', more)
                    if sm2: rights = rights_raw + more
                    else: rights = rights_raw

        if follow:
            fl = follow[0]
            fl_len = len(fl)
            if ln < 100:
                # Price: col 55-62
                if fl_len >= 62:
                    pm2 = re.match(r'^([\d,]+)', clean(fl[55:63]))
                    if pm2:
                        pv2 = pm2.group(1).replace(',', '')
                        if len(pv2) >= 4 and pv2 not in ['0000', '1000']:
                            price = pm2.group(1)
                # Date: col 80-124
                if fl_len >= 124: acq = parse_date_from_text(fl[80:124])
                elif fl_len >= 80: acq = parse_date_from_text(fl[80:fl_len])
                # Rights from follow (if incomplete)
                if len(re.findall(r'\d', rights)) < 2:
                    sm_f = re.search(r'(\d+)\s*分\s*之\s*(\d+)', fl)
                    if sm_f: rights = sm_f.group(1) + '分之' + sm_f.group(2)
                    elif '全部' in fl: rights = '全部'

        # Rights from full entry
        full_text = line + (' ' + ' '.join(follow) if follow else '')
        if not rights:
            sm3 = re.search(r'(\d+)\s*分\s*之\s*(\d+)', full_text)
            if sm3: rights = sm3.group(1) + '分之' + sm3.group(2)
            elif '全部' in full_text: rights = '全部'

        # Reason
        reason = ''
        for kw in ['買賣', '贈與', '繼承', '設定', '自拍', '建築', '交換', '補償']:
            if kw in full_text: reason = kw; break

        holder = clean(line[76:]) if len(line) >= 76 else person_name

        if loc and len(loc) >= 4:
            results.append({
                'location': loc, 'area': area, 'rights': rights,
                'holder': holder or person_name,
                'acquisition_time': acq, 'acquisition_reason': reason,
                'price': price, 'type': '土地'
            })

        i = j

    return results

def extract_land_from_block(block_text, person_name):
    """從一個 block 文字區間萃取土地資料（可能有多個 1.土地 sections）"""
    results = []
    land_starts = [m.start() for m in re.finditer(r'1\.土地', block_text)]
    for ls in land_starts:
        section_chunk = block_text[ls:]
        bldg_pos = section_chunk.find('2.建物')
        nl_pos = section_chunk.find('1.土地', 20)
        if bldg_pos == -1: land_end = nl_pos if nl_pos != -1 else len(section_chunk)
        elif nl_pos != -1 and nl_pos < bldg_pos: land_end = nl_pos
        else: land_end = bldg_pos
        section_text = section_chunk[:land_end]
        section_text = section_text[section_text.find('土地坐落')+4:] if '土地坐落' in section_text else section_text[len('1.土地'):]
        entries = parse_land_section(section_text, person_name)
        results.extend(entries)
    return results

def extract_from_pdf(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                      capture_output=True, text=True, timeout=300)
    if r.returncode != 0: return {}
    full_text = r.stdout

    # 收集所有 person markers（不 deduplicate）
    person_markers = []
    for m in re.finditer(r'申報人姓名\s+([^\n]+)', full_text):
        raw = m.group(1).strip()
        name = re.split(r'\s{2,}', raw)[0].strip()
        name = re.sub(r'[○●◎]', '', name).strip()
        if name and len(name) >= 2:
            person_markers.append((m.start(), name))
    person_markers.sort()

    results = {}  # name -> list of land entries
    for idx, (p_start, p_name) in enumerate(person_markers):
        p_end = person_markers[idx + 1][0] if idx + 1 < len(person_markers) else len(full_text)
        block_text = full_text[p_start:p_end]
        entries = extract_land_from_block(block_text, p_name)
        if entries:
            if p_name not in results:
                results[p_name] = []
            results[p_name].extend(entries)

    return {name: {'land': entries} for name, entries in results.items()}

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
            print(f'第 {issue_num} 期：已有，跳過')
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