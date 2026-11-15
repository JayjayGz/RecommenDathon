import { QUESTIONS, SECTIONS, DEMO_PORTFOLIO, isAnswered, cleanAnswers, answerLabel, makeQuestionnairePayload, fieldVisible } from './data.js';
import { portfolioCsv, createRequestGuard, boundedChatPayload } from './export.js';
import { normalizeRecommendation, allocationGroups } from './integration.js';

import { questionIllustration, marketScenario } from './illustrations.js';

const STORAGE_KEY = 'recommand.platform.word16.v2';
const $ = selector => document.querySelector(selector);
const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
const paths = {
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>', back: '<path d="m14 6-6 6 6 6"/>',
  check: '<path d="m5 12 4 4L19 6"/>', lock: '<rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  leaf: '<path d="M20 4C10 2 3 7 5 14c3 8 15 4 15-10Z"/><path d="M4 21 15 10"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  chart: '<path d="M4 4v16h16M8 15l4-5 4 2 4-7"/>',
  chat: '<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2v-9.5A8.5 8.5 0 0 1 10.5 4h2A8.5 8.5 0 0 1 21 11.5Z"/><path d="M7 10h9M7 14h6"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  edit: '<path d="m15 4 5 5M4 20l5-1L21 7a3.5 3.5 0 0 0-5-5L4 14Z"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  send: '<path d="m5 12 7-7 7 7M12 5v15"/>', plus: '<path d="M12 4v16M4 12h16"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 8.5a2.5 2.5 0 1 1 4 2c-1 .5-1.5 1.5-1.5 2.5M12 17h.01"/>',
  file: '<path d="M14 2H5v20h14V7ZM14 2v6h5M8 13h8M8 17h6"/>',
};
const icon = (name, className = '') => `<svg class="icon ${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.chart}</svg>`;
const spark = (className = '') => `<svg class="spark ${className}" viewBox="0 0 80 80" fill="none" aria-hidden="true"><path d="M40 0c0 27-13 40-40 40 27 0 40 13 40 40 0-27 13-40 40-40C53 40 40 27 40 0Z" fill="currentColor"/></svg>`;
const safelyNormalize = result => { try { return normalizeRecommendation(result); } catch { return null; } };
const formatWeight = value => new Intl.NumberFormat('fr-CA', { maximumFractionDigits: 2 }).format(value);

function readState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    const answers = cleanAnswers(saved.answers);
    const complete = saved.complete === true && QUESTIONS.every(question => isAnswered(question, answers));
    return {
      answers, complete, step: Number.isInteger(saved.step) ? Math.max(0, Math.min(QUESTIONS.length - 1, saved.step)) : 0,
      page: complete && ['portfolio', 'assistant'].includes(saved.page) ? saved.page : 'questionnaire',
      draft: typeof saved.draft === 'string' ? saved.draft.slice(0, 4000) : '',
      messages: complete && Array.isArray(saved.messages) ? saved.messages.filter(message => message && typeof message === 'object' && ['user', 'assistant'].includes(message.role) && typeof message.content === 'string').slice(-40).map(message => ({ role: message.role, content: message.content.slice(0, 10000) })) : [],
      result: complete && saved.result ? safelyNormalize(saved.result) : null,
      proposal: complete && saved.proposal ? safelyNormalize(saved.proposal) : null,
    };
  } catch { return { answers: {}, complete: false, step: 0, page: 'questionnaire', draft: '', messages: [], result: null, proposal: null }; }
}

const state = readState();
let agentConnected = false;
let portfolioConnected = false;
let loadingPortfolio = false;
let portfolioError = '';
let sending = false;
let sendError = '';
let storageAvailable = true;
let toastTimer;
const requestGuard = createRequestGuard();
const portfolioGuard = createRequestGuard();
const currentPortfolio = () => state.result?.portfolio || DEMO_PORTFOLIO;

function invalidateConversation() {
  requestGuard.invalidate();
  portfolioGuard.invalidate();
  sending = false;
  loadingPortfolio = false;
  sendError = '';
  portfolioError = '';
  state.messages = [];
  state.result = null;
  state.proposal = null;
}

function persist() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
  catch {
    if (storageAvailable) toast('La sauvegarde locale est indisponible. Gardez cet onglet ouvert.');
    storageAvailable = false;
  }
}
function toast(message) {
  $('#toast').textContent = message;
  $('#toast').classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 4200);
}

function render() {
  document.title = `Recommand — ${state.page === 'questionnaire' ? 'Votre profil investisseur' : state.page === 'portfolio' ? 'Votre portefeuille' : 'Votre assistant'}`;
  $('#app').innerHTML = `${header()}<main id="main" tabindex="-1">${state.page === 'questionnaire' ? questionnaire() : state.page === 'portfolio' ? portfolio() : assistant()}</main>${footer()}`;
  if (state.page === 'assistant') $('#chat-messages')?.scrollTo({ top: $('#chat-messages').scrollHeight, behavior: 'instant' });
}

function header() {
  const nav = [['questionnaire', 'Votre profil'], ['portfolio', 'Votre portefeuille'], ['assistant', 'Votre assistant']];
  return `<header class="header"><div class="header-inner">
    <a class="brand" href="#" data-action="brand" aria-label="Recommand, accueil">recommand<span class="brand-dot">.</span></a>
    <nav class="main-nav" aria-label="Votre parcours">${nav.map(([page, label], index) => `<button class="nav-item ${state.page === page ? 'active' : ''}" data-page="${page}" ${index > 0 && !state.complete ? 'disabled' : ''} ${state.page === page ? 'aria-current="page"' : ''}><span class="nav-number">${index === 0 && state.complete ? icon('check') : `0${index + 1}`}</span><span>${label}</span>${index > 0 && !state.complete ? icon('lock', 'nav-lock') : ''}</button>`).join('')}</nav>
    <button class="help-button" data-action="help" aria-label="Comprendre le parcours">${icon('help')}<span>Le concept</span></button>
  </div></header>`;
}

