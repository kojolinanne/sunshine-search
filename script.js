// 全域
let index = [];           // 期別索引（不含 full_text）
let loadedIssues = {};     // 已快取的 issue 資料 {issueNum: fullText}
let currentFilter = 'all';

const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const issueFilter = document.getElementById('issueFilter');
const resultsDiv = document.getElementById('results');
const noResults = document.getElementById('noResults');
const issueList = document.getElementById('issueList');
const resultCount = document.getElementById('resultCount');

// ─── 初始化 ───
async function init() {
  try {
    const resp = await fetch('data/index.json');
    index = await resp.json();

    // 期數下拉選單
    const sorted = [...index].sort((a, b) => b.issue - a.issue);
    sorted.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d.issue;
      opt.textContent = `第 ${d.issue} 期`;
      issueFilter.appendChild(opt);
    });

    renderIssueList(index);
    updateResultCount();
  } catch (err) {
    resultsDiv.innerHTML = '<p style="color:red">資料載入失敗</p>';
    console.error(err);
  }
}

// ─── 搜尋 ───
async function doSearch() {
  const query = searchInput.value.trim();
  if (!query) {
    resultsDiv.innerHTML = '';
    noResults.style.display = 'none';
    issueList.style.display = 'grid';
    return;
  }

  issueList.style.display = 'none';
  resultsDiv.innerHTML = '<p style="color:#666;padding:20px">搜尋中...</p>';

  // 依篩選決定要查哪些期
  const targetIssues = index
    .filter(d => currentFilter === 'all' || d.issue === parseInt(currentFilter))
    .sort((a, b) => b.issue - a.issue);

  const matches = [];

  for (const meta of targetIssues) {
    // 確保已載入該期 full_text
    if (!loadedIssues[meta.issue]) {
      try {
        const resp = await fetch(`data/issue_${meta.issue}.json`);
        const data = await resp.json();
        loadedIssues[meta.issue] = data.full_text;
      } catch {
        loadedIssues[meta.issue] = '';
      }
    }

    const text = loadedIssues[meta.issue];
    const lower = text.toLowerCase();
    const qLower = query.toLowerCase();
    let idx = 0;
    let found = false;

    while ((idx = lower.indexOf(qLower, idx)) !== -1) {
      found = true;
      const start = Math.max(0, idx - 180);
      const end = Math.min(text.length, idx + query.length + 180);
      let snippet = (start > 0 ? '...' : '') + text.slice(start, end) + (end < text.length ? '...' : '');
      // 標記關鍵字（大小寫通用）
      const regex = new RegExp(escapeReg(query), 'gi');
      snippet = snippet.replace(regex, m => `<mark>${m}</mark>`);

      matches.push({ issue: meta.issue, snippet });
      if (matches.filter(m => m.issue === meta.issue).length >= 3) break; // 每期最多3筆
      idx += qLower.length;
    }
  }

  renderResults(matches);
}

function renderResults(results) {
  resultsDiv.innerHTML = '';
  resultCount.textContent = `找到 ${results.length} 筆結果`;

  if (results.length === 0) {
    noResults.style.display = 'block';
    return;
  }
  noResults.style.display = 'none';

  // 按期數分組顯示
  const byIssue = {};
  results.forEach(r => {
    if (!byIssue[r.issue]) byIssue[r.issue] = [];
    byIssue[r.issue].push(r.snippet);
  });

  Object.keys(byIssue).sort((a, b) => b - a).forEach(issue => {
    const card = document.createElement('div');
    card.className = 'result-card';

    const snippets = byIssue[issue].map(s =>
      `<div class="result-snippet">${s}</div>`
    ).join('');

    card.innerHTML = `
      <div class="result-header">
        <span class="result-issue">第 ${issue} 期</span>
        <span style="color:#666;font-size:0.85rem">${byIssue[issue].length} 筆相符</span>
      </div>
      ${snippets}
      <a class="result-link" href="https://sunshine.cy.gov.tw/News.aspx?n=17&sms=8861" target="_blank">
        📄 查看原始 PDF（第 ${issue} 期）
      </a>
    `;
    resultsDiv.appendChild(card);
  });
}

function renderIssueList(data) {
  issueList.style.display = 'grid';
  issueList.innerHTML = '';

  [...data].sort((a, b) => b.issue - a.issue).forEach(d => {
    const card = document.createElement('div');
    card.className = 'issue-card';
    card.innerHTML = `
      <h3>第 ${d.issue} 期</h3>
      <p class="chars">約 ${(d.total_chars / 1000).toFixed(0)}K 字</p>
      <p style="font-size:0.8rem;color:#666;margin-top:6px">陽光法令主題網</p>
    `;
    card.style.cursor = 'pointer';
    card.addEventListener('click', () => {
      searchInput.value = `第${d.issue}期`;
      doSearch();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    issueList.appendChild(card);
  });
}

function updateResultCount() {
  const total = index.reduce((s, d) => s + d.total_chars, 0);
  resultCount.textContent = `${index.length} 期、約 ${(total/1000).toFixed(0)}K 字`;
}

function escapeReg(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// 事件
searchBtn.addEventListener('click', doSearch);
searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
issueFilter.addEventListener('change', () => {
  currentFilter = issueFilter.value;
  doSearch();
});

// 啟動
init();