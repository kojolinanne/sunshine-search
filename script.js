let dataset = null;
let filteredRecords = [];
let activeGroup = 'party';
const groupPages = {};   // { [groupLabel]: currentPage }
const PAGE_SIZE = 100;
const MAIN_ASSET_ORDER = [
  'land', 'building', 'vehicle', 'deposit', 'securities', 'insurance',
];

const els = {
  searchInput: document.getElementById('searchInput'),
  issueFilter: document.getElementById('issueFilter'),
  partyFilter: document.getElementById('partyFilter'),
  positionFilter: document.getElementById('positionFilter'),
  assetFilter: document.getElementById('assetFilter'),
  resetBtn: document.getElementById('resetBtn'),
  metrics: document.getElementById('metrics'),
  positionChart: document.getElementById('positionChart'),
  partyChart: document.getElementById('partyChart'),
  assetChart: document.getElementById('assetChart'),
  moneyChart: document.getElementById('moneyChart'),
  moneyChartTitle: document.getElementById('moneyChartTitle'),
  positionTotal: document.getElementById('positionTotal'),
  partyTotal: document.getElementById('partyTotal'),
  assetTotal: document.getElementById('assetTotal'),
  filterSummary: document.getElementById('filterSummary'),
  sourceRecordCount: document.getElementById('sourceRecordCount'),
  recordCount: document.getElementById('recordCount'),
  groupList: document.getElementById('groupList'),
  groupTabs: [...document.querySelectorAll('[data-group]')],
};

function renderGroupedList() {
  const groups = buildGroups(activeGroup);
  const totalItems = groups.reduce((total, group) => total + group.records.length, 0);
  const maxCount = Math.max(...groups.map(group => group.records.length), 1);
  els.groupList.innerHTML = '';
  els.recordCount.textContent = groups.length
    ? `${formatNumber(groups.length)} 個群組，${formatNumber(totalItems)} 筆`
    : '沒有符合條件的資料';

  if (!groups.length) {
    appendText(els.groupList, 'p', 'empty-group', '沒有符合條件的申報資料');
    return;
  }

  groups.forEach(group => {
    // 初始化或重置每組的頁碼（篩選條件改變時重置）
    if (groupPages[group.label] === undefined) groupPages[group.label] = 1;
    const totalPages = Math.ceil(group.records.length / PAGE_SIZE);
    const curPage = Math.min(groupPages[group.label], totalPages);
    const startIdx = (curPage - 1) * PAGE_SIZE;
    const endIdx = startIdx + PAGE_SIZE;
    const pageRecords = group.records.slice(startIdx, endIdx);

    const card = document.createElement('article');
    card.className = 'group-card';

    const header = document.createElement('div');
    header.className = 'group-header';

    const titleWrap = document.createElement('div');
    titleWrap.className = 'group-title-wrap';
    if (activeGroup === 'party') {
      appendPartyBadge(titleWrap, group.label, 'group-party-badge');
    } else {
      appendText(titleWrap, 'strong', 'group-title', group.label);
    }
    appendText(titleWrap, 'span', 'group-subtitle', `${formatNumber(group.records.length)} 筆申報 · ${formatNumber(group.uniquePeople)} 人`);

    const amountWrap = document.createElement('div');
    amountWrap.className = 'group-amounts';
    appendText(amountWrap, 'span', 'amount-label', getAmountLabel());
    appendText(amountWrap, 'strong', 'amount-value', formatMoney(group.amount));
    appendText(amountWrap, 'span', 'debt-value', `債務 ${formatMoney(group.debt)}`);

    header.append(titleWrap, amountWrap);

    const track = document.createElement('div');
    track.className = 'group-track';
    const fill = document.createElement('div');
    fill.className = 'group-fill';
    fill.style.width = `${Math.max(4, (group.records.length / maxCount) * 100)}%`;
    if (activeGroup === 'party') fill.style.background = getPartyStyle(group.label).color;
    track.appendChild(fill);

    // 本頁記錄卡片
    const records = document.createElement('div');
    records.className = 'record-card-grid';
    pageRecords.forEach(record => records.appendChild(createRecordCard(record)));

    // 分頁導航
    if (totalPages > 1) {
      const pager = document.createElement('div');
      pager.className = 'pagination';

      const prev = document.createElement('button');
      prev.textContent = '◀ 上一頁';
      prev.disabled = curPage <= 1;
      prev.className = 'page-btn';
      prev.addEventListener('click', () => {
        groupPages[group.label] = curPage - 1;
        renderGroupedList();
        scrollToCard(card);
      });

      // 頁碼按鈕（最多顯示 5 個）
      const pageNums = getPageNumbers(curPage, totalPages);
      pageNums.forEach(p => {
        const btn = document.createElement('button');
        btn.textContent = p === curPage ? `● ${p}` : p === '...' ? '…' : p;
        btn.className = `page-btn${p === curPage ? ' active' : ''}${p === '...' ? ' ellipsis' : ''}`;
        btn.disabled = p === '...' || p === curPage;
        if (p !== '...' && p !== curPage) {
          btn.addEventListener('click', () => {
            groupPages[group.label] = Number(p);
            renderGroupedList();
            scrollToCard(card);
          });
        }
        pager.appendChild(btn);
      });

      const next = document.createElement('button');
      next.textContent = '下一頁 ▶';
      next.disabled = curPage >= totalPages;
      next.className = 'page-btn';
      next.addEventListener('click', () => {
        groupPages[group.label] = curPage + 1;
        renderGroupedList();
        scrollToCard(card);
      });

      pager.appendChild(prev);
      pager.appendChild(next);
      records.appendChild(pager);
    }

    card.append(header, track, records);
    els.groupList.appendChild(card);
  });
}
const MONEY_ORDER = ['deposit', 'securities', 'business', 'claim', 'cash', 'valuable', 'virtual_asset'];
const PARTY_STYLES = {
  '中國國民黨': { className: 'party-kmt', color: '#1d4ed8' },
  '民主進步黨': { className: 'party-dpp', color: '#15803d' },
  '台灣民眾黨': { className: 'party-tpp', color: '#14b8a6' },
  '時代力量': { className: 'party-npp', color: '#eab308' },
  '親民黨': { className: 'party-pfp', color: '#f97316' },
  '台灣基進': { className: 'party-tsp', color: '#7c3aed' },
  '無黨籍': { className: 'party-independent', color: '#64748b' },
  '未標註': { className: 'party-unknown', color: '#94a3b8' },
};

