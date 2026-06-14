# 廉政專刊陽光法案系統 - 待辦事項

最後更新：2026-06-14
PDF 期別：292–319（共 28 期）

---

## 待修復問題

（目前無 P1-P3 緊急問題。P3 已於 2026-06-14 部分修復，見下方說明）

### P3｜land_detail 萃取品質（部分修復 ⚠）

- **現況**：`land_detail.json` 萃取邏輯已重寫（v11），但萃取品質仍不理想
- **根本原因**：PDF 版面複雜，兩種不同 column 格式混用，且 follow-line 數據分布不一致
- **2026-06-14 修復內容**：
  1. skip pattern bug：clean() 在中文間加空格導致 header 比對失效 → 改用 is_header_line() 直接比對原始字串
  2. 多人 block 問題：同一人在 PDF 中出現 2 次「申報人姓名」導致部分土地被錯誤歸屬 → 改為不 deduplicate person markers，依 name 合併
  3. 新舊雙格式支援：舊格式（len>=100）vs 新格式（len~79+111 pair）
- **萃取結果**（v11，共 28 期，共 14,640 筆）：
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
| 2026-06-14 | P3 land_detail 萃取重寫 | 重寫萃取邏輯（extract_land_v11.py），修復 skip bug、多人 block、新舊雙格式支援，14,640 筆（commit 0ccd2aa） |
| 2026-06-13 | 4個 detail JSON key 錯誤 | deposit/jewelry/cash/ship_detail.json 頂層 key 從 holder 改為 current_person（commit 94060df） |
| 2026-06-13 | 前端 showPersonAssetDetail 統計漏算 ntd_amount | 統計 now sums price/ntd_amount/total/balance（commit 58d9deb） |
| 2026-06-13 | ship_detail.json 假資料 | 全部 28 期 PDF 船舶欄位均為「本欄空白」，舊 149 筆為錯誤萃取，已清除 |
| 2026-06-13 | 卡片 +N 展開按鈕無作用 | 改為可點擊，點擊後展開顯示其餘所有財產類別（commit be9551a） |
| 2026-06-13 | 車輛萃取跨頁漏抓 | vehicle 從 747→1,087 輛（+45%），fix cross-page section handling（commit e59bbc5） |
| 2026-06-13 | P1 珠寶 price 萃取 | jewelry 從 46,625 筆（2%有價格）→1,252 筆（100%有價格），過濾金融商品 artifact、保險項目（commit 4e08b67） |

---

## 資料筆數現況（2026-06-14）

| 檔案 | 筆數 | 備註 |
|------|------|------|
| land_detail.json | 14,640 | ⚠ 部分修復（84%有rights，11%有area） |
| deposit_detail.json | 35,657 | ✅ 正常 |
| jewelry_detail.json | 1,252 | ✅ 已修復（100%有價格） |
| securities_detail.json | 4,121 | ✅ 正常 |
| insurance_detail.json | 5,857 | ✅ 正常 |
| credit_detail.json | 4,884 | ✅ 正常 |
| investment_detail.json | 1,761 | ✅ 正常 |
| debt_detail.json | 963 | ✅ 正常 |
| cash_detail.json | 312 | ✅ 正常 |
| vehicle_detail.json | 1,087 | ✅ 已修復 |
| ship_detail.json | 0 | ✅ 正確（PDF 全為空白） |
| aircraft_detail.json | 0 | ✅ 正確（PDF 全為空白） |

## 目前待修
- 無緊急問題（P3 部分修復後已趨於穩定）