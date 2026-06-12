#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的存款明細。
Section: （七）存款
格式：金融機構名、種類、幣別、所有人、外幣總額、新臺幣總額
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR_OLD = Path.home() / 'Downloads' / '廉政專刊'
PDF_DIR_NEW = Path(__file__).parent.parent
OUT_FILE    = Path(__file__).parent / 'data' / 'deposit_detail.json'

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
              '瑞典幣', '墨西哥披索', '印尼幣', '越南盾', '馬幣', '菲律賓披索')
ACCT_TYPES = ('活期儲蓄存款', '活期存款', '定期存款', '綜合存款', '支票存款',
              '外幣存款', '活期證券戶', '定期儲蓄存款')

def extract_from_pdf(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return {}
    pages = r.stdout.split('\x0c')

    current_person = None
    results = {}
    pending_bank_parts = []  # 累積銀行名片段
    in_section = False

    for pi, text in enumerate(pages):
        if not text.strip():
            continue

        # 更新當前申報人
        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2:
                current_person = name

        lines = text.split('\n')
        for li, line in enumerate(lines):
            ls = clean(line)

            # Section boundaries
            if '（七）存款' in ls and '（七）存款' in ls:
                in_section = True
                pending_bank_parts = []
                continue

            # End of section
            if in_section:
                if re.search(r'（八）|（九）|（十）|（六）|（十一）|（十二）|（十三）', ls) and '存款' not in ls:
                    in_section = False
                    pending_bank_parts = []
                    continue
                if ls.startswith('備註') and len(ls) < 10:
                    in_section = False
                    pending_bank_parts = []
                    continue

            if not in_section:
                continue

            # Skip blank / header / artifact lines
            if not ls or ls == '本欄空白':
                pending_bank_parts = []
                continue
            # Header rows (all spaced chars)
            if re.match(r'^[\s\u3000·\.]+$', ls):
                continue
            if '存 放 機 構' in ls or '總金額' in ls or '新臺幣總額' in ls:
                continue
            if re.match(r'^[（\u4e00-\u9fff]{1,4}$', ls):
                continue

            # Detect section marker embedded - start of new section
            if re.match(r'^[一二三四五六七八九十]+[）)]', ls):
                in_section = False
                pending_bank_parts = []
                continue

            # Strip for analysis
            stripped = ls.strip()

            # === 行首有中文字（可能是獨立數據行或銀行名片段） ===
            if stripped and re.match(r'[\u4e00-\u9fff]', stripped):
                first_char = stripped[0]
                # Check if it starts with a common bank/section start
                if stripped.startswith('（'):
                    in_section = False
                    pending_bank_parts = []
                    continue

                # Check if line has any data fields (amount or currency or account type)
                has_currency = any(c in stripped for c in CURRENCIES)
                has_type = any(t in stripped for t in ACCT_TYPES)
                has_amount = bool(re.search(r'[\d,]{4,}$', stripped))
                has_holder = bool(re.search(r'[\u4e00-\u9fff·]{2,6}\s+[\d,]', stripped))

                if has_currency or has_amount or (has_type and has_holder):
                    # This is a data line
                    # Combine pending bank with start of this line
                    bank_name = ' '.join(pending_bank_parts)
                    if bank_name:
                        # Find where bank name ends in this line
                        # The bank name is everything before the first clearly non-bank part
                        # Strategy: remove currency, type, holder, amounts
                        working = stripped
                        for c in CURRENCIES:
                            working = working.replace(c, ' ')
                        for t in ACCT_TYPES:
                            working = working.replace(t, ' ')
                        working = re.sub(r'[\d,]+', ' ', working)
                        working = re.sub(r'[\u4e00-\u9fff·]{2,6}', ' ', working)
                        working = re.sub(r'\s+', ' ', working).strip()
                        if working:
                            bank_name += ' ' + working
                        # Also try: take everything before the currency/type as bank
                        # Find earliest field position
                        first_field_pos = len(stripped)
                        for c in CURRENCIES:
                            pos = stripped.find(c)
                            if pos != -1 and pos < first_field_pos:
                                first_field_pos = pos
                        for t in ACCT_TYPES:
                            pos = stripped.find(t)
                            if pos != -1 and pos < first_field_pos:
                                first_field_pos = pos
                        bank_part = stripped[:first_field_pos].strip()
                        if bank_part:
                            bank_name = bank_part

                    bank_name = bank_name.strip()
                    if not bank_name:
                        bank_name = '不明'

                    # Now parse type, currency, holder, amount
                    acct_type = None
                    for t in ACCT_TYPES:
                        if t in stripped:
                            acct_type = t
                            break

                    currency = None
                    for c in CURRENCIES:
                        if c in stripped:
                            currency = c
                            break
                    if not currency:
                        currency = '新臺幣'

                    # Holder: find Chinese name 2-6 chars near end
                    holder = None
                    # Find all Chinese name candidates
                    for nc in re.findall(r'[\u4e00-\u9fff·]{2,6}', stripped):
                        if nc not in ('新臺幣', '本欄空白', '持有', '存款', '活期', '定期',
                                      '綜合', '支票', '儲蓄', '外幣', '別所', '總額',
                                      '幣別', '美元', '日圓', '歐元', '英鎊', '港幣',
                                      '人民幣', '澳幣', '加幣'):
                            holder = nc
                            break

                    if not holder:
                        holder = current_person or '不明'

                    # Amounts: find all comma-numbers
                    all_amounts = [parse_num(m) for m in re.findall(r'[\d,]+', stripped) if parse_num(m) is not None]
                    ntd_amount = None
                    foreign_amount = None
                    if len(all_amounts) >= 2:
                        # Assume last is NTD, second-to-last is foreign
                        ntd_amount = all_amounts[-1]
                        foreign_amount = all_amounts[-2]
                    elif all_amounts:
                        ntd_amount = all_amounts[-1]

                    pending_bank_parts = []

                    holder_key = holder
                    if holder_key not in results:
                        results[holder_key] = {'count': 0, 'items': []}
                    results[holder_key]['count'] += 1
                    results[holder_key]['items'].append({
                        'bank': bank_name,
                        'type': acct_type or '',
                        'currency': currency,
                        'holder': holder,
                        'foreign_amount': foreign_amount,
                        'ntd_amount': ntd_amount,
                    })
                else:
                    # This line has Chinese chars but no clear data fields
                    # It might be a bank name fragment
                    # If it's short (likely continuation) or doesn't look like a section marker
                    if len(stripped) < 50 and not re.match(r'^[一二三四五六七八九十零○●]+', stripped):
                        pending_bank_parts.append(stripped)
                    else:
                        # Might be something else, reset
                        pending_bank_parts = []
            else:
                # Line starts with whitespace - continuation of prev line
                stripped_inner = stripped
                if stripped_inner:
                    # Check if this is continuation of bank name (just a short Chinese piece)
                    # or if it has data fields
                    has_currency = any(c in stripped_inner for c in CURRENCIES)
                    has_type = any(t in stripped_inner for t in ACCT_TYPES)
                    has_amount = bool(re.search(r'[\d,]{4,}$', stripped_inner))
                    has_holder = bool(re.search(r'[\u4e00-\u9fff·]{2,6}\s+[\d,]', stripped_inner))

                    if has_currency or has_amount or (has_type and has_holder):
                        # This is a continuation of a data line - bank name ends at start
                        # Parse fields from this line
                        bank_name = ' '.join(pending_bank_parts)
                        if not bank_name:
                            bank_name = '不明'

                        acct_type = None
                        for t in ACCT_TYPES:
                            if t in stripped_inner:
                                acct_type = t
                                break

                        currency = None
                        for c in CURRENCIES:
                            if c in stripped_inner:
                                currency = c
                                break
                        if not currency:
                            currency = '新臺幣'

                        holder = None
                        for nc in re.findall(r'[\u4e00-\u9fff·]{2,6}', stripped_inner):
                            if nc not in ('新臺幣', '本欄空白', '持有', '存款', '活期', '定期',
                                          '綜合', '支票', '儲蓄', '外幣', '別所', '總額',
                                          '幣別', '美元', '日圓', '歐元', '英鎊', '港幣',
                                          '人民幣', '澳幣', '加幣'):
                                holder = nc
                                break
                        if not holder:
                            holder = current_person or '不明'

                        all_amounts = [parse_num(m) for m in re.findall(r'[\d,]+', stripped_inner) if parse_num(m) is not None]
                        ntd_amount = None
                        foreign_amount = None
                        if len(all_amounts) >= 2:
                            ntd_amount = all_amounts[-1]
                            foreign_amount = all_amounts[-2]
                        elif all_amounts:
                            ntd_amount = all_amounts[-1]

                        pending_bank_parts = []

                        holder_key = holder
                        if holder_key not in results:
                            results[holder_key] = {'count': 0, 'items': []}
                        results[holder_key]['count'] += 1
                        results[holder_key]['items'].append({
                            'bank': bank_name,
                            'type': acct_type or '',
                            'currency': currency,
                            'holder': holder,
                            'foreign_amount': foreign_amount,
                            'ntd_amount': ntd_amount,
                        })
                    else:
                        # Short fragment (like "行") - bank name continuation
                        if len(stripped_inner) < 30:
                            pending_bank_parts.append(stripped_inner)

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