function getPageNumbers(cur, total) {
  if (total <= 7) return Array.from({length: total}, (_, i) => i + 1);
  const pages = [];
  pages.push(1);
  if (cur > 4) pages.push('...');
  for (let i = Math.max(2, cur - 2); i <= Math.min(total - 1, cur + 2); i++) pages.push(i);
  if (cur < total - 3) pages.push('...');
  pages.push(total);
  return pages;
}

function scrollToCard(card) {
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function init() {
  try {
    const resp = await fetch('data/declarations.json');
    if (!resp.ok) throw new Error(`資料載入失敗：${resp.status}`);
    dataset = await resp.json();
    els.sourceRecordCount.textContent = `${formatNumber(dataset.metadata.record_count)} 筆申報表`;
    populateFilters();
    bindEvents();
    applyFilters();
  } catch (err) {
    els.metrics.textContent = '資料載入失敗';
    els.metrics.classList.add('error');
    console.error(err);
  }
}

function bindEvents() {
  els.searchInput.addEventListener('input', applyFilters);
  [els.issueFilter, els.partyFilter, els.positionFilter, els.assetFilter]
    .forEach(el => el.addEventListener('change', applyFilters));
  els.groupTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      activeGroup = tab.dataset.group;
      els.groupTabs.forEach(item => item.classList.toggle('is-active', item === tab));
      renderGroupedList();
    });
  });
  els.resetBtn.addEventListener('click', () => {
    els.searchInput.value = '';
    els.issueFilter.value = 'all';
    els.partyFilter.value = 'all';
    els.positionFilter.value = 'all';
    els.assetFilter.value = 'all';
    applyFilters();
  });
}

