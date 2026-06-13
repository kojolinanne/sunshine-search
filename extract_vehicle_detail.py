#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的車輛明細。
策略：pdftotext -layout 全速萃取，state-machine 追蹤當前申報人，
在有「（四）汽車」的頁面萃取車輛表格。
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR_OLD = Path.home() / 'Downloads' / '廉政專刊'
PDF_DIR_NEW = Path(__file__).parent.parent
OUT_FILE    = Path(__file__).parent / 'data' / 'vehicle_detail.json'

def find_pdf(n):
    for d in [PDF_DIR_NEW, PDF_DIR_OLD]:
        p = d / f'廉政專刊第{n}期.pdf'
        if p.exists():
            return p
    return None

def clean(s):
    if not s: return ''
    return re.sub(r'\s+', ' ', s).strip()

def parse_num(s):
    if not s: return None
    s = s.strip().replace(',', '').replace(' ', '')
    try: return int(float(s))
    except: return None

def extract_from_pdf(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return {}
    pages = r.stdout.split('\x0c')

    current_person = None
    results = {}

    def join_date_and_row(lines):
        """Prepend date-only lines (e.g. '            月 25 日') to the next real row.
        Also join pure-number lines (price fragments) with the preceding row."""
        merged = []
        for i, ln in enumerate(lines):
            stripped = ln.strip()
            if stripped and re.fullmatch(r'[\d,\s]+', stripped) and i > 0:
                # Price fragment: merge with previous row
                merged[-1] = merged[-1] + ' ' + stripped
            elif stripped and re.match(r'^\s*[月日\s\d]+$', stripped) and i > 0:
                # Date-only line (e.g. '月 25 日' or '  112 年 07'): merge with next
                merged[-1] = merged[-1] + ' ' + stripped
            else:
                merged.append(ln)
        return merged

    for page_idx, text in enumerate(pages):
        if not text.strip():
            continue

        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2:
                current_person = name

        if '（四）汽車' not in text:
            continue

        marker_idx = text.find('（四）汽車')
        rest = text[marker_idx + len('（四）汽車'):]
        next_sec = re.search(r'（[一二三四五六七八九十]+[）.]|（五）|（六）|（七）|（八）|（九）|（十）|（十一）|（十二）|（十三）|備註', rest)
        if next_sec:
            section = text[marker_idx:marker_idx + len('（四）汽車') + next_sec.start()]
        else:
            section = text[marker_idx:marker_idx + len('（四）汽車') + 1200]

        section_len = len(section) - len('（四）汽車')
        if section_len < 300 and page_idx + 1 < len(pages):
            next_page = pages[page_idx + 1]
            ns2 = re.search(r'（[一二三四五六七八九十]+[）.]|（五）|（六）|（七）|（八）|（九）|（十）|備註', next_page)
            if ns2:
                section += next_page[:ns2.start()]
            else:
                section += next_page

        lines = section.split('\n')
        lines = join_date_and_row(lines)  # join date/price fragments before parsing
        pending_date = ''

        for line in lines:
            ls = clean(line)
            if not ls:
                pending_date = ''
                continue

            ym_m = re.search(r'(\d+)\s*年\s*(\d+)\s*月', ls)
            d_m  = re.search(r'月\s*(\d+)\s*日', ls)
            if ym_m:
                pending_date = f'{ym_m.group(1)}年{ym_m.group(2)}月'
            if d_m and pending_date:
                pending_date += f'{d_m.group(1)}日'

            parts = ls.split()
            if len(parts) < 3:
                continue

            amount_candidates = []
            cc_candidates = []
            human_name = ''

            for p in parts:
                num = parse_num(p)
                if num is not None:
                    if num > 50000:
                        amount_candidates.append(num)
                    elif 100 < num < 10000:
                        cc_candidates.append(num)
                if re.match(r'^[\u4e00-\u9fff·]{2,6}$', p) and p not in ('買賣', '贈與', '繼承', '承受', '出租', '本欄空白'):
                    human_name = p

            if amount_candidates and human_name:
                price = max(amount_candidates)
                cc    = cc_candidates[0] if cc_candidates else None

                if human_name not in results:
                    results[human_name] = {'count': 0, 'total': 0, 'items': [], 'seen_prices': set()}

                if price in results[human_name]['seen_prices']:
                    pending_date = ''
                    continue

                results[human_name]['seen_prices'].add(price)
                results[human_name]['count'] += 1
                results[human_name]['total'] += price

                entry = {
                    'brand': parts[0],
                    'owner': human_name,
                    'amount': price,
                    'acquisition_date': pending_date,
                }
                if cc:
                    entry['cc'] = cc
                results[human_name]['items'].append(entry)
                pending_date = ''

    for h in results:
        results[h].pop('seen_prices', None)

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
            total = sum(v['count'] for v in result.values())
            print(f'  ✓ {len(result)} 人，{total} 輛（{elapsed:.1f}s）')
        else:
            print(f'  - 無（{elapsed:.1f}s）')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    total = sum(sum(v['count'] for v in d.values()) for d in all_data.values())
    print(f'\n完成：{len(all_data)} 期，{total} 輛 → {OUT_FILE}')

if __name__ == '__main__':
    main()