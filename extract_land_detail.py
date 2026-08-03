#!/usr/bin/env python3
"""
land_detail 萃取 v13 - 核心修復：多行 groupping

問題：PDF 多欄佈局，一筆土地橫跨多行（位置/面積/持分/取得時間分屬不同列）。
      舊版把所有行都當成獨立記錄，導致 location/area/price 全錯。

修復：
1. 以「地段路街市區」關鍵字判斷新記錄的開頭
2. 後續不以此類關鍵字開頭的行，視為上一筆記錄的延續（拼接 price/date/rights）
3. 同一筆土地的面積、持分、金額等只允許更新一次（避免覆蓋）
"""
import subprocess, re, json, time
from pathlib import Path

PDF_DIR = Path.home() / 'Downloads' / '廉政專刊'
OUT_FILE = Path(__file__).parent / 'data' / 'land_detail.json'
IN_BACKUP = Path(__file__).parent / 'data' / 'land_detail.json'
ISSUES = list(range(292, 320))

def find_pdf(n):
    p = PDF_DIR / f'廉政專刊第{n}期.pdf'
    if p.exists(): return p
    alt = Path(__file__).parent / 'data' / f'issue_{n}.pdf'
    if alt.exists(): return alt
    return None

def clean(s):
    if not s: return ''
    return re.sub(r'\s+', ' ', s).strip()

def is_land_addr(line):
    """判斷這一行是否為土地位置開頭（新記錄的觸發行）
    
    策略：
    - 「段」「路街」是唯一可靠的開頭標記
    - 「縣市區鄉鎮町丁目」開頭也可能，但必須排除表格 header
    - 排除碎片：純日期、純數字、太短
    """
    ls = line.strip()
    if len(ls) < 8:
        return False
    snippet = line[:50]
    
    # 排除表格 header 特徵
    header_bad = ['面積','公尺','權利','所有權','取得價','登記(','變動情形','坐  落',
                  '公 尺 )','( 持 分 )','取 得 價 額']
    if any(bad in ls[:30] for bad in header_bad):
        return False
    
    # 排除數字或符號開頭後緊接段（如 「1★基隆市...」）
    if re.match(r'^[\d★●○◎①②③④⑤⑥⑦⑧⑨⑩]+', ls[:10]):
        # 但若前面有足夠地名（如 「1.臺北市...」）可以接受
        after_prefix = re.sub(r'^[\d★●○◎①②③④⑤⑥⑦⑧⑨⑩\.\s]+', '', ls[:20])
        if len(after_prefix) < 6 or not re.search(r'[縣市區鄉鎮町丁目路街]', after_prefix[:6]):
            return False
    # 段/路街 → 可靠標記
    if '段' in snippet or '路街' in snippet:
        # 「段」字後緊接括號且前面沒有地名前綴 → 續行，不是新記錄
        # 「臺北市中正區五分鍾段一小段(」→ 前面有地名 → 是新記錄
        # 「段(未能交付信託原因」→ 前面無地名 → 是續行
        m_seg = re.search(r'段\s*[（(]', ls[:50])
        if m_seg:
            before = ls[:m_seg.start()]
            # 只有前面沒有地名時才是續行
            if not re.search(r'[縣市區鄉鎮町丁目路街]', before[:20]):
                return False
        return True
    
    # 縣市區鄉鎮町丁目開頭 → 需要像地名
    if any(k in snippet for k in ['縣','市','區','鄉','鎮','町','丁目']):
        # 排除碎片模式
        if re.match(r'^[\d月日/\-\s]+$', ls[:10]):
            return False
        # 排除非地名說明文字
        non_place = ['自用','附註','房地','本欄','監察院','特定區域','區域農牧',
                     '未能交付','能交付','坐落基地','取得','登記','變動',
                     '委員會','永久使用','社區','提供受益','受益人','信託原因',
                     '委託人','受託人','無法登記','所有權人','無償管理',
                     '停止信託','暫時保留','東關開發','綠野山坡']
        if any(w in ls[:20] for w in non_place):
            return False
        # 需要 2+ 中文字元作為地名前綴
        if not re.search(r'^[\u4e00-\u9fff]{2,}[縣市區鄉鎮町丁目]', ls):
            return False
        return True
    return False

def extract_date(line):
    """從一行中提取日期"""
    m = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', line)
    if m: return m.group(1) + '年' + m.group(2) + '月' + m.group(3) + '日'
    m2 = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月', line)
    if m2: return m2.group(1) + '年' + m2.group(2) + '月'
    return ''

