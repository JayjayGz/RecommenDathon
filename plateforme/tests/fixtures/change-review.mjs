export function simulationFixture() {
  const position = (symbol, weight) => ({ symbol, weight, name: symbol, category: 'Technologie', group: 'equity' });
  const initial = {
    runId: 'simulation-initiale', portfolio: { id: '1', name: 'Simulation initiale', positions: [position('AAA', 20), position('BBB', 80)] },
    explanation: 'Simulation éducative initiale.', evidence: [{ id: 'preuve-initiale', source: 'simulation', description: 'Valeurs fictives.' }],
    limitations: ['Exemple fictif.'], compliance: { passed: true },
  };
  const proposal = structuredClone(initial);
  proposal.runId = 'analyse-modification';
  proposal.portfolio.positions = [position('AAA', 25), position('BBB', 75)];
  proposal.changeReview = {
    method: 'questionnaire_change_review_v1', verdict: 'compatible', applied: false, confirmation_required: true,
    baseline_weights_pct: { AAA: 20, BBB: 80 }, strengths: ['La catégorie correspond aux préférences.'], cautions: [], limitations: [],
    conclusion: 'Avis : modification compatible avec les critères vérifiés, sous réserve de votre confirmation.',
    assets: [{ ticker: 'AAA', asset_class: 'equity', class_preference_match: true, sector_preference_match: true, before_pct: 20, after_pct: 25 }],
  };
  return { initial, proposal };
}
