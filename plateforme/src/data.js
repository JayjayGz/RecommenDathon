// Source: Questionnaire_investisseur_rendements_seuls.docx.
// Les libellés et les options sont conservés. Aucune question n'a été ajoutée.
export const QUESTIONNAIRE_VERSION = 'rendements-seuls-v1';
export const SECTIONS = ['Votre profil investisseur', 'Rendement et horizon', 'Revenus et secteurs', 'Placements et préférences'];
export const QUESTIONS = [
  { id: 'risk', section: 0, title: 'Quelle est votre tolérance au risque ?', type: 'single', layout: 'risk', options: [
    ['very_low', 'Très basse'], ['low', 'Basse'], ['medium', 'Moyenne'], ['high', 'Élevée'], ['very_high', 'Très élevée'],
  ] },
  { id: 'reaction', section: 0, title: 'Si 10 000 $ investis devenaient, sur une période de 3 mois, 8 000 $, quel en serait l’effet sur votre perception de la bourse ?', type: 'single', scenario: true, options: [
    ['worried', 'Inquiet — Je perdrais confiance et voudrais retirer mon argent.'],
    ['hesitant', 'Hésitant — Je serais stressé et aurais besoin de conseils avant de décider.'],
    ['concerned', 'Préoccupé — La baisse me dérangerait, mais je pourrais rester investi si le portefeuille me convient toujours.'],
    ['calm', 'Serein — J’accepte que de fortes baisses puissent arriver. Je pourrais rester investi, même sans savoir quand ni si la valeur remontera.'],
  ] },
  { id: 'return', section: 1, title: 'Quel type de rendement souhaitez-vous ?', type: 'single', layout: 'tiles', note: 'Un objectif exprimé n’est pas une promesse de rendement.', options: [
    ['3_4', '3 % à 4 % / an'], ['5_6', '5 % à 6 % / an'], ['7_9', '7 % à 9 % / an'], ['10_plus', '10 % et plus / an'],
  ] },
  { id: 'horizon', section: 1, title: 'Quel est votre horizon de placement ?', type: 'single', layout: 'tiles', options: [
    ['1_2', '1 à 2 ans'], ['5', '5 ans'], ['10', '10 ans'], ['15_plus', '15 ans et plus'],
  ] },
  { id: 'income', section: 2, title: 'Vos revenus sont-ils prévisibles pour les douze prochains mois ?', type: 'single', help: 'Une réponse. Salaire, pension ou autres revenus réguliers peuvent être concernés.', options: [
    ['regular', 'Réguliers — Je prévois des revenus assez stables.'],
    ['variable', 'Variables — Ils changent d’un mois à l’autre, mais je peux les estimer.'],
    ['fragile', 'Fragiles — Une baisse importante ou une interruption est possible.'],
    ['unknown', 'Inconnus — Je ne sais pas encore.'],
  ] },
  { id: 'sectors', section: 2, title: 'Quels secteurs vous intéressent particulièrement ?', type: 'multi', layout: 'grid', options: [
    ['technology', 'Technologie'], ['health', 'Soins de santé et biotechnologie'], ['financial_services', 'Services financiers'], ['materials', 'Matières premières et minéraux critiques'], ['real_estate', 'Immobilier et infrastructures'], ['finance', 'Finance'], ['consumer', 'Consommation — Produits et services de la vie quotidienne.'], ['other', 'Autre'],
  ], detail: { option: 'other', key: 'otherSector', label: 'Autre', placeholder: 'Précisez le secteur qui vous intéresse' } },
  { id: 'assets', section: 3, title: 'Quelles sont les classes d’actifs qui vous intéressent le plus ?', type: 'multi', layout: 'grid', options: [
    ['stocks', 'Actions'], ['bonds', 'Obligations'], ['funds', 'Fonds d’investissement'], ['cash', 'Liquidités bancaires et produits bancaires'], ['crypto', 'Cryptoactifs'],
  ], detail: { option: 'crypto', key: 'cryptoDetails', label: 'Cryptoactifs', placeholder: 'Vos précisions (facultatif)' } },
  { id: 'exclusions', section: 3, title: 'Y a-t-il des placements ou des activités que vous ne voulez pas dans votre portefeuille ?', type: 'single', help: 'Une réponse, puis un champ libre si nécessaire.', options: [
    ['none', 'Aucune — Je n’ai aucune exclusion particulière.'], ['limits', 'Limites — Oui, je veux exclure certains placements ou certaines activités.'], ['discussion', 'Discussion — J’aimerais comprendre les possibilités avant de préciser mes limites.'],
  ], text: true },
];

