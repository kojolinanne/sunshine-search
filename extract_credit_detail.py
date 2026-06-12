#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的債權明細。
PDF section: （十）債權
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR_OLD = Path.home() / 'Downloads' / '廉政專刊'
PDF_DIR_NEW = Path(__file__).parent.parent
OUT_FILE    = Path(__file__).parent / 'data' / 'credit_detail.json'

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

    for text in pages:
        if not text.strip():
            continue

        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2:
                current_person = name

        if '（十）債權' not in text:
            continue

        marker_idx = text.find('（十）債權')
        rest = text[marker_idx + len('（十）債權'):]
        next_sec = re.search(r'（十一）債務|（十二）事業|（十三）備', rest)
        end_idx = marker_idx + len('（十）債權') + (next_sec.start() if next_sec else len(rest))
        section = text[marker_idx:end_idx]

        holder = current_person or 'unknown'
        lines = section.split('\n')

        for ln in lines:
            ls = clean(ln)
            if not ls:
                continue
            if '（十）' in ls or '債  權' in ln or '債 權' in ln:
                continue
            if '本欄空白' in ls:
                break
            if '（十一）' in ls or '（十二）' in ls:
                break

            # 解析：類型、債權人、債務人及地址、餘額
            balance_m = re.search(r'([0-9,]+)\s*$', ls.strip())
            balance = balance_m.group(1) if balance_m else ''

            # 債務人通常有地址特徵
            addr = ''
            names = re.findall(r'[\u4e00-\u9fff]{2,8}', ls)
            debtor = ''
            for n in names:
                if n not in ['本欄空白']:
                    debtor = n
                    break

            if debtor or balance:
                if holder not in results:
                    results[holder] = []
                results[holder].append({
                    'type': '',
                    'creditor': holder,
                    'debtor': debtor,
                    'debtor_address': addr,
                    'balance': balance,
                    'acquisition_time': '',
                    'reason': ''
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
        if result is not None:
            all_data[issue_key] = result
            with open(OUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            total = sum(len(v) for v in result.values())
            print(f'  ✓ {len(result)} 人，{total} 筆（{elapsed:.1f}s）')
        else:
            print(f'  - 無（{elapsed:.1f}s）')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    total_all = sum(sum(len(v) for v in d.values()) for d in all_data.values())
    print(f'\n完成：{len(all_data)} 期，{total_all} 筆債權 → {OUT_FILE}')

if __name__ == '__main__':
    main()