function footer() {
  return `<footer class="footer"><span><span class="footer-mark">r.</span> Une idée qui prend forme. <span class="footer-event">Datathon 2026</span></span><div><span>Simulation · Aucun conseil en placement</span><button data-action="privacy">Données locales</button><button data-action="credits">Crédits</button></div></footer>`;
}

function answeredCount() {
  return QUESTIONS.filter((q, index) => isAnswered(q, state.answers) && (!q.optional || state.complete || index < state.step)).length;
}
function questionnaire() {
  const question = QUESTIONS[state.step];
  const answered = answeredCount();
  return `<div class="onboarding page-enter ${question.scenario ? 'scenario-page' : ''}"><section class="question-column" aria-label="Questionnaire investisseur">
    <div class="eyebrow"><span class="tiny-star">✳</span> L’INVESTISSEMENT, À VOTRE IMAGE</div>
    <h1>Tout commence<br>par <em>vous.</em></h1>
    <p class="hero-description">Vos envies, vos limites, votre horizon.<br>La première étape d’un portefeuille qui vous ressemble.</p>
    <div class="questionnaire-content">
      <div class="progress-meta"><span>VOTRE PROFIL INVESTISSEUR</span><span class="question-count"><strong>${String(state.step + 1).padStart(2, '0')}</strong><span> / ${QUESTIONS.length}</span></span></div>
      <div class="progress-track" role="progressbar" aria-label="Avancement du questionnaire" aria-valuenow="${answered}" aria-valuemin="0" aria-valuemax="${QUESTIONS.length}">${QUESTIONS.map((q, index) => `<span class="${index === state.step ? 'current' : ''} ${isAnswered(q, state.answers) && (!q.optional || state.complete || index < state.step) ? 'filled' : ''}"></span>`).join('')}</div>
      <div class="section-label"><span>${String(question.section + 1).padStart(2, '0')} / ${String(SECTIONS.length).padStart(2, '0')}</span>${SECTIONS[question.section]}</div>
      <form id="question-form" novalidate>
        <fieldset><legend id="question-title" class="question-title ${question.title.length > 120 ? 'long' : ''}">${escape(question.title)}</legend>
          <p class="question-help">${escape(question.help || (question.type === 'multi' ? 'Plusieurs réponses possibles.' : question.type === 'single' ? 'Choisissez une seule réponse.' : ''))}</p>
          ${question.scenario ? marketScenario() : ''}
          ${mainField(question)}
          <div id="question-details">${detailField(question)}</div>
          ${question.id === 'assets' ? '<p class="field-note">Si vous cochez « Toutes les catégories ci-dessus », il n’est pas nécessaire de cocher les autres choix.</p>' : ''}
        </fieldset>
        <p id="question-error" class="field-error" role="alert"></p>
        <div class="question-actions"><button type="button" class="back-button" data-action="previous" ${state.step === 0 ? 'disabled' : ''}>${icon('back')}<span>Retour</span></button><button type="submit" class="button primary next-button">${state.step === QUESTIONS.length - 1 ? 'Découvrir mon portefeuille' : 'Continuer'}${icon('arrow')}</button></div>
      </form>
      <div class="save-note">${icon('shield')}<span>${!storageAvailable ? 'Sauvegarde indisponible sur ce navigateur.' : portfolioConnected ? 'Vos réponses seront envoyées à votre moteur à la dernière étape.' : 'Vos réponses restent sur cet appareil.'}</span><span class="save-dot"></span><span id="answer-count" aria-live="polite">${answered}/${QUESTIONS.length} étapes complétées</span></div>
    </div>
  </section>${questionIllustration(question.id)}
  <div class="journey-strip"><div>${icon('file')}<span><strong>01. On fait connaissance</strong><small>${QUESTIONS.length} questions, à votre rythme</small></span></div><span class="journey-line"></span><div>${icon('chart')}<span><strong>02. Une vision d’ensemble</strong><small>Une répartition facile à lire</small></span></div><span class="journey-line"></span><div>${icon('chat')}<span><strong>03. À vous de préciser</strong><small>Un espace pour votre futur agent</small></span></div></div>
  </div>`;
}

function mainField(question) {
  if (question.type === 'number') return `<div class="amount-field"><label for="main-answer">Montant disponible</label><div><input id="main-answer" data-answer="${question.id}" type="number" inputmode="decimal" min="0" step="any" placeholder="Ex. : 100" value="${escape(state.answers[question.id] ?? '')}" aria-describedby="question-error"><span>$ CA</span></div></div>`;
  if (question.type === 'text') return `<div class="detail-field"><label for="main-answer">Vos précisions</label><textarea id="main-answer" data-answer="${question.id}" rows="5" maxlength="1000" placeholder="Ajoutez vos précisions ici…" ${state.answers.noNotes ? 'disabled' : ''}>${escape(state.answers[question.id] || '')}</textarea></div>`;
  return `<div class="options ${question.layout || 'list'}">${question.options.map(([value, label], index) => option(question, value, label, index)).join('')}</div>`;
}

function fieldPlaceholder(field) {
  const examples = {
    mortgageAmount: 'Ex. : 100 000', targetAmount: 'Ex. : 50 000',
    goalDetails: 'Ex. : achat d’une résidence',
    cryptoDetails: 'Précisez vos préférences…',
    exclusionDetails: 'Ex. : secteurs ou placements à exclure',
  };
  return examples[field.key] || (field.type === 'number' ? 'Ex. : 100' : 'Précisez votre situation…');
}

