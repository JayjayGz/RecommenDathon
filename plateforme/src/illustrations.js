// Illustrations SVG locales : aucun cours réel, aucun rendement projeté.
const drawings = {
  household: '<path d="m64 172 116-98 116 98v126H64Z" fill="#e4ddd1"/><path d="m48 178 132-112 132 112M91 155v130h178V155"/><circle cx="152" cy="182" r="20"/><circle cx="210" cy="182" r="20"/><path d="M119 254v-24a33 33 0 0 1 66 0v24m-5-27a33 33 0 0 1 63 0v27"/>',
  ledger: '<rect x="86" y="69" width="193" height="240" rx="15" fill="#fff"/><path d="M118 120h129M118 156h74m34 0h21M118 195h74m34 0h21M118 234h74m34 0h21M118 273h129"/><rect x="134" y="55" width="96" height="30" rx="9" fill="#d2c4af"/>',
  wallet: '<rect x="58" y="115" width="244" height="166" rx="25" fill="#d2c4af"/><path d="M77 115v-18a14 14 0 0 1 14-14h164v32"/><rect x="219" y="165" width="96" height="67" rx="12" fill="#fff"/><circle cx="249" cy="198" r="5" fill="#1c1c1c"/>',
  reserve: '<path d="M181 67c40 40 83 46 105 49v74c0 61-62 107-105 125-43-18-105-64-105-125v-74c32-5 72-17 105-49Z" fill="#e4ddd1"/><path d="m141 181 30 30 58-61"/><path d="M102 279h157"/>',
  target: '<circle cx="181" cy="186" r="113" fill="#e4ddd1"/><circle cx="181" cy="186" r="76" fill="#f5f3ef"/><circle cx="181" cy="186" r="36" fill="#d2c4af"/><path d="m181 186 113-113m-48 0h48v48"/>',
  calendar: '<rect x="74" y="90" width="218" height="219" rx="18" fill="#fff"/><path d="M74 145h218M124 68v43m118-43v43"/><path d="M114 181h20m35 0h20m35 0h20M114 218h20m35 0h20m35 0h20M114 255h20m35 0h20"/>',
  risk: '<path d="M62 278h248M79 278v-60h39v60m37 0V178h39v100m36 0V125h39v153" fill="#e4ddd1"/><path d="M67 109c31-30 65 54 101 17s64-28 100-59"/><circle cx="268" cy="67" r="8" fill="#1c1c1c"/>',
  book: '<path d="M181 101c-38-22-76-23-123-10v192c48-13 87-12 123 10 36-22 75-23 123-10V91c-47-13-85-12-123 10Z" fill="#fff"/><path d="M181 101v192M85 133l63 7m-63 31 63 7m-63 31 63 7m63-76 63-7m-63 45 63-7m-63 45 63-7"/>',
  city: '<path d="M50 291h271M70 291V173h72v118m-17-118V91h101v200m-17-137h83v137" fill="#e4ddd1"/><path d="M150 124h16m20 0h16m-52 34h16m20 0h16m-52 34h16m20 0h16m37 1h16m-16 35h16M91 207h27m-27 34h27"/>',
  allocation: '<circle cx="182" cy="182" r="111" fill="#e4ddd1"/><path d="M182 71v111h111" fill="#c2b197"/><path d="m182 182-80 77"/><circle cx="182" cy="182" r="55" fill="#f5f3ef"/><path d="M104 320h156"/>',
  choices: '<rect x="76" y="69" width="211" height="238" rx="17" fill="#fff"/><rect x="108" y="118" width="29" height="29" rx="5"/><rect x="108" y="174" width="29" height="29" rx="5"/><rect x="108" y="230" width="29" height="29" rx="5"/><path d="m112 132 9 8 16-20M158 132h92m-92 57h92m-92 56h92"/>',
  notes: '<rect x="69" y="86" width="224" height="213" rx="17" fill="#fff"/><path d="M106 135h147M106 176h112M106 217h67"/><path d="m210 259 18-47 73-73 28 28-73 73Z" fill="#d2c4af"/>',
};
const subjects = {
  marital: ['household','Votre situation familiale','Votre point de départ personnel.'],
  dependents: ['household','Les personnes qui comptent','Vos responsabilités font partie du portrait.'],
  annualIncome: ['wallet','Vos revenus','Une vue d’ensemble de votre situation.'],
  income: ['calendar','Les douze prochains mois','La prévisibilité de vos revenus.'],
  debt: ['ledger','Vos engagements','Le solde de vos dettes, en toute clarté.'],
  emergencyFund: ['reserve','Votre réserve pour les imprévus','L’épargne que vous gardez accessible.'],
  goal: ['target','Votre projet','Un objectif qui vous appartient.'],
  horizon: ['calendar','Votre horizon','Le temps dont vous disposez.'],
  liquidity: ['reserve','Face à l’imprévu','Vos besoins d’argent disponible.'],
  risk: ['risk','Votre rapport au risque','Votre aisance face aux fluctuations.'],
  knowledge: ['book','Vos connaissances','Votre expérience des placements.'],
  sectors: ['city','L’économie derrière les titres','Les domaines qui vous intéressent.'],
  assets: ['allocation','Vos catégories de placement','Des instruments aux rôles différents.'],
  exclusions: ['choices','Vos limites','Les choix qui vous conviennent.'],
  notes: ['notes','À vous de préciser','Un espace pour compléter votre portrait.'],
};
export function questionIllustration(id) {
  if (id === 'reaction') return '';
  const [drawing,title,caption] = subjects[id];
  return `<aside class="question-illustration" aria-label="${title}"><span class="illustration-kicker">VOTRE PROFIL INVESTISSEUR</span><svg viewBox="0 0 365 365" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="${title}">${drawings[drawing]}</svg><div><h2>${title}</h2><p>${caption}</p></div><small>Illustration du thème de la question</small></aside>`;
}

