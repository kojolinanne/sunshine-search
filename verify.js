#!/usr/bin/env node
/**
 * Sunshine Search Data Verification Script
 * - Build sorted party-grouped list (buildGroups('party') logic)
 * - Run integrity checks on all 1,496 records
 * - Output verification_people.md
 */

const fs = require('fs');
const path = require('path');

const DECL_PATH = path.join(__dirname, 'data/declarations.json');
const OUTPUT_PATH = path.join(__dirname, 'verification_people.md');

// ── Load data ──────────────────────────────────────────────────────────────
const data = JSON.parse(fs.readFileSync(DECL_PATH, 'utf8'));
const records = data.records;

console.log(`Loaded ${records.length} records`);

// ── Sorting helpers (mimic buildGroups('party')) ────────────────────────────
// In buildGroups('party') with no asset filter applied,
// getActiveAmount(record) returns record.disclosed_amount_total
// (MONEY_ORDER.includes('') === false)
function getActiveAmount(record) {
  return record.disclosed_amount_total || 0;
}

// ── Build party groups ──────────────────────────────────────────────────────
function buildPartyGroups(recs) {
  const map = new Map();
  recs.forEach(record => {
    const label = record.party || '未標註';
    if (!map.has(label)) map.set(label, []);
    map.get(label).push(record);
  });

  return [...map.entries()]
    .map(([label, recs]) => {
      const sorted = [...recs].sort((a, b) => getActiveAmount(b) - getActiveAmount(a));
      const amount = sorted.reduce((s, r) => s + getActiveAmount(r), 0);
      return { label, records: sorted, amount };
    })
    .sort((a, b) => {
      if (b.amount !== a.amount) return b.amount - a.amount;
      if (b.records.length !== a.records.length) return b.records.length - a.records.length;
      return String(a.label).localeCompare(String(b.label), 'zh-Hant');
    });
}

const groups = buildPartyGroups(records);

// ── Integrity checks ───────────────────────────────────────────────────────
const checkResults = [];
const ASSET_FLAG_KEYS = ['land','building','ship','vehicle','aircraft','cash','deposit','securities','valuable','insurance','virtual_asset','claim','business'];
const MONEY_ORDER = ['deposit','securities','business','claim','cash','valuable','virtual_asset'];

// asset_totals sum ≈ disclosed_amount_total  (1% tolerance)
function assetTotalsSum(record) {
  if (!record.asset_totals) return 0;
  return Object.values(record.asset_totals)
    .filter(v => v !== null && v !== undefined)
    .reduce((s, v) => s + v, 0);
}

function pctError(a, b) {
  if (!b) return a === 0 ? 0 : 100;
  return Math.abs(a - b) / b * 100;
}

// security_sections.stock.amount + fund.amount ≈ asset_totals.securities
function securitiesCheck(record) {
  if (!record.asset_totals || record.asset_totals.securities === null) return true; // N/A
  const stock = (record.security_sections && record.security_sections.stock && record.security_sections.stock.amount) || 0;
  const fund  = (record.security_sections && record.security_sections.fund  && record.security_sections.fund.amount)  || 0;
  const bond  = (record.security_sections && record.security_sections.bond  && record.security_sections.bond.amount)  || 0;
  const other = (record.security_sections && record.security_sections.other_security && record.security_sections.other_security.amount) || 0;
  const expected = stock + fund + bond + other;
  const actual = record.asset_totals.securities;
  return pctError(expected, actual) <= 1.0;
}

let passed = 0, failed = 0;
const failList = [];
const assetSumFails = [];

records.forEach((rec, idx) => {
  const issues = [];

  // 1. name non-empty
  if (!rec.name || rec.name.trim() === '') issues.push('name為空');

  // 2. issue is number
  if (typeof rec.issue !== 'number' || isNaN(rec.issue)) issues.push('issue非數字');

  // 3. disclosed_amount_total > 0
  if (typeof rec.disclosed_amount_total !== 'number' || rec.disclosed_amount_total <= 0)
    issues.push('disclosed_amount_total非正數');

  // 4. at least one asset_flags === true
  const anyAsset = ASSET_FLAG_KEYS.some(k => rec.asset_flags && rec.asset_flags[k] === true);
  if (!anyAsset) issues.push('無任何asset_flag為true');

  // 5. full_text non-empty
  if (!rec.full_text || rec.full_text.trim() === '') issues.push('full_text為空');

  // 6. full_text contains name
  if (rec.full_text && rec.name && !rec.full_text.includes(rec.name))
    issues.push('full_text未包含姓名');

  // 7. asset_totals sum ≈ disclosed_amount_total (1%)
  const atSum = assetTotalsSum(rec);
  const dat = rec.disclosed_amount_total || 0;
  if (atSum > 0 && pctError(atSum, dat) > 1.0)
    issues.push(`asset_totals總和(${atSum})與disclosed_amount_total(${dat})誤差>1%`);

  // 8. debt_total positive if present
  if (rec.debt_total !== null && rec.debt_total !== undefined && rec.debt_total < 0)
    issues.push('debt_total為負數');

  // 9. securities check
  if (!securitiesCheck(rec))
    issues.push('securities餘額與stock+fund總和不符');

  if (issues.length === 0) {
    passed++;
  } else {
    failed++;
    failList.push({ idx, name: rec.name, issue: rec.issue, party: rec.party, issues });
  }

  // track asset sum fails for top-5
  if (atSum > 0 && pctError(atSum, dat) > 1.0) {
    assetSumFails.push({ idx, name: rec.name, issue: rec.issue, atSum, dat, err: pctError(atSum, dat) });
  }
});

