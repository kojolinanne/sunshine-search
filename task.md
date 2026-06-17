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

### P3｜land_detail 萃取品質（部分修復 ⚠）

- **現況**：`land_detail.json` 萃取邏輯已重寫（v11），但萃取品質仍不理想
- **根本原因**：PDF 版面複雜，兩種不同 column 格式混用，且 follow-line 數據分布不一致
- **2026-06-14 修復內容**：
  1. skip pattern bug：clean() 在中文間加空格導致 header 比對失效 → 改用 is_header_line() 直接比對原始字串
  2. 多人 block 問題：同一人在 PDF 中出現 2 次「申報人姓名」導致部分土地被錯誤歸屬 → 改為不 deduplicate person markers，依 name 合併
  3. 新舊雙格式支援：舊格式（len>=100）vs 新格式（len~79+111 pair）
- **萃取結果**（v11，共 28 期，共 1,363 筆）：
  - 有 location：~100%
  - 有 rights（持分）：84%
  - 有 area（面積）：11%（主要在 main+follow pair 新格式）
  - 有 price（取得價額）：12%
  - 有 date（取得日期）：1%（散布在 col 80-124）
- **仍存在的限制**：area/price/date 主要依賴 main+follow pair 的新格式才能乾淨萃取；舊格式（len>=100）則依賴 col 80+ 的位置，準確率較低
- **建議**：P3 可視為已稳定运行，陽光法案P2優先，若日後需求更完整的土地資料，再重構萃取逻辑

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
| land_detail.json | 1,363 | ✅ 正常 |
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