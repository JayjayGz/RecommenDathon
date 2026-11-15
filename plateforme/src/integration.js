import { validatePortfolio } from './data.js';

export const ALLOCATION_COLORS = ['#303e32', '#60725b', '#97aa83', '#b6aa90', '#d4cbb9', '#d7b973', '#9d8f9f', '#829994'];
const text = (value, maximum) => typeof value === 'string' && value.trim().length > 0 && value.length <= maximum;
const color = value => typeof value === 'string' && /^#(?:[a-f\d]{3}|[a-f\d]{6})$/i.test(value);

// Contrôle de forme uniquement. Le moteur reste responsable de ses calculs et de sa conformité.
export function validateRecommendation(result) {
  return Boolean(result && text(result.runId, 160) && validatePortfolio(result.portfolio)
    && text(result.portfolio.id, 160) && text(result.portfolio.name, 160)
    && result.portfolio.positions.every(position => text(position.category, 120) && text(position.group, 80) && (position.color === undefined || color(position.color)))
    && text(result.explanation, 10000)
    && Array.isArray(result.evidence) && result.evidence.length > 0 && result.evidence.length <= 100
    && result.evidence.every(item => item && text(item.id, 100) && text(item.source, 1000) && text(item.description, 2000))
    && Array.isArray(result.limitations) && result.limitations.length <= 40 && result.limitations.every(item => text(item, 2000))
    && result.compliance?.passed === true);
}

export function normalizeRecommendation(result) {
  if (!validateRecommendation(result)) throw new Error('Le résultat ne contient pas une allocation, des sources et une validation complètes.');
  return {
    runId: result.runId,
    portfolio: { id: result.portfolio.id, name: result.portfolio.name, isDemo: false, positions: result.portfolio.positions.map((position, index) => ({ symbol: position.symbol, name: position.name, category: position.category, group: position.group, weight: position.weight, color: color(position.color) ? position.color : ALLOCATION_COLORS[index % ALLOCATION_COLORS.length], initials: position.symbol.slice(0, 3), icon: '' })) },
    explanation: result.explanation,
    evidence: result.evidence.map(item => ({ id: item.id, source: item.source, description: item.description })),
    limitations: [...result.limitations], compliance: { passed: true },
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