export const DEMO_PORTFOLIO = Object.freeze({
  id: 'illustration-v1', name: 'Une première perspective', isDemo: true,
  positions: [
    { symbol: 'SPY', name: 'FNB S&P 500', category: 'Actions américaines', weight: 20, color: '#303e32', group: 'Actions', initials: 'S&P', icon: 'sp' },
    { symbol: 'XIU.TO', name: 'FNB S&P/TSX 60', category: 'Actions canadiennes', weight: 20, color: '#60725b', group: 'Actions', initials: 'XIU', icon: 'xiu' },
    { symbol: 'NVDA', name: 'NVIDIA', category: 'Action individuelle', weight: 10, color: '#97aa83', group: 'Actions', initials: 'N', icon: 'nvda' },
    { symbol: 'XBB.TO', name: 'FNB d’obligations canadiennes', category: 'Obligations', weight: 25, color: '#b6aa90', group: 'Obligations', initials: 'XBB', icon: 'xbb' },
    { symbol: 'ZST.TO', name: 'FNB d’obligations à très court terme', category: 'Obligations', weight: 15, color: '#d4cbb9', group: 'Obligations', initials: 'ZST', icon: 'zst' },
    { symbol: 'GLD', name: 'FNB adossé à l’or', category: 'Matières premières', weight: 10, color: '#d7b973', group: 'Or', initials: 'Au', icon: 'gold' },
  ],
});

export function isAnswered(question, answers) {
  const valid = question.options.map(([value]) => value);
  const answer = answers[question.id];
  return question.type === 'multi'
    ? Array.isArray(answer) && answer.length > 0 && answer.every(value => valid.includes(value)) && new Set(answer).size === answer.length
    : typeof answer === 'string' && valid.includes(answer);
}

export function cleanAnswers(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return {};
  const result = {};
  QUESTIONS.forEach(question => {
    if (isAnswered(question, input)) result[question.id] = question.type === 'multi' ? [...input[question.id]] : input[question.id];
  });
  ['otherSector', 'cryptoDetails', 'exclusionDetails'].forEach(key => {
    if (typeof input[key] === 'string') result[key] = input[key].slice(0, 1000);
  });
  // Ne pas conserver de précisions devenues sans objet après une modification.
  if (!result.sectors?.includes('other')) delete result.otherSector;
  if (!result.assets?.includes('crypto')) delete result.cryptoDetails;
  if (result.exclusions === 'none') delete result.exclusionDetails;
  return result;
}

export function answerLabel(question, answers) {
  const answer = answers[question.id];
  return question.options.filter(([value]) => Array.isArray(answer) ? answer.includes(value) : answer === value).map(([, label]) => label).join(' · ');
}

export function validatePortfolio(input) {
  if (!input || !Array.isArray(input.positions) || input.positions.length < 1 || input.positions.length > 40) return false;
  const symbols = new Set();
  for (const position of input.positions) {
    if (!position || typeof position !== 'object' || Array.isArray(position)) return false;
    if (typeof position.symbol !== 'string' || !position.symbol.trim() || position.symbol.length > 30 || symbols.has(position.symbol)) return false;
    symbols.add(position.symbol);
    if (typeof position.name !== 'string' || !position.name.trim() || position.name.length > 160) return false;
    if (typeof position.weight !== 'number' || !Number.isFinite(position.weight) || position.weight <= 0 || position.weight > 100) return false;
  }
  return Math.abs(input.positions.reduce((sum, p) => sum + p.weight, 0) - 100) < 0.001;
}

export function makeQuestionnairePayload(answers) {
  return { version: QUESTIONNAIRE_VERSION, answers: cleanAnswers(answers) };
}
