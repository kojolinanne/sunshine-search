# 廉政專刊陽光法案系統 - 待辦事項

最後更新：2026-06-21
PDF 期別：292–319（共 28 期）

---

## 待修復問題

（目前無 P1-P4 緊急問題。以下為持續改善項目）

### P6｜陳鴻源（第295期）萃取完整性核查（發現於 2026-06-21）

> 陳鴻源是全系統披露金額最高者（3,503,668,702元），以 `full_text` 與各 `detail JSON` 逐一交叉比對。

#### 比對結果總表

| 項目 | PDF Header | asset_totals | detail JSON sum | 比對 | 萃取筆數 |
|------|-----------|-------------|-----------------|------|----------|
| disclosed_amount_total | — | 3,503,668,702 | — | ✅ 構成正確 | — |
| 存款 deposit | 170,909,648 | 170,909,648 | 166,888,831 | ⚠️ 少 4,020,817 | 46筆（bank名稱多為「不明」） |
| 有價證券 securities | 6,869,738 | 6,869,738 | **查無此人** | ❌ 陳鴻源不在 securities_detail[295]，只抓到26人 | — |
| 珠寶/古董/字畫 valuable | 52,273,300 | 52,273,300 | **查無此人** | ❌ 陳鴻源不在 jewelry_detail[295] | — |
| 債權 claim | 2,547,034,306 | 2,547,034,306 | credit_detail 完全混亂（creditor/debtor/balance 全部錯位） | ❌ | 多筆 |
| 債務 debt | 4,566,000,000 | —（未存） | 4,426,000,000 | ⚠️ 少 140,000,000 | 4筆（少一筆合作金庫 116M） |
| 事業投資 business | 726,581,710 | —（未存） | amount 全部為空 | ❌ | 8筆（公司名有重複） |
| 保險 insurance | 有（陳鴻源3筆+劉世琪11筆） | —（未存） | 陳鴻源不在 insurance_detail[295] | ❌ | 0 |
| 土地 land | ~197筆 | —（未存） | 萃取464筆（fragmented） | ⚠️ 萃取碎片化 | 464筆 |
| 車輛 vehicle | 1筆（劉世琪 Mercedes-Benz） | —（未存） | 待確認 | ⚠️ 配偶車輛可能漏抓 | — |
| 現金 cash | 待查 | —（未存） | 待查 | ? | — |

#### disclosed_amount_total 構成驗證
存款(170.9M) + 有價證券(6.9M) + 珠寶(52.3M) + 債權(2,547M) + 事業投資(726.6M) = **3,503.7M** ✅ 與 header 完全吻合。

---

### P5｜資料完整性驗證（發現於 2026-06-19）

- **完整名單與驗證報告**：`verification_people.md`（1,756 行）
- **驗證結果**：
  - `disclosed_amount_total = 0`：50 筆
  - `securities diff > 1%`（真正萃取問題）：9 筆

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

---

## 頁面預設排序名單（前 20 名）

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

---

## 已完成修復

| 日期 | 問題 | 修復內容 |
|------|------|----------|
| 2026-06-22 | P1 珠寶/古董/字畫萃取修復 | P6-2 jewelry_detail 已修復（P1 resolved） |
| 2026-06-22 | P2 車輛萃取修復 | P6-9 vehicle_detail 已修復（P2 resolved） |
| 2026-06-21 | P6 陳鴻源萃取核查 | 發現6個萃取問題，列為 P6（見上） |
| 2026-06-19 | mkrow(left) 傳 null 導致 appendChild(TypeError) → modal 無法顯示 | mkrow() 加 if(left) guard（commit 0a8ad13） |
| 2026-06-19 | full_text / securities 萃取修復 | rebuild_statistics.py 補回 full_text；securities section_between max_distance + parse_amount max_chars（commit 36b968d） |
| 2026-06-17 | P4 地方首長政黨歸屬 | 將 18 位地方首長政黨寫入 party_map.json，重新產生 declarations.json（commit e824ad0） |
| 2026-06-16 | script.js 語法錯誤（showPersonAssetDetail 回調缺 `}`） | 在 `else if (Array.isArray(d.data))` 區塊結尾加上 `}`（commit a89ec40） |
| 2026-06-16 | P3 land_detail 萃取重寫 | 重寫萃取邏輯（extract_land_v11.py），修復 skip bug、多人 block、新舊雙格式支援（commit 0ccd2aa） |
| 2026-06-15 | script.js timeout+parallel fetch | parallel fetch → 60s AbortController timeout，防止慢速網路永久卡死（commit 45c207d） |
| 2026-06-13 | 4個 detail JSON key 錯誤 | deposit/jewelry/cash/ship_detail.json 頂層 key 從 holder 改為 current_person（commit 94060df） |
| 2026-06-13 | 車輛萃取跨頁漏抓 | vehicle 從 636→756 輛（+19%），fix cross-page section handling（commit e59bbc5） |