function option(question, value, label, index) {
  const selected = question.type === 'multi' ? state.answers[question.id]?.includes(value) : state.answers[question.id] === value;
  const parts = label.split(' — ');
  const visual = question.layout === 'risk' ? `<span class="risk-glyph" aria-hidden="true">${[0, 1, 2, 3, 4].map(bar => `<i class="${bar <= index ? 'on' : ''}" style="height:${9 + bar * 5}px"></i>`).join('')}</span>` : '';
  return `<label class="option ${selected ? 'selected' : ''}"><input type="${question.type === 'multi' ? 'checkbox' : 'radio'}" name="${question.id}" value="${value}" ${selected ? 'checked' : ''} aria-describedby="question-error">${visual}<span class="option-label">${parts.length > 1 ? `<strong>${escape(parts.shift())}</strong><span>${escape(parts.join(' — '))}</span>` : escape(label)}</span><span class="option-check ${question.type === 'multi' ? 'square' : ''}" aria-hidden="true">${selected ? icon('check') : ''}</span></label>`;
}

function detailField(question) {
  return question.details.filter(field => fieldVisible(field, state.answers)).map(field => {
    const value = state.answers[field.key];
    const id = `detail-${field.key}`;
    const label = escape(field.label);
    let markup;
    if (field.type === 'single') markup = `<fieldset><legend>${label}</legend>${field.options.map(([key,text]) => `<label class="supplement-option"><input type="radio" data-detail="${field.key}" name="${field.key}" value="${key}" ${value === key ? 'checked' : ''}><span>${escape(text)}</span></label>`).join('')}</fieldset>`;
    else if (field.type === 'boolean') markup = `<label class="supplement-option"><input id="${id}" type="checkbox" data-detail="${field.key}" ${value ? 'checked' : ''}><span>${label}</span></label>`;
    else markup = `<label for="${id}">${label}</label><input id="${id}" data-detail="${field.key}" type="${field.type === 'number' ? 'number' : 'text'}" ${field.type === 'number' ? 'min="0" step="any" inputmode="decimal"' : 'maxlength="1000"'} placeholder="${escape(fieldPlaceholder(field))}" value="${escape(value ?? '')}">${field.type === 'number' ? '<small>Montant en dollars canadiens</small>' : ''}`;
    return `<div class="detail-field" data-field="${field.key}">${markup}</div>`;
  }).join('');
}

// Les réponses changent sur place : aucun démontage du formulaire ou du visuel.
function updateQuestionSelection(question) {
  document.querySelectorAll('#question-form .options>.option').forEach(element => {
    const input = element.querySelector('input');
    input.checked = question.type === 'multi' ? Boolean(state.answers[question.id]?.includes(input.value)) : state.answers[question.id] === input.value;
    element.classList.toggle('selected', input.checked);
    element.querySelector('.option-check').innerHTML = input.checked ? icon('check') : '';
  });
  const details = $('#question-details');
  const template = document.createElement('template');
  template.innerHTML = detailField(question);
  const expected = [...template.content.children];
  for (const element of [...details.children]) {
    if (!expected.some(next => next.dataset.field === element.dataset.field)) element.remove();
  }
  expected.forEach((element, index) => {
    const existing = [...details.children].find(current => current.dataset.field === element.dataset.field);
    if (!existing) details.insertBefore(element, details.children[index] || null);
  });
  if (question.id === 'notes') {
    $('#main-answer').disabled = state.answers.noNotes === true;
    if (state.answers.noNotes) $('#main-answer').value = '';
  }
  const answered = answeredCount();
  $('.progress-track').setAttribute('aria-valuenow', answered);
  document.querySelectorAll('.progress-track>span').forEach((segment,index) => segment.classList.toggle('filled', isAnswered(QUESTIONS[index],state.answers) && (!QUESTIONS[index].optional || state.complete || index < state.step)));
  $('#answer-count').textContent = `${answered}/${QUESTIONS.length} étapes complétées`;
  $('#question-error').textContent = '';
  refreshConnectionUI();
}

