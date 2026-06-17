# 廉政專刊陽光法案系統 - 待辦事項

最後更新：2026-06-17（自動檢查）
PDF 期別：292–319（共 28 期）

---

## 待修復問題

（目前無 P1-P2 緊急問題。以下為持續改善項目）

### P4｜地方首長政黨歸屬（蔣萬安等 13 筆顯示「未標註」）

- **問題**：`party_map.json` 目前只收錄「第十一屆立法委員」政黨資料（共 108 人），地方首長（含縣市首長）PDF 如未標明政黨，一律顯示「未標註」
- **受影響記錄**（共 13 筆申報）：
  - 中國國民黨：蔣萬安、侯友宜、盧秀燕、張麗善、徐榛蔚、鍾東錦、王惠美
  - 民主進步黨：陳其邁、翁章梁、周春米、許淑華
- **修復步驟**：
  1. 將已知政黨的地方首長姓名與政黨寫入 `data/party_map.json`（或另建 `data/local_party_map.json`）
  2. 修改 `build_statistics.py` 的 `build_records()` 载入地方首長政黨資料
  3. 重新執行 `build_statistics.py` 產生 `declarations.json`
  4. 重新執行 `incremental_download.py` 更新 GitHub Pages
- **優先級**：低（不影響資料正確性，僅為 UI 呈現）

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
| 2026-06-14 | P3 land_detail 萃取重寫 | 重寫萃取邏輯（extract_land_v11.py），修復 skip bug、多人 block、新舊雙格式支援，1,363 筆（commit 0ccd2aa） |
| 2026-06-13 | 4個 detail JSON key 錯誤 | deposit/jewelry/cash/ship_detail.json 頂層 key 從 holder 改為 current_person（commit 94060df） |
| 2026-06-13 | 前端 showPersonAssetDetail 統計漏算 ntd_amount | 統計 now sums price/ntd_amount/total/balance（commit 58d9deb） |
| 2026-06-13 | ship_detail.json 假資料 | 全部 28 期 PDF 船舶欄位均為「本欄空白」，舊 149 筆為錯誤萃取，已清除 |
| 2026-06-13 | 卡片 +N 展開按鈕無作用 | 改為可點擊，點擊後展開顯示其餘所有財產類別（commit be9551a） |
| 2026-06-13 | 車輛萃取跨頁漏抓 | vehicle 從 636→756 輛（+19%），fix cross-page section handling（commit e59bbc5） |
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
- 無緊急問題（P1 珠寶、P2 車輛已修復，P3 土地萃取已趨於穩定可繼續使用）