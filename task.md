# 廉政專刊陽光法案系統 - 待辦事項

最後更新：2026-06-19
PDF 期別：292–319（共 28 期）

---

## 待修復問題

（目前無 P1-P4 緊急問題。以下為持續改善項目）

### P5｜資料完整性驗證（發現於 2026-06-19）

- **背景**：依 `script.js` 預設排序（`activeGroup='party'`，依政黨群組金額總和→個人 disclosed_amount_total），對 1,496 筆資料執行自動化完整性檢查
- **完整名單與驗證報告**：`verification_people.md`（1,756 行）
- **驗證結果**：
  - `disclosed_amount_total = 0`：50 筆
  - `securities diff > 1%`（真正萃取問題）：9 筆（如下）

#### Securities 萃取錯誤（差額 > 1%，需修復 extract_securities_detail.py）

| 姓名 | 期別 | 問題 |
|------|------|------|
| 吳銘賜 | 303 | fund/other 萃取 53,000,950，實際僅計入 1,460（差 3,630,102%） |
| 黃國榮 | 317 | stock+fund 萃取僅 1，實際應為 59（差 98.31%） |
| 林鼎超 | 315 | 差額 2.74% |
| 林立生 | 292 | 差額 1.49% |
| 吳志中 | 305 | 差額 1.19% |
| 周羿希 | 309 | 完全漏抓（萃取 0，實際應為 12） |
| 張桂綿 | 298 | 完全漏抓（萃取 0，實際應為 8,209） |
| 陳儀君 | 295 | 完全漏抓（萃取 0，實際應為 110） |
| 張惇涵 | 293 | 完全漏抓（萃取 0，實際應為 28） |

#### disclosed_amount_total = 0（需確認，50 筆）

- **需人工核查**：4 筆記錄 `asset_flags` 全為空（完全未萃取到任何資產）
- **其餘 46 筆**：可能為合法（僅持有非貨幣型資產：土地、建築物、車輛、保險），建議以「無貨幣資產」標註，而非 0

#### 頁面預設排序名單（前 20 名）

1. 陳鴻源 / 第295期 / 副議長 / 3,503,668,702元（未標註）
2. 陳錦錠 / 第295期 / 議員 / 1,774,292,239元（未標註）
3. 曾麗燕 / 第303期 / 議員 / 958,229,845元（未標註）
4. 廖秀紅 / 第304期 / 議員 / 865,851,056元（未標註）
5. 劉曾玉春 / 第298期 / 議員 / 837,200,147元（未標註）
6. 張清照 / 第300期 / 議長 / 814,842,421元（未標註）
7. 鄭麗君 / 第296期 / 副院長 / 668,949,614元（未標註）
8. 張鎮榮 / 第303期 / 議長 / 646,190,634元（未標註）
9. 林宜敬 / 第293期 / 部長 / 551,313,635元（未標註）
10. 鄭聚然 / 第316期 / 議員 / 531,034,499元（未標註）
11. 李妍慧 / 第305期 / 副委員長 / 376,084,591元（未標註）
12. 趙永清 / 第309期 / 監察委員 / 375,480,409元（未標註）
13. 林佳龍 / 第293期 / 部長 / 333,573,942元（未標註）
14. 方信淵 / 第316期 / 議員 / 282,914,677元（未標註）
15. 何文海 / 第300期 / 議員 / 273,959,393元（未標註）
16. 郭智輝 / 第292期 / 部長 / 267,378,427元（未標註）
17. 賴淑惠 / 第315期 / 副市長 / 250,745,993元（未標註）
18. 金瑞龍 / 第295期 / 議員 / 240,154,443元（未標註）
19. 張勝德 / 第310期 / 議長 / 213,229,371元（未標註）
20. 林孟令 / 第300期 / 議員 / 207,447,971元（未標註）

**完整 1,496 筆名單（含所有政黨群組）見：`verification_people.md`**

---

### P4｜地方首長政黨歸屬（✅ 已修復，2026-06-17）

- **問題**：`party_map.json` 原本只收錄「第十一屆立法委員」政黨資料（共 108 人），地方首長 PDF 未標明政黨者顯示「未標註」
- **受影響**：蔣萬安、侯友宜、盧秀燕、陳其邁等 18 位地方首長
- **修復方式**：直接將已知政黨寫入 `party_map.json`（無需查 PDF），重新執行 `build_statistics.py`（commit e824ad0）
- **P4 視為已解決**

---

### P3｜land_detail 萃取品質（✅ 已修復，2026-06-17）

- **根本問題**：pdftotext -layout 對多byte字符（中文）使用 3-byte 編碼，v11 固定 byte 位置全部錯位，導致 area/rights/price 抓錯位置。
- **修復（v12）**：改用 regex 在整行文本中直接定位各欄位：
  - area：地址關鍵詞（段/路/街...）之後第一個數值（含小數）
  - rights：紧随 area 段落後的 `分之N` 或 `全部`
  - price：行末倒數取逗號千分位數字
  - date：regex 搜索 `\d{2,3}年\d{1,2}月`
- **萃取結果（v12，28期，共 14,609 筆）**：
  - area: 98.1%（v11: 11.4%，**+86.7pp**）
  - rights: 82.4%（v11: 83.7%）
  - price: 17.0%（v11: 12.1%，**+4.9pp**）
  - date: 36.3%（v11: 無萃取）
- **萃取腳本**：`extract_land_v12.py`（commit 6b62b3f）
- **P3 視為已解決**

---

## 已完成修復

