// Source : Word fourni, avec les retraits explicites utilisateur (Discussion, situation séparée, montant visé).
export const QUESTIONNAIRE_VERSION = 'questionnaire-word-15-v5';
export const SECTIONS = ["Situation familiale", "Revenus", "Dettes et épargne disponible", "Objectifs et besoins de liquidités", "Tolérance au risque", "Connaissances et préférences de placement", "Exclusions et précisions complémentaires"];
export const QUESTIONS = [
  {
    "id": "dependents",
    "section": 0,
    "title": "Combien de personnes dépendent financièrement de vous ou sont sous votre responsabilité légale ?",
    "type": "single",
    "options": [
      [
        "none",
        "Aucune personne."
      ],
      [
        "one",
        "Une personne."
      ],
      [
        "many",
        "Deux personnes ou plus."
      ],
      [
        "other",
        "Autre situation."
      ]
    ],
    "help": "Pensez aux enfants, aux proches que vous soutenez ou aux personnes sous votre tutelle. Aucun nom n’est nécessaire.",
    "details": [
      {
        "key": "dependentsOther",
        "label": "Précisez votre situation (obligatoire)",
        "type": "text",
        "required": true,
        "when": {
          "field": "dependents",
          "values": [
            "other"
          ]
        }
      },
      {
        "key": "supportMode",
        "label": "Si vous avez des personnes à charge, assumez-vous principalement ces dépenses ou les partagez-vous ? Précision facultative.",
        "type": "single",
        "required": false,
        "options": [
          [
            "main",
            "Je les assume principalement."
          ],
          [
            "shared",
            "Je les partage avec quelqu’un."
          ]
        ],
        "when": {
          "field": "dependents",
          "values": [
            "one",
            "many",
            "other"
          ]
        }
      }
    ]
  },
  {
    "id": "annualIncome",
    "section": 1,
    "title": "Quel est votre revenu annuel personnel avant impôt ?",
    "type": "single",
    "options": [
      [
        "under_50k",
        "De 0 $ à moins de 50 000 $."
      ],
      [
        "50_100k",
        "De 50 000 $ à moins de 100 000 $."
      ],
      [
        "100_150k",
        "De 100 000 $ à moins de 150 000 $."
      ],
      [
        "150k_plus",
        "150 000 $ ou plus."
      ],
      [
        "other",
        "Autre situation."
      ]
    ],
    "help": "Incluez salaire, revenus de travail autonome, pension et autres revenus réguliers. Si vos revenus varient, indiquez une estimation annuelle.",
    "details": [
      {
        "key": "incomeOther",
        "label": "Précisez votre situation (obligatoire)",
        "type": "text",
        "required": true,
        "when": {
          "field": "annualIncome",
          "values": [
            "other"
          ]
        }
      }
    ]
  },
  {
    "id": "income",
    "section": 1,
    "title": "Vos revenus sont-ils prévisibles pour les douze prochains mois ?",
    "type": "single",
    "options": [
      [
        "regular",
        "Réguliers — Je prévois des revenus assez stables."
      ],
      [
        "variable",
        "Variables — Ils changent d’un mois à l’autre, mais je peux les estimer."
      ],
      [
        "fragile",
        "Fragiles — Une baisse importante ou une interruption est possible."
      ],
      [
        "unknown",
        "Inconnus — Je ne sais pas encore."
      ]
    ],
    "help": "Salaire, pension ou autres revenus réguliers peuvent être concernés.",
    "details": []
  },
  {
    "id": "debt",
    "section": 2,
    "title": "À combien estimez-vous le montant total de vos dettes actuelles ?",
    "type": "single",
    "options": [
      [
        "none",
        "Aucune dette."
      ],
      [
        "under_25k",
        "Plus de 0 $ à moins de 25 000 $."
      ],
      [
        "25_100k",
        "De 25 000 $ à moins de 100 000 $."
      ],
      [
        "100k_plus",
        "100 000 $ ou plus."
      ],
      [
        "other",
        "Autre situation."
      ]
    ],
    "help": "Indiquez le solde restant à rembourser, pas vos paiements mensuels. Incluez cartes et marges de crédit, prêts automobiles, étudiants et hypothécaires.",
    "details": [
      {
        "key": "debtOther",
        "label": "Précisez votre situation (obligatoire)",
        "type": "text",
        "required": true,
        "when": {
          "field": "debt",
          "values": [
            "other"
          ]
        }
      },
      {
        "key": "mortgageAmount",
        "label": "Part approximative correspondant à un prêt hypothécaire, si applicable et connue",
        "type": "number",
        "required": false
      }
    ]
  },
  {
    "id": "emergencyFund",
    "section": 2,
    "title": "Quel montant avez-vous actuellement de côté pour faire face aux imprévus ?",
    "type": "number",
    "options": [],
    "help": "Votre fonds d’urgence correspond à l’argent rapidement accessible pour une dépense imprévue ou une interruption de revenu. N’incluez pas vos limites de crédit. Inscrivez 0 si vous n’avez pas encore de fonds d’urgence.",
    "details": []
  },
  {
    "id": "goal",
    "section": 3,
    "title": "Quel est votre objectif principal pour cet investissement ?",
    "type": "single",
    "options": [
      [
        "retirement",
        "Préparer ma retraite — Constituer une épargne pour mes besoins futurs."
      ],
      [
        "project",
        "Financer un projet précis — Par exemple, une propriété, des études ou un projet personnel."
      ],
      [
        "wealth",
        "Développer mon patrimoine — Faire croître mon épargne sans projet de dépense précis pour le moment."
      ],
      [
        "other",
        "Autre objectif — Par exemple, obtenir un complément de revenu."
      ]
    ],
    "details": [
      {
        "key": "goalDetails",
        "label": "Précisez votre objectif (obligatoire si Autre)",
        "type": "text",
        "required": false,
        "when": {
          "field": "goal",
          "values": [
            "project",
            "other"
          ]
        },
        "requiredWhen": {
          "field": "goal",
          "values": [
            "other"
          ]
        }
      }
    ]
  },
  {
    "id": "horizon",
    "section": 3,
    "title": "Quel est votre horizon de placement ?",
    "type": "single",
    "options": [
      [
        "1_2",
        "1 à 2 ans."
      ],
      [
        "5",
        "5 ans."
      ],
      [
        "10",
        "10 ans."
      ],
      [
        "15_plus",
        "15 ans et plus."
      ]
    ],
    "details": []
  },
  {
    "id": "liquidity",
    "section": 3,
    "title": "Si vous aviez une dépense imprévue importante, devriez-vous utiliser cet investissement ?",
    "type": "single",
    "options": [
      [
        "no",
        "Non."
      ],
      [
        "partly",
        "En partie."
      ],
      [
        "yes",
        "Oui."
      ],
      [
        "unknown",
        "Je ne sais pas."
      ]
    ],
    "details": []
  },
  {
    "id": "risk",
    "section": 4,
    "title": "Quelle est votre tolérance au risque ?",
    "type": "single",
    "options": [
      [
        "very_low",
        "Très basse."
      ],
      [
        "low",
        "Basse."
      ],
      [
        "medium",
        "Moyenne."
      ],
      [
        "high",
        "Élevée."
      ],
      [
        "very_high",
        "Très élevée."
      ]
    ],
    "help": "La tolérance au risque décrit votre aisance face aux fluctuations et aux pertes possibles. Elle est distincte de votre capacité financière à supporter ces pertes.",
    "details": [],
    "layout": "risk"
  },
  {
    "id": "reaction",
    "section": 4,
    "title": "Si 10 000 $ investis devenaient, sur une période de 3 mois, 8 000 $, quel en serait l’effet sur votre perception de la bourse ?",
    "type": "single",
    "options": [
      [
        "worried",
        "Inquiet — Je perdrais confiance et voudrais retirer mon argent."
      ],
      [
        "hesitant",
        "Hésitant — Je serais stressé et aurais besoin de conseils avant de décider."
      ],
      [
        "concerned",
        "Préoccupé — La baisse me dérangerait, mais je pourrais rester investi si le portefeuille me convient toujours."
      ],
      [
        "calm",
        "Serein — J’accepte que de fortes baisses puissent arriver. Je pourrais rester investi, même sans savoir quand ni si la valeur remontera."
      ]
    ],
    "help": "Mise en situation fictive. La valeur du placement diminue de 2 000 $.",
    "details": [],
    "scenario": true
  },
  {
    "id": "knowledge",
    "section": 5,
    "title": "Comment décririez-vous vos connaissances en placement ?",
    "type": "single",
    "options": [
      [
        "beginner",
        "Débutant — Je découvre les placements et les marchés financiers."
      ],
      [
        "basic",
        "Quelques connaissances — Je connais les principaux types de placements."
      ],
      [
        "good",
        "Bonne compréhension — Je comprends leurs risques et les principes de diversification."
      ],
      [
        "advanced",
        "Expérience approfondie — Je connais plusieurs produits et suis régulièrement les marchés."
      ]
    ],
    "details": []
  },
  {
    "id": "sectors",
    "section": 5,
    "title": "Quels secteurs vous intéressent particulièrement ?",
    "type": "multi",
    "options": [
      [
        "technology",
        "Technologie — Informatique, logiciels et semi-conducteurs."
      ],
      [
        "health",
        "Santé — Médicaments, soins de santé et biotechnologie."
      ],
      [
        "finance",
        "Finance — Banques, assurances et services financiers."
      ],
      [
        "energy",
        "Énergie — Pétrole et gaz."
      ],
      [
        "real_estate",
        "Immobilier — Via un FNB immobilier."
      ],
      [
        "industry",
        "Industrie — Transport, aéronautique et équipements industriels."
      ],
      [
        "consumer",
        "Consommation — Alimentation, commerce et biens de consommation."
      ],
      [
        "communications",
        "Communications — Télécommunications, médias et divertissement."
      ],
      [
        "utilities",
        "Services aux collectivités — Services publics."
      ]
    ],
    "details": [],
    "layout": "grid"
  },
  {
    "id": "assets",
    "section": 5,
    "title": "Quelles sont les classes d’actifs qui vous intéressent le plus ?",
    "type": "multi",
    "options": [
      [
        "stocks",
        "Actions — Titres de sociétés canadiennes et américaines."
      ],
      [
        "equity_funds",
        "FNB d’actions — Fonds diversifiés ou sectoriels."
      ],
      [
        "bonds",
        "Revenu fixe — Via des FNB obligataires."
      ],
      [
        "alternatives",
        "Immobilier et matières premières — Via des fonds cotés."
      ],
      [
        "crypto",
        "Cryptoactifs — Bitcoin, Ether, XRP, Litecoin et Bitcoin Cash."
      ],
      [
        "futures",
        "Contrats à terme sur matières premières — Pétrole, gaz, or, argent et cuivre."
      ],
      [
        "fx",
        "Devises — Paires de devises, dont EUR/USD et USD/CAD."
      ],
      [
        "all",
        "Toutes les catégories ci-dessus."
      ]
    ],
    "details": [
      {
        "key": "cryptoDetails",
        "label": "Si cryptoactifs, vos précisions facultatives",
        "type": "text",
        "required": false,
        "when": {
          "field": "assets",
          "values": [
            "crypto",
            "all"
          ]
        }
      }
    ],
    "layout": "grid"
  },
  {
    "id": "exclusions",
    "section": 6,
    "title": "Y a-t-il des placements ou des activités que vous ne voulez pas dans votre portefeuille ?",
    "type": "single",
    "options": [
      [
        "none",
        "Aucune — Je n’ai aucune exclusion particulière."
      ],
      [
        "limits",
        "Limites — Oui, je veux exclure certains placements ou certaines activités."
      ]
    ],
    "details": [
      {
        "key": "exclusionDetails",
        "label": "Précisez ce que vous voulez exclure (obligatoire)",
        "type": "text",
        "required": true,
        "when": {
          "field": "exclusions",
          "values": [
            "limits"
          ]
        }
      }
    ]
  },
  {
    "id": "notes",
    "section": 6,
    "title": "Avez-vous d’autres précisions à apporter pour nous aider à comprendre votre situation ?",
    "type": "text",
    "options": [],
    "help": "Vous pouvez préciser un projet à venir, une dépense importante, un changement familial ou professionnel, une contrainte ou une préoccupation concernant vos placements. N’inscrivez aucun numéro de compte ni renseignement bancaire confidentiel. Écrivez vos précisions ou cochez « Je n’ai rien à ajouter ».",
    "details": [
      {
        "key": "noNotes",
        "label": "Je n’ai rien à ajouter.",
        "type": "boolean",
        "required": false
      }
    ],
    "confirmField": "noNotes"
  }
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

export function fieldVisible(field, answers) {
  if (!field.when) return true;
  const value = answers[field.when.field];
  return field.when.values.some(item => Array.isArray(value) ? value.includes(item) : value === item);
}

function validValue(field, value) {
  if (field.type === 'number') return typeof value === 'number' && Number.isFinite(value) && value >= 0;
  if (field.type === 'boolean') return typeof value === 'boolean';
  if (field.type === 'text') return typeof value === 'string' && value.trim().length > 0 && value.length <= 1000;
  const allowed = field.options.map(([key]) => key);
  if (field.type === 'multi') return Array.isArray(value) && value.length > 0 && new Set(value).size === value.length
    && value.every(item => allowed.includes(item)) && (!value.includes('all') || value.length === 1);
  return typeof value === 'string' && allowed.includes(value);
}

export function fieldRequired(field, answers) {
  return field.required === true || Boolean(field.requiredWhen && fieldVisible({ when: field.requiredWhen }, answers));
}

export function isAnswered(question, answers) {
  // confirmField: an explicit checkbox (e.g. "Je n’ai rien à ajouter") can stand in for the main answer.
  const main = question.optional || validValue(question, answers[question.id])
    || (question.confirmField !== undefined && answers[question.confirmField] === true);
  return Boolean(main && question.details.every(field => !fieldRequired(field, answers) || !fieldVisible(field, answers) || validValue(field, answers[field.key])));
}

export function cleanAnswers(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return {};
  const result = {};
  for (const question of QUESTIONS) {
    if (validValue(question, input[question.id])) result[question.id] = Array.isArray(input[question.id]) ? [...input[question.id]] : input[question.id];
    for (const field of question.details) {
      if (fieldVisible(field, input) && validValue(field, input[field.key])) result[field.key] = input[field.key];
    }
  }
  if (result.noNotes === true) delete result.notes;
  if (input.context && typeof input.context === 'object' && !Array.isArray(input.context)) {
    const ids = new Set(QUESTIONS.filter(q => q.type !== 'text').map(q => q.id));
    const context = Object.fromEntries(Object.entries(input.context).filter(([id, value]) => ids.has(id)
      && typeof value === 'string' && value.trim().length > 0 && value.length <= 1000));
    if (Object.keys(context).length) result.context = context;
  }
  return result;
}

export function validateAnswers(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return false;
  const clean = cleanAnswers(input);
  // Reject unknown, invalid, hidden or contradictory fields at the HTTP boundary.
  return Object.keys(input).length === Object.keys(clean).length
    && Object.keys(input).every(key => JSON.stringify(input[key]) === JSON.stringify(clean[key]))
    && QUESTIONS.every(q => isAnswered(q, clean));
}

export function answerLabel(question, answers) {
  const answer = answers[question.id];
  let label = '';
  if (question.type === 'number') label = typeof answer === 'number' ? `${new Intl.NumberFormat('fr-CA').format(answer)} $ CA` : '';
  else if (question.type === 'text') label = answer || (answers.noNotes ? 'Je n’ai rien à ajouter.' : 'Aucune précision ajoutée.');
  else label = question.options.filter(([value]) => Array.isArray(answer) ? answer.includes(value) : answer === value).map(([, text]) => text).join(' · ');
  const details = question.details.filter(field => fieldVisible(field, answers) && validValue(field, answers[field.key]) && field.type !== 'boolean').map(field => {
    const value = answers[field.key];
    return `${field.label} : ${field.type === 'single' ? field.options.find(([key]) => key === value)[1] : field.type === 'number' ? `${value} $ CA` : value}`;
  });
  return [label, ...details, answers.context?.[question.id] ? `Vos précisions : ${answers.context[question.id]}` : ''].filter(Boolean).join('\n');
}

export function makeQuestionnairePayload(answers) {
  return { version: QUESTIONNAIRE_VERSION, answers: cleanAnswers(answers) };
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
