#!/usr/bin/env python3
"""
land_detail 萃取 v3 - 行分組策略（專治分欄切割問題）

PDF 版面觀察：
  土地 entry 標準 layout（pdftotext -layout）：
    新竹縣芎林鄉上德段 0200 小段        [col~46]    110 年 05      [col~64]  17,000,000  ← 行1：位置+日期+價額
                                        84.17     全部                程瑞芳           買賣    ← 行2：面積+持分+所有人+原因

策略：
  1. 找所有「土地坐落行」（行首 ~35 字內含地址關鍵字）
  2. 該行 + 其後 1-2 行 → 組成一個 land entry
  3. 統一從這些行解析 location / area / rights / acquisition_time / price
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

def has_addr_kw(s, max_len=35):
    """行首 max_len 字內含地址關鍵字 → 這是土地坐落行"""
    prefix = s[:max_len] if len(s) > max_len else s
    kw = ['段', '路', '街', '市', '區', '里', '巷', '弄', '町', '丁目', '縣', '鄉', '鎮']
    return any(k in prefix for k in kw)

def extract_fields(combo_text):
    """從一行或組合行文字中抽取土地欄位"""
    loc_m = re.search(r'([^\n]{4,50}段[^\n]*|[^\n]{4,50}路[^\n]*|[^\n]{4,50}市[^\n]*|[^\n]{4,50}區[^\n]*|[^\n]{4,50}鄉[^\n]*|[^\n]{4,50}鎮[^\n]*|[^\n]{4,50}町[^\n]*|[^\n]{4,50}丁目[^\n]*)', combo_text)
    location = clean(loc_m.group(1)) if loc_m else ''

    share_m = re.search(r'(\d+\s*分\s*之\s*\d+)', combo_text)
    rights = clean(share_m.group(1)) if share_m else ''

    date_m = re.search(r'(\d+\s*年\s*\d+\s*月\s*\d+\s*日?)', combo_text)
    acq_time = clean(date_m.group(1)) if date_m else ''

    # 價額：找 5 位以上的數字（排除持分格式）
    price_candidates = re.findall(r'\b([0-9,]{5,})\b', combo_text)
    price = ''
    for c in price_candidates:
        # 排除看起來像日期或持分的數字
        if not re.search(r'\d+[年日月]', combo_text[combo_text.find(c)-3:combo_text.find(c)+3]):
            if not re.match(r'^\d+,?\d*,?\d*$', c):  # 不是持分格式
                price = c
                break
    # 備用：找結尾的大數字
    if not price:
        price_m = re.search(r'([0-9,]{5,})\s*$', combo_text.strip())
        if price_m: price = price_m.group(1)

    # 面積：行首的小數值（<=10位）且不是持分
    area_m = re.match(r'^([\d,]+(?:\.\d+)?)\s+(?!\d+\s*分)', combo_text.strip())
    area = area_m.group(1) if area_m and len(area_m.group(1)) <= 12 else ''

    return location, area, rights, acq_time, price

def parse_land_lines(lines, current_person):
    """核心解析：掃描所有行，分組後抽取欄位"""
    results = []
    n = len(lines)
    i = 0

    while i < n:
        line = clean(lines[i])

        # 跳過 header、空行、非土地行
        if not line: i+=1; continue
        if any(kw in line[:8] for kw in ['面  積', '權利範圍', '所 有 權', '取 得 價', '土地坐',
                                          '土地變動', '公   尺', '持 分 )', '建物', '（二）', '（三）', '本欄空白']):
            i+=1; continue
        if re.match(r'^[（（十三）備]', line): i+=1; continue

        # 檢查是否為土地坐落行
        if not has_addr_kw(line): i+=1; continue

        # === 這行是土地坐落：收集其後 1-2 行 ===
        entry_lines = [line]
        for j in [1, 2]:
            if i+j < n:
                nxt = clean(lines[i+j])
                if nxt and not any(kw in nxt[:6] for kw in ['面  積', '權利範圍', '所 有 權', '取 得 價', '土地變動', '（二）', '（三）', '本欄空白']) and not re.match(r'^[（（]', nxt):
                    # 不是 header 行，也不是另一個坐落行（行首有地址關鍵字）
                    if not has_addr_kw(nxt) or j == 2:  # 第2行不論是否為坐落行都附加
                        entry_lines.append(nxt)
                        i += 1
                    else:
                        break
                else:
                    break
            else:
                break

        combo = ' '.join(entry_lines)
        location, area, rights, acq_time, price = extract_fields(combo)

        if location and len(location) >= 4:
            results.append({
                'location': location,
                'area': area,
                'rights': rights,
                'holder': current_person or 'unknown',
                'acquisition_time': acq_time,
                'acquisition_reason': '',
                'price': price,
                'type': '土地'
            })

        i += 1

    return results

def extract_from_pdf(pdf_path, current_person):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                      capture_output=True, text=True, timeout=300)
    if r.returncode != 0: return []
    pages = r.stdout.split('\x0c')

    all_land = []
    cp = current_person

    for pi, text in enumerate(pages):
        if not text.strip(): continue

        # 更新 current_person
        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2: cp = name

        if '不動產' not in text: continue

        # 擷取土地 section
        mi = text.find('（二）不動產')
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
        land_text = land_text[land_text.find('1.土地') + len('1.土地'):]

        items = parse_land_lines(land_text.split('\n'), cp)
        all_land.extend(items)

    return all_land

def main():
    # 先讀 backup（清理前的乾淨版）並建立 issue→person→land 結構
    if IN_BACKUP.exists():
        with open(IN_BACKUP, encoding='utf-8') as f:
            orig = json.load(f)
    else:
        orig = {}

    all_data = {str(n): {} for n in ISSUES}

    for issue_num in ISSUES:
        issue_key = str(issue_num)
        if issue_key in orig:
            all_data[issue_key] = orig[issue_key]
        else:
            pdf_path = find_pdf(issue_num)
            if not pdf_path:
                print(f'第 {issue_num} 期：PDF 不存在')
                continue
            t0 = time.time()
            print(f'處理第 {issue_num} 期（萃取）...', flush=True)
            items = extract_from_pdf(pdf_path, None)
            elapsed = time.time() - t0
            if items:
                # 組織成 {person: {land: []}} 並填入 all_data
                by_person = {}
                for item in items:
                    holder = item.get('holder', 'unknown')
                    if holder not in by_person: by_person[holder] = {'land': []}
                    by_person[holder]['land'].append(item)
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