assetSumFails.sort((a, b) => b.err - a.err);
const topAssetFails = assetSumFails.slice(0, 5);

// ── Party statistics ─────────────────────────────────────────────────────────
const partyStats = groups.map(g => ({
  label: g.label,
  count: g.records.length,
  totalAmount: g.amount,
  avgAmount: g.amount / g.records.length,
}));

// ── Generate Markdown ───────────────────────────────────────────────────────
const now = new Date();
const generatedAt = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';

// Unique issues range
const allIssues = [...new Set(records.map(r => r.issue))].sort((a, b) => a - b);
const issueMin = Math.min(...allIssues);
const issueMax = Math.max(...allIssues);
const issueCount = allIssues.length;

function fmt(n) {
  return n.toLocaleString('zh-TW');
}

function fmtMoney(n) {
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '億';
  if (n >= 1e4) return (n / 1e4).toFixed(0) + '萬';
  return fmt(n);
}

function fmtMoneyFull(n) {
  return fmt(n) + '元';
}

let md = '';
md += `# 廉政專刊陽光法案系統 - 資料驗證報告\n\n`;
md += `生成時間：${generatedAt}\n`;
md += `總記錄數：${records.length} 筆\n`;
md += `PDF 期別：${issueMin}-${issueMax}（共 ${issueCount} 期）\n\n`;
md += `---\n\n`;
md += `## 頁面預設排序名單（依政黨群組金額總和 → 個人 disclosed_amount_total）\n\n`;

groups.forEach((group, gi) => {
  md += `### 群組 ${gi + 1}：${group.label}（總金額：${fmtMoneyFull(group.amount)}）\n`;
  group.records.forEach((rec, ri) => {
    const num = ri + 1;
    const amountStr = fmtMoneyFull(rec.disclosed_amount_total);
    const titleStr = rec.title || '';
    const issueStr = rec.issue ? `第${rec.issue}期` : '';
    md += `${num}. ${rec.name} / ${issueStr} / ${titleStr} / ${amountStr}\n`;
  });
  md += '\n';
});

md += `---\n\n`;
md += `## 資料完整性檢查結果\n\n`;
md += `### 摘要\n`;
md += `- 通過：${passed} 筆\n`;
md += `- 失敗：${failed} 筆\n`;
md += `- 失敗率：${((failed / records.length) * 100).toFixed(2)}%\n\n`;

md += `### 失敗項目列表\n`;
if (failList.length === 0) {
  md += `（無失敗項目）\n\n`;
} else {
  md += `| 序號 | 姓名 | 期別 | 政黨 | 失敗原因 |\n`;
  md += `|------|------|------|------|----------|\n`;
  failList.forEach(f => {
    md += `| ${f.idx + 1} | ${f.name} | ${f.issue} | ${f.party} | ${f.issues.join('；')} |\n`;
  });
  md += '\n';
}

md += `### 金額總計對帳（Asset Totals Sum vs Disclosed Amount）\n`;
md += `- 通過：${passed - assetSumFails.length} 筆\n`;
md += `- 失敗：${assetSumFails.length} 筆（列出差額最大的前 5 筆）\n\n`;
if (topAssetFails.length > 0) {
  md += `| 序號 | 姓名 | 期別 | asset_totals總和 | disclosed_amount_total | 誤差率 |\n`;
  md += `|------|------|------|-----------------|------------------------|--------|\n`;
  topAssetFails.forEach(f => {
    md += `| ${f.idx + 1} | ${f.name} | ${f.issue} | ${fmt(f.atSum)} | ${fmt(f.dat)} | ${f.err.toFixed(2)}% |\n`;
  });
  md += '\n';
} else {
  md += `（無失敗項目）\n\n`;
}

md += `## 各政黨群組統計\n\n`;
md += `| 政黨 | 人數 | 總金額（元） | 平均金額（元） |\n`;
md += `|------|------|-------------|---------------|\n`;
partyStats.forEach(p => {
  md += `| ${p.label} | ${p.count} | ${fmt(p.totalAmount)} | ${fmt(Math.round(p.avgAmount))} |\n`;
});
md += '\n';

// ── Write output ────────────────────────────────────────────────────────────
fs.writeFileSync(OUTPUT_PATH, md, 'utf8');
console.log(`Written: ${OUTPUT_PATH}`);
console.log(`Passed: ${passed}, Failed: ${failed}`);
console.log(`Top asset sum fails:`, topAssetFails.map(f => `${f.name}(${f.err.toFixed(1)}%)`));