#!/usr/bin/env python3
"""
萃取廉政專刊 PDF 的保險明細。
每筆保單：policy number 行（含有 ○○○+） + 後面 1-2 行（holder / type / date）
利用 layout 縮排量區分：大縮排 → holder 是第一個姓名；小縮排 → holder 是最後一個姓名。
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR_OLD = Path.home() / 'Downloads' / '廉政專刊'
PDF_DIR_NEW = Path(__file__).parent.parent
OUT_FILE   = Path(__file__).parent / 'data' / 'insurance_detail.json'

def find_pdf(n):
    for d in [PDF_DIR_NEW, PDF_DIR_OLD]:
        p = d / f'廉政專刊第{n}期.pdf'
        if p.exists():
            return p
    return None

def clean(s):
    if not s: return ''
    return re.sub(r'\s+', ' ', s).strip()

SKIP_WORDS = {
    '本欄空白', '終身', '定期', '儲蓄型', '投資型', '醫療', '壽險',
    '癌症', '長照', '實支', '年金', '退休金', '能照護', '照護', '失能',
    '變額', '增額', '還本', '年年', '美元', '外幣', '防癌', '手術',
    '住院', '傷害', '豁免', '養老', '平安', '久久', '樂樂', '滿滿',
    '新安', '金康', '金平安', '美利', '真有利', '珍有利', '健康',
    '守護', '珍愛', '愛扶', '長青', '豐', '扶', '康健',
    '永康', '永樂', '祥', '利', '美', '真',
    # 產品名片段（常見片段）
    '本保險', '外幣利率變', '旺外幣利率變', '順外幣利率變',
    '動型', '費二十', '型終身', '終身壽', '本保險乙', '本保險甲',
    '安康', '美利大', '富利旺', '新平安', '靈活理', '鈞安保', '富邦人壽',
    '南山人壽', '華郵政', '郵政簡易', '至尊', '金美滿', '康樂',
    '美享利', '金享利', '智富紅', '美利富', '美利多',
    '手術醫療', '年年常春', '福保本', '財變額', '利率變動',
    '增富年', '鑫美多', '鑫富雙', '幸福人', '新登峰',
    '吉祥如', '金玉富貴', '金美多多', '澳幣終',
    '限期繳費', '傳富新', '壽新富', '壽限',
    # 公司名（純公司行不應作為持有人）
    '股份有限公司',
}

def extract_holder(ln, skip_words):
    """
    根據行左側空白量（padding）判斷 holder 位置：
    - 大縮排（>=40空格）：holder 是第一個中文姓名
    - 小縮排（<20空格）：行開頭是公司名片段，holder 是最後一個中文姓名
    """
    ls = ln.lstrip()
    pad = len(ln) - len(ls)
    names = re.findall(r'[\u4e00-\u9fff·]{2,10}', ls)
    filtered = [n for n in names if not any(
        n.startswith(s) or n == s for s in skip_words)]
    if not filtered:
        return None
    if pad >= 40:
        return filtered[0]   # 大縮排：取第一個
    else:
        return filtered[-1]   # 小縮排：取倒數第一個

def extract_period(block_text):
    # 匹配 89年01月12日/終身 或 108年12月10日/153年12月09日
    # （日期各部分可能有空格）
    m = re.search(
        r'(\d+\s*年\s*\d+\s*月\s*\d+\s*日/[A-Za-z0-9年年月日\s]+)',
        block_text)
    if not m:
        return ''
    # 取到第一個換行或 "  公司" 之前
    raw = m.group(1)
    # 清理內部空格
    raw = re.sub(r'\s+', '', raw)
    # 截斷到第一個連續的結束關鍵字（如 "終身"、年份、空白）
    # 終身之後不應該有內容；15年/153年12月09日的數字部分是日期
    # 簡單：取到最後一個日期數字之後的第一個連續中文段結束
    return raw

def extract_from_pdf(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return {}
    pages = r.stdout.split('\x0c')

    results = {}   # {holder: {count, items, seen}}

    for pi, text in enumerate(pages):
        if not text.strip():
            continue

        # 更新當前申報人（fallback 用）
        current_person = None
        for m in re.finditer(r'申報人姓名\s+([^\n]+)', text):
            raw = m.group(1).strip()
            name = re.split(r'\s{2,}', raw)[0].strip()
            name = re.sub(r'[○●◎]', '', name).strip()
            if name and len(name) >= 2:
                current_person = name

        if '2.保險' not in text:
            continue

        # ── 取保險 section ──────────────────────────────────────
        marker_idx = text.find('2.保險')
        rest = text[marker_idx + len('2.保險'):]
        next_sec = re.search(r'（[一二三四五六七八九十\d]+[）.]|\d+\.|其他有價證券', rest)
        end_idx = marker_idx + len('2.保險') + (next_sec.start() if next_sec else len(rest))
        section = text[marker_idx:end_idx]
        lines = section.split('\n')

        # ── 收集所有 policy 行位置 ───────────────────────────────
        # 同時維護「最後看見的公司名」→ 處理副約行無前綴的狀況
        last_company = ''
        policy_positions = []   # [(line_index, policy_str, company)]
        for li, ln in enumerate(lines):
            ls = clean(ln)
            m = re.search(r'○{3,}', ls)
            if m:
                policy_str = m.group(0)
                before = ls[:m.start()].strip()
                if before:
                    company = before[-20:]
                    last_company = company
                else:
                    # 無公司前綴（副約行如 "○○○603"）→ 沿用上次公司名
                    company = last_company
                policy_positions.append((li, policy_str, company))

        # ── 每個 policy → 解析 holder / period ───────────────────
        for li, policy_str, company in policy_positions:
            next_li = li + 1
            if next_li >= len(lines):
                continue

            # 跳過連續 policy 行（副約行如 "○○○603"）
            next_ls = clean(lines[next_li])
            if re.search(r'○{3,}', next_ls):
                continue

            # ── 找 holder & period ─────────────────────────────────
            # 策略：
            #  多人名行 → 大縮排(pad>=40)取第1個；小縮排取第1個（產品被過濾後，持有人會在最前）
            #  單人名行 → 須 pad>=40 才取；否則跳過
            #  無符合行 → fallback current_person / 空 period
            holder = current_person or 'unknown'
            period = ''
            # 嘗試從 policy 行直接取（壓縮格式適用）
            policy_line = clean(lines[li])
            period_m = re.search(
                r'(\d+\s*年\s*\d+\s*月\s*\d+\s*日\s*/\s*[A-Za-z0-9年年月日\s]+)',
                policy_line)
            if period_m:
                period = re.sub(r'\s+', '', period_m.group(1))

            for delta in range(6):   # 看往後最多6行
                hl_idx = next_li + delta
                if hl_idx >= len(lines):
                    break
                hl = lines[hl_idx]
                hl_ls = hl.lstrip()
                hl_pad = len(hl) - len(hl_ls)
                if re.search(r'○{3,}', clean(hl)):
                    break   # 遇到下一個 policy 行就停
                names = re.findall(r'[\u4e00-\u9fff·]{2,4}', hl_ls)
                filtered = [n for n in names if n not in SKIP_WORDS
                             and not any(n.startswith(s) for s in SKIP_WORDS)
                             and not any(n in s for s in SKIP_WORDS)]
                if not filtered:
                    continue
                if len(filtered) >= 2:
                    # 多人名行：取第1個（過濾掉產品後，持有人會在前面）
                    holder = filtered[0]
                    current_person = holder  # 讓子 policy 能延用
                    break
                else:  # 單人名
                    # pad>=40 → 標準持有人行；pad=0 + 短名（≤4字）→ 壓縮格式持有人的残餘（過濾產品後只剩持有人）
                    if hl_pad >= 40 or (hl_pad == 0 and len(filtered[0]) <= 4):
                        holder = filtered[0]
                        current_person = holder
                        break
                    # pad<40 且非壓縮格式 → 產品片段或公司行，跳過

            # 若上面沒取到 period（間距格式），試著從 holder 行抓
            if not period:
                for delta in range(6):
                    hl_idx = next_li + delta
                    if hl_idx >= len(lines):
                        break
                    period_m = re.search(
                        r'(\d+\s*年\s*\d+\s*月\s*\d+\s*日\s*/\s*[A-Za-z0-9年年月日\s]+)',
                        lines[hl_idx])
                    if period_m:
                        period = re.sub(r'\s+', '', period_m.group(1))
                        break

            # 清理 company（去掉內部空格）
            company_clean = re.sub(r'\s+', '', company).strip()

            # ── 去重 & 寫入 ───────────────────────────────────────
            # key 加入 holder 避免不同人但同 company/policy 被錯誤合併
            key = (company_clean[:10] if company_clean else company[:10],
                   policy_str[:8], holder)
            if holder not in results:
                results[holder] = {'count': 0, 'items': [], 'seen': set()}
            if key in results[holder]['seen']:
                continue
            results[holder]['seen'].add(key)
            results[holder]['count'] += 1
            results[holder]['items'].append({
                'company': company_clean if company_clean else company,
                'policy':  policy_str,
                'holder':  holder,
                'period':  period,
            })

    for h in results:
        results[h].pop('seen', None)
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
    print(f'\n完成：{len(all_data)} 期，{total} 筆保險 → {OUT_FILE}')

if __name__ == '__main__':
    main()