def extract_price(line):
    """從一行提取價格數字（至少4位）。
    
    優先在行尾找（通常價格在行尾）。至少4位數字 + 含千分位逗號更可靠。
    """
    line = line.strip()
    if not line:
        return ''
    # 先從行尾找
    m = re.search(r'([\d,]+)\s*$', line)
    if m:
        v = m.group(1).replace(',', '')
        if len(v) >= 4:
            return m.group(1)
    # 行尾沒找到，從中段找（至少7位數字）
    m2 = re.search(r'(?:^|\s)([\d,]{7,})(?:\s|$)', line)
    if m2:
        return m2.group(1)
    return ''

def extract_rights(line):
    """從一行萃取持分（分之N / 全部）"""
    m = re.search(r'(\d+)\s*分之\s*(\d+)', line)
    if m: return m.group(1) + '分之' + m.group(2)
    if '全部' in line: return '全部'
    return ''

def extract_reason(line):
    """萃取取得原因"""
    for kw in ['買賣','贈與','繼承','設定','自拍','建築','交換','補償','塗銷','拍賣']:
        if kw in line: return kw
    return ''

def extract_area(line):
    """萃取面積。
    
    策略：找「段」字之後的第二個數字（第一個可能是小段號碼）。
    也從行首找高精度數字（含小數）。
    面積通常在續行（像「84.17」這樣的格式），含小數點或 >= 20。
    """
    line = line.strip()
    if not line:
        return ''
    
    # 優先從行首找小數格式（續行的面積通常是「數字.數字」開頭）
    m = re.match(r'^([\d,]+\.\d+)', line)
    if m:
        return m.group(1)
    
    # 從「段」字之後找（找第二個數字區塊）
    # 但先檢查：全行中是否有 rights 分子特徵（分之/空格式分）
    # 如果有，主行中的數字很可能是分子，放棄從主行萃取 area
    # 空格式如「100000 分 109 年 02」中的「分」
    if re.search(r'分之|\d{3,}\s+分', line):
        # 有持分模式，主行數字可能是分子，不從主行取 area
        pass
    else:
        pos = line.find('段')
        if pos >= 0 and pos < 50:
            search = line[pos+1:pos+50]
            nums = re.findall(r'([\d,]+(?:\.\d+)?)', search)
            if len(nums) >= 2:
                return nums[1]
            elif len(nums) == 1:
                v = nums[0].replace(',', '')
                if '.' in nums[0] or len(v) >= 5:
                    return nums[0]
    
    # 行中找「大數字 + 小數」的面積
    m2 = re.search(r'([\d,]{2,}\.\d+)', line)
    if m2:
        return m2.group(1)
    
    # 續行面積：行中第一個逗號分隔的數字（>=4位數字部分）
    # 排除顯然是持分的 (如「3 分之 1」前面的 3)
    # 也排除 rights 分子附近（如「度育賢段 100000 分之」中的 100000）
    m3 = re.search(r'\b(\d{1,3}(?:,\d{3})+)\b', line)
    if m3:
        # 檢查該數字是否在「分之」前面（分子）或後面（分母）
        after_num = line[m3.end():m3.end()+20]
        before_num = line[max(0,m3.start()-15):m3.start()]
        if '分之' in after_num[:10] or re.search(r'分之\s*$', before_num):
            pass  # 這是分子/分母，排除
        else:
            v = m3.group(1).replace(',', '')
            if len(v) >= 4:
                return m3.group(1)
    
    return ''

