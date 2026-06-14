#!/usr/bin/env python3
"""
land_detail 萃取 v8 - 正確版

核心發現：
  PDF 是兩欄佈局：左欄=地址+面積+持分，右欄=取得時間+價額
  pdftotext -layout 把兩欄合成一行，但每個 entry 的地址和數值都在同一行！
  之前只取 col 0-65（截斷了一半數據）+ col 75+ 的數值被錯誤放到 follow lines

v8 策略：
  1. 主行=col 0-110 的完整行（包含地址+日期+價格都在同一行）
  2. 主行的 col 0-55 = location, col 60-75 = area, col 80-95 = date, col 95+ = price
  3. follow lines 補充持分（share/持分有時會溢出到 follow line）
  4. 識別截斷續行：以「段(或 路(or ...」開頭的行是前一筆記錄的延續
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

def is_continuation(line):
    """檢查是否為截斷續行（段(, 路(, 市(, etc.）"""
    lc = line.lstrip()[:4]
    return lc.startswith(('段(', '路(', '街(', '市(', '區(', '縣(', '鄉(', '鎮('))

def has_addr_kw(s):
    return any(k in s[:65] for k in ['段','路','街','市','區','縣','鄉','鎮','町','丁目'])

def parse_entry_from_line(full_line):
    """
    從完整的一行萃取土地 entry。
    兩欄佈局：
      col  0-55: location
      col 60-75: area（面積）
      col 80-95: acquisition date（取得時間）
      col 95+ :  price（取得價額）
    """
    line = full_line
    if len(line) < 10: return None

    # location: col 0-55（但要去除尾部空白）
    loc = clean(line[:56])

    # 驗證：location 必須包含地址關鍵字
    if not any(k in loc for k in ['段','路','街','市','區','縣','鄉','鎮','町','丁目']):
        return None

    # area: col 60-75 的數值
    area = ''
    area_candidate = clean(line[60:76])
    am = re.match(r'^([\d,]+(?:\.\d+)?)', area_candidate)
    if am: area = am.group(1)

    # date: col 80-95
    date_str = clean(line[80:96])
    acq = ''
    dm = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月', date_str)
    if dm:
        acq = dm.group(1) + '年' + dm.group(2) + '月'
        # 找 日
        day_m = re.search(r'月\s*(\d{1,2})\s*日', line[80:])
        if day_m: acq += '月' + day_m.group(1) + '日'
    elif re.search(r'\d{1,2}\s*日', line[60:100]):
        # fallback: 在 col 60-100 範圍內找日期
        dm2 = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月', line[60:100])
        if dm2:
            acq = dm2.group(1) + '年' + dm2.group(2) + '月'
            day2 = re.search(r'月\s*(\d{1,2})\s*日', line[60:100])
            if day2: acq += '月' + day2.group(1) + '日'

    # price: col 95+ 的數值（取倒數第一個大數值）
    price = ''
    price_candidates = re.findall(r'\b([0-9,]{5,})\b', line[95:])
    for pc in reversed(price_candidates):
        val = pc.replace(',', '')
        if len(val) >= 5 and val not in ['00000', '10000', '100000']:
            price = pc; break

    # 從整行（含 follow lines）找持分
    full_text = line  # 稍後用 follow lines 擴展

    return {'loc': loc, 'area': area, 'acq': acq, 'price': price, 'raw': line}

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

        # 跳過 header
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

        i = 0
        while i < len(data_lines):
            line = data_lines[i]
            # 跳過截斷續行
            if is_continuation(line):
                i += 1; continue
            # 主 entry 行必須有地址關鍵字
            if not has_addr_kw(line):
                i += 1; continue

            # 收集 follow lines（最多 2 行）
            follow = []
            j = i + 1
            while j < len(data_lines) and j <= i + 2:
                nxt = data_lines[j]
                if is_continuation(nxt): break
                nxt_c = clean(nxt)
                # 另一個新地址（非截斷）→ 停止
                if any(k in nxt[:65] for k in ['段','路','街','市','區','縣','鄉','鎮','町','丁目']) and j > i + 1:
                    break
                follow.append(nxt); j += 1

            # 用 parse_entry_from_line 處理主行
            entry_data = parse_entry_from_line(line)
            if not entry_data:
                i += 1; continue

            full_text = entry_data['raw'] + ' ' + ' '.join(follow)

            # 持分（從 full_text）
            rights = ''
            share_m = re.search(r'(\d+\s*分\s*之\s*\d+)', full_text)
            if share_m: rights = clean(share_m.group(1))
            elif '全部' in full_text: rights = '全部'

            # 取得原因
            reason = ''
            for kw in ['買賣', '贈與', '繼承', '設定', '自拍', '建築', '交換', '補償']:
                if kw in full_text: reason = kw; break

            # 如果 area 為空，試著從 follow[0] 找（行首數值）
            area = entry_data['area']
            if not area:
                for fl in follow:
                    fl_c = clean(fl)
                    am = re.match(r'^([\d,]+(?:\.\d+)?)\s', fl_c)
                    if am:
                        area = am.group(1); break

            # 如果 acq date 為空，從 full_text 找
            acq = entry_data['acq']
            if not acq:
                dm = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月', full_text)
                if dm:
                    acq = dm.group(1) + '年' + dm.group(2) + '月'
                    day_m = re.search(r'月\s*(\d{1,2})\s*日', full_text)
                    if day_m: acq += '月' + day_m.group(1) + '日'

            # 如果 price 為空，從 full_text 找
            price = entry_data['price']
            if not price:
                for pm in reversed(re.findall(r'\b([0-9,]{5,})\b', full_text)):
                    val = pm.replace(',', '')
                    if len(val) >= 5 and val not in ['00000', '10000', '100000']:
                        price = pm; break

            loc = entry_data['loc']
            if loc and len(loc) >= 4:
                results.append({
                    'location': loc,
                    'area': area,
                    'rights': rights,
                    'holder': person_name,
                    'acquisition_time': acq,
                    'acquisition_reason': reason,
                    'price': price,
                    'type': '土地'
                })
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