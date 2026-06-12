let dataset = null;
let securitiesData = null;
let debtData = null;
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
    const secResp = await fetch('data/securities_detail.json');
    if (secResp.ok) {
      securitiesData = await secResp.json();
    }
    const debtResp = await fetch('data/debt_detail.json');
    if (debtResp.ok) {
      debtData = await debtResp.json();
    }
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
      record.full_text || '',
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
  setTimeout(bindChartClicks, 0);
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
  const keys = MAIN_ASSET_ORDER.filter(key => record.asset_flags[key]);
  const items = keys.map(key => ({ key, name: dataset.asset_labels[key] }));

  if (!items.length) {
    parent.textContent = '未解析';
  } else {
    items.slice(0, limit).forEach(({ key, name }) => {
      const el = appendText(parent, 'span', 'tag', name);
      el.dataset.key = key;
      el.style.cursor = 'pointer';
      el.title = `點擊查看「${name}」詳細資料`;
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        openAssetModal(key, record);
      });
    });
    if (items.length > limit) {
      const more = appendText(parent, 'span', 'tag more-tag', `+${items.length - limit}`);
      more.title = `還有 ${items.length - limit} 種類型`;
    }
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


// ── 資產類別詳情彈出視窗 ──
const modal = document.getElementById('assetModal');
const modalTitle = document.getElementById('modalTitle');
const modalSubtitle = document.getElementById('modalSubtitle');
const modalStats = document.getElementById('modalStats');
const modalSectionTitle = document.getElementById('modalSectionTitle');
const modalRecords = document.getElementById('modalRecords');

// ── Detail JSON lazy-load cache ──
const detailCache = {};
const DETAIL_FILES = {
  land: 'data/land_detail.json',
  vehicle: 'data/vehicle_detail.json',
  insurance: 'data/insurance_detail.json',
  investment: 'data/investment_detail.json',
  jewelry: 'data/jewelry_detail.json',
  cash: 'data/cash_detail.json',
  credit: 'data/credit_detail.json',
  securities: 'data/securities_detail.json',
  deposit: 'data/deposit_detail.json',
  debt: 'data/debt_detail.json',
  ship: 'data/ship_detail.json',
};

async function loadDetail(key) {
  if (detailCache[key] !== undefined) return detailCache[key];
  const path = DETAIL_FILES[key];
  if (!path) { detailCache[key] = null; return null; }
  try {
    const resp = await fetch(path);
    detailCache[key] = resp.ok ? await resp.json() : null;
  } catch(e) { detailCache[key] = null; }
  return detailCache[key];
}

async function getPersonDetail(personName, assetKey) {
  const json = await loadDetail(assetKey);
  if (!json) return [];
  const results = [];
  for (const issueKey in json) {
    const persons = json[issueKey];
    if (persons && typeof persons === 'object' && !Array.isArray(persons)) {
      const data = persons[personName];
      if (data) results.push({ issue: parseInt(issueKey), data });
    }
  }
  return results;
}

