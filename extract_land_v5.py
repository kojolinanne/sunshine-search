#!/usr/bin/env python3
"""
land_detail 萃取 v5 - 修正 person boundary 問題

每期 PDF 包含多位申報人的財產申報。
每人有多個不動產 section（跨頁），以「申報人姓名」為界。

v4 問題：找到第一個「1.土地」→ 遇到「（三）船舶」就停止，
        但「（三）船舶」涵蓋了多人的土地 sections，導致 197 筆（應為 ~45）。

v5 策略：
  1. 整個 PDF 文字串成一個長字串
  2. 用「申報人姓名」來切割每個區塊（person block）
  3. 對每個 person block，分別找其下的 1.土地 sections 並萃取
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
    """處理分行的日期"""
    year_matches = list(re.finditer(r'(\d{2,3}\s*年\s*\d{1,2})', all_text))
    md_matches = list(re.finditer(r'月\s*(\d{1,2})\s*日', all_text))
    if not year_matches: return ''
    ym = year_matches[0].group(0).replace(' ', '')
    if md_matches:
        md = md_matches[0].group(0).replace(' ', '')
        return ym + ' ' + md
    return ym

def parse_land_entry(addr_line, follow_lines):
    loc = clean(addr_line[:65])
    all_text = addr_line + ' ' + ' '.join(follow_lines)
    acq = parse_date_robust(all_text)
    price = ''
    for pm in reversed(re.findall(r'\b([0-9,]{5,})\b', all_text)):
        val = pm.replace(',', '')
        if len(val) >= 5 and val not in ['00000', '10000', '100000']:
            price = pm; break
    area = ''
    for fl in follow_lines:
        m = re.match(r'^([\d,]+(?:\.\d+)?)\s', clean(fl))
        if m: area = m.group(1); break
    rights = ''
    share_m = re.search(r'(\d+\s*分\s*之\s*\d+)', all_text)
    if share_m: rights = clean(share_m.group(1))
    elif '全部' in all_text: rights = '全部'
    reason = ''
    for kw in ['買賣', '贈與', '繼承', '設定', '自拍', '建築', '交換', '補償']:
        if kw in all_text: reason = kw; break
    return loc, area, rights, acq, price, reason

def parse_person_block(block_text, person_name):
    """
    解析單一 person block 的土地 sections。
    找出 block 內所有的 1.土地 sections。
    """
    results = []

    # 找 block 中所有的「1.土地」位置（每個不動產 section）
    land_starts = [m.start() for m in re.finditer(r'1\.土地', block_text)]
    if not land_starts:
        return results

    for li, land_start in enumerate(land_starts):
        # 找對應的 2.建物 位置（該 section 結束）
        section_chunk = block_text[land_start:]
        bldg_pos = section_chunk.find('2.建物')
        next_land_pos = section_chunk.find('1.土地', 20)  # 下一個 1.土地（在 20 字後）
        if bldg_pos == -1:
            # 沒有 2.建物就到 block 末尾或下一個 1.土地
            land_end = next_land_pos if next_land_pos != -1 else len(section_chunk)
        elif next_land_pos != -1 and next_land_pos < bldg_pos:
            land_end = next_land_pos
        else:
            land_end = bldg_pos

        land_section = section_chunk[land_start:land_end]

        # 去除「土地變動情形」區塊
        chg = land_section.rfind('土地變動情形')
        if chg != -1: land_section = land_section[:chg]

        # 去除 header 行（1.土地 標題行到「土地坐落」行）
        pos = land_section.find('土地坐落')
        if pos != -1:
            land_section = land_section[pos + 4:]

        # 跳過 header lines
        lines = land_section.split('\n')
        skip_patterns = ['面  積', '權利範圍', '所 有 權', '取 得 價', '土地坐',
                         '土地變動', '公   尺', '建物', '（二）', '（三）']
        data_lines = []
        for ln in lines:
            ln_c = clean(ln)
            if not ln_c: continue
            if any(p in ln_c[:8] for p in skip_patterns): continue
            if re.match(r'^[（（]', ln_c): continue
            if '本欄空白' in ln_c: break
            data_lines.append(ln)

        # 行分組
        i = 0
        while i < len(data_lines):
            if not has_addr_kw(data_lines[i]):
                i += 1; continue

            follow = []
            j = i + 1
            while j < len(data_lines) and j <= i + 2:
                nxt = data_lines[j]
                nxt_c = clean(nxt)
                if has_addr_kw(nxt) and j == i + 2: break
                follow.append(nxt); j += 1

            loc, area, rights, acq, price, reason = parse_land_entry(data_lines[i], follow)
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
    """萃取整個 PDF，按 person blocks 分別解析"""
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                      capture_output=True, text=True, timeout=300)
    if r.returncode != 0: return []
    full_text = r.stdout

    results_by_person = {}

    # 用「申報人姓名」切割為 person blocks
    person_blocks = []
    for m in re.finditer(r'申報人姓名\s+([^\n]+)', full_text):
        raw = m.group(1).strip()
        name = re.split(r'\s{2,}', raw)[0].strip()
        name = re.sub(r'[○●◎]', '', name).strip()
        if name and len(name) >= 2:
            person_blocks.append((m.start(), name))
    person_blocks.sort()

    # 對每個 person block，取其文字區間
    for pi, (person_start, person_name) in enumerate(person_blocks):
        if pi + 1 < len(person_blocks):
            block_end = person_blocks[pi + 1][0]
        else:
            block_end = len(full_text)
        block_text = full_text[person_start:block_end]

        # 解析該 person 的土地
        land_items = parse_person_block(block_text, person_name)
        if land_items:
            results_by_person[person_name] = {'land': land_items}

    return results_by_person

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