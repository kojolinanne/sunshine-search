#!/usr/bin/env python3
"""
清理 land_detail.json - 移除 header/date fragment，並嘗試合併被分欄切割的 entries。

PDF 分欄佈局問題：
  土地「坐落」和「面積/持分/所有人/取得日期」分屬不同列，
  pdftotext -layout 萃取時，同一筆土地被切成 3-5 個獨立的爛 entry。

策略：
  1. 移除 header fragment（location 太短或只有「面/積/權/所/取」等）
  2. 移除 date fragment（純日期如「112年01月09日」，無 location 關鍵字）
  3. 對於「地址 only」entry，檢查前後相鄰 entry 是否可以合併
  4. 合併時：location 取最長者，area/rights/price/acquisition 從鄰居補全
"""
import json, re
from pathlib import Path

IN_FILE  = Path(__file__).parent / 'data' / 'land_detail.json'
OUT_FILE = Path(__file__).parent / 'data' / 'land_detail.json'

def is_header_fragment(loc):
    """location 太短或只是表頭殘片"""
    if len(loc) < 4: return True
    # 表頭關鍵字
    header_keywords = ['面  積', '面  積極', '權利範圍', '權利', '所有權人',
                       '取 得', '取得時', '取得原', '登記', '取得價', '價  額',
                       '所 有', '所  有', '公  尺', '面  積(', '土地坐']
    for kw in header_keywords:
        if kw in loc:
            return True
    # 純符號/單字
    if re.match(r'^[\W_]+$', loc):
        return True
    return False

def is_date_fragment(loc):
    """純日期 fragment，沒有地址關鍵字"""
    # 確認是日期格式
    if not re.match(r'^\s*\d+\s*年', loc) and not re.match(r'^\s*月', loc):
        return False
    # 但如果同時有地址關鍵字，則是有效 entry
    addr_kw = ['段', '路', '街', '市', '區', '里', '巷', '弄', '町', '丁目', '縣', '鄉', '鎮', '市']
    if any(kw in loc for kw in addr_kw):
        return False
    return True

def has_meaningful_data(item):
    """entry 有實質資料（area / rights / price / acquisition_time）"""
    return bool(item.get('area') or item.get('rights') or 
                item.get('price') or item.get('acquisition_time'))

def addr_keyword_count(loc):
    """計算 location 中有多少地址關鍵字"""
    kw = ['段', '路', '街', '市', '區', '里', '巷', '弄', '町', '丁目', '縣', '鄉', '鎮', '樓']
    return sum(1 for k in kw if k in loc)

def try_merge(prev_item, curr_item):
    """
    嘗試合併兩個連續 entry。
    典型 pattern: [location fragment] + [area/rights fragment]
    合併規則：
      - 取 location 最長者
      - area/rights/price/acquisition_time: 取有值者（優先取有值的）
    Returns merged item or None if can't merge.
    """
    loc_prev = prev_item.get('location', '')
    loc_curr = curr_item.get('location', '')

    # 兩個都有實質 location → 不應合併（各自獨立 entry）
    if addr_keyword_count(loc_prev) >= 2 and addr_keyword_count(loc_curr) >= 2:
        return None

    # 其中一個 location 很短（< 10字）且另一個有實質資料 → 合併
    merged = dict(curr_item)  # 預設用 curr 為主體

    # 選更長的 location
    if len(loc_prev) > len(loc_curr):
        merged['location'] = loc_prev

    # 取有值的欄位
    for field in ['area', 'rights', 'price', 'acquisition_time', 'acquisition_reason']:
        if not merged.get(field) and prev_item.get(field):
            merged[field] = prev_item[field]

    return merged

def clean_person_land(land_items):
    """清理單一人的 land 列表"""
    if not land_items:
        return []

    # Step 1: 標記每個 entry 的品質分數
    scored = []
    for item in land_items:
        loc = item.get('location', '')
        score = 0
        reasons = []

        if is_header_fragment(loc):
            score = -100
            reasons.append('header')
        elif is_date_fragment(loc):
            score = -50
            reasons.append('date_frag')
        elif addr_keyword_count(loc) >= 2:
            score = 10
            if has_meaningful_data(item):
                score += 5
            reasons.append('addr_ok')
        elif addr_keyword_count(loc) == 1 and has_meaningful_data(item):
            score = 5
            reasons.append('addr_partial+data')
        elif addr_keyword_count(loc) >= 1:
            score = 2
            reasons.append('addr_only')
        else:
            score = -20
            reasons.append('unknown')

        scored.append((item, score, reasons[0]))

    # Step 2: 嘗試合併相鄰可合併的 entries
    merged = []
    i = 0
    while i < len(scored):
        item, score, reason = scored[i]

        if score < 0:
            # 壞 entry → 跳過（但如果是 addr_only 且周圍有好 entry，嘗試合併）
            merged.append(item)
            i += 1
            continue

        # 嘗試與下一個 entry 合併
        if i + 1 < len(scored):
            next_item, next_score, next_reason = scored[i + 1]
            merged_item = try_merge(item, next_item)
            if merged_item and next_score < 0:
                # 合併成功，消耗兩個 entry
                merged.append(merged_item)
                i += 2
                continue

        merged.append(item)
        i += 1

    # Step 3: 最終過濾
    # 移除：header fragment、純日期 fragment（沒有有效欄位）
    final = []
    for item in merged:
        loc = item.get('location', '')
        if is_header_fragment(loc):
            continue
        if is_date_fragment(loc) and not has_meaningful_data(item):
            continue
        # 如果 location 太短但有實質資料，標記為可疑但保留
        if addr_keyword_count(loc) == 0 and not has_meaningful_data(item):
            continue
        final.append(item)

    return final

def clean_all():
    print('開始清理 land_detail.json...')
    with open(IN_FILE, encoding='utf-8') as f:
        data = json.load(f)

    total_before = 0
    total_after = 0
    issues_cleaned = 0

    for issue_key, persons in data.items():
        has_changes = False
        for person, data_by_person in persons.items():
            land = data_by_person.get('land', [])
            before_len = len(land)
            total_before += before_len

            cleaned = clean_person_land(land)
            after_len = len(cleaned)
            total_after += after_len

            if after_len != before_len:
                data_by_person['land'] = cleaned
                has_changes = True
                issues_cleaned += 1

    print(f'清理完成:')
    print(f'  處理 {len(data)} 期')
    print(f'  總 entry: {total_before} → {total_after} (移除 {total_before - total_after})')
    print(f'  涉及 {issues_cleaned} 個人員')

    # 備份並寫入
    backup = IN_FILE.with_suffix('.json.bak')
    with open(backup, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'  備份: {backup}')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'  寫入: {OUT_FILE}')

if __name__ == '__main__':
    clean_all()