function portfolio() {
  const selectedPortfolio = currentPortfolio();
  const positions = selectedPortfolio.positions;
  return `<div class="dashboard page-enter"><div class="dashboard-heading"><div><div class="eyebrow"><span class="status-dot"></span> VOTRE POINT DE DÉPART</div><h1>Votre portefeuille.<br><em>En toute clarté.</em></h1><p>Une vue d’ensemble aujourd’hui. Une conversation pour la suite.</p></div><div class="heading-actions"><button class="button outline" data-action="profile">${icon('edit')}Mes réponses</button><button class="icon-button" data-action="export" aria-label="Exporter le portefeuille et les réponses">${icon('download')}</button></div></div>
    ${portfolioBanner()}
    <div class="portfolio-grid"><section class="allocation-card"><div class="card-heading"><div><span class="eyebrow">LA VUE D’ENSEMBLE</span><h2>Une place pour chaque actif.</h2></div><span class="soft-badge">${positions.length} positions</span></div><div class="allocation-visual"><div class="donut" role="img" aria-label="${escape(allocationGroups(selectedPortfolio).map(group => `${group.weight} % ${group.name}`).join(", "))}" style="background:${donutGradient(positions)}"><div class="donut-hole"><span>Répartition</span><strong>100<span>%</span></strong><small>${selectedPortfolio.isDemo ? "Exemple illustratif" : "Simulation du moteur"}</small></div></div><div class="allocation-legend">${allocationGroups(selectedPortfolio).map(group => `<div><span style="--dot:${group.color}"></span><div><strong>${escape(group.name)}</strong><small>${group.count} position${group.count > 1 ? 's' : ''}</small></div><b>${formatWeight(group.weight)} %</b></div>`).join('')}</div></div><div class="allocation-footnote">${icon('leaf')}Une représentation de la répartition, sans projection de rendement.</div></section>
    <aside class="agent-card"><span class="eyebrow">LA SUITE, ENSEMBLE</span>${spark('agent-spark')}<h2>Un portefeuille.<br>Encore plus <em>vous.</em></h2><p>Précisez vos préférences, explorez vos options et posez vos questions dans un seul espace.</p><button class="button dark" data-page="assistant">Ouvrir la conversation${icon('arrow')}</button><small><span class="status-dot neutral"></span>${agentConnected ? 'Service agent configuré' : 'Espace prêt · Agent à connecter'}</small></aside>
    <section class="holdings-card"><div class="card-heading"><div><span class="eyebrow">DANS LE DÉTAIL</span><h2>${selectedPortfolio.isDemo ? "De quoi se compose cet exemple ?" : "Les actifs de votre portefeuille"}</h2></div><button class="text-button" data-action="export">Exporter ${icon('download')}</button></div><div class="holdings-table-wrap"><table class="holdings-table"><thead><tr><th>Actif</th><th>Catégorie</th><th>Répartition</th><th><span class="sr-only">Détails</span></th></tr></thead><tbody>${positions.map(position => `<tr><td><button class="holding-link" data-holding="${escape(position.symbol)}"><span class="asset-icon ${position.icon}">${escape(position.initials)}</span><span><strong>${escape(position.name)}</strong><small>${escape(position.symbol)}</small></span></button></td><td class="holding-category">${escape(position.category)}</td><td><div class="weight-cell"><span class="weight-track"><i style="width:${position.weight}%;background:${position.color}"></i></span><strong>${formatWeight(position.weight)} %</strong></div></td><td><button class="row-detail" data-holding="${escape(position.symbol)}" aria-label="Détails de ${escape(position.name)}">${icon('arrow')}</button></td></tr>`).join('')}</tbody><tfoot><tr><td>Total</td><td></td><td>100 %</td><td></td></tr></tfoot></table></div></section>
    <aside class="profile-card"><div class="card-heading"><div><span class="eyebrow">LE FIL DE VOTRE PROFIL</span><h2>Ce qui compte pour vous.</h2></div></div>${profileFact('shield', 'Tolérance déclarée', answerLabel(QUESTIONS.find(q => q.id === 'risk'), state.answers))}${profileFact('clock', 'Horizon de placement', answerLabel(QUESTIONS.find(q => q.id === 'horizon'), state.answers))}${profileFact('chart', 'Objectif principal', answerLabel(QUESTIONS.find(q => q.id === 'goal'), state.answers))}<button class="text-button" data-action="profile">Revoir mes ${QUESTIONS.length} réponses ${icon('arrow')}</button><p class="profile-caveat">Vos réponses sont enregistrées. Leur interprétation sera assurée par votre futur moteur.</p></aside></div>
    ${state.result ? resultEvidence(state.result) : ""}
    <section class="bottom-editorial"><span>CHAQUE PARCOURS EST DIFFÉRENT.</span><p>Le vôtre mérite<br><em>sa propre perspective.</em></p>${spark()}<button class="text-button" data-page="assistant">La conversation commence ici ${icon('arrow')}</button></section>
  </div>`;
}

function profileFact(symbol, label, value) { return `<div class="profile-fact">${icon(symbol)}<span><small>${label}</small><strong>${escape(value)}</strong></span></div>`; }
function donutGradient(positions) {
  let angle = 0;
  return `conic-gradient(${positions.map(position => { const start = angle; angle += position.weight * 3.6; const gap = Math.min(1.5, position.weight * 3.6 * .12); return `${position.color} ${start}deg ${angle - gap}deg, transparent ${angle - gap}deg ${angle}deg`; }).join(',')})`;
}

function portfolioBanner() {
  if (loadingPortfolio) return `<div class="demo-banner"><span class="loading-ring" role="status" aria-label="Chargement"></span><p><strong>Votre moteur prépare votre portefeuille.</strong> L’exemple reste visible pendant la préparation de votre simulation.</p></div>`;
  if (state.result) return `<div class="demo-banner result-banner">${icon('check')}<p><strong>${escape(state.result.portfolio.name)}</strong> · Simulation transmise par votre moteur. Les sources et les limites accompagnent le résultat.</p><button class="text-button" data-action="sources">Comprendre ${icon('arrow')}</button></div>`;
  return `<div class="demo-banner">${icon('info')}<p><strong>Un aperçu pour explorer la plateforme.</strong> Cette allocation fictive ne tient pas compte de vos réponses. Votre moteur de recommandation la remplacera après intégration.${portfolioError ? `<span class="portfolio-error">${escape(portfolioError)}</span>` : ''}</p>${portfolioConnected ? `<button class="text-button" data-action="generate-portfolio">${portfolioError ? 'Réessayer' : 'Créer ma simulation'} ${icon('arrow')}</button>` : '<span class="badge">DÉMONSTRATION</span>'}</div>`;
}

function sourceMarkup(item) {
  let source = escape(item.source);
  try {
    const url = new URL(item.source);
    if (['https:', 'http:'].includes(url.protocol)) source = `<a href="${escape(url.href)}" target="_blank" rel="noopener noreferrer">${escape(item.source)}</a>`;
  } catch { /* Une source peut être un fichier du jeu de données. */ }
  return `<div class="evidence-source"><span>${escape(item.id)}</span><div><strong>${source}</strong><p>${escape(item.description)}</p></div></div>`;
}

function evidenceBody(result) {
  return `<p class="result-explanation">${escape(result.explanation)}</p><details><summary>Consulter les sources · ${result.evidence.length}</summary><div class="evidence-sources">${result.evidence.map(sourceMarkup).join('')}</div></details><details><summary>Hypothèses et limites · ${result.limitations.length}</summary>${result.limitations.length ? `<ul>${result.limitations.map(item => `<li>${escape(item)}</li>`).join('')}</ul>` : '<p>Le moteur n’a communiqué aucune limite. Cela ne signifie pas qu’il n’en existe aucune.</p>'}</details><p class="run-reference">Simulation · Référence ${escape(result.runId)}</p>`;
}

function resultEvidence(result) { return `<section class="evidence-card"><div class="eyebrow">POUR COMPRENDRE VOTRE PORTEFEUILLE</div><h2>Les raisons. Les sources. Les limites.</h2>${evidenceBody(result)}</section>`; }

