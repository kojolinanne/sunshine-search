#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的航空器明細。
Section: （五）航空器
格式：形式、用途、所有人、取得時間、取得原因、取得價額
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR_OLD = Path.home() / 'Downloads' / '廉政專刊'
PDF_DIR_NEW = Path(__file__).parent.parent
OUT_FILE    = Path(__file__).parent / 'data' / 'aircraft_detail.json'

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
    pending_date = ''

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

            if '（五）航空器' in ls:
                in_section = True
                pending_date = ''
                continue

            if in_section:
                if re.search(r'（六）|（七）|（八）|（九）|（十）|（十一）|（十二）|（十三）', ls):
                    in_section = False
                    pending_date = ''
                    continue
                if ls.startswith('備註') and len(ls) < 10:
                    in_section = False
                    continue

            if not in_section:
                continue

            if not ls or ls == '本欄空白':
                pending_date = ''
                continue
            if re.match(r'^[\s\u3000·\.]+$', ls):
                continue
            if '國籍標示' in ls or '型 式' in ls or '登 記' in ls or '製造廠' in ls:
                continue

            # Track date
            ym_m = re.search(r'(\d+)\s*年\s*(\d+)\s*月', ls)
            d_m = re.search(r'月\s*(\d+)\s*日', ls)
            if ym_m:
                pending_date = f'{ym_m.group(1)}年{ym_m.group(2)}月'
            if d_m and pending_date:
                pending_date += f'{d_m.group(1)}日'

            # Find holder
            holder = None
            for nc in re.findall(r'[\u4e00-\u9fff·]{2,6}', ls):
                if nc not in ('本欄空白', '持有', '航空器', '飛機', '直升机', '用途',
                              '取得', '原因', '價額', '登記', '買賣', '贈與', '繼承',
                              '承受', '民航', '公用', '私人'):
                    holder = nc
                    break

            if not holder:
                continue

            # Find price (large number)
            numbers = [parse_num(m) for m in re.findall(r'[\d,]+', ls) if parse_num(m) is not None]
            price = None
            for n in sorted(numbers, reverse=True):
                if n >= 100000:
                    price = int(n)
                    break

            # Find reason
            reason = None
            for r_word in ('買賣', '贈與', '繼承', '承受', '拍賣', '其他'):
                if r_word in ls:
                    reason = r_word
                    break

            # Find usage
            usage = None
            for u in ('公用', '私人', '商用', '教學', '競技', '農業', '救護'):
                if u in ls:
                    usage = u
                    break

            # Find form/type
            form = None
            for f in ('直昇機', '飛機', '航空器', '螺旋槳', '噴射機', '教練機',
                      '民航機', '私人飛機'):
                if f in ls:
                    form = f
                    break

            if holder and price:
                holder_key = holder
                if holder_key not in results:
                    results[holder_key] = {'count': 0, 'items': []}

                results[holder_key]['count'] += 1
                results[holder_key]['items'].append({
                    'form': form or '',
                    'usage': usage or '',
                    'holder': holder,
                    'acquisition_time': pending_date,
                    'acquisition_reason': reason or '',
                    'price': price,
                })
                pending_date = ''

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