function populateFilters() {
  setOptions(els.issueFilter, '全部期數', unique(dataset.records.map(record => record.issue)).sort((a, b) => b - a), issue => `第 ${issue} 期`);
  setOptions(els.partyFilter, '全部政黨', Object.keys(dataset.summary.parties));
  setOptions(els.positionFilter, '全部職務', Object.keys(dataset.summary.positions));
  setOptions(
    els.assetFilter,
    '全部資產種類',
    MAIN_ASSET_ORDER.filter(key => dataset.asset_labels[key]),
    key => dataset.asset_labels[key],
  );
}

function setOptions(select, allLabel, values, labeler = value => value) {
  select.innerHTML = '';
  const all = document.createElement('option');
  all.value = 'all';
  all.textContent = allLabel;
  select.appendChild(all);

  values.forEach(value => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = labeler(value);
    select.appendChild(option);
  });
}

function applyFilters() {
  const query = normalize(els.searchInput.value);
  const issue = els.issueFilter.value;
  const party = els.partyFilter.value;
  const position = els.positionFilter.value;
  const asset = els.assetFilter.value;

  filteredRecords = dataset.records.filter(record => {
    const queryText = normalize([
      record.name, record.agency, record.title, record.party, record.declaration_type,
    ].join(' '));

    return (!query || queryText.includes(query))
      && (issue === 'all' || String(record.issue) === issue)
      && (party === 'all' || record.party === party)
      && (position === 'all' || record.position_group === position)
      && matchesAssetFilter(record, asset);
  });

  render();
}

function render() {
  renderFilterSummary();
  renderMetrics();
  renderCharts();
  renderGroupedList();
}

function renderFilterSummary() {
  const labels = [];
  if (els.issueFilter.value !== 'all') labels.push(`第 ${els.issueFilter.value} 期`);
  if (els.partyFilter.value !== 'all') labels.push(els.partyFilter.value);
  if (els.positionFilter.value !== 'all') labels.push(els.positionFilter.value);
  if (els.assetFilter.value !== 'all') labels.push(getAssetFilterLabel(els.assetFilter.value));
  if (els.searchInput.value.trim()) labels.push(`含「${els.searchInput.value.trim()}」`);
  els.filterSummary.textContent = labels.length ? labels.join(' / ') : '全部資料';
}

function matchesAssetFilter(record, asset) {
  if (asset === 'all') return true;
  return Boolean(record.asset_flags[asset]);
}

function getAssetFilterLabel(asset) {
  return dataset.asset_labels[asset] || asset;
}

function getActiveAmount(record) {
  return getActiveAmountValue(record) || 0;
}

function getActiveAmountValue(record) {
  const asset = els.assetFilter.value;
  if (MONEY_ORDER.includes(asset)) {
    return record.asset_totals[asset] || null;
  }
  return record.disclosed_amount_total;
}

function getAmountLabel() {
  const asset = els.assetFilter.value;
  if (MONEY_ORDER.includes(asset)) return `${getAssetFilterLabel(asset)}金額`;
  return '已解析金額';
}

function getAmountNote() {
  const asset = els.assetFilter.value;
  if (MONEY_ORDER.includes(asset)) return `只加總${getAssetFilterLabel(asset)}總額欄位`;
  return '只加總有總額欄位的資產';
}

function renderMetrics() {
  const uniquePeople = new Set(filteredRecords.map(record => record.name)).size;
  const totalAmount = sum(filteredRecords, getActiveAmount);
  const totalDebt = sum(filteredRecords, record => record.debt_total || 0);
  const markedParties = filteredRecords.filter(record => record.party !== '未標註').length;

  const metrics = [
    ['申報表', formatNumber(filteredRecords.length), '每份申報表算一筆'],
    ['申報人', formatNumber(uniquePeople), '同一人跨期只算一人'],
    [getAmountLabel(), formatMoney(totalAmount), getAmountNote()],
    ['債務', formatMoney(totalDebt), '獨立列示，不從資產扣除'],
    ['有政黨來源', `${formatNumber(markedParties)} 筆`, '沒有來源就列未標註'],
  ];

  els.metrics.innerHTML = '';
  metrics.forEach(([label, value, note]) => {
    const item = document.createElement('article');
    item.className = 'metric';
    appendText(item, 'span', 'metric-label', label);
    appendText(item, 'strong', 'metric-value', value);
    appendText(item, 'span', 'metric-note', note);
    els.metrics.appendChild(item);
  });
}

