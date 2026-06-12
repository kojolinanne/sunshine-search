#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的事業投資明細。
PDF section: （十二）事業投資
格式：投資人、投資事業名稱、投資事業地址、投資金額、取得時間、原因
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR_OLD = Path.home() / 'Downloads' / '廉政專刊'
PDF_DIR_NEW = Path(__file__).parent.parent
OUT_FILE    = Path(__file__).parent / 'data' / 'investment_detail.json'

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

        if '（十二）事業投資' not in text:
            continue

        marker_idx = text.find('（十二）事業投資')
        rest = text[marker_idx + len('（十二）事業投資'):]
        next_sec = re.search(r'（十三）備', rest)
        end_idx = marker_idx + len('（十二）事業投資') + (next_sec.start() if next_sec else len(rest))
        section = text[marker_idx:end_idx]

        holder = current_person or 'unknown'
        lines = section.split('\n')

        # 跳過表頭
        data_started = False
        for ln in lines:
            ls = clean(ln)
            if not ls:
                continue
            # 跳過 section header 和表頭行
            if '（十二）' in ls or '事業投資' in ls or '投  資  人' in ln or '投 資 人' in ln:
                continue
            if '本欄空白' in ls:
                break
            if '投  資  事  業' in ln or '投 資 事 業' in ln:
                continue
            if re.match(r'^備+\s*', ls):
                break

            # 解析行：投資人 事業名稱 地址 金額 時間 原因
            # 或：事業名稱 地址 金額
            if '（十三）' in ls:
                break

            # 投資金額（數字，結尾）
            amount_m = re.search(r'([0-9,]+)\s*$', ls.strip())
            amount = amount_m.group(1) if amount_m else ''

            # 嘗試找出公司名稱（含有公司/有限公司/企業/股份等）
            company = ''
            for pat in [r'[^\s]{2,10}有限公司', r'[^\s]{2,10}股份', r'[^\s]{2,10}企業', r'[^\s]{2,10}公司']:
                cm = re.search(pat, ls)
                if cm:
                    company = cm.group(0)
                    break
            if not company:
                # 取第一個夠長的中文字串作為公司名
                names = re.findall(r'[\u4e00-\u9fff]{3,15}', ls)
                for n in names:
                    if n not in ['本欄空白', '備    註', '（十三）']:
                        company = n
                        break

            if company or amount:
                if holder not in results:
                    results[holder] = []
                results[holder].append({
                    'investor': holder,
                    'company_name': company,
                    'company_address': '',
                    'amount': amount,
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
    print(f'\n完成：{len(all_data)} 期，{total_all} 筆事業投資 → {OUT_FILE}')

if __name__ == '__main__':
    main()