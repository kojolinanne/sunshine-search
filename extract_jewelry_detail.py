#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的珠寶、古董、字畫明細。
Section: （九）珠寶、古董、字畫及其他具有相當價值之財產
Format: 財產種類、件數、所有人、價額
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR_OLD = Path.home() / 'Downloads' / '廉政專刊'
PDF_DIR_NEW = Path(__file__).parent.parent
OUT_FILE    = Path(__file__).parent / 'data' / 'jewelry_detail.json'

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

            if '（九）珠' in ls:
                in_section = True
                continue

            if in_section:
                if re.search(r'（十）|（十一）|（十二）|（十三）|（七）|（八）', ls):
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
            if '財 產 種 類' in ls or '項 / 件' in ls or '總價額' in ls or '（總價額' in ls:
                continue
            # Skip insurance section header within (九)
            if re.match(r'^\s*[\u4e00-\u9fff]+保\s*險', ls):
                continue

            stripped = ls.strip()
            if not stripped:
                continue

            # Skip if only a few Chinese chars (likely table artifact)
            if re.match(r'^[\u4e00-\u9fff]{1,4}$', stripped):
                continue

            # Find holder
            holder = None
            for nc in re.findall(r'[\u4e00-\u9fff·]{2,6}', stripped):
                if nc not in ('本欄空白', '持有', '珠寶', '古董', '字畫', '具有',
                              '相當', '價值', '財產', '種類', '件數', '價額',
                              '新臺幣', '合計', '總計'):
                    holder = nc
                    break

            if not holder:
                continue

            # Find count (small number like 1, 2, 3)
            numbers = [int(parse_num(m)) for m in re.findall(r'\b[\d,]+\b', stripped) if parse_num(m) is not None and parse_num(m) <= 1000]
            count = None
            for n in numbers:
                if 1 <= n <= 100:
                    count = n
                    break

            # Find price (large number)
            all_nums = [parse_num(m) for m in re.findall(r'[\d,]+', stripped) if parse_num(m) is not None]
            price = None
            for n in sorted(all_nums, reverse=True):
                if n >= 1000:
                    price = int(n)
                    break

            # Find type
            jtype = None
            for t in ('珠寶', '古董', '字畫', '玉石', '瓷器', '書畫', '雕塑',
                      '金飾', '銀飾', '鑽石', '名表', '郵票', '錢幣', '藝術品',
                      '藝術品', '黃金', '白銀', '珠寶玉石'):
                if t in stripped:
                    jtype = t
                    break

            if holder and price:
                holder_key = holder
                if holder_key not in results:
                    results[holder_key] = {'count': 0, 'items': []}

                results[holder_key]['count'] += 1
                results[holder_key]['items'].append({
                    'type': jtype or '',
                    'count': count,
                    'holder': holder,
                    'price': price,
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
