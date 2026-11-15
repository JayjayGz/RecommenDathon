// Shape check for the supplied fr-CA form. The backend validates answers and policy.
const IDS = new Set(['situation_conjugale', 'personnes_a_charge', 'revenu_annuel', 'stabilite_revenus', 'dettes', 'fonds_urgence', 'objectif_investissement', 'horizon', 'besoin_imprevu', 'tolerance_risque', 'reaction_baisse', 'connaissances', 'secteurs', 'classes_actifs', 'exclusions', 'precisions_finales']);

export function isFrenchQuestionnaire(input) {
  if (!input || input.langue !== 'fr-CA' || input.devise !== 'CAD' || !Array.isArray(input.questions) || input.questions.length !== IDS.size) return false;
  const seen = new Set();
  return input.questions.every(question => {
    if (!question || typeof question !== 'object' || !IDS.has(question.id) || seen.has(question.id)) return false;
    seen.add(question.id);
    return Object.hasOwn(question, 'reponse');
  });
}
