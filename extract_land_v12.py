#!/usr/bin/env python3
"""
land_detail 萃取 v12 - 修正：column offset 错误（改用 regex 定位）

问题：v11 用固定 byte 位置萃取，但 pdftotext 对多字节字符使用 3-byte 编码，
  导致 line[N] 索引的是 byte 而非 character，位置全部错位。

解决：改用 regex 在整行文本中直接匹配各字段。
  pdftotext -layout 输出每列宽度固定（英文空格填充），
  所以各字段总是出现在特定的相对 offset 之后。
  
实证（第310期 PDF）：
  "地利段[27 spaces]279.89     5分之1  陳志成  拍賣  220,100"
  
  - area: 在 "段" 或 "路" 等地址关键词之后，取第一个数值（含小数）
  - rights: "分之N" 或 "全部"，紧跟 area 之后
  - owner: 紧跟 rights 之后的中文字符串（在日期之前）
  - price: 行末尾的数字（逗号千分位）
  - date: 在 follow 行的 byte 78-90（"111 年 10 月" 等）
    或通过 regex 直接在行中搜索 \d{2,3}年\d{1,2}月
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR = Path.home() / 'Downloads' / '廉政專刊'
OUT_FILE = Path(__file__).parent / 'data' / 'land_detail.json'
IN_BACKUP = Path(__file__).parent / 'data' / 'land_detail.json'
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
    for p in ['面積(', '權利範圍', '所有權', '取得價', '土地坐', '土地變動', '公尺)', '建物', '（二）', '（三）']:
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

def extract_date(line):
    """从一行中提取日期（regex-based）"""
    m = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', line)
    if m: return m.group(1) + '年' + m.group(2) + '月' + m.group(3) + '日'
    m2 = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月', line)
    if m2: return m2.group(1) + '年' + m2.group(2) + '月'
    return ''

def parse_land_section(section_text, person_name):
    """解析一个 land section（传入 section_chunk，不含 1.土地 标题）"""
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
        while j < len(data_lines) and j <= i + 4:
            nxt = data_lines[j]
            if is_addr_line(nxt) and j > i + 1:
                if nxt.lstrip()[:3] in ['段(', '路(', '市(', '區(']:
                    follow.append(nxt); j += 1; continue
                break
            follow.append(nxt); j += 1

        ln = len(line)
        loc = clean(line[:29])
        area = rights = price = acq = ''

        # === 用 regex 在整行中定位各字段 ===
        # 在地址关键词之后取 area（第一个数值，含小数）
        addr_pos = 0
        for kw in ['段','路','街','市','區','縣','鄉','鎮','町','丁目']:
            p = line.find(kw)
            if p >= 0 and (addr_pos == 0 or p < addr_pos):
                addr_pos = p
        
        if addr_pos > 0:
            search_from = addr_pos + 1
            # 找 area：地址关键词之后的第一个数字（含小数）
            area_m = re.search(r'([\d,]+(?:\.\d+)?)', line[search_from:])
            if area_m: area = area_m.group(1)
        
        # 找 rights：area 之后，到 owner 之前的 "分之N" 或 "全部"
        if area:
            area_end = search_from + area_m.start() + len(area_m.group(0)) if area_m else search_from + 20
        else:
            area_end = search_from + 20
        
        rights_section = line[area_end:area_end + 60]
        rights_match = re.search(r'(\d+)\s*分之\s*(\d+)', rights_section)
        if rights_match:
            rights = rights_match.group(1) + '分之' + rights_match.group(2)
        elif '全部' in rights_section:
            rights = '全部'
        else:
            # 从整行找（可能 rights 格式略有不同）
            full_rights = re.search(r'(\d+)\s*分之\s*(\d+)', line)
            if full_rights: rights = full_rights.group(1) + '分之' + full_rights.group(2)
            elif '全部' in line: rights = '全部'
        
        # 找 owner：rights 之后，日期/价格之前的连续中文字符串
        owner_end = ln
        # price 通常在行末（数字，逗号分隔）
        price_m = re.search(r'([\d,]+)\s*$', clean(line[-20:]))
        if price_m:
            pv = price_m.group(1).replace(',', '')
            if len(pv) >= 4 and pv not in ['0000', '1000', '1111']:
                price = price_m.group(1)
            owner_end = ln - (20 - price_m.start())
        
        # owner = rights 之后到 price/date 之前的中文名
        if rights:
            rights_end = area_end + len(rights_section)
            owner_search = line[rights_end:owner_end]
            owner_m = re.search(r'[\u4e00-\u9fff]{2,4}', owner_search)
            holder = owner_m.group(0) if owner_m else person_name
        else:
            # 无 rights 时，直接在行中搜索 owner
            owner_search = line[area_end:owner_end]
            owner_m = re.search(r'[\u4e00-\u9fff]{2,4}', owner_search)
            holder = owner_m.group(0) if owner_m else person_name
        
        if not holder: holder = person_name

        # Acquisition reason
        reason = ''
        for kw in ['買賣', '贈與', '繼承', '設定', '自拍', '建築', '交換', '補償']:
            if kw in line: reason = kw; break

        # Follow lines: date + additional rights
        if follow:
            fl = follow[0]
            fl_len = len(fl)

            # Date from follow line (regex-based)
            acq = extract_date(fl)
            if not acq and len(follow) > 1:
                acq = extract_date(follow[1])
            if not acq:
                acq = extract_date(line)

            # Rights from follow (if incomplete)
            if len(re.findall(r'\d', rights)) < 2:
                sm_f = re.search(r'(\d+)\s*分之?\s*(\d+)', fl)
                if sm_f:
                    rights = sm_f.group(1) + '分之' + sm_f.group(2)
                elif '全部' in fl:
                    rights = '全部'
                elif fl_len >= 42:
                    sm_f2 = re.search(r'(\d+)\s*分?\s*之', clean(fl[41:52]))
                    if sm_f2: rights = sm_f2.group(1) + '分之'

        # Rights from full entry (fallback)
        if not rights or len(re.findall(r'\d', rights)) < 2:
            sm3 = re.search(r'(\d+)\s*分之?\s*(\d+)', line)
            if sm3: rights = sm3.group(1) + '分之' + sm3.group(2)
            elif '全部' in line: rights = '全部'
            else:
                for fl in follow:
                    sm4 = re.search(r'(\d+)\s*分之?\s*(\d+)', fl)
                    if sm4: rights = sm4.group(1) + '分之' + sm4.group(2); break
                    if '全部' in fl: rights = '全部'; break

        if loc and len(loc) >= 4:
            results.append({
                'location': loc,
                'area': area,
                'rights': rights,
                'holder': holder,
                'acquisition_time': acq,
                'acquisition_reason': reason,
                'price': price,
                'type': '土地'
            })

        i = j

    return results


def extract_land_from_block(block_text, person_name):
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

    person_markers = []
    for m in re.finditer(r'申報人姓名\s+([^\n]+)', full_text):
        raw = m.group(1).strip()
        name = re.split(r'\s{2,}', raw)[0].strip()
        name = re.sub(r'[○●◎]', '', name).strip()
        if name and len(name) >= 2:
            person_markers.append((m.start(), name))
    person_markers.sort()

    results = {}
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
            print(f'第 {issue_num} 期：已有，跳过')
            continue
        pdf_path = find_pdf(issue_num)
        if not pdf_path:
            print(f'第 {issue_num} 期：PDF 不存在')
            continue
        t0 = time.time()
        print(f'处理第 {issue_num} 期...', flush=True)
        result = extract_from_pdf(pdf_path)
        elapsed = time.time() - t0
        if result:
            all_data[issue_key] = result
            total_land = sum(len(v.get('land', [])) for v in result.values())
            print(f'  ✓ {len(result)} 人，土地 {total_land} 笔（{elapsed:.1f}s）')
        else:
            print(f'  - 无（{elapsed:.1f}s）')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    total = sum(len(v.get('land', [])) for d in all_data.values() for v in d.values())
    print(f'\n完成：{len(all_data)} 期，土地 {total} 笔 → {OUT_FILE}')


if __name__ == '__main__':
    main()