def parse_land_section(section_text, person_name):
    """
    解析土地區塊。多行 groupping：
    - 遇到地段路市區關鍵字開頭 → 新記錄
    - 其他行視為延續，補充 price / date / rights / reason
    """
    results = []
    # 移除「土地變動情形」之後的內容（空格版本）
    chg = section_text.rfind('土地變動情形')
    if chg == -1:
        chg = section_text.rfind('地變動情形')
    if chg == -1:
        # 模糊匹配：大空格版本的「土 地 變 動 情 形」
        m = re.search(r'土\s{2,}地\s{2,}變\s{2,}動\s{2,}情\s{2,}形', section_text)
        if m:
            chg = m.start()
    if chg != -1:
        section_text = section_text[:chg]

    raw_lines = section_text.split('\n')
    # 過濾有意義的資料行
    data_lines = []
    for ln in raw_lines:
        ls = clean(ln)
        if not ls: continue
        # 排除 header/footer 行
        skip_headers = ['土 地 坐 落','土 地 變 動','土 地 坐 落 受 託',
                        '變動時間','變動原因','變動時之價額']
        if any(ls.startswith(h) for h in skip_headers):
            continue
        # 排除明確 header（不含重要數據）
        # 複合 header：多個 header 關鍵字同時出現 → 必定是表格標頭
        header_kw_parts = ['公 尺', '( 持 分 )', '得 ) 時', '得)原因', '取 得 價']
        header_hits = sum(1 for k in header_kw_parts if k in ls)
        if header_hits >= 2:
            continue
        if '取 得 價 額' in ls and len(ls) < 30:
            continue
        if '所 有 權 人' in ls and not re.search(r'[段路街市區縣鄉鎮]', ls):
            continue
        if '面積(平方' in ls and ('權利範圍' in ls or '所有權' in ls):
            continue
        # 排除太短碎片
        if len(ls) < 5:
            continue
        # (或（開頭：如果有地段關鍵字或持分數據，保留
        if re.match(r'^[（(]', ls):
            if not re.search(r'[段路街市區縣鄉鎮町丁]|分之', ls):
                continue
        if '本欄空白' in ls:
            continue
        # 排除純日期/空格碎片
        if re.match(r'^[\d月日/\-\s]+$', ls):
            continue
        data_lines.append(ln)

    records = []  # list of dict
    cur = None

    for ln in data_lines:
        ls = clean(ln)
        
        # 判斷是否為新記錄開頭
        is_new = is_land_addr(ln)
        
        if is_new:
            # 新記錄開始
            if cur and cur.get('location'):
                records.append(cur)
            cur = {
                'location': '',
                'area': '',
                'rights': '',
                'holder': person_name,
                'acquisition_time': '',
                'acquisition_reason': '',
                'price': '',
                'over5': False,
                'type': '土地'
            }
            # 檢查是否 over5（只在主行有地段且無價格時才標記）
            if '(超過五年)' in ln or '(超過5年)' in ln or '超過五年' in ln:
                cur['over5'] = True
            # 位置
            for kw in ['段','路街']:
                pos = ln.rfind(kw)
                if pos >= 0 and pos < 55:
                    cur['location'] = clean(ln[:pos+len(kw)])
                    break
            if not cur['location']:
                for kw in ['市','區','縣','鄉','鎮','町','丁目']:
                    pos = ln.rfind(kw)
                    if pos >= 0 and pos < 55:
                        cur['location'] = clean(ln[:pos+len(kw)])
                        break
            cur['area'] = extract_area(ln)
            cur['rights'] = extract_rights(ln)
            cur['price'] = extract_price(ln)
            cur['acquisition_reason'] = extract_reason(ln)
            cur['acquisition_time'] = extract_date(ln)
        else:
            # 延續行：只補充欄位
            if cur is None:
                continue
            # 續行 over5 檢查：只在沒有價格時
            if not cur['price'] and ('(超過五年)' in ln or '(超過5年)' in ln or '超過五年' in ln):
                cur['over5'] = True
            if not cur['price']:
                cur['price'] = extract_price(ln)
            if not cur['acquisition_time']:
                cur['acquisition_time'] = extract_date(ln)
            if not cur['rights']:
                cur['rights'] = extract_rights(ln)
            if not cur['acquisition_reason']:
                cur['acquisition_reason'] = extract_reason(ln)
            # 續行 area 可覆蓋主行不合理 area（大整數被小數格式取代）
            cont_area = extract_area(ln)
            if cont_area:
                if not cur['area']:
                    cur['area'] = cont_area
                else:
                    # 主行 area 純整數且 >= 1000，續行有小數點或逗號 → 覆蓋
                    cur_clean = cur['area'].replace(',', '')
                    cont_clean = cont_area.replace(',', '')
                    if (cur_clean.isdigit() and len(cur_clean) >= 4 and
                        ('.' in cont_area or ',' in cont_area) and
                        cont_clean.replace('.', '').isdigit()):
                        cur['area'] = cont_area

    # 最後一筆記錄
    if cur and cur.get('location'):
        records.append(cur)

    # 過濾有意義的記錄
    # 同時：如果有價格就取消 over5（價格與超過五年矛盾）
    filtered = []
    for r in records:
        loc = r.get('location', '')
        if not loc or len(loc) < 5:
            continue
        # 排除表格 header/footer 汙染
        if any(bad in loc for bad in ['面  積','面積(','權利範圍','所有權','取得價',
                                       '土地坐','土地變動','變動情形','變動時',
                                       '公尺)','( 持 分 )','得 ) 時','得) 時',
                                       '得)原因','登記(取','受 託 人','申報人',
                                       '監察院公報','廉政專刊']):
            continue
        # 排除純日期/碎片
        if re.match(r'^[\d月日/\-\s\.]+$', loc):
            continue
        if re.match(r'^\d{1,2}\s*月\s*\d{1,2}\s*日', loc) and len(loc) < 15:
            continue
        # 排除「附註」或明顯是說明文字
        if '自用房屋' in loc or '房地總價' in loc:
            continue
        # 有價格就取消 over5（價格與「超過五年」依法空白矛盾）
        if r.get('price') and len(r['price'].replace(',','')) >= 4 and r.get('over5'):
            r['over5'] = False
        filtered.append(r)
    return filtered


