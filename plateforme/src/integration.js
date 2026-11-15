import { validatePortfolio } from './data.js';

export const ALLOCATION_COLORS = ['#303e32', '#60725b', '#97aa83', '#b6aa90', '#d4cbb9', '#d7b973', '#9d8f9f', '#829994'];
const text = (value, maximum) => typeof value === 'string' && value.trim().length > 0 && value.length <= maximum;
const color = value => typeof value === 'string' && /^#(?:[a-f\d]{3}|[a-f\d]{6})$/i.test(value);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const finite = value => typeof value === 'number' && Number.isFinite(value);
const percentages = value => object(value) && Object.keys(value).length <= 40
  && Object.entries(value).every(([key, weight]) => text(key, 200) && finite(weight) && weight >= 0 && weight <= 100);
const total = value => Object.values(value).reduce((a, b) => a + b, 0);
const checked = value => object(value) && value.status === 'PASS' && value.passes === true
  && object(value.checks) && Object.keys(value.checks).length > 0 && Object.keys(value.checks).length <= 30
  && Object.values(value.checks).every(c => object(c) && c.passes === true);

export function validateAnalysis(analysis, evidence) {
  if (!object(analysis) || JSON.stringify(analysis).length > 25000 || analysis.method !== 'portfolio_review_v1'
      || typeof analysis.manifest_hash !== 'string' || !/^[a-f0-9]{64}$/.test(analysis.manifest_hash)) return false;
  const r = analysis.review;
  const ids = new Set(evidence.map(e => e.id));
  const cited = values => Array.isArray(values) && values.length > 0 && values.length <= 20 && values.every(id => ids.has(id));
  if (!object(r) || r.method !== 'portfolio_review_v1' || !percentages(r.asset_class_weights_pct)
      || Math.abs(total(r.asset_class_weights_pct) - 100) > 1e-5 || !percentages(r.listing_currency_weights_pct)
      || Math.abs(total(r.listing_currency_weights_pct) - 100) > 1e-5 || !cited(analysis.evidence_ids)) return false;
  const s = r.sectors, d = r.diversification, risk = r.risk;
  if (!object(s) || s.scope !== 'direct_stocks_only' || !percentages(s.weights_pct)
      || !finite(s.covered_pct) || !finite(s.unclassified_pct) || s.unclassified_pct < 0
      || Math.abs(total(s.weights_pct) - s.covered_pct) > 1e-5
      || Math.abs(s.covered_pct + s.unclassified_pct - 100) > 1e-5) return false;
  if (!object(d) || !Number.isInteger(d.holding_count) || d.holding_count < 1 || d.holding_count > 40
      || !text(d.largest_ticker, 30) || !finite(d.largest_weight_pct) || d.largest_weight_pct <= 0 || d.largest_weight_pct > 100
      || !finite(d.holding_hhi) || d.holding_hhi <= 0 || d.holding_hhi > 1
      || !finite(d.effective_holdings) || d.effective_holdings < 1 || d.effective_holdings > 40) return false;
  if (!object(risk) || !['annual_growth_pct','volatility_pct','max_drawdown_pct'].every(k => finite(risk[k]))
      || risk.volatility_pct < 0 || risk.max_drawdown_pct > 0 || !object(r.profile_fit)
      || !['PASS','CONFLICT'].includes(r.profile_fit.status) || !object(r.profile_fit.checks)
      || !Array.isArray(r.findings) || r.findings.length > 10 || !Array.isArray(r.limitations)
      || r.limitations.length > 10 || !r.limitations.every(x => text(x, 2000))) return false;
  const search = analysis.search;
  if (!object(search) || search.method !== 'same_class_held_transfers_v1'
      || !['complete','budget_limited','no_passing_portfolio'].includes(search.status)
      || search.max_candidates !== 6 || search.max_suggestions !== 2
      || !Number.isInteger(search.evaluated_candidates) || search.evaluated_candidates < 0 || search.evaluated_candidates > 6
      || !Array.isArray(analysis.suggestions) || analysis.suggestions.length > 2) return false;
  return analysis.suggestions.every(candidate => {
    if (!object(candidate) || !/^C[1-6]$/.test(candidate.id) || !text(candidate.issue_id, 200)
        || candidate.objective !== 'reduce_holding_concentration' || candidate.applied !== false
        || !validatePortfolio(candidate.portfolio) || !checked(candidate.validation) || !cited(candidate.evidence_ids)
        || !Array.isArray(candidate.changes) || candidate.changes.length !== 2
        || !candidate.changes.every(c => object(c) && text(c.ticker, 30) && Number.isInteger(c.add_pct) && Math.abs(c.add_pct) <= 5)) return false;
    const comparison = candidate.comparison;
    if (!object(comparison) || !['holding_hhi','annual_growth_pct','volatility_pct','max_drawdown_pct'].every(k =>
      object(comparison[k]) && finite(comparison[k].before) && finite(comparison[k].after))) return false;
    return comparison.holding_hhi.after < comparison.holding_hhi.before
      && comparison.volatility_pct.after <= comparison.volatility_pct.before
      && comparison.max_drawdown_pct.after >= comparison.max_drawdown_pct.before;
  });
}

// Contrôle de forme uniquement. Le moteur reste responsable de ses calculs et de sa conformité.
export function validateRecommendation(result) {
  return Boolean(result && text(result.runId, 160) && validatePortfolio(result.portfolio)
    && text(result.portfolio.id, 160) && text(result.portfolio.name, 160)
    && result.portfolio.positions.every(position => text(position.category, 120) && text(position.group, 80) && (position.color === undefined || color(position.color)))
    && text(result.explanation, 10000)
    && Array.isArray(result.evidence) && result.evidence.length > 0 && result.evidence.length <= 100
    && result.evidence.every(item => item && text(item.id, 100) && text(item.source, 1000) && text(item.description, 2000))
    && Array.isArray(result.limitations) && result.limitations.length <= 40 && result.limitations.every(item => text(item, 2000))
    && result.compliance?.passed === true
    && (result.analysis === undefined || validateAnalysis(result.analysis, result.evidence)));
}

export function normalizeRecommendation(result) {
  if (!validateRecommendation(result)) throw new Error('Le résultat ne contient pas une allocation, des sources et une validation complètes.');
  return {
    runId: result.runId,
    portfolio: { id: result.portfolio.id, name: result.portfolio.name, isDemo: false, positions: result.portfolio.positions.map((position, index) => ({ symbol: position.symbol, name: position.name, category: position.category, group: position.group, weight: position.weight, color: color(position.color) ? position.color : ALLOCATION_COLORS[index % ALLOCATION_COLORS.length], initials: position.symbol.slice(0, 3), icon: '' })) },
    explanation: result.explanation,
    evidence: result.evidence.map(item => ({ id: item.id, source: item.source, description: item.description })),
    limitations: [...result.limitations], compliance: { passed: true },
    ...(result.analysis === undefined ? {} : { analysis: JSON.parse(JSON.stringify(result.analysis)) }),
  };
}

export function allocationGroups(portfolio) {
  const groups = new Map();
  portfolio.positions.forEach(position => {
    const item = groups.get(position.group) || { name: position.group, weight: 0, count: 0, color: position.color };
    item.weight += position.weight;
    item.count++;
    groups.set(item.name, item);
  });
  return [...groups.values()];
}
