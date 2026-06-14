#!/usr/bin/env python3
"""
land_detail 萃取 v6 - 修正版

問題：PDF 行末截斷導致長地址被切成多行：
  新北市金山區頂角段半嶺子小          ← 主地址行
  段(山坡地保育區，含農牧、交           ← 截斷續行

問題：相同地址重複出現（江雅綺有 2 筆土地位置相同但面積/持分不同）
問題：area 與地址行相鄰時被視為 follow 行

v6 修正：
  1. 如果 follow 行以數字開頭（area），將其視為當前 entry 的 area
  2. 跳過重複的 address line（連續兩行 address 相同時，取第一行）
  3. 拼接截斷的地址續行（行首含地址關鍵字但很短時，附加下一行）
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
    return any(k in s[:65] for k in ['段','路','街','市','區','縣','鄉','鎮','町','丁目'])

def parse_date_robust(all_text):
    year_matches = list(re.finditer(r'(\d{2,3}\s*年\s*\d{1,2})', all_text))
    md_matches = list(re.finditer(r'月\s*(\d{1,2})\s*日', all_text))
    if not year_matches: return ''
    ym = year_matches[0].group(0).replace(' ', '')
    if md_matches:
        md = md_matches[0].group(0).replace(' ', '')
        return ym + ' ' + md
    return ym

def parse_land_entry(addr_line, follow_lines):
    # 嘗試拼接截斷的地址續行
    full_addr = addr_line[:65]
    for fl in follow_lines:
        fl_c = clean(fl)
        # 如果 fl 沒有數值（是地址的一部分）
        if fl_c and not re.match(r'^[\d,]+', fl_c) and len(fl_c) < 40:
            # 是截斷續行
            full_addr = full_addr + clean(fl[:50])

    loc = clean(full_addr[:65])
    all_text = full_addr + ' ' + ' '.join(follow_lines)
    acq = parse_date_robust(all_text)

    # 價額
    price = ''
    for pm in reversed(re.findall(r'\b([0-9,]{5,})\b', all_text)):
        val = pm.replace(',', '')
        if len(val) >= 5 and val not in ['00000', '10000', '100000']:
            price = pm; break

    # 面積（優先取 follow lines 中行首的數值，其次取行末）
    area = ''
    for fl in follow_lines:
        fl_c = clean(fl)
        # 行首數值（直接的面積）
        m = re.match(r'^([\d,]+(?:\.\d+)?)\s', fl_c)
        if m: area = m.group(1); break
    # 備用：找 follow lines 中的最大數值（非日期格式的）
    if not area:
        for fl in follow_lines:
            nums = re.findall(r'\b([0-9,]{3,})\b', fl)
            for n in nums:
                val = n.replace(',', '')
                if len(val) >= 3 and val not in ['000', '100', '1000']:
                    if area == '' or (len(val) > len(area.replace(',', '')) and re.match(r'^\d+$', val)):
                        area = n

    # 持分
    rights = ''
    share_m = re.search(r'(\d+\s*分\s*之\s*\d+)', all_text)
    if share_m: rights = clean(share_m.group(1))
    elif '全部' in all_text: rights = '全部'

    # 取得原因
    reason = ''
    for kw in ['買賣', '贈與', '繼承', '設定', '自拍', '建築', '交換', '補償']:
        if kw in all_text: reason = kw; break

    return loc, area, rights, acq, price, reason

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
        data_lines = [ln for ln in lines
                      if clean(ln) and not any(p in clean(ln)[:8] for p in skip)
                      and not re.match(r'^[（（]', clean(ln))
                      and '本欄空白' not in clean(ln)]

        i = 0
        prev_addr = ''
        while i < len(data_lines):
            line = data_lines[i]
            line_c = clean(line)
            if not has_addr_kw(line): i += 1; continue

            # 跳過連續重複的 address line
            addr_only = clean(line[:65])
            if addr_only == prev_addr:
                i += 1; continue
            prev_addr = addr_only

            # 收集 follow lines（最多 3 行，彈性收集）
            follow = []
            j = i + 1
            while j < len(data_lines) and j <= i + 3:
                nxt = data_lines[j]
                nxt_c = clean(nxt)
                # 遇到 header 或新 address line（且非截斷續行）則停止
                if any(p in nxt_c[:8] for p in skip): break
                if re.match(r'^[（（]', nxt_c): break
                # 如果是另一個新地址行（行首含地址且與目前地址不同）→ 停止
                if has_addr_kw(nxt) and j > i + 1:
                    # 但先檢查是否是截斷續行（很短）
                    if len(clean(nxt[:65])) >= 10:
                        break
                follow.append(nxt); j += 1

            loc, area, rights, acq, price, reason = parse_land_entry(line, follow)
            if loc and len(loc) >= 4:
                results.append({
                    'location': loc, 'area': area, 'rights': rights,
                    'holder': person_name,
                    'acquisition_time': acq, 'acquisition_reason': reason,
                    'price': price, 'type': '土地'
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