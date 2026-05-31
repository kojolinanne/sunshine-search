#!/usr/bin/env python3
"""將分期全文 JSON 轉成前端統計用的結構化申報資料。"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / 'data'

DECLARATION_MARKER = '公\n職\n人\n員\n財\n產\n申\n報\n表'
DECLARATION_MARKER_ALT = '公\n\n職\n\n人\n\n員\n\n財\n\n產\n\n申\n\n報\n\n表'
TRUST_MARKER = '公\n職\n人\n員\n信\n託\n財\n產\n申\n報\n表'
CHANGE_MARKER = '公\n職\n人\n員\n變\n動\n財\n產\n申\n報\n表'
MARKERS = [
    ('declaration', DECLARATION_MARKER),
    ('declaration', DECLARATION_MARKER_ALT),
    ('trust', TRUST_MARKER),
    ('change', CHANGE_MARKER),
]

MAIN_ASSET_LABELS = {
    'land': '土地',
    'building': '建物',
    'ship': '船舶',
    'vehicle': '汽車',
    'aircraft': '航空器',
    'cash': '現金',
    'deposit': '存款',
    'securities': '有價證券',
    'valuable': '珠寶、古董、字畫等',
    'insurance': '保險',
    'virtual_asset': '虛擬資產',
    'claim': '債權',
    'business': '事業投資',
}

MONEY_ASSET_LABELS = {
    'cash': '現金',
    'deposit': '存款',
    'securities': '有價證券',
    'valuable': '珠寶、古董、字畫等',
    'virtual_asset': '虛擬資產',
    'claim': '債權',
    'business': '事業投資',
}

SECURITY_LABELS = {
    'stock': '股票',
    'bond': '債券',
    'fund': '基金受益憑證',
    'other_security': '其他有價證券',
}

POSITION_KEYWORDS = [
    ('立法委員', '立法委員'),
    ('議長', '地方民代'),
    ('副議長', '地方民代'),
    ('議員', '地方民代'),
    ('代表', '地方民代'),
    ('市長', '地方首長'),
    ('縣長', '地方首長'),
    ('鄉長', '地方首長'),
    ('鎮長', '地方首長'),
    ('院長', '中央首長'),
    ('部長', '中央行政主管'),
    ('次長', '中央行政主管'),
    ('秘書長', '中央行政主管'),
    ('總裁', '中央行政主管'),
    ('審計長', '中央行政主管'),
    ('主任委員', '中央行政主管'),
    ('副主任委員', '中央行政主管'),
    ('副委員長', '中央行政主管'),
    ('監察委員', '監察司法職務'),
    ('大法官', '監察司法職務'),
    ('法官', '監察司法職務'),
    ('局長', '行政主管'),
    ('處長', '行政主管'),
    ('副局長', '行政主管'),
    ('廠長', '行政主管'),
    ('董事', '法人董監事'),
]

TITLE_KEYWORDS = [
    '立法委員', '議長', '副議長', '議員', '代表', '市長', '縣長', '鄉長', '鎮長',
    '院長', '副院長', '部長', '次長', '秘書長', '總裁', '副總裁', '審計長',
    '主任委員', '副主任委員', '副委員長', '局長', '副局長', '處長', '廠長', '董事長',
    '董事', '監事', '監察委員', '大法官', '法官', '委員',
]

LABEL_WORDS = {
    '申報人姓名', '服務機關', '服 務 機 關', '職稱', '職 稱', '申', '報', '日',
    '配偶及', '稱', '未成', '申報類別', '年', '謂', '子女', '姓', '名',
    '公', '職', '人', '員', '財', '產', '表',
}

SECTION_RANGES = {
    'land': ('1.土地', ('2.建物',)),
    'building': ('2.建物', ('（三）船舶',)),
    'ship': ('（三）船舶', ('（四）汽車',)),
    'vehicle': ('（四）汽車', ('（五）航空器',)),
    'aircraft': ('（五）航空器', ('（六）現金',)),
    'cash': ('（六）現金', ('（七）存款',)),
    'deposit': ('（七）存款', ('（八）有價證券',)),
    'securities': ('（八）有價證券', ('（九）珠寶',)),
    'valuable': ('1.珠寶', ('2.保險',)),
    'insurance': ('2.保險', ('3.虛擬資產', '（十）債權')),
    'virtual_asset': ('3.虛擬資產', ('（十）債權',)),
    'claim': ('（十）債權', ('（十一）債務',)),
    'debt': ('（十一）債務', ('（十二）事業投資',)),
    'business': ('（十二）事業投資', ('（十三）備',)),
}

SECURITY_RANGES = {
    'stock': ('1.股票', ('2.債券',)),
    'bond': ('2.債券', ('3.基金受益憑證',)),
    'fund': ('3.基金受益憑證', ('4.其他有價證券',)),
    'other_security': ('4.其他有價證券', ('（九）珠寶',)),
}

def compact(value: str) -> str:
    return re.sub(r'\s+', '', value)

def clean_line(value: str) -> str:
    return re.sub(r'\s+', ' ', value).strip()

def remove_number_prefix(value: str) -> str:
    return re.sub(r'^\d+[.．、]\s*', '', clean_line(value)).strip()

def split_documents(text: str):
    markers = []
    for kind, marker in MARKERS:
        for match in re.finditer(re.escape(marker), text):
            markers.append((match.start(), kind, marker))

    markers.sort(key=lambda item: item[0])
    for index, (start, kind, marker) in enumerate(markers):
        end = markers[index + 1][0] if index + 1 < len(markers) else len(text)
        yield kind, text[start:end]

def section_between(text: str, start_pattern: str, end_patterns: tuple[str, ...]) -> str:
    start = text.find(start_pattern)
    if start == -1:
        return ''

    end_candidates = [text.find(pattern, start + len(start_pattern)) for pattern in end_patterns]
    end_candidates = [pos for pos in end_candidates if pos != -1]
    end = min(end_candidates) if end_candidates else len(text)
    return text[start:end]

def parse_amount(text: str) -> int | None:
    pattern = re.compile(r'總(?:金額|價額)[:：]\s*新臺幣(?P<body>[^元]{0,120})元')
    for match in pattern.finditer(text):
        body = match.group('body')
        if any(token in body for token in ['（總', '(總', '本欄空白', '名稱', '名\n稱', '所\n有']):
            continue
        numbers = re.findall(r'\d[\d,]*(?:\.\d+)?', body)
        if len(numbers) != 1:
            continue
        return int(float(numbers[0].replace(',', '')))
    return None

def is_blank_section(text: str) -> bool:
    flat = compact(text)
    if not flat:
        return True
    if '本欄空白' in flat and parse_amount(text) is None:
        return True
    if '本欄空白' not in flat:
        return False

    has_date = re.search(r'\d{2,3}年\d{1,2}月\d{1,2}日', flat)
    has_place = re.search(r'(臺|台)?[\u4e00-\u9fff]{1,4}[縣市][\u4e00-\u9fff]{0,8}[區鄉鎮市段]', flat)
    has_money = re.search(r'\d{1,3}(?:,\d{3})+', text)
    has_latin = re.search(r'[A-Za-z]{2,}', text)
    return not any([has_date, has_place, has_money, has_latin])

def parse_presence(text: str, key: str) -> bool:
    section = section_between(text, *SECTION_RANGES[key])
    if not section:
        return False
    if key in {'land', 'building'}:
        return bool(re.search(r'(臺|台)?[\u4e00-\u9fff]{1,4}[縣市][\u4e00-\u9fff]{0,8}[區鄉鎮市段]', section))
    return not is_blank_section(section)

def parse_header(doc: str):
    lines = [clean_line(line) for line in doc.splitlines()]
    lines = [line for line in lines if line]

    try:
        asset_start = next(i for i, line in enumerate(lines) if line.startswith('（二）不動產'))
    except StopIteration:
        asset_start = min(len(lines), 80)

    header = lines[:asset_start]
    name_index = next((i for i, line in enumerate(header) if '申報人姓名' in line), -1)

    agency = ''
    if name_index > 0:
        agency_lines = [remove_number_prefix(line) for line in header[:name_index]]
        agency_lines = [line for line in agency_lines if len(line) > 1 and line not in LABEL_WORDS]
        agency_candidates = [line for line in agency_lines if not is_title_line(line)]
        agency = agency_candidates[-1] if agency_candidates else ''

    name = extract_name(header, name_index)
    title = extract_title(header, name_index)
    declaration_type = extract_declaration_type(header)
    declaration_date = extract_date(header)

    return {
        'name': name,
        'agency': agency or '未解析',
        'title': title or '未解析',
        'position_group': classify_position(title),
        'declaration_type': declaration_type or '未解析',
        'declaration_date': declaration_date,
    }

def extract_name(header: list[str], name_index: int) -> str:
    if name_index == -1:
        return '未解析'

    same_line = header[name_index].split('申報人姓名', 1)[-1].strip()
    same_line = re.split(r'服\s*務\s*機\s*關|職\s*稱', same_line)[0].strip()
    if same_line and is_name_candidate(same_line):
        return normalize_name(same_line)

    for line in header[name_index + 1: name_index + 6]:
        if '服 務 機 關' in line or '服務機關' in line:
            break
        if is_name_candidate(line):
            return normalize_name(line)

    service_index = next((i for i in range(name_index, min(len(header), name_index + 8))
                          if '服 務 機 關' in header[i] or '服務機關' in header[i]), -1)
    if service_index != -1:
        for line in header[service_index + 1: service_index + 5]:
            if is_name_candidate(line):
                return normalize_name(line)

    for line in header[name_index + 1: name_index + 12]:
        if is_name_candidate(line):
            return normalize_name(line)

    return '未解析'

def is_name_candidate(value: str) -> bool:
    value = normalize_name(remove_number_prefix(value))
    if not value or value in LABEL_WORDS or '○' in value:
        return False
    if any(word in value for word in ['申報', '服務', '職稱', '配偶', '未成年', '財團法人', '委員會', '政府', '法院']):
        return False
    if is_title_candidate(value):
        return False
    return bool(re.fullmatch(r'[\u4e00-\u9fffA-Za-z．‧·]{2,8}', value))

def normalize_name(value: str) -> str:
    return re.sub(r'\s+', '', remove_number_prefix(value))

def extract_title(header: list[str], name_index: int) -> str:
    pre_lines = header[max(0, name_index - 3): name_index] if name_index != -1 else []
    post_lines = header[name_index + 1 if name_index != -1 else 0: min(len(header), 28)]
    search_lines = pre_lines + post_lines
    for line in search_lines:
        candidate = remove_number_prefix(line)
        if is_title_candidate(candidate):
            return candidate
    return ''

def is_title_candidate(value: str) -> bool:
    if '委員會' in value:
        return False
    return any(keyword in value for keyword in TITLE_KEYWORDS)

def is_title_line(value: str) -> bool:
    return is_title_candidate(value)

def extract_declaration_type(header: list[str]) -> str:
    for line in header:
        match = re.search(r'申\s*報\s*類\s*別\s*(.+)$', line)
        if match:
            return clean_line(match.group(1))
    return ''

def extract_date(header: list[str]) -> str | None:
    joined = ''.join(header)
    match = re.search(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', joined)
    if not match:
        return None
    roc_year, month, day = map(int, match.groups())
    return f'{roc_year + 1911:04d}-{month:02d}-{day:02d}'

def classify_position(title: str) -> str:
    for keyword, group in POSITION_KEYWORDS:
        if keyword in title:
            return group
    return '其他職務'

def parse_assets(doc: str):
    flags = {}
    totals = {}
    for key in MAIN_ASSET_LABELS:
        if key in {'land', 'building', 'ship', 'vehicle', 'aircraft', 'insurance'}:
            flags[key] = parse_presence(doc, key)
            totals[key] = None
            continue

        section = section_between(doc, *SECTION_RANGES[key])
        amount = parse_amount(section)
        totals[key] = amount
        flags[key] = amount is not None and amount > 0
        if key != 'securities' and amount is None and section and not is_blank_section(section):
            flags[key] = True

    debt_section = section_between(doc, *SECTION_RANGES['debt'])
    debt_total = parse_amount(debt_section)
    debt_flag = debt_total is not None and debt_total > 0
    if debt_total is None and debt_section and not is_blank_section(debt_section):
        debt_flag = True

    security_sections = {}
    for key in SECURITY_LABELS:
        section = section_between(doc, *SECURITY_RANGES[key])
        amount = parse_amount(section)
        security_sections[key] = {
            'amount': amount,
            'has': amount is not None and amount > 0,
        }
        if amount is None and section and not is_blank_section(section):
            security_sections[key]['has'] = True

    if totals['securities'] is None:
        flags['securities'] = any(item['has'] for item in security_sections.values())

    disclosed_total = sum(totals[key] or 0 for key in MONEY_ASSET_LABELS)

    return {
        'asset_flags': flags,
        'asset_totals': totals,
        'security_sections': security_sections,
        'debt_total': debt_total,
        'has_debt': debt_flag,
        'asset_type_count': sum(1 for value in flags.values() if value),
        'disclosed_amount_total': disclosed_total,
    }

def load_party_map():
    path = DATA_DIR / 'party_map.json'
    if not path.exists():
        return {}, None, None
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    return data.get('parties', {}), data.get('source'), data.get('note')

def build_records():
    parties, party_source, party_note = load_party_map()
    records = []

    for issue_path in sorted(DATA_DIR.glob('issue_*.json'), reverse=True):
        with open(issue_path, encoding='utf-8') as f:
            issue_data = json.load(f)
        issue = int(issue_data['issue'])

        sequence = 0
        for kind, doc in split_documents(issue_data['full_text']):
            if kind != 'declaration':
                continue

            sequence += 1
            header = parse_header(doc)
            assets = parse_assets(doc)
            party = parties.get(header['name'], '未標註')
            party_origin = 'party_map' if party != '未標註' else 'not_in_source'

            records.append({
                'id': f'{issue}-{sequence:04d}',
                'issue': issue,
                'sequence': sequence,
                **header,
                'party': party,
                'party_origin': party_origin,
                **assets,
                'source_file': issue_path.name,
            })

    metadata = {
        'generated_at': date.today().isoformat(),
        'record_count': len(records),
        'party_source': party_source,
        'party_note': party_note,
        'amount_note': '金額合計只加總申報表已有總金額或總價額欄位的項目；不動產、車輛、保險等常無總價欄位，不納入金額合計。',
    }
    return records, metadata

def summarize(records):
    by_party = Counter(record['party'] for record in records)
    by_position = Counter(record['position_group'] for record in records)
    by_issue = Counter(str(record['issue']) for record in records)
    by_asset = {
        key: sum(1 for record in records if record['asset_flags'].get(key))
        for key in MAIN_ASSET_LABELS
    }
    by_money = {
        key: sum(record['asset_totals'].get(key) or 0 for record in records)
        for key in MONEY_ASSET_LABELS
    }
    by_security = {
        key: sum(1 for record in records if record['security_sections'].get(key, {}).get('has'))
        for key in SECURITY_LABELS
    }

    party_amounts = defaultdict(int)
    position_amounts = defaultdict(int)
    debt_total = 0
    for record in records:
        party_amounts[record['party']] += record['disclosed_amount_total']
        position_amounts[record['position_group']] += record['disclosed_amount_total']
        debt_total += record['debt_total'] or 0

    return {
        'records': len(records),
        'unique_people': len({record['name'] for record in records if record['name'] != '未解析'}),
        'issues': dict(sorted(by_issue.items(), reverse=True)),
        'parties': dict(by_party.most_common()),
        'positions': dict(by_position.most_common()),
        'asset_holders': by_asset,
        'money_totals': by_money,
        'security_holders': by_security,
        'party_amounts': dict(sorted(party_amounts.items(), key=lambda item: item[1], reverse=True)),
        'position_amounts': dict(sorted(position_amounts.items(), key=lambda item: item[1], reverse=True)),
        'disclosed_amount_total': sum(record['disclosed_amount_total'] for record in records),
        'debt_total': debt_total,
        'top_disclosed': [
            {
                'id': record['id'],
                'name': record['name'],
                'party': record['party'],
                'title': record['title'],
                'agency': record['agency'],
                'issue': record['issue'],
                'amount': record['disclosed_amount_total'],
            }
            for record in sorted(records, key=lambda item: item['disclosed_amount_total'], reverse=True)[:20]
        ],
    }

def main():
    records, metadata = build_records()
    payload = {
        'metadata': metadata,
        'asset_labels': MAIN_ASSET_LABELS,
        'money_asset_labels': MONEY_ASSET_LABELS,
        'security_labels': SECURITY_LABELS,
        'records': records,
        'summary': summarize(records),
    }

    output_path = DATA_DIR / 'declarations.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'輸出：{output_path}')
    print(f'申報紀錄：{len(records)}')

if __name__ == '__main__':
    main()
