#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的債務明細（第十一）債務）。
策略：pdftotext 萃取文字，正規表達式解析。
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR = Path.home() / 'Downloads' / '廉政專刊'
OUT_FILE = Path(__file__).parent / 'data' / 'debt_detail.json'

def parse_num(s):
    if not s: return None
    s = s.strip().replace(',', '').replace(' ', '')
    try: return int(float(s))
    except: return None

def extract_from_pdf(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return {}
    pages_text = r.stdout.split('\x0c')

    # 建立人名→頁面索引
    person_pages = {}
    for pi, text in enumerate(pages_text):
        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2:
                person_pages.setdefault(name, set()).add(pi)

    name_all_pages = {n: s.copy() for n, s in person_pages.items()}
    for pi, text in enumerate(pages_text):
        for name in person_pages:
            if name in text:
                name_all_pages[name].add(pi)

    results = {}
    for person_name, page_set in name_all_pages.items():
        person_debts = []
        for pi in page_set:
            if pi >= len(pages_text): continue
            text = pages_text[pi]
            if person_name not in text: continue

            debt_m = re.search(r'（十一）債務[^\n]*（總金額[：:]\s*新臺幣\s*([0-9,，]+)\s*元）', text)
            if not debt_m:
                continue

            debt_start = debt_m.end()
            next_sec = re.search(r'（十二）', text[debt_start:])
            debt_section = text[debt_start:debt_start + next_sec.start() if next_sec else len(text)]

            # 解析：債權人資訊在「授信」行的上一行（layout模式特徵）
            prev_line = ''
            for line in debt_section.split('\n'):
                line = line.rstrip()
                prev_stripped = prev_line.strip()
                if not prev_stripped:
                    prev_line = line
                    continue
                # 上一行是債權人（含日期、原因的行）
                creditor = prev_stripped
                is_debt_row = (f'授信' in line or '房貸' in line or '信貸' in line or '車貸' in line) and person_name in line
                if is_debt_row:
                    # 找金額（倒數第一個大數字）
                    amounts = re.findall(r'\b(\d{1,3}(?:,\d{3}){2,})\b', line)
                    for amt_str in amounts:
                        amount = parse_num(amt_str)
                        if amount and amount > 1000:
                            person_debts.append({'creditor': creditor, 'amount': amount})
                            break
                prev_line = line

        if person_debts:
            results[person_name] = {
                'total': sum(d['amount'] for d in person_debts),
                'count': len(person_debts),
                'items': person_debts[:20]
            }

    return results

def main():
    issues = list(range(292, 320))
    all_data = {}

    if OUT_FILE.exists():
        try:
            with open(OUT_FILE, encoding='utf-8') as f:
                all_data = json.load(f)
            print(f'已讀取 {len(all_data)} 期歷史進度')
        except Exception:
            pass

    for issue_num in issues:
        issue_key = str(issue_num)
        if issue_key in all_data:
            print(f'第 {issue_num} 期：已有資料，跳過')
            continue

        pdf_path = PDF_DIR / f'廉政專刊第{issue_num}期.pdf'
        if not pdf_path.exists():
            print(f'第{issue_num}期：PDF 不存在，跳過')
            continue

        t0 = time.time()
        print(f'處理第 {issue_num} 期 ({pdf_path.stat().st_size/1024/1024:.1f}MB)...', flush=True)
        result = extract_from_pdf(pdf_path)
        elapsed = time.time() - t0

        if result:
            all_data[issue_key] = result
            with open(OUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            total_count = sum(v['count'] for v in result.values())
            print(f'  ✓ {len(result)} 人，{total_count} 筆債務（{elapsed:.0f}s）')
        else:
            print(f'  - 無債務資料（{elapsed:.0f}s）')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    total_count = sum(sum(v['count'] for v in d.values()) for d in all_data.values())
    print(f'\n完成：{len(all_data)} 期，{total_count} 筆債務記錄')
    print(f'寫入：{OUT_FILE}')

if __name__ == '__main__':
    print(f'PDF 目錄：{PDF_DIR}')
    print(f'輸出：{OUT_FILE}')
    print('=' * 40)
    main()