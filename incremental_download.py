#!/usr/bin/env python3
"""
增量下載腳本：每次執行下載一期 PDF，處理後加入專案。
支援電子書（有實質內容）和目錄（無實質內容）兩種 PDF。
目錄只標記為已處理（不会再 retry），電子書才真正下載。
"""
import subprocess, json, re, html, os, sys
from pathlib import Path
from datetime import datetime

ROOT = Path('/home/openclaw/.openclaw/workspace_coding/sunshine-search')
DATA = ROOT / 'data'
DECL_FILE = DATA / 'declarations.json'
STATE_FILE = ROOT / 'download_state.json'
MAX_SIZE_MB = 80   # 超過這個就拆分

# ── 讀取狀態 ──
def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    with open(DECL_FILE, encoding='utf-8') as f:
        decl = json.load(f)
    processed = set(r['issue'] for r in decl['records'])
    return {
        'processed': sorted(processed),
        'next_to_try': 108,
        'total_downloaded': 0,
        'total_failed': 0,
        'last_run': None,
        'direction': 'asc',
    }

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ── 取得期別 URL 與類型 ──
def get_issue_info(issue_num):
    """回傳 (url, is_catalog, filename) 或 (None, None, None)"""
    import base64
    pages = [
        'https://sunshine.cy.gov.tw/News.aspx?n=17&sms=8861&page=1&PageSize=200',
        'https://sunshine.cy.gov.tw/News.aspx?n=17&sms=8861&page=2&PageSize=200',
    ]
    for page_url in pages:
        r = subprocess.run(['curl', '-s', '--max-time', '15', page_url],
                          capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            continue
        decoded = html.unescape(r.stdout)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', decoded, re.DOTALL)
        for row in rows:
            if f'廉政專刊第{issue_num}期' not in row:
                continue
            href_m = re.search(r'href="(https://www-ws\.cy\.gov\.tw/Download\.ashx\?u=[^"]+)"', row)
            if not href_m:
                continue
            url = href_m.group(1)
            n_match = re.search(r'n=([^&]+)', url)
            filename = ''
            if n_match:
                n_enc = n_match.group(1).replace('%2F','/').replace('%2f','/')\
                                         .replace('%3D','=').replace('%3d','=')
                try:
                    filename = base64.b64decode(n_enc).decode('utf-8', errors='replace')
                except Exception:
                    pass
            is_catalog = '目錄' in filename
            return url, is_catalog, filename
    return None, None, None

# ── 下載一期 ──
def download_issue(issue_num):
    url, is_catalog, filename = get_issue_info(issue_num)

    if url is None:
        return None, None, f'第{issue_num}期在網站上找不到 URL'

    out_path = DATA / f'issue_{issue_num}.json'
    out_pdf = Path.home() / 'Downloads' / '廉政專刊' / f'廉政專刊第{issue_num}期.pdf'

    if is_catalog:
        # 目錄 PDF：不下載，只標記為已處理
        print(f'  第{issue_num}期為目錄檔（無實質內容），標記為已處理', flush=True)
        return None, True, f'目錄 ({filename})'

    if out_path.exists() and out_pdf.exists():
        return out_path, False, '已存在，略過'

    # 下載 PDF
    tmp_pdf = str(out_pdf)
    r = subprocess.run([
        'curl', '-L', '-o', tmp_pdf,
        '-w', '%{http_code}',
        '--max-time', '120', url
    ], capture_output=True, text=True, timeout=130)

    if not r.stdout.strip().startswith('200'):
        return None, False, f'HTTP {r.stdout.strip()}'

    size = os.path.getsize(tmp_pdf) if os.path.exists(tmp_pdf) else 0
    if size < 50000:
        os.remove(tmp_pdf)
        return None, False, f'檔案太小 ({size} bytes)'

    # 萃取文字
    text_r = subprocess.run(['pdftotext', '-enc', 'UTF-8', tmp_pdf, '-'],
                           capture_output=True, text=True, timeout=60)
    if text_r.returncode != 0:
        return None, False, 'pdftotext 失敗'

    lines = [l.strip() for l in text_r.stdout.splitlines()]
    cleaned = '\n'.join(l for l in lines if l)

    m = re.search(r'廉政專刊第(\d+)期', cleaned)
    actual_issue = int(m.group(1)) if m else issue_num

    data = {
        'issue': actual_issue,
        'total_chars': len(cleaned),
        'preview': cleaned[:1500],
        'full_text': cleaned
    }
    out = DATA / f'issue_{actual_issue}.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if actual_issue != issue_num:
        correct_pdf = Path.home() / 'Downloads' / '廉政專刊' / f'廉政專刊第{actual_issue}期.pdf'
        out_pdf.rename(correct_pdf)

    return out, False, f'OK ({len(cleaned):,} 字)'

# ── 重建 declarations.json ──
def rebuild_decls():
    sys.path.insert(0, str(ROOT))
    import importlib
    if 'build_statistics' in sys.modules:
        del sys.modules['build_statistics']
    import build_statistics as bs
    records, metadata = bs.build_records()
    payload = {
        'metadata': metadata,
        'asset_labels': bs.MAIN_ASSET_LABELS,
        'money_asset_labels': bs.MONEY_ASSET_LABELS,
        'security_labels': bs.SECURITY_LABELS,
        'records': records,
        'summary': bs.summarize(records),
    }
    tmp = DECL_FILE.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.rename(DECL_FILE)
    return len(records)

# ── 拆分 declarations.json ──
def check_and_split():
    size_mb = os.path.getsize(DECL_FILE) / 1024 / 1024
    print(f'  declarations.json: {size_mb:.1f} MB', flush=True)
    if size_mb <= MAX_SIZE_MB:
        return
    print(f'  超過 {MAX_SIZE_MB}MB，開始拆分...', flush=True)
    with open(DECL_FILE, encoding='utf-8') as f:
        decl = json.load(f)
    records_by_issue = {}
    for rec in decl['records']:
        i = rec['issue']
        if i not in records_by_issue:
            records_by_issue[i] = []
        records_by_issue[i].append(rec)
    chunks = []
    issues = sorted(records_by_issue.keys())
    for i in range(0, len(issues), 50):
        chunk_issues = issues[i:i+50]
        chunk_records = [rec for issue in chunk_issues for rec in records_by_issue[issue]]
        chunks.append((chunk_issues[0], chunk_issues[-1], chunk_records))
    base_payload = {
        'metadata': decl['metadata'],
        'asset_labels': decl['asset_labels'],
        'money_asset_labels': decl['money_asset_labels'],
        'security_labels': decl['security_labels'],
        'index': [{'from': c[0], 'to': c[1], 'count': len(c[2])} for c in chunks],
    }
    for chunk in chunks:
        chunk_name = f'declarations_{chunk[0]}-{chunk[1]}.json'
        with open(DATA / chunk_name, 'w', encoding='utf-8') as f:
            json.dump({**base_payload, 'records': chunk[2]}, f, ensure_ascii=False, indent=2)
        print(f'  寫入 {chunk_name}: {len(chunk[2])} 筆', flush=True)
    index = {
        'chunks': [{'file': f'declarations_{c[0]}-{c[1]}.json',
                    'from': c[0], 'to': c[1], 'count': len(c[2])} for c in chunks],
        'total_records': len(decl['records']),
        'generated_at': datetime.now().isoformat(),
    }
    with open(DATA / 'index.json', 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f'  拆分完成：共 {len(chunks)} 個檔案', flush=True)

# ── 主程式 ──
def main():
    state = load_state()
    processed = set(state['processed'])
    next_issue = state['next_to_try']
    direction = state.get('direction', 'asc')

    # 找下一個要處理的期別
    attempts = 0
    while attempts < 500:
        attempts += 1
        if direction == 'desc':
            while next_issue in processed and next_issue >= 108:
                next_issue -= 1
            if next_issue < 108:
                print(f'全部期別已處理完畢', flush=True)
                state['last_run'] = datetime.now().isoformat()
                save_state(state)
                return
        else:
            while next_issue in processed and next_issue <= 319:
                next_issue += 1
            if next_issue > 319:
                print(f'全部期別已處理完畢（最高319期）', flush=True)
                state['last_run'] = datetime.now().isoformat()
                save_state(state)
                return
        break  # 找到有效的 next_issue

    print(f'嘗試第 {next_issue} 期...', flush=True)
    path, is_catalog, msg = download_issue(next_issue)

    if is_catalog:
        # 目錄：加入 processed 以後不再 retry
        print(f'  {msg}', flush=True)
        state['processed'].append(next_issue)
        state['processed'].sort()
        state['next_to_try'] = next_issue - 1 if direction == 'desc' else next_issue + 1

    elif path:
        print(f'  下載成功：{msg}', flush=True)
        state['processed'].append(next_issue)
        state['processed'].sort()
        state['total_downloaded'] += 1
        print(f'  重建 declarations.json...', flush=True)
        count = rebuild_decls()
        print(f'  目前 {count} 筆記錄', flush=True)
        check_and_split()
        state['next_to_try'] = next_issue - 1 if direction == 'desc' else next_issue + 1

    else:
        print(f'  失敗：{msg}', flush=True)
        state['total_failed'] += 1
        if '找不到 URL' in msg:
            print(f'  第{next_issue}期不在網站上，跳過', flush=True)
            state['next_to_try'] = next_issue - 1 if direction == 'desc' else next_issue + 1

    state['last_run'] = datetime.now().isoformat()
    save_state(state)

    # 懶載入 full_text
    sys.path.insert(0, str(ROOT))
    if 'add_fulltext' in sys.modules:
        del sys.modules['add_fulltext']
    import add_fulltext
    add_fulltext.main()

if __name__ == '__main__':
    print(f'[{datetime.now().strftime("%H:%M:%S")}] 增量下載開始', flush=True)
    main()
    print(f'[{datetime.now().strftime("%H:%M:%S")}] 完成', flush=True)