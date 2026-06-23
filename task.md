# Task: 修復土地價格萃取與顯示

## 目標
所有土地記錄的價格資訊應正確顯示（前端正確呈現已萃取到的資料）。

---

## 已完成的修復

### 1. extract_land_detail.py — 增加 over5 檢測（2026-06-23）
**檔案：** `/home/openclaw/.openclaw/workspace_coding/sunshine-search/extract_land_detail.py`

萃取時偵測「(超過五年)」並設定 `over5: true`：
```python
price_m = re.search(r'([0-9,]+)\s*$', ls.strip())
price = ''
over5 = False
if price_m:
    price = price_m.group(1)
elif '超過五年' in ls or '(超過五年)' in ls:
    over5 = True
```

### 2. script.js — 前端顯示（2026-06-23）
**檔案：** `/home/openclaw/.openclaw/workspace_coding/sunshine-search/script.js`

土地 modal 顯示邏輯（`renderLandRows`）：
```javascript
if (land.over5) {
    tr.appendChild(mkcell('⏳ (超過五年)'));
} else if (land.price) {
    tr.appendChild(mkcell(land.price));
} else {
    tr.appendChild(mkcell('—', 'text-muted'));
}
```

### 3. 後處理腳本 — 修補 3,575 筆（2026-06-23）
執行：掃描 location/holder 欄位含「超過五年」的記錄，設定 `over5: true`
執行：年 < 89（2000 年前取得）且無價格的記錄，設定 `over5: true`

---

## 目前資料狀態

```
土地總筆數：14,609
  有數字價格（price）：   2,485（17.0%）
  (超過五年)（over5）：   1,420（9.7%）  ← 含 location/holder 文字偵測  + 年份推估
  無任何資訊（blank）：  10,704（73.3%）
  覆蓋率： 26.7%
```

**剩餘 10,704 筆空白分為兩類：**
- 無日期且無價格（~7,010筆）：PDF 中日期和價格欄位均為空白，可能是：
  - 「(超過五年)」但萃取時續行文字未被併入記錄
  - 確實無價格也無日期的遺漏
- 有日期（89年=2000年之後）但無價格（~3,694筆）：PDF 中這些欄位真的空白，可能是：
  - 不適用申報的類型（如國有非公用土地）
  - 萃取失敗

---

## 待處理項目

### [ ] 項目一：重新萃取 land_detail.json（新萃取腳本才能抓到 34,529 筆記錄）

**現況：**
- `extract_land_detail.py` 嘗試萃取 28 期 PDF，日誌顯示完成：28 期，**土地 34,529 筆，建物 678 筆**
- 但寫入磁碟的 `land_detail.json` 仍是舊的 14,609 筆（檔案內容、大小、修改時間都沒變）
- 原因：script.remove(cache loading) 把所有期都視為「已有」而 skip，無新資料寫入

**需要：**
1. 確認為何新萃取腳本寫入的筆數（34,529）與實際檔案不符
2. 強制重新萃取（刪除或改名 land_detail.json 再跑一次）
3. 驗證新萃取確實包含更多土地記錄（特別是原本被視為「續行」而遺漏的那些）

**驗證方式：**
```bash
cd /home/openclaw/.openclaw/workspace_coding/sunshine-search
# 備份
cp data/land_detail.json data/land_detail.json.bak_20260623
# 刪除並重跑
rm data/land_detail.json
python3 extract_land_detail.py 2>&1 | tail -5
# 比對新舊筆數
```

### [ ] 項目二：提升 over5 覆蓋率（26.7% → 目標 60%+）

**問題：**
萃取腳本把「(超過五年)」的後續行（continuation line）視為獨立的 land 記錄：
```
location: "718 2 分之 1 陳鴻源 買賣 (超過五年)"  ← 錯誤：location 被汙染
area: ""                                          ← 錯誤：area 為空
over5: true                                       ← 正確：有偵測到
```

正確應為：
```
location: "新北市石碇區烏塗窟段大格門小段"
area: "718"
rights: "2 分之 1"
over5: true
```

**可能解法：**
1. 在 parse_land_section 中，skip 純數字的 continuation line，把後面的 "(超過五年)" 關聯到上一筆記錄
2. 或在後處理時，偵測 location 格式異常（純數字开头）的記錄，嘗試與上下筆合併

### [ ] 項目三：確認無日期blank（~7,010筆）的實際內容

抽取 5-10 筆樣本，比對 PDF 原始文字，確認：
- 是否真的是「(超過五年)」但萃取失敗
- 還是 PDF 中就沒有這些資料

```python
# 建議：用 pdftotext 抽查
pdftotext -layout "廉政專刊第292期.pdf" - | grep -A5 "劉得金" | head -20
```

### [ ] 項目四：前端部署驗證
確認 `script.js` 的 over5 顯示修改已 commit 並 deploy 到 GitHub Pages
```bash
cd /home/openclaw/.openclaw/workspace_coding/sunshine-search
git log --oneline -5
git status
```

---

## 已驗證正常的部分
- ✅ script.js 語法正確（commit a89ec40）
- ✅ declarations.json 載入正常（30MB, Promise.all + 60s timeout）
- ✅ land modal 點擊正常（commit 0a8ad13 null guard）
- ✅ deposit/securities/insurance 等其他資產Detail JSON 正常

---

## 預估嚴重程度
- **medium**：73% 土地顯示「-」，但主要是 PDF 本身沒有填寫（依法可空白），非萃取嚴重失敗
- 修復萃取腳本後預期可提升至 60%+