export function marketScenario() {
  const grid = [...Array(14)].map((_,i)=>`<path d="M${12+i*30} 8v268"/>`).join('') + [...Array(10)].map((_,i)=>`<path d="M8 ${12+i*27}h420"/>`).join('');
  const bars = [...Array(64)].map((_,i)=>`<rect x="${10+i*6.5}" y="${282-(9+(i*17)%19+(i>58?(i-58)*5:0))}" width="4" height="${9+(i*17)%19+(i>58?(i-58)*5:0)}"/>`).join('');
  return `<aside class="market-scenario" aria-label="Mise en situation fictive"><div class="market-bulletin">Bulletin spécial · Mise en situation fictive</div><div class="market-body"><div class="market-story"><h2>Une baisse en trois mois</h2><p class="market-amount">10 000 $ <span>→</span> 8 000 $</p><p>La valeur du placement diminue de 2 000 $. Comment cette situation changerait-elle votre perception de la bourse ?</p><small>Illustration fictive, sans lien avec une actualité réelle.</small></div><svg class="market-chart" viewBox="0 0 440 295" role="img" aria-label="Graphique illustratif d’une baisse en trois mois, de 10 000 dollars à 8 000 dollars"><defs><linearGradient id="arrow-fill" x2="0" y2="1"><stop stop-color="#69737a"/><stop offset="1" stop-color="#20272b"/></linearGradient><filter id="arrow-shadow"><feDropShadow dx="2" dy="5" stdDeviation="3" flood-opacity=".4"/></filter></defs><rect width="440" height="295" fill="#f6f7f9"/><g stroke="#cbd0d7" stroke-width=".6">${grid}</g><path d="m10 51 6 15 5-7 5 9 8-17 7 8 8-21 9-8 8 17 5-7 7 17 9-9 10 22 8-12 9 23 7-4 9 20 9-8 8 16 7-4 8 22 8-5 10 23 7-7 8 20 9-6 9 18 8-7 9 19 8-3 9 18 9-5 8 17 9-2 9 17 9-8 9 20 9-6 8 13 8-4 8 16 8-5 9 18 10-6 9 10 9-3" stroke="#bf283e" stroke-width="1.5" fill="none"/><path d="m10 77 7 13 7-5 8 11 7-10 8 17 7-5 9 18 9-9 8 17 9-6 8 18 9-5 9 16 8-6 10 21 7-8 8 15 9-3 9 18 9-5 8 17 9-7 8 15 8-4 10 17 8-6 9 15 10-4 10 15 8-3 9 13 9-4 9 15 9-2 10 13 9-5 9 12 9-2 10 11 9-4 10 10 9-2" stroke="#4486af" stroke-width="1.4" fill="none"/><g fill="#b73544">${bars}</g><path d="m10 23 77 62 59-27 51 65 59-35 47 65 39-22 56 70 10-9 11 43-43-18 13-6-51-57-43 24-47-66-54 33-56-66-54 23-82-67Z" fill="url(#arrow-fill)" stroke="#3c454b" stroke-width="4" filter="url(#arrow-shadow)"/></svg></div></aside>`;
}