| 日期 | 問題 | 修復內容 |
|------|------|----------|
| 2026-06-17 | P4 地方首長政黨歸屬 | 將 18 位地方首長政黨寫入 party_map.json，重新產生 declarations.json（commit e824ad0） |
| 2026-06-16 | P3 land_detail 萃取重寫 | 重寫萃取邏輯（extract_land_v11.py），修復 skip bug、多人 block、新舊雙格式支援（commit 0ccd2aa） |
| 2026-06-13 | 4個 detail JSON key 錯誤 | deposit/jewelry/cash/ship_detail.json 頂層 key 從 holder 改為 current_person（commit 94060df） |
| 2026-06-13 | 前端 showPersonAssetDetail 統計漏算 ntd_amount | 統計 now sums price/ntd_amount/total/balance（commit 58d9deb） |
| 2026-06-13 | ship_detail.json 假資料 | 全部 28 期 PDF 船舶欄位均為「本欄空白」，舊 149 筆為錯誤萃取，已清除 |
| 2026-06-13 | 卡片 +N 展開按鈕無作用 | 改為可點擊，點擊後展開顯示其餘所有財產類別（commit be9551a） |
| 2026-06-13 | 車輛萃取跨頁漏抓 | vehicle 從 636→756 輛（+19%），fix cross-page section handling（commit e59bbc5） |
| 2026-06-19 | mkrow(left) 傳 null 導致 appendChild(TypeError) → modal 無法顯示 | mkrow() 加 if(left) guard（commit 0a8ad13） |
| 2026-06-16 | script.js 語法錯誤（showPersonAssetDetail 回調缺 `}`） | 在 `else if (Array.isArray(d.data))` 區塊結尾加上 `}`，關閉 `details.forEach` callback（commit a89ec40） |
| 2026-06-15 | script.js timeout+parallel fetch | parallel fetch → 60s AbortController timeout，防止慢速網路永久卡死（commit 45c207d） |

---

## 資料筆數現況（2026-06-15）

| 檔案 | 筆數 | 備註 |
|------|------|------|
| land_detail.json | 14,609 | ✅ area 98%, price 17%, date 36% |
| deposit_detail.json | 1,411 | ✅ 正常 |
| jewelry_detail.json | 511 | ✅ 正常（100%有價格） |
| securities_detail.json | 713 | ✅ 正常 |
| insurance_detail.json | 2,981 | ✅ 正常 |
| credit_detail.json | 1,470 | ✅ 正常 |
| investment_detail.json | 492 | ✅ 正常 |
| debt_detail.json | 551 | ✅ 正常 |
| cash_detail.json | 229 | ✅ 正常 |
| vehicle_detail.json | 756 | ✅ 正常 |
| ship_detail.json | 0 | ✅ 正確（PDF 全為空白） |
| aircraft_detail.json | 0 | ✅ 正確（PDF 全為空白） |

## 目前待修
- 無緊急問題（P1–P4 已全部修復，以下為持續改善項目）

---

## 可改進項目（網站與資料品質）

### 改進｜搜尋體驗（✅ 已完成，2026-06-18）

- **實作**：fuse.js 7.0.0 fuzzy search + 即時 autocomplete 建議（commit 1d26ce6）
  - `buildFuseIndex()`：name/agency/title/party/position_group 加權搜尋
  - debounce 300ms，顯示前 5 個候選
  - 鍵盤支援：↑↓ 選擇、Enter 確認、Esc 關閉
- **優先級**：中

### 改進｜載入體驗（✅ 已完成，2026-06-18）

- **實作**：progress bar + 逐項狀態指示（commit c9460d6）
  - 3 行逐項狀態（主資料/有價證券/負債）：○ 載入中 → ✓ 完成
  - 底部 progress bar 顯示整體進度百分比
  - 載入完成後顯示「N 筆申報表已載入」
  - aria-live / role=progressbar 無障礙支援
- **優先級**：中

### 改進｜詳情彈窗首次載入慢

- **現況**：點擊卡片展開某類資產時，需下載對應 detail JSON（如 land_detail.json 4.4MB），首次約需 3-5 秒，無載入提示。
- **改善方向**：`openAssetModal()` 加入「載入中」提示，detail JSON 改 gzip 傳輸。
- **優先級**：中

### 改進｜分群瀏覽無分頁，大量結果難以瀏覽

- **現況**：切換到「政黨」或「職務」分群時，所有卡片一口氣 render，無虛擬滾動，大群組可能上百張卡片，滾動會卡頓。
- **改善方向**：加入「載入更多」按鈕或 IntersectionObserver 虛擬滾動。
- **優先級**：低

### 改進｜卡片點擊展開沒有視覺關閉提示

- **現況**：點擊卡片展開所有財產類別後，沒有明顯的「點擊收合」提示，操作依賴嘗試錯誤。
- **改善方向**：展開狀態加「點擊收合」hint（小型 tooltip 或 badge）。
- **優先級**：低

### 改進｜無障礙設計（鍵盤導航、ARIA）

- **現況**：篩選器、搜尋框、卡片都沒有 `tabindex`、`role`、`aria-label`，鍵盤使用者難以操作。
- **改善方向**：
  1. 所有可操作元素加 `tabindex="0"` 和 `role`
  2. 搜尋框加 `aria-label` / `aria-autocomplete`
  3. modal 加 `role="dialog"` / `aria-modal`
- **優先級**：低

### 待追蹤｜珠寶（jewelry_detail）萃取品質

- **現況**：jewelry_detail.json 共 511 筆，需抽樣確認 price 是否為直接萃取而非從申報總額而來。
- **優先級**：低（不影響主要功能）
