# 公職人員財產申報統計

陽光法令主題網（第300期～第319期）公職人員財產申報資料統計網站。

![demo](https://img.shields.io/badge/GitHub%20Pages-部署完成-brightgreen)

## 功能

- 依期數、政黨、職務、資產種類篩選
- 統計申報筆數、申報人數、可讀金額與債務
- 以圖表呈現職務分布、政黨分布、持有資產種類與可讀金額合計
- 明細表可搜尋姓名、機關、職稱或政黨
- 響應式設計（手機可用）

## 部署方式

### 方法一：GitHub Pages（免費，5分鐘）

```bash
# 1. 在 GitHub 建立新 repo（例如 sunshine-search）
# 2. 在本機執行：
cd sunshine-search
gh repo create sunshine-search --public --push --source=.

# 或者手動：
# git remote add origin https://github.com/你的帳號/sunshine-search.git
# git branch -M gh-pages
# git push -u origin gh-pages
```

**然後在 GitHub 設定 GitHub Pages：**
> Settings → Pages → Source 選 `gh-pages` branch → Save

完成後就可在 `https://你的帳號.github.io/sunshine-search/` 存取。

### 方法二：本地測試

```bash
cd sunshine-search
python3 -m http.server 8080
# 開 http://localhost:8080
```

## 資料更新

如果需要處理新一期 PDF：

```bash
# 把新 PDF 放到 ~/Downloads/廉政專刊第XXX期.pdf
python3 extract_all.py        # 更新 data/issue_XXX.json、data/index.json、data/declarations.json
git add data/
git commit -m "新增第XXX期"
git push
```

`extract_all.py` 會處理 `~/Downloads` 內所有符合 `廉政專刊第XXX期.pdf` 的檔案，既有的分期 JSON 會保留，最後依 `data/issue_*.json` 重建索引與統計資料。執行前需先安裝 `pdftotext`。

也可以只更新單一 PDF：

```bash
python3 extract_text.py ~/Downloads/廉政專刊第XXX期.pdf
```

只重建統計資料：

```bash
python3 build_statistics.py
```

## 資料口徑

- `data/declarations.json` 是前端圖表與明細表使用的結構化資料。
- 金額合計只加總申報表已有「總金額」或「總價額」欄位的項目。
- 不動產、汽車、保險等常沒有總價欄位，因此只統計是否持有，不納入可讀金額合計。
- 政黨不是財產申報表欄位；目前只用 `data/party_map.json` 中可追溯來源標註，其餘顯示「未標註」。

## 技術棧

- 純前端（HTML + CSS + JS，無後端）
- Python 產生靜態 JSON 統計資料
- GitHub Pages 托管
- 20 期、約 10M 字，前端只載入統計 JSON

## 授權

資料版權：監察院陽光法令主題網