function proposalCard() {
  const proposal = state.proposal;
  return `<article class="proposal-card"><span class="eyebrow">UNE NOUVELLE PERSPECTIVE</span><h3>${escape(proposal.portfolio.name)}</h3><div class="proposal-positions">${proposal.portfolio.positions.map(position => { const previous = currentPortfolio().positions.find(item => item.symbol === position.symbol)?.weight || 0; return `<div><span>${escape(position.symbol)}</span><span>${formatWeight(previous)} % ${icon('arrow')} <strong>${formatWeight(position.weight)} %</strong></span></div>`; }).join('')}${currentPortfolio().positions.filter(position => !proposal.portfolio.positions.some(item => item.symbol === position.symbol)).map(position => `<div><span>${escape(position.symbol)}</span><span>${formatWeight(position.weight)} % ${icon('arrow')} <strong>0 %</strong></span></div>`).join('')}</div><p>Une proposition de simulation à examiner avant de l’appliquer à votre vue.</p><div class="proposal-actions"><button class="text-button" data-action="proposal-sources">Sources et limites</button><button class="button primary" data-action="accept-proposal">Retenir cette version ${icon('check')}</button></div></article>`;
}

function assistant() {
  return `<div class="assistant-page page-enter"><div class="assistant-title"><div><div class="eyebrow"><span class="tiny-star">✳</span> VOTRE ESPACE DE CONVERSATION</div><h1>Affinons <em>la suite.</em></h1></div><button class="text-button" data-page="portfolio">Voir mon portefeuille ${icon('arrow')}</button></div>
    <div class="conversation-layout"><aside class="conversation-sidebar"><span class="eyebrow">VOTRE POINT DE DÉPART</span><h2>La vue d’ensemble,<br>toujours à portée.</h2><div class="mini-allocation-bar">${currentPortfolio().positions.map(position => `<span style="width:${position.weight}%;background:${position.color}" title="${escape(position.symbol)} : ${formatWeight(position.weight)} %"></span>`).join('')}</div><span class="badge">${currentPortfolio().isDemo ? "ALLOCATION ILLUSTRATIVE" : "SIMULATION DU MOTEUR"}</span><div class="sidebar-positions">${currentPortfolio().positions.map(position => `<div><span style="--dot:${position.color}">${escape(position.symbol)}</span><strong>${formatWeight(position.weight)} %</strong></div>`).join('')}</div><div class="sidebar-profile">${profileFact('shield', 'Tolérance déclarée', answerLabel(QUESTIONS.find(q => q.id === 'risk'), state.answers))}${profileFact('clock', 'Votre horizon', answerLabel(QUESTIONS.find(q => q.id === 'horizon'), state.answers))}</div><button class="text-button" data-action="profile">Mes réponses ${icon('arrow')}</button><div class="sidebar-image"><img src="/assets/water.jpg" alt="Un horizon calme sur l’eau"><span>De la place<br>pour vos ambitions.</span></div></aside>
    <section class="chat-card" aria-label="Conversation avec votre assistant"><header class="chat-header"><div class="assistant-avatar">${spark()}</div><div><strong>Votre assistant Recommand</strong><span><i class="status-dot ${agentConnected ? '' : 'neutral'}"></i>${agentConnected ? 'Service configuré' : 'En attente de votre agent'}</span></div><button class="icon-button" data-action="agent-info" aria-label="Informations sur la connexion de l’agent">${icon('info')}</button></header>
    <div id="chat-messages" class="chat-messages" role="log" aria-live="polite" aria-label="Messages de la conversation">${state.messages.length ? state.messages.map(message => `<article class="message ${message.role}"><span class="message-author">${message.role === 'user' ? 'Vous' : 'Assistant'}</span><p>${escape(message.content)}</p></article>`).join('') : chatWelcome()}${state.proposal ? proposalCard() : ""}${sending ? `<div class="sending" role="status"><span></span><span></span><span></span><small>Votre agent prépare sa réponse…</small></div>` : ''}</div>
    <div class="chat-compose-area">${!agentConnected ? `<div class="connection-note">${icon('info')}<span>Votre équipe connectera l’agent. Vous pouvez déjà préparer votre message.</span></div>` : ''}${sendError ? `<p class="field-error chat-error" role="alert">${escape(sendError)}</p>` : ''}<form id="chat-form"><label for="chat-input" class="sr-only">Votre message à l’assistant</label><textarea id="chat-input" maxlength="4000" rows="2" placeholder="Ce que vous aimeriez préciser…" ${sending ? 'disabled' : ''}>${escape(state.draft)}</textarea><div class="composer-bottom"><span>${icon('lock')}<span>${agentConnected ? 'Envoyé uniquement à votre service configuré' : 'Brouillon enregistré sur cet appareil'}</span></span><button type="submit" class="send-button" ${!agentConnected || sending || !state.draft.trim() ? 'disabled' : ''} aria-label="Envoyer le message">${icon('send')}</button></div></form><p class="chat-disclaimer">Simulation. Les échanges ne constituent pas un conseil en placement.</p></div></section></div></div>`;
}

function chatWelcome() {
  return `<div class="chat-welcome">${spark('welcome-spark')}<span class="eyebrow">UN ESPACE POUR ALLER PLUS LOIN</span><h2>Votre portefeuille est<br>un <em>point de départ.</em></h2><p>Une préférence à préciser ? Un choix à comprendre ?<br>Votre futur assistant partira de vos réponses.</p><div class="prompt-suggestions">${['Comprendre la répartition du portefeuille', 'Préciser les secteurs qui m’intéressent', 'Discuter de mes exclusions'].map((prompt, index) => `<button data-prompt="${escape(prompt)}"><span>${icon(['chart', 'leaf', 'shield'][index])}${prompt}</span>${icon('arrow')}</button>`).join('')}</div>${!agentConnected ? '<small class="welcome-status"><i class="status-dot neutral"></i>L’interface est prête. Aucun agent n’est encore actif.</small>' : ''}</div>`;
}

function showModal(title, content, className = '') {
  const modal = $('#modal');
  if (modal.open) modal.close();
  modal.className = className;
  modal.innerHTML = `<div class="modal-top"><h2 id="modal-title">${title}</h2><button class="icon-button" data-action="close-modal" aria-label="Fermer">${icon('close')}</button></div>${content}`;
  modal.showModal();
}

