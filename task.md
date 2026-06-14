# 廉政專刊陽光法案系統 - 待辦事項

最後更新：2026-06-14
PDF 期別：292–319（共 28 期）

---

## 待修復問題

### P3｜land_detail 萃取品質（可延後）

- **現況**：`land_detail.json` 每筆土地被萃取成多個 fragment（1筆土地→17個錯誤 entry）
- **原因**：PDF 多欄 layout 導致文字被錯誤切割
- **影響**：土地筆數看起來很多（34,529），但摻雜大量無意義的 fragment
- **修復方向**：重寫版面處理邏輯，分欄識別重組後再萃取（工作量較大，可延後處理）

---

## 已完成修復

| 日期 | 問題 | 修復內容 |
|------|------|----------|
| 2026-06-13 | 4個 detail JSON key 錯誤 | deposit/jewelry/cash/ship_detail.json 頂層 key 從 holder 改為 current_person（commit 94060df） |
| 2026-06-13 | 前端 showPersonAssetDetail 統計漏算 ntd_amount | 統計 now sums price/ntd_amount/total/balance（commit 58d9deb） |
| 2026-06-13 | ship_detail.json 假資料 | 全部 28 期 PDF 船舶欄位均為「本欄空白」，舊 149 筆為錯誤萃取，已清除 |
| 2026-06-13 | 卡片 +N 展開按鈕無作用 | 改為可點擊，點擊後展開顯示其餘所有財產類別（commit be9551a） |
| 2026-06-13 | 車輛萃取跨頁漏抓 | vehicle 從 747→1,087 輛（+45%），fix cross-page section handling（commit e59bbc5） |
| 2026-06-13 | P1 珠寶 price 萃取 | jewelry 從 46,625 筆（2%有價格）→1,252 筆（100%有價格），過濾金融商品 artifact、保險項目（commit 4e08b67） |

---

## 資料筆數現況（2026-06-13）

| 檔案 | 筆數 | 備註 |
|------|------|------|
| land_detail.json | 34,529 | ⚠ 有 fragment 問題（P3） |
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
- **P3（可延後）**：land_detail fragment 問題（工作量較大）