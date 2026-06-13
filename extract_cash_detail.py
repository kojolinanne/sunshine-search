#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的現金明細。
Section: （六）現金
格式：幣別、所有人、外幣總額、新臺幣總額
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR_OLD = Path.home() / 'Downloads' / '廉政專刊'
PDF_DIR_NEW = Path(__file__).parent.parent
OUT_FILE    = Path(__file__).parent / 'data' / 'cash_detail.json'

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
    try: return float(s)
    except: return None

CURRENCIES = ('新臺幣', '美元', '日圓', '歐元', '英鎊', '港幣', '人民幣',
              '澳幣', '加幣', '瑞士法郎', '新加坡幣', '泰銖', '紐幣', '南非幣',
              '瑞典幣', '墨西哥披索', '印尼幣', '越南盾')

def extract_from_pdf(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return {}
    pages = r.stdout.split('\x0c')

    current_person = None
    results = {}
    in_section = False

    for pi, text in enumerate(pages):
        if not text.strip():
            continue

        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2:
                current_person = name

        lines = text.split('\n')
        for li, line in enumerate(lines):
            ls = clean(line)

            if '（六）現金' in ls:
                in_section = True
                continue

            if in_section:
                # End conditions
                if re.search(r'（七）|（八）|（九）|（十）|（十一）|（十二）|（十三）', ls) and '（六）現金' not in ls:
                    in_section = False
                    continue
                if ls.startswith('備註') and len(ls) < 10:
                    in_section = False
                    continue

            if not in_section:
                continue

            if not ls or ls == '本欄空白':
                continue
            if re.match(r'^[\s\u3000·\.]+$', ls):
                continue
            if '總金額' in ls or '新臺幣總額' in ls or '外幣總額' in ls:
                continue
            if re.match(r'^[\u4e00-\u9fff]{1,4}$', ls):
                continue

            stripped = ls.strip()
            if not stripped:
                continue

            # Find currency
            currency = None
            for c in CURRENCIES:
                if c in stripped:
                    currency = c
                    break
            if not currency:
                currency = '新臺幣'

            # Find holder
            holder = None
            for nc in re.findall(r'[\u4e00-\u9fff·]{2,6}', stripped):
                if nc not in ('新臺幣', '本欄空白', '持有', '現金', '外幣', '總額',
                              '幣別', '美元', '日圓', '歐元', '英鎊', '港幣', '人民幣',
                              '澳幣', '加幣', '新台幣'):
                    holder = nc
                    break
            if not holder:
                holder = current_person or '不明'

            # Find amounts
            all_amounts = [parse_num(m) for m in re.findall(r'[\d,]+', stripped) if parse_num(m) is not None]
            ntd_amount = None
            foreign_amount = None
            if len(all_amounts) >= 2:
                ntd_amount = all_amounts[-1]
                foreign_amount = all_amounts[-2]
            elif len(all_amounts) == 1:
                ntd_amount = all_amounts[0]

            if ntd_amount is not None or currency != '新臺幣':
                # Fix: use current_person as key so getPersonDetail can find by person name
                holder_key = current_person
                if holder_key not in results:
                    results[holder_key] = {'count': 0, 'items': []}
                results[holder_key]['count'] += 1
                results[holder_key]['items'].append({
                    'currency': currency,
                    'holder': holder,
                    'foreign_amount': foreign_amount,
                    'ntd_amount': ntd_amount,
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
            total = sum(v['count'] for v in result.values())
            print(f'  ✓ {len(result)} 人，{total} 筆（{elapsed:.1f}s）')
        else:
            print(f'  - 無（{elapsed:.1f}s）')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    total = sum(sum(v['count'] for v in d.values()) for d in all_data.values())
    print(f'\n完成：{len(all_data)} 期，{total} 筆 → {OUT_FILE}')

if __name__ == '__main__':
    main()