function openAssetModal(assetKey, personRecord) {
  var isPersonMode = !!personRecord;
  var label = dataset.asset_labels[assetKey] || assetKey;
  var isMoney = MONEY_ORDER.includes(assetKey);
  var records = filteredRecords.filter(function(r){ return r.asset_flags[assetKey]; });

  modalTitle.textContent = isPersonMode ? personRecord.name + ' 的 ' + label : label;
  modalSubtitle.textContent = isPersonMode
    ? personRecord.title + ' · ' + personRecord.agency
    : records.length + ' 人次持有';

  modalStats.innerHTML = '';
  modalRecords.innerHTML = '';
  modalSectionTitle.textContent = '';

  if (isPersonMode) {
    showPersonAssetDetail(personRecord.name, assetKey, label);
  } else {
    var uniquePeople = new Set(records.map(function(r){ return r.name; })).size;
    var totalAmount = sum(records, function(r){ return r.asset_totals[assetKey] || 0; });
    var iss = isMoney
      ? formatMoney(totalAmount)
      : [...new Set(records.map(function(r){ return r.issue; }))].length + ' 期';
    [
      { label: '持有人次', value: formatNumber(records.length), note: '申報時有填寫此類資產' },
      { label: '人數', value: formatNumber(uniquePeople), note: '去重後人數' },
      { label: isMoney ? '加總總額' : '涵蓋期別', value: iss, note: isMoney ? '加總該欄位總額' : '有記錄的最早至最新' },
    ].forEach(function(s) {
      var el2 = document.createElement('div');
      el2.className = 'modal-stat';
      el2.innerHTML = '<span class="modal-stat-label">' + s.label + '</span><strong class="modal-stat-value">' + s.value + '</strong><span class="modal-stat-note">' + s.note + '</span>';
      modalStats.appendChild(el2);
    });
    var list = document.createElement('div');
    list.className = 'modal-record-list';
    var sorted = records.slice().sort(function(a, b) {
      var va = isMoney ? (a.asset_totals[assetKey] || 0) : (a.disclosed_amount_total || 0);
      var vb = isMoney ? (b.asset_totals[assetKey] || 0) : (b.disclosed_amount_total || 0);
      return vb - va;
    }).slice(0, 20);
    sorted.forEach(function(r) {
      var row = document.createElement('div');
      row.className = 'modal-record-row';
      var amt = isMoney ? r.asset_totals[assetKey] : r.disclosed_amount_total;
      var pIssues = [...new Set(records.filter(function(x){ return x.name === r.name; }).map(function(x){ return x.issue; }))].sort(function(a,b){ return b-a; });
      row.innerHTML = '<div><div class="modal-record-name">' + r.name + '</div><div class="modal-record-meta">' + r.title + ' · ' + r.position_group + ' · 第 ' + pIssues.slice(0,3).join('/') + ' 期</div></div><div class="modal-record-amount">' + (amt ? formatMoney(amt) : '未列總額') + '</div>';
      list.appendChild(row);
    });
    modalRecords.appendChild(list);
  }
  modal.hidden = false;
  document.body.style.overflow = 'hidden';
}

async function showPersonAssetDetail(personName, assetKey, label) {
  var details = await getPersonDetail(personName, assetKey);
  var list = document.createElement('div');
  list.className = 'modal-record-list';

  var totalItems = 0, totalAmount = 0;
  details.forEach(function(d) {
    if (!d.data) return;
    if (Array.isArray(d.data)) {
      totalItems += d.data.length;
      d.data.forEach(function(i){ if(i.amount) totalAmount+=parseFloat(i.amount)||0; if(i.price) totalAmount+=parseFloat(i.price)||0; });
    } else if (d.data.items) {
      totalItems += d.data.items.length;
      d.data.items.forEach(function(i){ if(i.amount) totalAmount+=parseFloat(i.amount)||0; if(i.price) totalAmount+=parseFloat(i.price)||0; });
    } else if (d.data.land) { totalItems += d.data.land.length; }
    if (d.data.total) totalAmount += parseFloat(d.data.total)||0;
  });

  [
    { label: '期別數', value: details.length + ' 期', note: '有記錄的期別' },
    { label: '總筆數', value: formatNumber(totalItems), note: '明細筆數加總' },
    { label: '估計總額', value: totalAmount > 0 ? formatMoney(totalAmount) : '-', note: '已解析金額（僅供參考）' },
  ].forEach(function(s) {
    var el2 = document.createElement('div');
    el2.className = 'modal-stat';
    el2.innerHTML = '<span class="modal-stat-label">' + s.label + '</span><strong class="modal-stat-value">' + s.value + '</strong><span class="modal-stat-note">' + s.note + '</span>';
    modalStats.appendChild(el2);
  });

  modalSectionTitle.textContent = '第 292–319 期明細（共 ' + details.length + ' 期有記錄）';

  if (!details.length) {
    list.innerHTML = '<div style="padding:16px;color:var(--muted);text-align:center">無明細記錄</div>';
    modalRecords.appendChild(list);
    return;
  }

  details.forEach(function(d2) {
    if (!d2.data) return;
    renderDetailRows(personName, assetKey, d2.issue, d2.data, list);
  });

  modalRecords.appendChild(list);
}

