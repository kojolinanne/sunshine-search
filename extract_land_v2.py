#!/usr/bin/env python3
"""
land_detail 萃取 v2 - 解決分欄切割問題。

PDF 版面分析（pdftotext -layout）：
  土地坐落      面積(平方公尺)  權利範圍(持分)  登記(取得)時間  取得價額
  ─────────────────────────────────────────────────────────────
  新竹縣芎林鄉    84.17          全部            程瑞芳         17,000,000
  上德段0200小段                   110年05月09日  買賣

問題：坐落和面積/持分分屬兩列，萃取時各自獨立變成 fragment。
策略：行分組 - 對每一行，若含地址關鍵字，與其後 1-2 行綁定成同一筆土地。
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR = Path.home() / 'Downloads' / '廉政專刊'
OUT_FILE = Path(__file__).parent / 'data' / 'land_detail.json'
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

def is_address_line(text):
    """這行文字是否像土地坐落（含有地址關鍵字）"""
    addr_kw = ['段', '路', '街', '市', '區', '里', '巷', '弄', '町', '丁目', '縣', '鄉', '鎮']
    return any(k in text for k in addr_kw)

def parse_land_section_v2(section_text, current_person):
    """
    解析土地 section（傳入已裁切的不動產區塊文字）。
    使用行分組策略：遇到地址行則開新 entry，與其後 1-2 行內容合併。
    """
    lines = section_text.split('\n')
    results = []
    i = 0

    while i < len(lines):
        line = clean(lines[i])

        # 遇空白行或 header 行則跳過
        if not line or '面  積' in line or '權利範圍' in line or '所 有 權' in line or \
           '取 得 價' in line or '土地坐' in line or '土地變動' in line:
            i += 1
            continue

        # 遇到建物區塊離開
        if '2.建物' in line or re.match(r'^\s*建\s*物', line):
            break

        # 只處理有地址關鍵字的行
        if not is_address_line(line):
            # 檢查是否為持分/面積/日期殘留行（但沒有地址）→ 嘗試附加到前一個結果
            if results and (re.search(r'\d+\s*分\s*之', line) or re.match(r'^\d+[/,.]?\d*', line.strip()) or
                            re.match(r'^\d+\s*年', line) or re.match(r'^[上下中東西南北]', line)):
                # 附加到前一個 entry
                last = results[-1]
                # 如果前 entry 沒有 area，嘗試從這行取得
                if not last.get('area'):
                    area_m = re.match(r'([\d,]+(?:\.\d+)?)', line.strip())
                    if area_m and len(line.strip()) < 30:
                        last['area'] = area_m.group(1)
                if not last.get('rights'):
                    share_m = re.search(r'(\d+\s*分\s*之\s*\d+)', line)
                    if share_m:
                        last['rights'] = clean(share_m.group(1))
                if not last.get('price'):
                    price_m = re.search(r'([0-9,]+)\s*$', line.strip())
                    if price_m and len(line) < 30:
                        last['price'] = price_m.group(1)
                i += 1
                continue
            i += 1
            continue

        # === 這是地址行：開新 entry ===
        entry = {
            'location': '',
            'area': '',
            'rights': '',
            'holder': current_person or 'unknown',
            'acquisition_time': '',
            'acquisition_reason': '',
            'price': '',
            'type': '土地'
        }

        # 收集地址文字（可能跨 2 行）
        addr_parts = []
        j = i
        while j < len(lines) and len(addr_parts) < 3:
            l = clean(lines[j])
            if not l: break
            # 如果遇到 header 行則停止
            if '面  積' in l or '權利範圍' in l or '所 有 權' in l or '取 得 價' in l or \
               '土地變動' in l or '建物' in l[:4] or re.match(r'^[（（]', l):
                break
            # 遇到另一個地址行也停止
            if j > i and is_address_line(l) and not re.match(r'^[上下中東西南北]', l):
                break
            if is_address_line(l) or re.match(r'^[上下中東西南北]', l):
                addr_parts.append(l)
            j += 1

        entry['location'] = ' '.join(addr_parts)

        # 處理緊接在後的「面積/持分/日期/價額」行
        k = j
        while k < len(lines) and k < j + 3:
            l = clean(lines[k])
            if not l: break
            # header/blank 行
            if not l or '面  積' in l or '權利範圍' in l or '所 有 權' in l or '取 得 價' in l or \
               '土地變動' in l or '建物' in l[:4] or '本欄空白' in l:
                k += 1
                continue
            # 遇到下一個地址行（跨區塊）
            if is_address_line(l) and k > j:
                break

            # 持分
            if not entry.get('rights'):
                share_m = re.search(r'(\d+\s*分\s*之\s*\d+)', l)
                if share_m:
                    entry['rights'] = clean(share_m.group(1))

            # 面積（純數字，長度短）
            if not entry.get('area'):
                area_m = re.search(r'^([\d,]+(?:\.\d+)?)(?:\s|$)', l.strip())
                if area_m and len(l.strip()) < 30:
                    entry['area'] = area_m.group(1)

            # 日期（110 年 05 月 09 日）
            if not entry.get('acquisition_time'):
                date_m = re.search(r'(\d+\s*年\s*\d+\s*月\s*\d+\s*日?)', l)
                if date_m:
                    entry['acquisition_time'] = clean(date_m.group(1))

            # 價額（結尾的大數字）
            if not entry.get('price'):
                # 結尾數字（排除日期數字）
                price_m = re.search(r'([0-9,]{4,})\s*$', l.strip())
                if price_m and not re.search(r'年|月|日', l):
                    entry['price'] = price_m.group(1)

            # 所有人
            if not current_person:
                holder_m = re.search(r'^([^\d\s][^\d]{1,10}?(?:[男女]|[A-Za-z]))', l)
                if holder_m:
                    h = clean(holder_m.group(1))
                    if len(h) >= 2 and len(h) <= 6:
                        entry['holder'] = h

            k += 1

        # 只有 location 有效（有地址關鍵字）才保留
        if is_address_line(entry['location']):
            results.append(entry)

        i = max(j, k)
        if i == j and j == i:
            i = j + 1

    return results

def extract_from_pdf(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                      capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return {}
    pages = r.stdout.split('\x0c')

    results = {}
    current_person = None

    for pi, text in enumerate(pages):
        if not text.strip(): continue

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

        # 找不動產 section 邊界
        marker_idx = text.find('（二）不動產')
        if marker_idx == -1: continue

        rest = text[marker_idx + len('（二）不動產'):]
        next_sec = re.search(r'（三）船舶|（四）汽車|（七）存款|（八）有價證券|（六）現金|（九）珠寶|（十）債權|（十一）債務|（十二）事業投資|（十三）備', rest)
        end_idx = marker_idx + len('（二）不動產') + (next_sec.start() if next_sec else len(rest))
        section = text[marker_idx:end_idx]

        # 找土地/建物範圍
        land_start = section.find('1.土地')
        bldg_start = section.find('2.建物')
        land_end = bldg_start if bldg_start != -1 else len(section)

        if land_start != -1 and land_start < land_end:
            land_text = section[land_start:land_end]
            # 去除「土地變動情形」區塊
            change_pos = land_text.rfind('土地變動情形')
            if change_pos != -1:
                land_text = land_text[:change_pos]
            land_text = land_text[land_text.find('1.土地') + len('1.土地'):]

            # 用 v2 解析
            items = parse_land_section_v2(land_text, current_person)
            if items:
                if current_person not in results:
                    results[current_person] = {}
                results[current_person]['land'] = results[current_person].get('land', []) + items

    return results

def main():
    all_data = {str(n): {} for n in ISSUES}
    if OUT_FILE.exists():
        try:
            with open(OUT_FILE, encoding='utf-8') as f:
                existing = json.load(f)
                # 保留現有資料，併入 all_data
                for k, v in existing.items():
                    if k in all_data:
                        all_data[k] = v
        except Exception: pass

    for issue_num in ISSUES:
        issue_key = str(issue_num)
        pdf_path = find_pdf(issue_num)
        if not pdf_path:
            print(f'第 {issue_num} 期：PDF 不存在')
            continue
        t0 = time.time()
        print(f'處理第 {issue_num} 期...', flush=True)
        result = extract_from_pdf(pdf_path)
        elapsed = time.time() - t0
        if result:
            # 與舊資料合併
            for person, data in result.items():
                if person not in all_data[issue_key]:
                    all_data[issue_key][person] = {}
                all_data[issue_key][person].update(data)
            total_land = sum(len(v.get('land', [])) for v in result.values())
            print(f'  ✓ {len(result)} 人，土地 {total_land} 筆（{elapsed:.1f}s）')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    total = sum(len(v.get("land", [])) for d in all_data.values() for v in d.values())
    print(f'\n完成：{len(all_data)} 期，土地 {total} 筆 → {OUT_FILE}')

if __name__ == '__main__':
    main()