#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的不動產（土地 + 建物）明細。
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR_OLD = Path.home() / 'Downloads' / '廉政專刊'
PDF_DIR_NEW = Path(__file__).parent.parent
OUT_FILE   = Path(__file__).parent / 'data' / 'land_detail.json'

def find_pdf(n):
    for d in [PDF_DIR_NEW, PDF_DIR_OLD]:
        p = d / f'廉政專刊第{n}期.pdf'
        if p.exists():
            return p
    return None

def clean(s):
    if not s: return ''
    return re.sub(r'\s+', ' ', s).strip()

def extract_from_pdf(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return {}
    pages = r.stdout.split('\x0c')

    results = {}
    current_person = None

    for pi, text in enumerate(pages):
        if not text.strip():
            continue

        # 更新 current_person
        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2:
                current_person = name

        # 只處理不動產 section
        if '（二）不動產' not in text and '不動產' not in text:
            continue

        # 找不動產 section
        marker_idx = text.find('（二）不動產')
        if marker_idx == -1:
            continue

        # 找下一個大 section 終止
        rest = text[marker_idx + len('（二）不動產'):]
        next_sec_match = re.search(r'（三）船舶|（四）汽車|（七）存款|（八）有價證券|（六）現金|（九）珠寶|（十）債權|（十一）債務|（十二）事業投資|（十三）備', rest)
        end_idx = marker_idx + len('（二）不動產') + (next_sec_match.start() if next_sec_match else len(rest))
        section = text[marker_idx:end_idx]

        # 找 1.土地 和 2.建物 各自範圍
        land_start = section.find('1.土地')
        bldg_start = section.find('2.建物')
        land_end   = bldg_start if bldg_start != -1 else len(section)
        bldg_end   = len(section)

        # ── 解析土地 ──────────────────────────────────────────────
        if land_start != -1 and land_start < land_end:
            land_text = section[land_start:land_end]
            # 跳過「土地變動情形」
            变动_pos = land_text.rfind('土地變動情形')
            if 变动_pos != -1:
                land_text = land_text[:变动_pos]
            land_text = land_text[land_text.find('1.土地') + len('1.土地'):]

            lines = land_text.split('\n')
            # 找表頭行（含有「面積」「權利」「所 有 權」「取 得 價」）
            header_idx = -1
            for i, ln in enumerate(lines):
                if '面  積' in ln and ('權' in ln or '所' in ln):
                    header_idx = i
                    break

            pending = {}  # {idx: data}
            for li, ln in enumerate(lines[header_idx+1:] if header_idx >= 0 else lines):
                li = li + (header_idx + 1 if header_idx >= 0 else 0)
                ls = clean(ln)

                # 遇到下一個區塊就停
                if re.match(r'^\s*建\s*物|^    2\.|土地變動|^（', ls) or '建物' in ls[:5]:
                    break
                if '2.建物' in ls or '建物' in ls[:4]:
                    break

                # 跳過表頭和空行
                if '面  積' in ln or '所 有 權' in ln or '公   尺' in ln or not ls.strip():
                    continue
                if '本欄空白' in ln:
                    break

                # 解析土地列：位置、面積、權利範圍(持分)、所有人、取得時間、取得原因、價額
                # Layout 特徵：土地位置通常有「段」「路」「街」等關鍵字
                # 持分如 10000 分之 267 或 76 分之 3
                location = ''
                area = ''
                rights = ''
                price = ''
                acq_time = ''
                acq_reason = ''

                # 以「段/路/街/區」找位置
                loc_m = re.search(r'([^\n]{5,50})?(段|路[一二三四五六七八九十\d]+段|[東西南北中]路|[一二三四五六七八九十\d]+段)', ls)
                if loc_m:
                    location = clean(loc_m.group(0))
                else:
                    # 取前面有內容的部分作為位置
                    parts = [p.strip() for p in re.split(r'\s{3,}', ls) if p.strip()]
                    if parts:
                        location = parts[0]

                # 持分 (10000 分之 N / N 分之 M)
                share_m = re.search(r'(\d+\s*分\s*之\s*\d+)', ls)
                if share_m:
                    rights = clean(share_m.group(1))

                # 價額（數字金額，通常是最後的數值欄）
                price_m = re.search(r'([0-9,]+)\s*$', ls.strip())
                if price_m:
                    price = price_m.group(1)

                # 所有人（從 current_person 或從行末非數字欄位）
                holder = current_person or 'unknown'

                if location:
                    if holder not in results:
                        results[holder] = {}
                    if 'land' not in results[holder]:
                        results[holder]['land'] = []

                    area_m = re.search(r'([0-9,]+)\s*$', ls)
                    if area_m and len(ls) < 80:
                        area = area_m.group(1)

                    results[holder]['land'].append({
                        'location': location,
                        'area': area,
                        'rights': rights,
                        'holder': holder,
                        'acquisition_time': acq_time,
                        'acquisition_reason': acq_reason,
                        'price': price,
                        'type': '土地'
                    })

        # ── 解析建物 ──────────────────────────────────────────────
        if bldg_start != -1:
            bldg_text = section[bldg_start:bldg_end]
            变动_pos = bldg_text.rfind("建  物  變  動")
            if 变动_pos != -1:
                bldg_text = bldg_text[:变动_pos]
            bldg_text = bldg_text[bldg_text.find('2.建物') + len('2.建物'):]

            lines = bldg_text.split('\n')
            holder = current_person or 'unknown'

            for ln in lines:
                ls = clean(ln)
                if not ls:
                    continue
                if '建物變動' in ls or '建  物  變' in ls:
                    break
                if re.match(r'^[（（十三）備]', ls):
                    break
                if '本欄空白' in ls:
                    break

                # 建物位置通常含「市」「區」「段」「號」
                if re.search(r'[市區段號路街]', ls) and len(ls) > 5:
                    location = ls[:60]
                    share_m = re.search(r'(\d+\s*分\s*之\s*\d+)', ls)
                    rights = clean(share_m.group(1)) if share_m else ''
                    price_m = re.search(r'([0-9,]+)\s*$', ls.strip())
                    price = price_m.group(1) if price_m else ''

                    if holder not in results:
                        results[holder] = {}
                    if 'building' not in results[holder]:
                        results[holder]['building'] = []

                    results[holder]['building'].append({
                        'location': location,
                        'area': '',
                        'rights': rights,
                        'holder': holder,
                        'acquisition_time': '',
                        'acquisition_reason': '',
                        'price': price,
                        'type': '建物'
                    })

    return results

def main():
    issues = list(range(292, 320))
    all_data = {}

    if OUT_FILE.exists():
        try:
            with open(OUT_FILE, encoding='utf-8') as f:
                all_data = json.load(f)
            print(f'已讀取 {len(all_data)} 期進度')
        except Exception:
            pass

    for issue_num in issues:
        issue_key = str(issue_num)
        if issue_key in all_data:
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
            with open(OUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            land_n = sum(len(v.get('land',[])) for v in result.values())
            bldg_n = sum(len(v.get('building',[])) for v in result.values())
            print(f'  ✓ {len(result)} 人，土地{land_n} 筆，建物{bldg_n} 筆（{elapsed:.1f}s）')
        else:
            print(f'  - 無（{elapsed:.1f}s）')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    total_land = sum(sum(len(v.get('land',[])) for v in d.values()) for d in all_data.values())
    total_bldg = sum(sum(len(v.get('building',[])) for v in d.values()) for d in all_data.values())
    print(f'\n完成：{len(all_data)} 期，土地{total_land} 筆，建物{total_bldg} 筆 → {OUT_FILE}')

if __name__ == '__main__':
    main()