function renderCharts() {
  const positions = countBy(filteredRecords, record => record.position_group);
  const parties = countBy(filteredRecords, record => record.party);
  const assetHolders = MAIN_ASSET_ORDER
    .filter(key => dataset.asset_labels[key])
    .map(key => [dataset.asset_labels[key], filteredRecords.filter(record => record.asset_flags[key]).length])
    .filter(([, value]) => value > 0);
  const moneyTotals = MONEY_ORDER
    .map(key => [dataset.money_asset_labels?.[key] || dataset.asset_labels[key], sum(filteredRecords, record => record.asset_totals[key] || 0)])
    .filter(([label, value]) => label && value > 0);

  els.positionTotal.textContent = `${formatNumber(filteredRecords.length)} 筆`;
  els.partyTotal.textContent = `${formatNumber(filteredRecords.length)} 筆`;
  els.assetTotal.textContent = `${formatNumber(filteredRecords.length)} 筆`;

  const total = Math.max(filteredRecords.length, 1);
  renderBarChart(els.positionChart, positions, value => `${formatNumber(value)} 筆 · ${formatPercent(value / total)}`, { limit: 7 });
  renderBarChart(els.partyChart, parties, value => `${formatNumber(value)} 筆 · ${formatPercent(value / total)}`, { limit: 6, palette: 'party' });
  renderBarChart(els.assetChart, assetHolders, value => `${formatNumber(value)} 人次`, { limit: 8 });
  els.moneyChartTitle.textContent = getAmountLabel();
  renderBarChart(els.moneyChart, getMoneyChartEntries(moneyTotals), formatMoney, { limit: 7 });
}

function getMoneyChartEntries(defaultEntries) {
  const asset = els.assetFilter.value;
  if (MONEY_ORDER.includes(asset)) {
    return [[getAssetFilterLabel(asset), sum(filteredRecords, getActiveAmount)]].filter(([, value]) => value > 0);
  }
  return defaultEntries;
}

function renderBarChart(container, entries, formatter, options = {}) {
  container.innerHTML = '';
  const sorted = collapseEntries([...entries].sort((a, b) => b[1] - a[1]), options.limit || 8);
  const max = Math.max(...sorted.map(([, value]) => value), 1);

  if (!sorted.length) {
    appendText(container, 'p', 'empty', '沒有符合條件的資料');
    return;
  }

  sorted.forEach(([label, value]) => {
    const row = document.createElement('div');
    row.className = 'bar-row';

    const header = document.createElement('div');
    header.className = 'bar-header';
    if (options.palette === 'party') {
      appendPartyBadge(header, label, 'bar-party');
    } else {
      appendText(header, 'span', 'bar-label', label);
    }
    appendText(header, 'span', 'bar-value', formatter(value));

    const track = document.createElement('div');
    track.className = 'bar-track';
    const fill = document.createElement('div');
    fill.className = 'bar-fill';
    if (options.palette === 'party') {
      fill.style.background = getPartyStyle(label).color;
    }
    fill.style.width = `${Math.max(3, (value / max) * 100)}%`;
    track.appendChild(fill);

    row.append(header, track);
    container.appendChild(row);
  });
}

function collapseEntries(entries, limit) {
  if (entries.length <= limit) return entries;
  const visible = entries.slice(0, limit - 1);
  const rest = entries.slice(limit - 1).reduce((total, [, value]) => total + value, 0);
  if (rest > 0) visible.push(['其他', rest]);
  return visible;
}


function buildGroups(mode) {
  const map = new Map();

  filteredRecords.forEach(record => {
    getGroupLabels(record, mode).forEach(label => {
      if (!map.has(label)) map.set(label, []);
      map.get(label).push(record);
    });
  });

  return [...map.entries()]
    .map(([label, records]) => ({
      label,
      records: [...records].sort((a, b) => getActiveAmount(b) - getActiveAmount(a)),
      uniquePeople: new Set(records.map(record => record.name)).size,
      amount: sum(records, getActiveAmount),
      debt: sum(records, record => record.debt_total || 0),
    }))
    .sort((a, b) => b.amount - a.amount || b.records.length - a.records.length || String(a.label).localeCompare(String(b.label), 'zh-Hant'));
}

