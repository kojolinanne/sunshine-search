#!/usr/bin/env python3
"""
land_detail 萃取 v7 - 乾淨版

核心問題：PDF 行的兩種型態
  A) 主地址行：包含「段/路/街/市/區/縣/鄉/鎮/町/丁目」+ 通常有日期/價格（col 80+）
  B) 截斷續行：以「段(」、「路(」開頭 → 是前一個 entry 的續行，不是新 entry

v7 策略：
  1. 嚴格識別：行首 col 0-3 是「段(」、「路(」、「市(」、「區(」 → 截斷續行，跳過
  2. 正確 group：addr line + 其後的 1-2 行（不含截斷續行）= 1 筆記錄
  3. 面積：addr line col 60-75 可能是 area；但多數 area 在 follow line 行首
  4. 地址擷取：取 addr line 的 col 0-65
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

def is_continuation_line(line):
    """檢查是否為截斷續行（不是新 entry）"""
    lc = line.lstrip()[:4]
    return lc.startswith(('段(', '路(', '街(', '市(', '區(', '縣(', '鄉(', '鎮('))

def parse_date_robust(all_text):
    """從 all_text 找 YYYY年MM月 或 YYYY年MM月DD日"""
    # 先找「年」前面的數字
    m = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月', all_text)
    if m:
        ym = m.group(1) + '年' + m.group(2) + '月'
        md_m = re.search(r'月\s*(\d{1,2})\s*日', all_text)
        if md_m: return ym + ' ' + md_m.group(0).replace(' ', '')
        return ym
    return ''

def parse_land_entry(addr_line, follow_lines):
    """解析單一土地 entry"""
    loc = clean(addr_line[:65])
    all_text = loc + ' ' + ' '.join(follow_lines)

    # 取得日期
    acq = parse_date_robust(all_text)

    # 取得價額（找最大數值）
    price = ''
    for pm in reversed(re.findall(r'\b([0-9,]{5,})\b', all_text)):
        val = pm.replace(',', '')
        if len(val) >= 5 and val not in ['00000', '10000', '100000']:
            price = pm; break

    # 面積：找 follow line 行首的數值（這是主要方式）
    area = ''
    for fl in follow_lines:
        fl_c = clean(fl)
        m = re.match(r'^([\d,]+(?:\.\d+)?)\s', fl_c)
        if m:
            area = m.group(1); break

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
            line_c = clean(line)
            # 跳過截斷續行
            if is_continuation_line(line):
                i += 1; continue
            # 跳過不含地址關鍵字的行
            if not any(k in line[:65] for k in ['段','路','街','市','區','縣','鄉','鎮','町','丁目']):
                i += 1; continue

            # 收集 follow lines（遇到截斷續行就停，且最多取 2 行）
            follow = []
            j = i + 1
            while j < len(data_lines) and j <= i + 2:
                nxt = data_lines[j]
                if is_continuation_line(nxt): break
                nxt_c = clean(nxt)
                # 另一個新地址（非截斷）→ 停止
                if any(k in nxt[:65] for k in ['段','路','街','市','區','縣','鄉','鎮','町','丁目']) and j > i + 1:
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