def extract_land_from_block(block_text, person_name):
    """從一個人的 block 中萃取土地。
    
    block_text 是申報人到下一個申報人之間的全部內容。
    我們直接從（二）不動產 / 1.土地 開始解析到 2.建物 之前，
    不再做內部分段（避免 pdftotext 多欄佈局導致過早截止）。
    """
    # 找（二）不動產 之後到 2.建物 之前的範圍（整個不動產 section）
    marker_map = {
        'land': ('1.土地', '2.建物'),
    }
    
    land_start = block_text.find('1.土地')
    bldg_start = block_text.find('2.建物')
    
    if land_start == -1:
        return []
    
    # 以 2.建物 為截止點（如果有的話）
    if bldg_start != -1 and bldg_start > land_start:
        land_section = block_text[land_start:bldg_start]
    else:
        # 找不到 2.建物，就處理到 block 結尾
        land_section = block_text[land_start:]
    
    entries = parse_land_section(land_section, person_name)
    return entries


def extract_from_pdf(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', str(pdf_path), '-'],
                      capture_output=True, text=True, timeout=300)
    if r.returncode != 0: return {}
    full_text = r.stdout

    # 找出每個人的 block（以「申報人姓名」為界）
    person_markers = []
    for m in re.finditer(r'申報人姓名\s+([^\n]+)', full_text):
        raw = m.group(1).strip()
        name = re.split(r'\s{2,}', raw)[0].strip()
        name = re.sub(r'[○●◎]', '', name).strip()
        if name and len(name) >= 2:
            person_markers.append((m.start(), name))
    person_markers.sort()

    results = {}
    # 合併同一人的所有 block，按 (location, area) 去重，保留所有記錄
    person_entries = {}  # name -> list of unique (location, area) -> entries
    for idx, (p_start, p_name) in enumerate(person_markers):
        p_end = person_markers[idx + 1][0] if idx + 1 < len(person_markers) else len(full_text)
        block_text = full_text[p_start:p_end]
        entries = extract_land_from_block(block_text, p_name)
        if not entries:
            continue
        if p_name not in person_entries:
            person_entries[p_name] = {}
        for e in entries:
            key = (e.get('location', ''), e.get('area', ''))
            # 保留 price 最多的那一筆記錄（覆蓋同一 key）
            if key not in person_entries[p_name] or (
                e.get('price') and not person_entries[p_name][key].get('price')
            ):
                person_entries[p_name][key] = e

    for name, entry_dict in person_entries.items():
        results[name] = list(entry_dict.values())

    return results


def main():
    orig = {}

    all_data = {str(n): {} for n in ISSUES}
    for k, v in orig.items():
        if k in all_data: all_data[k] = v

    for issue_num in ISSUES:
        issue_key = str(issue_num)
        if all_data[issue_key]:
            print(f'第 {issue_num} 期：已有，跳过')
            continue
        pdf_path = find_pdf(issue_num)
        if not pdf_path:
            print(f'第 {issue_num} 期：PDF 不存在')
            continue
        t0 = time.time()
        print(f'处理第 {issue_num} 期...', flush=True)
        result = extract_from_pdf(pdf_path)
        elapsed = time.time() - t0
        if result:
            # Convert {name: [entries]} → {name: {land: [entries]}} for land_detail.json compatibility
            wrapped = {name: {'land': entries} for name, entries in result.items()}
            all_data[issue_key] = wrapped
            total_land = sum(len(v['land']) for v in wrapped.values())
            print(f'  ✓ {len(result)} 人，土地 {total_land} 笔（{elapsed:.1f}s）')
        else:
            print(f'  - 无（{elapsed:.1f}s）')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    total = sum(len(v) for d in all_data.values() for v in d.values())
    print(f'\n完成：{len(all_data)} 期，土地 {total} 笔 → {OUT_FILE}')


if __name__ == '__main__':
    main()