function getGroupLabels(record, mode) {
  if (mode === 'party') return [record.party];
  if (mode === 'position') return [record.position_group];
  if (mode === 'issue') return [`第 ${record.issue} 期`];
  if (mode === 'asset') {
    const assets = MAIN_ASSET_ORDER
      .filter(key => record.asset_flags[key])
      .map(key => dataset.asset_labels[key]);
    return assets.length ? assets : ['未解析'];
  }
  return ['其他'];
}

function createRecordCard(record) {
  const card = document.createElement('section');
  card.className = 'record-card';

  const head = document.createElement('div');
  head.className = 'record-head';
  appendText(head, 'strong', 'record-name', record.name);
  appendText(head, 'span', 'record-money', formatActiveMoney(record));

  const meta = document.createElement('div');
  meta.className = 'record-meta';
  appendText(meta, 'span', '', `${record.title} · ${record.position_group}`);
  appendText(meta, 'span', '', record.agency);

  const partyRow = document.createElement('div');
  partyRow.className = 'record-party-row';
  appendPartyBadge(partyRow, record.party);
  appendText(partyRow, 'span', 'issue-meta', `第 ${record.issue} 期 · ${formatDate(record.declaration_date)}`);

  const assets = document.createElement('div');
  assets.className = 'record-assets';
  appendAssetTags(assets, record, 5);

  const debt = document.createElement('div');
  debt.className = 'record-debt';
  debt.textContent = record.debt_total ? `債務 ${formatExactMoney(record.debt_total)}` : '債務未列總額';

  card.append(head, meta, partyRow, assets, debt);
  return card;
}

function appendAssetTags(parent, record, limit = 6) {
  const names = MAIN_ASSET_ORDER
    .filter(key => record.asset_flags[key])
    .map(key => dataset.asset_labels[key]);

  if (!names.length) {
    parent.textContent = '未解析';
  } else {
    names.slice(0, limit).forEach(name => appendText(parent, 'span', 'tag', name));
    if (names.length > limit) appendText(parent, 'span', 'tag more-tag', `+${names.length - limit}`);
  }
}

function appendText(parent, tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  el.textContent = text;
  parent.appendChild(el);
  return el;
}

function appendPartyBadge(parent, party, extraClass = '') {
  const badge = document.createElement('span');
  const style = getPartyStyle(party);
  badge.className = `party-badge ${style.className} ${extraClass}`.trim();
  badge.textContent = party;
  parent.appendChild(badge);
  return badge;
}

function getPartyStyle(party) {
  return PARTY_STYLES[party] || { className: 'party-other', color: '#7c3aed' };
}

function countBy(records, getter) {
  const counts = new Map();
  records.forEach(record => {
    const key = getter(record);
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  return [...counts.entries()];
}

function sum(records, getter) {
  return records.reduce((total, record) => total + getter(record), 0);
}

function unique(values) {
  return [...new Set(values)];
}

function normalize(value) {
  return String(value || '').replace(/\s+/g, '').toLowerCase();
}

function formatNumber(value) {
  return new Intl.NumberFormat('zh-TW').format(value);
}

function formatExactMoney(value) {
  if (!value) return '未列總額';
  return `NT$ ${formatNumber(value)}`;
}

function formatActiveMoney(record) {
  const value = getActiveAmountValue(record);
  return value ? formatMoney(value) : '未列總額';
}

function formatMoney(value) {
  if (!value) return 'NT$ 0';
  if (value >= 100000000) return `NT$ ${(value / 100000000).toFixed(1)} 億`;
  if (value >= 10000) return `NT$ ${(value / 10000).toFixed(0)} 萬`;
  return `NT$ ${formatNumber(value)}`;
}

function formatPercent(value) {
  return `${Math.round(value * 100)}%`;
}

function formatDate(value) {
  return value || '未解析日期';
}

init();
