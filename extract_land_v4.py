#!/usr/bin/env python3
"""
land_detail 萃取 v4 - 固定欄位切片 + 行分組

PDF 版面觀察（pdftotext -layout）：
  新竹縣芎林鄉上德段 0200 小段     110 年 05            17,000,000    ← 行1：位置+日期+價額
                                84.17     全部            程瑞芳         買賣    ← 行2：面積+持分+所有人+原因
  (自用房屋之坐落基地)            月 01 日              (房地總價額)   ← 行3：補充日期

問題：坐落+日期在同一行，面積/持分在次行，日期的「月X日」部分在第三行。
策略：行分組 → 合併所有行 → 統一萃取
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
    """處理分行的日期：110 年 05 (地址行) + 月 01 日 (次行) → 110年05 月01日"""
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

    # 日期（分行）
    acq = parse_date_robust(all_text)

    # 價額
    price = ''
    price_matches = re.findall(r'\b([0-9,]{5,})\b', all_text)
    for pm in reversed(price_matches):
        val = pm.replace(',', '')
        if len(val) >= 5 and val not in ['00000', '10000', '100000']:
            price = pm; break

    # 面積（follow lines 行首）
    area = ''
    for fl in follow_lines:
        m = re.match(r'^([\d,]+(?:\.\d+)?)\s', clean(fl))
        if m: area = m.group(1); break

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

def parse_land_section(text, current_person):
    lines = text.split('\n')
    results = []
    i = 0

    while i < len(lines):
        line = clean(lines[i])
        if not line: i += 1; continue
        if any(kw in line[:8] for kw in ['面  積','權利範圍','所 有','取 得 價','土地坐',
                                           '土地變動','公   尺','建物','（二）','（三）','本欄空白']):
            i += 1; continue
        if re.match(r'^[（（]', line): i += 1; continue
        if not has_addr_kw(lines[i]): i += 1; continue

        follow = []
        j = i + 1
        while j < len(lines) and j <= i + 2:
            nxt = clean(lines[j])
            if not nxt: break
            if any(kw in nxt[:8] for kw in ['面  積','權利範圍','所 有','取 得 價','土地坐',
                                               '土地變動','公   尺','建物']) or re.match(r'^[（（]', nxt) or '本欄空白' in nxt:
                break
            if has_addr_kw(lines[j]) and j == i + 2: break
            follow.append(lines[j]); j += 1

        loc, area, rights, acq, price, reason = parse_land_entry(lines[i], follow)
        if loc and len(loc) >= 4:
            results.append({
                'location': loc, 'area': area, 'rights': rights,
                'holder': current_person or 'unknown',
                'acquisition_time': acq, 'acquisition_reason': reason,
                'price': price, 'type': '土地'
            })
        i = j

    return results

def extract_from_pdf(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                      capture_output=True, text=True, timeout=300)
    if r.returncode != 0: return []
    pages = r.stdout.split('\x0c')

    all_land = []
    current_person = None

    for pi, text in enumerate(pages):
        if not text.strip(): continue
        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2: current_person = name
        if '不動產' not in text: continue

        mi = text.find('（二）不動產')
        if mi == -1: mi = text.find('不動產')
        if mi == -1: continue
        rest = text[mi + 5:]
        ne = re.search(r'（三）船舶|（四）汽車|（七）存款|（八）有價證券|（六）現金|（九）珠寶|（十）債權|（十一）債務|（十二）事業投資|（十三）備', rest)
        end = mi + 5 + (ne.start() if ne else len(rest))
        section = text[mi:end]

        ls = section.find('1.土地')
        le = section.find('2.建物')
        land_text = section[ls:le if le != -1 else len(section)]
        chg = land_text.rfind('土地變動情形')
        if chg != -1: land_text = land_text[:chg]
        land_start = land_text.find('1.土地')
        if land_start != -1: land_text = land_text[land_start + len('1.土地'):]

        items = parse_land_section(land_text, current_person)
        all_land.extend(items)

    return all_land

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
        items = extract_from_pdf(pdf_path)
        elapsed = time.time() - t0
        if items:
            by_person = {}
            for item in items:
                h = item.get('holder', 'unknown')
                if h not in by_person: by_person[h] = {'land': []}
                by_person[h]['land'].append(item)
            all_data[issue_key] = by_person
            print(f'  ✓ {len(by_person)} 人，土地 {len(items)} 筆（{elapsed:.1f}s）')
        else:
            print(f'  - 無（{elapsed:.1f}s）')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    total = sum(len(v.get('land', [])) for d in all_data.values() for v in d.values())
    print(f'\n完成：{len(all_data)} 期，土地 {total} 筆 → {OUT_FILE}')

if __name__ == '__main__':
    main()