function showProfile() {
  showModal('Votre profil, en vos mots.', `<p class="modal-intro">Les ${QUESTIONS.length} réponses qui serviront de point de départ à votre moteur de recommandation.</p><div class="profile-review">${QUESTIONS.map((question, index) => `<div><span class="review-number">${String(index + 1).padStart(2, '0')}</span><div><small>${escape(question.title)}</small><strong>${escape(answerLabel(question, state.answers))}</strong></div><button class="icon-button" data-edit-question="${index}" aria-label="Modifier la réponse ${index + 1}">${icon('edit')}</button></div>`).join('')}</div><button class="button primary modal-full" data-action="export-json">Exporter mes réponses ${icon('download')}</button>`);
}

function handleAction(action) {
  if (action === 'generate-portfolio') { generatePortfolio(); return; }
  if (action === 'sources' && state.result) { showModal('Comprendre cette simulation.', evidenceBody(state.result)); return; }
  if (action === 'proposal-sources' && state.proposal) { showModal('Comprendre la proposition.', evidenceBody(state.proposal)); return; }
  if (action === 'accept-proposal' && state.proposal) {
    requestGuard.invalidate(); portfolioGuard.invalidate(); loadingPortfolio = false; sending = false; sendError = ''; portfolioError = '';
    state.result = state.proposal; state.proposal = null; persist(); navigate('portfolio'); toast('Cette version est maintenant affichée dans votre portefeuille.'); return;
  }
  if (action === 'brand') { navigate(state.complete ? 'portfolio' : 'questionnaire'); return; }
  if (action === 'previous' && state.step > 0) { state.step--; persist(); render(); focusQuestion(); return; }
  if (action === 'close-modal') { $('#modal').close(); return; }
  if (action === 'profile') { showProfile(); return; }
  if (action === 'help') {
    showModal('D’abord vous. Puis la suite.', `<p class="modal-intro">Un parcours en trois étapes, pensé pour rester simple.</p><div class="concept-steps"><div><span>01</span><h3>Faites le point.</h3><p>Répondez aux ${QUESTIONS.length} questions du questionnaire investisseur. Vous pouvez revenir sur chaque choix.</p></div><div><span>02</span><h3>Prenez du recul.</h3><p>Découvrez une présentation lisible du portefeuille : actifs, catégories et répartition. Pour le moment, l’allocation affichée est un exemple fictif.</p></div><div><span>03</span><h3>Affinez par la conversation.</h3><p>Votre équipe branchera son agent à l’espace de discussion pour personnaliser la recommandation. Aucun agent n’est simulé dans cette version.</p></div></div><p class="modal-note">Prototype local AlphaForge AI · Datathon 2026. Aucun achat ni ordre de bourse n’est possible.</p>`);
    return;
  }
  if (action === 'privacy') {
    showModal('Vos données, sur cet appareil.', `<p class="modal-intro">Les réponses, le brouillon et la conversation sont conservés dans le stockage local de ce navigateur.</p><div class="privacy-lines"><p>${icon('shield')}Aucune inscription ni connexion bancaire.</p><p>${icon('lock')}Sans service configuré par votre équipe, aucun envoi de vos réponses.</p><p>${icon('info')}Sur un ordinateur partagé, les autres utilisateurs du même profil de navigateur peuvent accéder à ces données.</p></div><p>Si un moteur est configuré, la dernière étape du questionnaire lui transmet vos réponses pour préparer la simulation. L’envoi d’un message transmet les réponses, le portefeuille et la conversation au service agent configuré. L’historique local peut être réinitialisé ci-dessous.</p><button class="button outline" data-action="confirm-reset">Réinitialiser mon parcours ${icon('back')}</button>`);
    return;
  }
  if (action === 'confirm-reset') { showModal('Repartir d’une page blanche ?', '<p class="modal-intro">Vos réponses, votre brouillon et la conversation de cette plateforme seront effacés de ce navigateur. Vous pouvez les exporter avant de continuer.</p><div class="modal-buttons"><button class="button outline" data-action="export-json">Exporter mes données</button><button class="button primary" data-action="reset">Recommencer</button></div>'); return; }
  if (action === 'reset') { invalidateConversation(); Object.assign(state, { answers: {}, complete: false, step: 0, page: 'questionnaire', draft: '', messages: [] }); persist(); $('#modal').close(); render(); window.scrollTo(0, 0); toast('Votre nouveau parcours peut commencer.'); return; }
  if (action === 'agent-info') {
    showModal('Un espace prêt à se connecter.', `<p class="modal-intro">${agentConnected ? 'Un service agent est configuré sur votre serveur local.' : 'Le futur agent sera développé et connecté par votre équipe.'}</p><p>Cette interface prépare les échanges et conserve votre brouillon. Votre agent pourra proposer une nouvelle répartition, accompagnée de ses sources et de ses limites. Vous choisirez de retenir cette version.</p><p>Le contrat de branchement est documenté dans <code>docs/AGENT_INTEGRATION.md</code>. Votre moteur reste responsable de l’interprétation du questionnaire, des calculs, des preuves et de la validation des recommandations.</p><button class="button outline" data-action="refresh-agent">Vérifier la configuration ${icon('arrow')}</button>`);
    return;
  }
  if (action === 'refresh-agent') { $('#modal').close(); checkAgent(true); return; }
  if (action === 'credits') {
    showModal('Des inspirations, une identité.', `<p class="modal-intro">Recommand est un prototype indépendant réalisé pour le Datathon 2026. Il n’est affilié à aucune institution financière.</p><div class="credits-list"><h3>Direction et parcours</h3><p>Un thème crème et noir inspiré de la référence Wealthsimple fournie.</p><h3>Illustrations</h3><p>Illustrations SVG originales et locales adaptées au sujet de chaque question. Le bulletin de baisse reproduit la composition de la capture fournie et reste une mise en situation fictive, sans cotations réelles. Sources des anciennes photos conservées : <code>docs/INSPIRATIONS.md</code>.</p><h3>Questionnaire</h3><p>Les 16 questions, les choix et les champs complémentaires proviennent exclusivement du Word sélectionné. Aucun profil de risque ni rendement n’est déduit par l’interface.</p></div>`);
    return;
  }
  if (action === 'export') { showModal('Gardez une copie.', `<p class="modal-intro">Exportez vos réponses, votre conversation et la répartition affichée.</p><div class="export-options"><button data-action="export-json">${icon('file')}<span><strong>Le parcours complet</strong><small>Réponses, conversation et portefeuille · JSON</small></span>${icon('download')}</button><button data-action="export-csv">${icon('chart')}<span><strong>La répartition ${currentPortfolio().isDemo ? 'illustrative' : 'du moteur'}</strong><small>${currentPortfolio().positions.length} positions et leurs poids · CSV</small></span>${icon('download')}</button></div>`); return; }
  if (action === 'export-json') { download('recommand-parcours.json', JSON.stringify({ exportedAt: new Date().toISOString(), questionnaire: makeQuestionnairePayload(state.answers), portfolio: currentPortfolio(), result: state.result, conversation: state.messages, draft: state.draft, disclaimer: currentPortfolio().isDemo ? 'Simulation. Allocation illustrative non personnalisée. Aucun conseil en placement.' : 'Simulation transmise par le moteur. Aucun conseil en placement.' }, null, 2), 'application/json;charset=utf-8'); return; }
  if (action === 'export-csv') { download(currentPortfolio().isDemo ? 'recommand-allocation-illustrative.csv' : 'recommand-allocation-simulation.csv', portfolioCsv(currentPortfolio()), 'text/csv;charset=utf-8'); }
}

