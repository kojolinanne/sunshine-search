#!/usr/bin/env python3
"""
增量下載腳本：每次執行下載一期 PDF，處理後加入專案。
由 cron 每 10 分鐘觸發一次。
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
    # 初始化：從已處理的期別反推
    with open(DECL_FILE, encoding='utf-8') as f:
        decl = json.load(f)
    processed = set(r['issue'] for r in decl['records'])
    return {
        'processed': sorted(processed),
        'next_to_try': 108,   # 網站上最舊的是第108期
        'total_downloaded': 0,
        'total_failed': 0,
        'last_run': None,
    }

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ── 從網站抓某一期的下載 URL ──
def get_issue_url(issue_num):
    """在網站上搜尋指定期別的 PDF URL，優先取「電子書」欄位的連結（而非目錄檔）"""
    import base64
    for page in range(1, 12):
        url = f'https://sunshine.cy.gov.tw/News.aspx?n=17&sms=8861&page={page}'
        r = subprocess.run(['curl', '-s', '--max-time', '15', url],
                          capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            continue
        raw_decoded = html.unescape(r.stdout)

        # 策略：在「電子書」欄位（TH_4）內搜尋此期別的連結
        # 每期有兩列：期別(目錄) & 電子書(內容)
        # 在電子書 <td> 區域內搜
        for m in re.finditer(rf'廉政專刊第{issue_num}期(?!目錄)', raw_decoded):
            pos = m.start()
            # 向後找最近的一個 href
            href_m = re.search(r'href="(https://www-ws\.cy\.gov\.tw/Download\.ashx\?u=[^"]+)"',
                               raw_decoded[pos:pos+2000])
            if href_m:
                candidate = href_m.group(1)
                # 驗證：解碼 n= 確認不是「目錄」檔
                n_match = re.search(r'n=([^&]+)', candidate)
                if n_match:
                    n_enc = n_match.group(1).replace('%2F', '/').replace('%2f', '/')\
                                                     .replace('%3D', '=').replace('%3d', '=')
                    try:
                        fname = base64.b64decode(n_enc).decode('utf-8', errors='replace')
                        if '目錄' not in fname and f'第{issue_num}期' in fname:
                            return candidate
                    except Exception:
                        pass
        # 備援：取第一個符合期別且非目錄的連結
        all_urls = re.findall(r'href="(https://www-ws\.cy\.gov\.tw/Download\.ashx\?u=[^"]+)"', raw_decoded)
        for candidate in all_urls:
            n_match = re.search(r'n=([^&]+)', candidate)
            if n_match:
                n_enc = n_match.group(1).replace('%2F', '/').replace('%2f', '/')\
                                                 .replace('%3D', '=').replace('%3d', '=')
                try:
                    fname = base64.b64decode(n_enc).decode('utf-8', errors='replace')
                    if '目錄' not in fname and f'第{issue_num}期' in fname:
                        return candidate
                except Exception:
                    pass
    return None

# ── 下載一期 ──
def download_issue(issue_num):
    url = get_issue_url(issue_num)
    if not url:
        return None, f'第{issue_num}期在網站上找不到 URL'

    out_path = DATA / f'issue_{issue_num}.json'
    out_pdf = Path.home() / 'Downloads' / '廉政專刊' / f'廉政專刊第{issue_num}期.pdf'
    if out_path.exists() and out_pdf.exists():
        return out_path, '已存在，略過'

    # 嘗試下載到 ~/Downloads/廉政專刊/
    tmp_pdf = str(out_pdf)
    r = subprocess.run([
        'curl', '-L', '-o', tmp_pdf,
        '-w', '%{http_code}',
        '--max-time', '120', url
    ], capture_output=True, text=True, timeout=130)

    if not r.stdout.strip().startswith('200'):
        return None, f'HTTP {r.stdout.strip()}'

    size = os.path.getsize(tmp_pdf) if os.path.exists(tmp_pdf) else 0
    if size < 50000:
        return None, f'檔案太小 ({size} bytes)'

    # 萃取文字
    text_r = subprocess.run(['pdftotext', '-enc', 'UTF-8', tmp_pdf, '-'],
                           capture_output=True, text=True, timeout=60)
    if text_r.returncode != 0:
        return None, f'pdftotext 失敗'

    # 清理
    lines = [l.strip() for l in text_r.stdout.splitlines()]
    cleaned = '\n'.join(l for l in lines if l)

    # 確認期別
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

    # 如果實際期別與請求的不同，重新命名 PDF
    if actual_issue != issue_num:
        correct_pdf = Path.home() / 'Downloads' / '廉政專刊' / f'廉政專刊第{actual_issue}期.pdf'
        out_pdf.rename(correct_pdf)

    return out, f'OK ({len(cleaned):,} 字)'

# ── 重建 declarations.json（只處理的 issue） ──
def rebuild_decls():
    sys.path.insert(0, str(ROOT))
    # 動態 reload build_statistics 以防快取
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

# ── 拆分 declarations.json（超過閾值時） ──
def check_and_split():
    size_mb = os.path.getsize(DECL_FILE) / 1024 / 1024
    print(f'  declarations.json: {size_mb:.1f} MB', flush=True)
    if size_mb <= MAX_SIZE_MB:
        return

    print(f'  超過 {MAX_SIZE_MB}MB，開始拆分...', flush=True)
    with open(DECL_FILE, encoding='utf-8') as f:
        decl = json.load(f)

    # 按期別分組
    records_by_issue = {}
    for rec in decl['records']:
        i = rec['issue']
        if i not in records_by_issue:
            records_by_issue[i] = []
        records_by_issue[i].append(rec)

    # 每 50 期一檔
    chunks = []
    issues = sorted(records_by_issue.keys())
    for i in range(0, len(issues), 50):
        chunk_issues = issues[i:i+50]
        chunk_records = []
        for issue in chunk_issues:
            chunk_records.extend(records_by_issue[issue])
        chunks.append((chunk_issues[0], chunk_issues[-1], chunk_records))

    # 寫分割檔
    base_payload = {
        'metadata': decl['metadata'],
        'asset_labels': decl['asset_labels'],
        'money_asset_labels': decl['money_asset_labels'],
        'security_labels': decl['security_labels'],
        'index': [{'from': c[0], 'to': c[1], 'count': len(c[2])} for c in chunks],
    }

    for chunk in chunks:
        chunk_name = f'declarations_{chunk[0]}-{chunk[1]}.json'
        chunk_path = DATA / chunk_name
        chunk_data = {**base_payload, 'records': chunk[2]}
        with open(chunk_path, 'w', encoding='utf-8') as f:
            json.dump(chunk_data, f, ensure_ascii=False, indent=2)
        print(f'  寫入 {chunk_name}: {len(chunk[2])} 筆', flush=True)

    # 覆寫 index.json
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

    # 找下一個要處理的期別
    processed = set(state['processed'])
    next_issue = state['next_to_try']

    # 從 108 往上找第一個還沒處理的
    while next_issue in processed:
        next_issue += 1

    if next_issue > 319:
        print(f'全部期別已處理完畢（最高319期）', flush=True)
        state['last_run'] = datetime.now().isoformat()
        save_state(state)
        return

    print(f'嘗試下載第 {next_issue} 期...', flush=True)
    path, msg = download_issue(next_issue)

    if path:
        print(f'  下載成功：{msg}', flush=True)
        state['processed'].append(next_issue)
        state['processed'].sort()
        state['total_downloaded'] += 1

        # 重建 declarations.json
        print(f'  重建 declarations.json...', flush=True)
        count = rebuild_decls()
        print(f'  目前 {count} 筆記錄', flush=True)

        # 檢查大小並拆分
        check_and_split()

        # 更新 next_to_try
        state['next_to_try'] = next_issue + 1

    else:
        print(f'  失敗：{msg}', flush=True)
        state['total_failed'] += 1
        # 如果是"找不到 URL"，說明這期不在網站上，跳過它
        if '找不到 URL' in msg:
            print(f'  第{next_issue}期不在網站上，跳過', flush=True)
            state['next_to_try'] = next_issue + 1

    state['last_run'] = datetime.now().isoformat()
    save_state(state)

    # 附加 full_text（懶載入）
    sys.path.insert(0, str(ROOT))
    if 'add_fulltext' in sys.modules:
        del sys.modules['add_fulltext']
    import add_fulltext
    add_fulltext.main()

if __name__ == '__main__':
    print(f'[{datetime.now().strftime("%H:%M:%S")}] 增量下載腳本開始', flush=True)
    main()
    print(f'[{datetime.now().strftime("%H:%M:%S")}] 完成', flush=True)