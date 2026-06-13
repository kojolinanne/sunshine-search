# 廉政專刊陽光法案系統 - 待辦事項

最後更新：2026-06-13
PDF 期別：292–319（共 28 期）

---

## 待修復問題

### P1｜珠寶 detail price 大量為 null

- **現況**：`jewelry_detail.json` 共 46,625 筆，其中 45,736 筆（98%）`price` 為 `null`
- **原因**：`extract_jewelry_detail.py` 的 price 萃取門檻太高（需 `n >= 1000`），導致大量珠寶價格沒抓到
- **影響**：點進個人珠寶明細，幾乎全顯示「-」無金額
- **修復方向**：
  1. 修正 `extract_jewelry_detail.py` 的 price 萃取門檻
  2. 重新萃取 292–319 期
  3. 驗證 price 有值比例提升

---

### P2｜車輛 detail 筆數偏低

- **現況**：`vehicle_detail.json` 僅 747 筆，預期應有 1,500+
- **原因**：萃取腳本可能漏抓或格式解析有誤
- **影響**：少數車主的車輛資料不完整
- **修復方向**：
  1. review `extract_vehicle_detail.py` 的萃取邏輯
  2. 比對 PDF 原始文字與萃取結果
  3. 重新萃取

---

### P3｜land_detail 萃取品質（可延後）

- **現況**：`land_detail.json` 每筆土地被萃取成多個 fragment（1筆土地→17個錯誤 entry）
- **原因**：PDF 多欄 layout 導致文字被錯誤切割
- **影響**：土地筆數看起來很多（34,529），但摻雜大量無意義的 fragment
- **修復方向**：重寫版面處理邏輯，分欄識別重組後再萃取（工作量較大，可延後處理）

---

## 已完成修復

| 日期 | 問題 | 修復內容 |
|------|------|----------|
| 2026-06-13 | 4個 detail JSON key 錯誤 | deposit/jewelry/cash/ship_detail.json 頂層 key 從 holder 值改為人名（current_person），commit 94060df |
| 2026-06-13 | 前端 showPersonAssetDetail 統計漏算 ntd_amount | 統計 now sums price/ntd_amount/total/balance，commit 58d9deb |
| 2026-06-13 | ship_detail.json 假資料 | 全部 28 期 PDF 船舶欄位均為「本欄空白」，舊 149 筆為錯誤萃取，已清除 |
| 2026-06-13 | 卡片 +N 展開按鈕無作用 | 改為可點擊，點擊後展開顯示其餘所有財產類別，commit be9551a |
| 2026-06-13 | ship render 用錯欄位 | `item.kind`→`item.type`、`item.tons`→`item.tonnage`、`item.amount`→`item.price`，commit 58d9deb |

---

## 資料筆數現況（2026-06-13）

| 檔案 | 筆數 | 備註 |
|------|------|------|
| land_detail.json | 34,529 | ⚠ 有 fragment 問題 |
| deposit_detail.json | 35,657 | ✅ 正常（人名 key） |
| jewelry_detail.json | 46,625 | ⚠ price 98%為 null |
| cash_detail.json | 312 | ✅ 正常（人名 key） |
| ship_detail.json | 0 | ✅ 正確（PDF 全為空白） |
| vehicle_detail.json | 747 | ⚠ 偏低 |
| securities_detail.json | 4,121 | ✅ 正常 |
| insurance_detail.json | 5,857 | ✅ 正常 |
| credit_detail.json | 4,884 | ✅ 正常 |
| investment_detail.json | 1,761 | ✅ 正常 |
| debt_detail.json | 963 | ✅ 正常 |
| aircraft_detail.json | 0 | ✅ 正常（PDF 全為空白） |