function download(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a'); link.href = url; link.download = filename; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000); toast('Votre fichier a été exporté.');
}

function navigate(page) {
  if (!['questionnaire', 'portfolio', 'assistant'].includes(page) || (page !== 'questionnaire' && !state.complete)) return;
  state.page = page; persist(); render(); window.scrollTo(0, 0); $('#main').focus({ preventScroll: true });
}
function focusQuestion() { window.scrollTo({ top: Math.min(window.scrollY, 160), behavior: 'smooth' }); $('#question-title')?.setAttribute('tabindex', '-1'); $('#question-title')?.focus({ preventScroll: true }); }

async function checkAgent(notify = false) {
  try {
    const response = await fetch('/api/config', { signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error();
    const config = await response.json();
    agentConnected = config.agentConnected === true;
    portfolioConnected = config.portfolioConnected === true;
    refreshConnectionUI();
    if (notify) toast(agentConnected ? 'Votre service agent est configuré.' : 'Aucun agent configuré pour le moment.');
  } catch {
    agentConnected = false; portfolioConnected = false;
    refreshConnectionUI();
    if (notify) toast('Le serveur local est inaccessible. Vérifiez qu’il est démarré.');
  }
}

function refreshConnectionUI() {
  if (state.page === 'questionnaire') {
    if ($('.save-note>span')) $('.save-note>span').textContent = !storageAvailable ? 'Sauvegarde indisponible sur ce navigateur.' : portfolioConnected ? 'Vos réponses seront envoyées à votre moteur à la dernière étape.' : 'Vos réponses restent sur cet appareil.';
    return;
  }
  const active = document.activeElement;
  const selection = active?.id === 'chat-input' ? [active.selectionStart, active.selectionEnd] : null;
  render();
  if (selection && $('#chat-input')) { $('#chat-input').focus({ preventScroll: true }); $('#chat-input').setSelectionRange(...selection); }
}

async function generatePortfolio() {
  if (!portfolioConnected || !state.complete || loadingPortfolio) return;
  const request = portfolioGuard.begin();
  requestGuard.invalidate(); sending = false; sendError = '';
  loadingPortfolio = true; portfolioError = ''; render();
  try {
    const response = await fetch('/api/portfolio', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ questionnaire: makeQuestionnairePayload(state.answers) }), signal: AbortSignal.any([request.signal, AbortSignal.timeout(35000)]) });
    const payload = await response.json();
    if (!response.ok) throw new Error(typeof payload.message === 'string' ? payload.message : 'Le moteur n’a pas pu fournir une simulation complète. Vos réponses sont conservées.');
    const result = normalizeRecommendation(payload);
    if (!portfolioGuard.isCurrent(request)) return;
    requestGuard.invalidate(); sending = false; sendError = '';
    state.result = result; state.proposal = null; state.messages = []; persist();
  } catch (error) {
    if (!portfolioGuard.isCurrent(request)) return;
    portfolioError = error.name === 'TimeoutError' ? 'Le moteur a dépassé le délai de réponse. Réessayez.' : error.message;
  } finally { if (portfolioGuard.isCurrent(request)) { loadingPortfolio = false; render(); } }
}