function renderDetailRows(personName, assetKey, issue, data, list) {
  var h = function(s){ return String(s).replace(/&/g,'&').replace(/</g,'<').replace(/>/g,'>').replace(/"/g,'"'); };

  function mkrow(left, right, extraStyle) {
    var d = document.createElement('div');
    d.className = 'modal-record-row';
    if (extraStyle) d.setAttribute('style', extraStyle);
    d.appendChild(left);
    if (right) d.appendChild(right);
    return d;
  }

  function mkdiv(cls, txt) {
    var e = document.createElement('div');
    if (cls) e.className = cls;
    if (txt) e.textContent = txt;
    return e;
  }

  function left(name, meta) {
    var d = document.createElement('div');
    d.appendChild(mkdiv('modal-record-name', name));
    if (meta) d.appendChild(mkdiv('modal-record-meta', meta));
    return d;
  }

  function amtDiv(amount) {
    var e = document.createElement('div');
    e.className = 'modal-record-amount';
    e.textContent = amount;
    return e;
  }

  if (assetKey === 'land') {
    (data.land || []).forEach(function(item) {
      var loc = (item.location||'').replace(/\s+/g,' ').trim();
      var rights = item.rights || '';
      var price = item.price ? formatMoney(parseFloat(item.price)) : '-';
      var reason = item.acquisition_reason || '';
      var area = item.area || '';
      var d = mkrow(null, null, 'display:block');
      d.appendChild(mkdiv('modal-record-name', '📍 '+(loc.slice(0,42)||'（未解析）')+(rights?' · '+rights:'')));
      d.appendChild(mkdiv('modal-record-meta', (area?'面積: '+area+' · ':'')+(reason?reason+' · ':'')+'第'+issue+'期'));
      d.appendChild(mkdiv('', '💰 '+price));
      list.appendChild(d);
    });

  } else if (assetKey === 'vehicle') {
    (data.items || []).forEach(function(item) {
      var brand = item.brand || '（未解析）';
      var cc = item.cc ? ' '+item.cc+'cc' : '';
      var amount = item.amount ? formatMoney(item.amount) : '-';
      var acq = item.acquisition_date || '';
      list.appendChild(mkrow(left('🚗 '+h(brand+cc), acq||'第'+issue+'期'), amtDiv(amount)));
    });

  } else if (assetKey === 'insurance') {
    (data.items || []).forEach(function(item) {
      var company = item.company || '（未解析）';
      var policy = item.policy || '（未解析）';
      var period = item.period || '';
      var amount = (item.amount||item.price) ? formatMoney(parseFloat(item.amount||item.price)) : '-';
      list.appendChild(mkrow(left('🏦 '+h(company), '保單: '+h(policy)+' · '+(period||'第'+issue+'期')), amtDiv(amount)));
    });

  } else if (assetKey === 'investment') {
    var idata = Array.isArray(data) ? data : (data ? [data] : []);
    idata.forEach(function(item) {
      var company = item.company_name || '（未解析）';
      var addr = item.company_address || '';
      var amount = item.amount ? formatMoney(parseFloat(item.amount)) : '-';
      var time = item.acquisition_time || '';
      list.appendChild(mkrow(left('🏢 '+h(company), (addr?h(addr)+' · ':'')+(time||'第'+issue+'期')), amtDiv(amount)));
    });

  } else if (assetKey === 'jewelry') {
    (data.items || []).forEach(function(item) {
      var type = item.type || '珠寶/古董/字畫';
      var cnt = item.count || '1';
      var price = item.price ? formatMoney(item.price) : '-';
      list.appendChild(mkrow(left('💎 '+h(type)+' × '+cnt, '第'+issue+'期'), amtDiv(price)));
    });

  } else if (assetKey === 'cash') {
    (data.items || []).forEach(function(item) {
      var currency = item.currency || '未解析';
      var amount = (item.amount||item.total) ? formatMoney(parseFloat(item.amount||item.total)) : '-';
      list.appendChild(mkrow(left('💵 '+h(currency), '第'+issue+'期'), amtDiv(amount)));
    });

  } else if (assetKey === 'securities') {
    var sec = [...(data.stock||[]), ...(data.bond||[]), ...(data.fund||[])];
    sec.forEach(function(item) {
      var isStock = data.stock && data.stock.indexOf(item) !== -1;
      var isFund = data.fund && data.fund.indexOf(item) !== -1;
      var icon = isStock ? '💹 股票' : (isFund ? '📊 基金' : '📄 債券');
      var name = item.name || '（未解析）';
      var amount = item.amount ? formatMoney(item.amount) : '-';
      var extra = item.shares ? ' '+item.shares.toLocaleString()+' 股' : (item.units ? ' '+item.units.toLocaleString()+' 單位' : '');
      list.appendChild(mkrow(left(icon+'：'+h(name), extra+' 第'+issue+'期'), amtDiv(amount)));
    });

  } else if (assetKey === 'debt') {
    (data.items || []).forEach(function(item) {
      var creditor = (item.creditor||'（未解析）').replace(/\s+/g,' ').trim();
      var amount = item.amount ? formatMoney(item.amount) : '-';
      list.appendChild(mkrow(left('📋 '+h(creditor.slice(0,40)), '第'+issue+'期'), amtDiv(amount)));
    });

  } else if (assetKey === 'credit') {
    (Array.isArray(data) ? data : []).forEach(function(item) {
      var creditor = item.creditor || '（未解析）';
      var debtor = item.debtor || '（未解析）';
      var balance = item.balance ? formatMoney(parseFloat(item.balance)) : '-';
      list.appendChild(mkrow(left('🔑 債權人：'+h(creditor), '債務人：'+h(debtor)+' · 第'+issue+'期'), amtDiv(balance)));
    });

  } else if (assetKey === 'ship') {
    (data.items || []).forEach(function(item) {
      var kind = item.kind || '船舶';
      var tons = item.tons || '';
      var port = item.port || '';
      var amount = item.amount ? formatMoney(parseFloat(item.amount)) : '-';
      list.appendChild(mkrow(left('🚢 '+h(kind), (tons?'總噸數: '+tons+' · ':'')+(port?'船籍港: '+port+' · ':'')+'第'+issue+'期'), amtDiv(amount)));
    });

  } else if (assetKey === 'deposit') {
    (data.items || []).forEach(function(item) {
      var bank = item.bank || '（未解析）';
      var type = item.type || '';
      var ntd = item.ntd_amount ? formatMoney(item.ntd_amount) : '-';
      var foreign = item.foreign_amount ? ' 外幣 '+item.foreign_amount.toLocaleString() : '';
      list.appendChild(mkrow(left('🏦 '+h(bank), (type?type+' · ':'')+'第'+issue+'期'+foreign), amtDiv(ntd)));
    });

  } else {
    var d = mkrow(null, null, 'display:block;font-family:monospace;font-size:0.78rem;white-space:pre-wrap;max-width:420px;overflow:hidden');
    d.appendChild(mkdiv('modal-record-name', '第 '+issue+' 期'));
    d.appendChild(mkdiv('modal-record-meta', JSON.stringify(data).slice(0,160)));
    list.appendChild(d);
  }
}


function closeModal() {
  modal.hidden = true;
  document.body.style.overflow = '';
}

document.getElementById('modalClose').addEventListener('click', closeModal);
modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !modal.hidden) closeModal(); });

// ── 圖表點擊綁定（資產種類 + 金額圖） ──
function bindChartClicks() {
  document.querySelectorAll('#assetChart .bar-row, #moneyChart .bar-row').forEach(row => {
    const label = row.querySelector('.bar-label')?.textContent?.trim();
    if (!label) return;
    const btn = document.createElement('button');
    btn.className = 'chart-detail-btn';
    btn.textContent = '詳情';
    btn.style.cssText = 'font-size:0.75rem;padding:2px 8px;min-height:24px;width:auto;background:var(--accent);border-radius:999px;margin-left:8px;';
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      // 找出對應的 assetKey
      const key = MAIN_ASSET_ORDER.find(k => dataset.asset_labels[k] === label)
        || MONEY_ORDER.find(k => (dataset.money_asset_labels?.[k] || dataset.asset_labels[k]) === label);
      if (key) openAssetModal(key);
    });
    const header = row.querySelector('.bar-header');
    if (header) header.appendChild(btn);
  });
}

init();