---

## P6 待修項目（陳鴻源核查發現）

### 🔴 P6-1｜securities_detail 完全遺漏陳鴻源（第295期）

- **現象**：securities_detail[295] 只有 26 人，陳鴻源完全不在名單內
- **原因**：萃取腳本 `extract_securities_detail.py` 在某些 PDF 中定位有價證券 section 失敗
- **修復方向**：檢查 extract_securities_detail.py 的 section_between 起訖 MARKER，確保 295 期有正確匹配
- **優先級**：高

### 🔴 P6-2｜jewelry_detail 完全遺漏陳鴻源（第295期）（P1 - ✅ 已修復）

- **現象**：jewelry_detail[295] 只有 108 筆（company_name 為 key），陳鴻源完全不在名單內
- **PDF 有珠寶**：52,273,300 元（美元結構型商品，配偶劉世琪持有）
- **原因**：`extract_jewelry_detail.py` 的 section 解析可能有問題
- **優先級**：高
- **狀態**：✅ 已修復（2026-06-22）

### 🔴 P6-3｜insurance_detail 完全遺漏陳鴻源（第295期）

- **現象**：insurance_detail[295] 有 108 筆，公司名為 key，陳鴻源不在其中
- **PDF 有保險**：陳鴻源 3 筆（宏泰/南山/新光壽險）+ 劉世琪 11 筆
- **原因**：`extract_insurance_detail.py` 解析失敗
- **優先級**：高

### 🔴 P6-4｜credit_detail 萃取完全錯位

- **現象**：creditor=陳鴻源、debtor=「取得/類債/間原/古亭開發事業股份/股東往來」全部錯位，balance 全空
- **PDF 事實**：陳鴻源是「債權人」，債務人是「古亭開發事業股份有限公司」等，balance=2,547,034,306
- **原因**：`extract_credit_detail.py` column alignment 解析失敗
- **優先級**：高

### 🔴 P6-5｜investment_detail amount 全為空

- **現象**：陳鴻源 8 筆事業投資，amount 全部為空
- **PDF header**：726,581,710 元
- **原因**：`extract_investment_detail.py` 無法從 PDF 表格萃取金額欄位
- **優先級**：高

### 🟡 P6-6｜debt_detail 少一筆記錄（差額 140,000,000）

- **現象**：萃取 4 筆合計 4,426,000,000，PDF header 為 4,566,000,000
- **差額**：140,000,000（少了合作金庫商業銀行永和分行的授信）
- **優先級**：中

### 🟡 P6-7｜deposit_detail 差額 4,020,817

- **現象**：46 筆加總 = 166,888,831，asset_totals.deposit = 170,909,648
- **差額**：4,020,817
- **原因**：部分銀行名稱萃取為「不明」（應為 臺灣銀行 1,047,438 那一筆被錯誤解析）
- **優先級**：中

### 🟡 P6-8｜land_detail 碎片化（P3 - 低優先級，可延後）

- **現象**：萃取 464 筆，PDF 約 197 筆
- **原因**：PDF 多欄佈局導致每行被當成獨立記錄
- **優先級**：低（不影響 disclosed_amount_total 正確性，已延後處理）

### 🟡 P6-9｜vehicle_detail 配偶車輛可能漏抓（P2 - ✅ 已修復）

- **現象**：PDF 有 1 筆 Mercedes-Benz 2,996cc（劉世琪），vehicle_detail 待確認是否包含
- **優先級**：低
- **狀態**：✅ 已修復（2026-06-22）

---

## 可改進項目（網站與資料品質）

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

---

## 資料筆數現況（2026-06-15）

| 檔案 | 筆數 | 備註 |
|------|------|------|
| land_detail.json | 14,609 | ⚠️ 碎片化（萃取464/實際197，陳鴻源） |
| deposit_detail.json | 1,411 | ⚠️ 差額 4,020,817（陳鴻源） |
| jewelry_detail.json | 511 | ❌ 陳鴻源不在名單內（P6-2） |
| securities_detail.json | 713 | ❌ 陳鴻源不在名單內（P6-1） |
| insurance_detail.json | 2,981 | ❌ 陳鴻源不在名單內（P6-3） |
| credit_detail.json | 1,470 | ❌ 萃取錯位（P6-4） |
| investment_detail.json | 492 | ❌ amount 全為空（P6-5） |
| debt_detail.json | 551 | ⚠️ 少 140M（P6-6） |
| cash_detail.json | 229 | ✅ 正常 |
| vehicle_detail.json | 756 | ✅ 正常 |
| ship_detail.json | 0 | ✅ 正確（PDF 全為空白） |
| aircraft_detail.json | 0 | ✅ 正確（PDF 全為空白） |