async function sendMessage() {
  if (!agentConnected || sending || !state.draft.trim()) return;
  sending = true; sendError = '';
  const request = requestGuard.begin();
  const submittedDraft = state.draft;
  const message = submittedDraft.trim(); render();
  try {
    const payload = boundedChatPayload({ message, conversation: state.messages, questionnaire: makeQuestionnairePayload(state.answers), portfolio: currentPortfolio() });
    const response = await fetch('/api/agent/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: AbortSignal.any([request.signal, AbortSignal.timeout(35000)]) });
    if (!response.ok) throw new Error(response.status === 503 ? 'Votre agent n’est pas encore disponible. Votre brouillon est conservé.' : 'Le service n’a pas pu répondre. Votre brouillon est conservé ; réessayez.');
    const result = await response.json();
    if (!requestGuard.isCurrent(request)) return;
    if (typeof result.message !== 'string' || !result.message.trim() || result.message.length > 10000) throw new Error('La réponse du service est invalide. Votre brouillon est conservé.');
    const proposal = result.proposal ? normalizeRecommendation(result.proposal) : null;
    state.messages.push({ role: 'user', content: message }, { role: 'assistant', content: result.message });
    state.proposal = proposal;
    state.messages = state.messages.slice(-40);
    if (state.draft === submittedDraft) state.draft = '';
    persist();
  } catch (error) { if (!requestGuard.isCurrent(request)) return; sendError = error.name === 'TimeoutError' || error.name === 'AbortError' ? 'Le délai de réponse est dépassé. Votre brouillon est conservé.' : error instanceof TypeError ? 'Connexion au serveur interrompue. Votre brouillon est conservé.' : error.message; }
  finally { if (requestGuard.isCurrent(request)) { sending = false; render(); $('#chat-input')?.focus({ preventScroll: true }); } }
}

document.addEventListener('click', event => {
  const pageButton = event.target.closest('[data-page]');
  if (pageButton) { event.preventDefault(); navigate(pageButton.dataset.page); return; }
  const actionButton = event.target.closest('[data-action]');
  if (actionButton) { event.preventDefault(); handleAction(actionButton.dataset.action); return; }
  const editButton = event.target.closest('[data-edit-question]');
  if (editButton) { $('#modal').close(); state.step = Number(editButton.dataset.editQuestion); state.page = 'questionnaire'; persist(); render(); focusQuestion(); return; }
  const prompt = event.target.closest('[data-prompt]');
  if (prompt) { if (sending) return; state.draft = prompt.dataset.prompt; persist(); render(); $('#chat-input').focus({ preventScroll: true }); return; }
  const holdingButton = event.target.closest('[data-holding]');
  if (holdingButton) {
    const position = currentPortfolio().positions.find(item => item.symbol === holdingButton.dataset.holding);
    if (!position) return;
    showModal(escape(position.name), `<span class="holding-symbol">${escape(position.symbol)} · ${escape(position.category)}</span><div class="holding-detail-weight"><strong>${formatWeight(position.weight)}<span>%</span></strong><span>${currentPortfolio().isDemo ? 'de l’exemple illustratif' : 'de votre simulation'}</span></div>${currentPortfolio().isDemo ? '<p>Cette position fait partie d’un exemple fixe destiné à présenter la plateforme. Son poids ne découle pas de vos réponses au questionnaire.</p><p>Votre moteur fournira les actifs retenus, leurs pondérations, les raisons de ses choix et les limites des données utilisées.</p>' : `<p>Cette répartition a été transmise par votre moteur. Consultez ses sources et ses limites pour comprendre la simulation.</p><button class="button outline" data-action="sources">Comprendre le résultat ${icon('arrow')}</button>`}<p class="modal-note">Simulation uniquement. Aucune transaction, cotation en temps réel ou promesse de rendement.</p>`);
  }
});

function saveQuestionInput(target) {
  const question = QUESTIONS[state.step];
  const wasComplete = state.complete;
  invalidateConversation();
  state.complete = false;
  const key = target.dataset.detail || target.dataset.answer || question.id;
  if (target.dataset.detail || target.dataset.answer) {
    const field = question.details.find(item => item.key === key) || question;
    if (field.type === 'boolean') state.answers[key] = target.checked;
    else if (target.value === '') delete state.answers[key];
    else state.answers[key] = field.type === 'number' ? Number(target.value) : target.value;
    if (key === 'noNotes' && target.checked) delete state.answers.notes;
  } else if (question.type === 'multi') {
    const selected = new Set(state.answers[question.id] || []);
    if (question.id === 'assets' && target.value === 'all' && target.checked) selected.clear();
    if (question.id === 'assets' && target.value !== 'all') selected.delete('all');
    target.checked ? selected.add(target.value) : selected.delete(target.value);
    state.answers[question.id] = [...selected];
  } else state.answers[question.id] = target.value;
  for (const field of question.details) if (!fieldVisible(field, state.answers)) delete state.answers[field.key];
  persist();
  updateQuestionSelection(question);
  if (wasComplete) $('.header').outerHTML = header();
}

document.addEventListener('change', event => {
  if (event.target.matches('#question-form input[type="radio"], #question-form input[type="checkbox"]')) saveQuestionInput(event.target);
});
document.addEventListener('input', event => {
  if (event.target.closest('#question-form') && (event.target.dataset.detail || event.target.dataset.answer) && !event.target.matches('[type="radio"], [type="checkbox"]')) saveQuestionInput(event.target);
  if (event.target.id === 'chat-input') { state.draft = event.target.value; persist(); $('.send-button').disabled = !agentConnected || sending || !state.draft.trim(); }
});

document.addEventListener('submit', event => {
  if (event.target.id === 'question-form') {
    event.preventDefault();
    const question = QUESTIONS[state.step];
    if (!isAnswered(question, state.answers)) { $('#question-error').textContent = question.type === 'number' ? 'Indiquez un montant valide, égal ou supérieur à zéro.' : 'Complétez la question et les champs requis pour continuer.'; $('#question-error').scrollIntoView({ block: 'nearest', behavior: 'smooth' }); document.querySelector('#question-form input, #question-form textarea')?.focus({ preventScroll: true }); return; }
    if (state.step < QUESTIONS.length - 1) { state.step++; persist(); render(); focusQuestion(); }
    else {
      const missing = QUESTIONS.findIndex(q => !isAnswered(q, state.answers));
      if (missing >= 0) { state.step = missing; persist(); render(); focusQuestion(); return; }
      state.complete = true; state.page = 'portfolio'; persist(); render(); window.scrollTo(0, 0); $('#main').focus({ preventScroll: true });
      if (portfolioConnected && !state.result) generatePortfolio();
    }
  }
  if (event.target.id === 'chat-form') { event.preventDefault(); sendMessage(); }
});

document.addEventListener('keydown', event => {
  if (event.target.id === 'chat-input' && event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); sendMessage(); }
});
$('#modal').addEventListener('click', event => { if (event.target === $('#modal')) { const bounds = $('#modal').getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) $('#modal').close(); } });

render();
checkAgent();
