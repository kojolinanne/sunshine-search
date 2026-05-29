# 🔍 廉政專刊搜尋

陽光法令主題網（第300期～第319期）靜態搜尋網站。

![demo](https://img.shields.io/badge/GitHub%20Pages-部署完成-brightgreen)

## 功能

- 全文關鍵字搜尋（懶載入，速快）
- 期數篩選
- 點期數卡可查該期內容
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
python3 extract_all.py        # 重新產生 data/
git add data/
git commit -m "新增第XXX期"
git push
```

## 技術棧

- 純前端（HTML + CSS + JS，無後端）
- Fuse.js 模糊搜尋（但目前用關鍵字匹配）
- GitHub Pages 托管
- 20 期、約 10M 字，Lazy-load 確保速度

## 授權

資料版權：監察院陽光法令主題網