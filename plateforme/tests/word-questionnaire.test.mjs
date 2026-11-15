import { loadExposureCategories } from '../lib/exposure-categories.mjs';
const exposureFixture = await loadExposureCategories();
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { JSDOM } from 'jsdom';
import { QUESTIONS, SECTIONS, QUESTIONNAIRE_VERSION, cleanAnswers, isAnswered, validateAnswers, makeQuestionnairePayload } from '../src/data.js';
import { marketScenario, questionIllustration } from '../src/illustrations.js';
import { simulationFixture } from './fixtures/change-review.mjs';

const fixture = JSON.parse(await readFile(new URL('./fixtures/questionnaire-word.json', import.meta.url), 'utf8'));
const key = 'recommand.platform.word16.v2';
const appUrl = new URL('../src/app.js', import.meta.url);
const html = await readFile(new URL('../index.html', import.meta.url), 'utf8');
const completeAnswers = () => Object.fromEntries([
  ...QUESTIONS.filter(q => !q.optional).map(q => [q.id, q.type === 'number' ? 0 : q.type === 'multi' ? [q.options[0][0]] : q.options[0][0]]),
]);

async function open(t, saved = {}, legacy = false, options = {}) {
  const dom = new JSDOM(html, { url: 'http://localhost:4173', runScripts: 'outside-only' });
  const w = dom.window;
  t.after(() => w.close());
  w.localStorage.setItem(legacy ? 'recommand.platform.v1' : key, JSON.stringify(saved));
  w.scrollTo = () => {};
  w.HTMLElement.prototype.scrollIntoView = () => {};
  w.HTMLElement.prototype.scrollTo = () => {};
  w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  w.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
  w.AbortSignal = AbortSignal;
  w.AbortController = AbortController;
  const serviceFetch=options.fetch || (async () => ({ ok: true, json: async () => options.config || { agentConnected: false, portfolioConnected: false } }));
  w.fetch=(url,...args)=>url==='/api/asset-categories' ? Promise.resolve({ok:true,json:async()=>options.exposureData || exposureFixture}) : serviceFetch(url,...args);
  w.__modules = {};
  let source = await readFile(appUrl, 'utf8');
  for (const [statement,names,path] of [...source.matchAll(/^import\s+\{([^}]+)\}\s+from\s+'([^']+)';/gm)]) {
    w.__modules[path] = await import(new URL(path, appUrl));
    source = source.replace(statement, `const {${names}} = window.__modules[${JSON.stringify(path)}];`);
  }
  w.eval(source);
  await new Promise(resolve => setImmediate(resolve));
  const $ = selector => w.document.querySelector(selector);
  return { w, $, saved: () => JSON.parse(w.localStorage.getItem(key) || '{}'),
    choose(value, field) {
      const input = $(`#question-form input${field ? `[data-detail="${field}"]` : ':not([data-detail])'}[value="${value}"]`);
      assert.ok(input, `${value} option exists`); input.focus(); input.click(); return input;
    },
    type(selector,value) { const input = $(selector); assert.ok(input, selector); input.focus(); input.value = value; input.dispatchEvent(new w.Event('input', { bubbles: true })); return input; },
    next() { $('#question-form').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true })); },
  };
}

test('all 15 questions match the Word snapshot with the explicit user removals', () => {
  assert.equal(fixture.source, 'Questionnaire_client_Recommand_20261115_103525.docx');
  assert.match(fixture.sha256, /^[0-9a-f]{64}$/);
  assert.equal(QUESTIONS.length, 15);
  assert.deepEqual(SECTIONS, fixture.sections);
  const expected = structuredClone(fixture.questions.filter(q=>q.id!=='marital'));
  for(const q of expected) q.details=q.details.filter(f=>f.key!=='withdrawalTiming');
  expected.find(q => q.id === 'goal').details = expected.find(q => q.id === 'goal').details.filter(field => field.key !== 'targetAmount');
  const exclusions = expected.find(q => q.id === 'exclusions');
  exclusions.options = exclusions.options.filter(([value]) => value !== 'discussion');
  exclusions.details[0].label = 'Si limites, vos précisions facultatives';
  exclusions.details[0].when.values = ['limits'];
  for (const q of expected) for (const f of q.details) {
    if (['maritalOther','dependentsOther','incomeOther','debtOther'].includes(f.key)) { f.required=true; f.label='Pr\u00e9cisez votre situation (obligatoire)'; }
    if (f.key==='goalDetails') { f.requiredWhen={field:'goal',values:['other']}; f.label='Pr\u00e9cisez votre objectif (obligatoire si Autre)'; }
  }
  assert.deepEqual(QUESTIONS, expected);
  assert.equal(QUESTIONS.some(q => q.id === 'return'), false);
  assert.equal(QUESTIONS.some(q => q.id === 'monthlyExpenses'), false);
});

const resetResult = () => ({
  runId: 'reset-regression',
  portfolio: { id: 'test-only', name: 'Simulation de test', positions: [{ symbol: 'TEST', name: 'Actif de test', category: 'Test', group: 'Test', weight: 100 }] },
  explanation: 'Résultat fictif utilisé uniquement par les tests.',
  evidence: [{ id: 'T1', source: 'Fixture locale', description: 'Donnée de test' }],
  limitations: ['Fixture sans données de marché.'], compliance: { passed: true },
});

test('the shared reset clears the entire profile from each page and survives reload', async t => {
  for (const page of ['questionnaire', 'portfolio', 'assistant']) {
    const app = await open(t, { page, step: 5, complete: true, answers: completeAnswers(), draft: 'Brouillon', messages: [{role:'user',content:'Ancienne conversation'}], result: resetResult(), proposal: resetResult() });
    app.w.localStorage.setItem('recommand.platform.v1', 'obsolete');
    app.w.localStorage.setItem('recommand.platform.word16.v1', 'obsolete');
    app.w.localStorage.setItem('unrelated-app', 'keep');
    const reset = app.$('.header [data-action="reset"]');
    assert.ok(reset, `reset is visible in the shared header on ${page}`);
    assert.match(reset.getAttribute('aria-label'), /Recommencer mon profil/);
    reset.click();
    assert.deepEqual(app.saved(), { answers: {}, complete: false, step: 0, page: 'questionnaire', draft: '', messages: [], result: null, proposal: null });
    assert.equal(app.$('#question-title').textContent, QUESTIONS[0].title);
    assert.equal(app.$('#question-form input:checked'), null);
    assert.equal(app.$('[data-page="portfolio"]').disabled, true);
    assert.equal(app.w.localStorage.getItem('recommand.platform.v1'), null);
    assert.equal(app.w.localStorage.getItem('recommand.platform.word16.v1'), null);
    assert.equal(app.w.localStorage.getItem('unrelated-app'), 'keep');
    const reload = await open(t, app.saved());
    assert.deepEqual(reload.saved().answers, {});
    assert.equal(reload.$('#question-title').textContent, QUESTIONS[0].title);
  }
});

test('removed marital choice and goal amount are absent, pruned and rejected by the contract', async t => {
  const obsolete = { ...completeAnswers(), marital: 'separated', targetAmount: 50000 };
  const app = await open(t, { answers: obsolete, complete: true, page: 'portfolio', result: resetResult(), messages: [{role:'assistant',content:'Ancien résultat'}] });
  assert.equal(app.$('input[value="separated"]'), null);
  assert.equal(app.saved().answers.marital, undefined);
  assert.equal(app.saved().answers.targetAmount, undefined);
  assert.equal(app.saved().complete, false);
  assert.equal(app.saved().result, null);
  assert.deepEqual(app.saved().messages, []);
  assert.equal(app.$('#question-form input:checked').value, 'none');
  const amountOnly = await open(t, { answers: { ...completeAnswers(), targetAmount: 50000 }, complete: true, page: 'portfolio', result: resetResult() });
  assert.equal(amountOnly.saved().complete, false);
  assert.deepEqual(amountOnly.saved().answers, completeAnswers());
  amountOnly.$('[data-question-index="5"]').click();
  assert.equal(amountOnly.$('[data-detail="targetAmount"]'), null);
  amountOnly.choose('project');
  assert.ok(amountOnly.$('[data-detail="goalDetails"]'));
  assert.equal(validateAnswers({ ...completeAnswers(), marital: 'separated' }), false);
  assert.equal(validateAnswers({ ...completeAnswers(), targetAmount: 50000 }), false);
  assert.equal(validateAnswers(completeAnswers()), true);
  const template = JSON.parse(await readFile(new URL('../Questionnaire_client_Recommand.json', import.meta.url), 'utf8'));
  assert.equal(template.questions.some(q => q.id === 'situation_conjugale'), false);
  assert.equal(template.questions.find(q=>q.id==='horizon').champs_complementaires.some(f=>f.id==='delai_retrait'),false);
  assert.equal(template.questions.find(q => q.id === 'objectif_investissement').champs_complementaires.some(f => f.id === 'objectif_montant'), false);
});

test('reset cancels pending chat and portfolio responses instead of restoring the old profile', async t => {
  for (const kind of ['chat', 'portfolio']) {
    let finish, signal;
    const app = await open(t, { page: kind === 'chat' ? 'assistant' : 'portfolio', complete: true, answers: completeAnswers(), draft: 'Une question de test' }, false, {
      fetch: async (url, options) => {
        if (url === '/api/config') return { ok: true, json: async () => ({ agentConnected: true, portfolioConnected: true }) };
        signal = options.signal;
        return new Promise(resolve => { finish = resolve; });
      },
    });
    if (kind === 'chat') app.$('#chat-form').dispatchEvent(new app.w.Event('submit', { bubbles: true, cancelable: true }));
    else app.$('[data-action="generate-portfolio"]').click();
    assert.equal(typeof finish, 'function');
    app.$('.header [data-action="reset"]').click();
    assert.equal(signal.aborted, true);
    finish({ ok: true, json: async () => kind === 'chat' ? { message: 'Réponse tardive', proposal: resetResult() } : resetResult() });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(app.saved().page, 'questionnaire');
    assert.equal(app.saved().step, 0);
    assert.deepEqual(app.saved().answers, {});
    assert.deepEqual(app.saved().messages, []);
    assert.equal(app.saved().result, null);
    assert.equal(app.saved().proposal, null);
  }
});

test('the refined conversation shows a compact context, free text entry without preset suggestions', async t => {
  const app = await open(t, { page: 'assistant', complete: true, answers: completeAnswers() });
  assert.match(app.$('.assistant-title h1').textContent, /Affinons votre portefeuille/);
  assert.equal(app.$('.conversation-sidebar img'), null);
  assert.equal(app.w.document.querySelectorAll('[data-prompt]').length, 0);
  assert.ok(app.$('.chat-card.is-empty'));
  assert.match(app.$('label[for="chat-input"]').textContent, /Que souhaitez-vous préciser/);
  assert.equal(app.$('.prompt-suggestions'), null);
  const prompt = 'Ma question personnelle';
  app.type('#chat-input', prompt);
  assert.equal(app.$('#chat-input').value, prompt);
  assert.equal(app.w.document.activeElement, app.$('#chat-input'));
  assert.equal(app.saved().draft, prompt);
  assert.deepEqual(app.saved().answers, completeAnswers());
  assert.equal(app.$('.send-button').disabled, true);
});

test('single choices preserve main, form, illustration and keyboard focus', async t => {
  const app = await open(t);
  const main = app.$('#main'), form = app.$('#question-form'), art = app.$('.question-illustration');
  const a = app.choose('none');
  assert.equal(app.$('#main'), main); assert.equal(app.$('#question-form'), form);
  assert.equal(app.$('.question-illustration'), art); assert.equal(app.w.document.activeElement, a);
  app.choose('one');
  assert.equal(a.checked, false); assert.equal(app.saved().answers.dependents, 'one');
  assert.equal(app.$('[role="progressbar"]').getAttribute('aria-valuenow'), '1');
  assert.equal(app.$('[role="progressbar"]').getAttribute('aria-valuemax'), '15');
});

test('other details and shared charges keep typed values and remove hidden answers', async t => {
  const app = await open(t, { step: 0 });
  app.choose('other');
  const field = app.type('[data-detail="dependentsOther"]', 'Responsabilité familiale');
  app.choose('shared','supportMode');
  assert.equal(app.$('[data-detail="dependentsOther"]'), field);
  assert.equal(app.saved().answers.supportMode, 'shared');
  app.choose('none');
  assert.equal(app.$('[data-detail="dependentsOther"]'), null);
  assert.equal(app.saved().answers.dependentsOther, undefined);
  assert.equal(app.saved().answers.supportMode, undefined);
});

test('emergency fund accepts numeric zero and rejects missing or negative amount', async t => {
  const app = await open(t, { step: 4 });
  app.next(); assert.match(app.$('#question-error').textContent, /montant valide/);
  const main = app.$('#main');
  app.type('[data-answer="emergencyFund"]', '-1'); app.next();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[4].title);
  app.type('[data-answer="emergencyFund"]', '0');
  assert.equal(app.$('#main'), main); assert.equal(app.saved().answers.emergencyFund, 0);
  app.next(); assert.equal(app.$('#question-title').textContent, QUESTIONS[5].title);
});

test('horizon has no removed withdrawal follow-up and a single answer is sufficient',async t=>{
 const app=await open(t,{step:QUESTIONS.findIndex(q=>q.id==='horizon')});
 app.choose('10');assert.equal(app.$('[data-detail="withdrawalTiming"]'),null);
 app.next();assert.equal(app.$('#question-title').textContent,QUESTIONS.find(q=>q.id==='liquidity').title);
});

test('empty fields show examples without saving them as answers or replacing entered values', async t => {
  const amount = await open(t, { step: 4 });
  assert.equal(amount.$('[data-answer="emergencyFund"]').placeholder, 'Ex. : 100');
  assert.equal(amount.$('[data-answer="emergencyFund"]').value, '');
  amount.next(); assert.equal(amount.saved().answers?.emergencyFund, undefined);
  amount.type('[data-answer="emergencyFund"]', '100');
  assert.equal(amount.saved().answers.emergencyFund, 100);
  const debt = await open(t, { step: 3, answers: { mortgageAmount: 24 } });
  assert.equal(debt.$('[data-detail="mortgageAmount"]').placeholder, 'Ex. : 100 000');
  assert.equal(debt.$('[data-detail="mortgageAmount"]').value, '24');
  debt.choose('other');
  assert.ok(debt.$('[data-detail="debtOther"]').placeholder);
  const notes = await open(t, { step: 14 });
  assert.ok(notes.$('[data-answer="notes"]').placeholder);
  assert.equal(notes.$('[data-answer="notes"]').value, '');
});

test('all assets is exclusive, crypto details persist for all and are cleared when irrelevant', async t => {
  const app = await open(t, { step: 12 });
  app.choose('crypto'); const text = app.type('[data-detail="cryptoDetails"]', 'Précision');
  app.choose('bonds'); assert.equal(app.$('[data-detail="cryptoDetails"]'), text);
  app.choose('all'); assert.deepEqual(app.saved().answers.assets, ['all']);
  assert.equal(app.$('[data-detail="cryptoDetails"]'), text);
  app.choose('stocks'); assert.deepEqual(app.saved().answers.assets, ['stocks']);
  assert.equal(app.saved().answers.cryptoDetails, undefined);
});

test('optional final notes can be empty, typed or explicitly declined', async t => {
  const app = await open(t, { step: 14, answers: completeAnswers() });
  app.type('[data-answer="notes"]', 'Mon projet');
  app.$('[data-detail="noNotes"]').click();
  assert.equal(app.$('[data-answer="notes"]').disabled, true);
  assert.equal(app.saved().answers.notes, undefined);
  app.next(); assert.equal(app.saved().complete, true); assert.ok(app.$('.dashboard'));
});

test('exclusion details survive a relevant choice and disappear with no exclusions', async t => {
  const app = await open(t, { step: 13 });
  app.choose('limits'); const field = app.type('[data-detail="exclusionDetails"]','Précision sur les placements');
  assert.equal(app.$('input[value="discussion"]'), null);
  assert.equal(app.$('[data-detail="exclusionDetails"]'),field);
  assert.equal(app.saved().answers.exclusionDetails, 'Précision sur les placements');
  app.choose('none'); assert.equal(app.$('[data-detail="exclusionDetails"]'),null);
  assert.equal(app.saved().answers.exclusionDetails,undefined);
});

test('removed discussion answers are cleared without inventing a replacement', async t => {
  const app = await open(t, { step: 13, complete: true, answers: { ...completeAnswers(), exclusions: 'discussion', exclusionDetails: 'Ancien choix' } });
  assert.equal(app.$('input:checked'), null);
  assert.equal(app.$('[data-detail="exclusionDetails"]'), null);
  assert.equal(app.$('[data-page="portfolio"]').disabled, true);
  const oldAnswers = { ...completeAnswers(), exclusions: 'discussion' };
  assert.equal(validateAnswers(oldAnswers), false);
  assert.equal(cleanAnswers(oldAnswers).exclusions, undefined);
  assert.equal(validateAnswers({ ...completeAnswers(), exclusions: 'limits', exclusionDetails: 'Mes limites' }), true);
});

test('all 15 questions are traversable and answers remain available on return', async t => {
  const app = await open(t);
  for (const q of QUESTIONS) {
    assert.equal(app.$('#question-title').textContent, q.title);
    if (q.type === 'number') app.type('[data-answer="emergencyFund"]', '2500.50');
    else if (q.type !== 'text') app.choose(q.options[0][0]);
    app.next();
  }
  assert.equal(app.saved().page, 'portfolio'); assert.ok(app.$('.dashboard'));
  assert.equal(app.$('.portfolio-context').textContent.includes('Rendement souhaité'), false);
  app.$('[data-page="questionnaire"]').click();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[14].title);
  app.$('[data-action="previous"]').click();
  assert.equal(app.$('input[value="none"]').checked, true);
});

test('progress navigation jumps freely and preserves radio and numeric answers', async t => {
  const app = await open(t);
  assert.equal(app.w.document.querySelectorAll('.progress-track button').length, QUESTIONS.length);
  assert.equal(app.$('[aria-current="step"]').dataset.questionIndex, '0');
  app.choose('one');
  assert.equal(app.$('[data-question-index="0"]').classList.contains('filled'), true);
  app.$('[data-question-index="4"] span').click();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[4].title);
  assert.equal(app.w.document.activeElement, app.$('#question-title'));
  assert.equal(app.$('[aria-current="step"]').dataset.questionIndex, '4');
  app.type('#main-answer', '100');
  app.$('[data-question-index="0"]').click();
  assert.equal(app.$('input[value="one"]').checked, true);
  app.$('[data-question-index="4"]').click();
  assert.equal(app.$('#main-answer').value, '100');
  assert.equal(app.saved().step, 4);
  assert.equal(app.saved().answers.emergencyFund, 100);
  assert.equal(app.$('[role="progressbar"]').getAttribute('aria-valuenow'), '2');
});

test('jumping to the last question cannot bypass required answers', async t => {
  const app = await open(t);
  app.$('[data-question-index="14"]').click();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[14].title);
  app.next();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[0].title);
  assert.equal(app.saved().step, 0);
  assert.equal(app.$('[data-page="portfolio"]').disabled, true);
  assert.notEqual(app.saved().complete, true);
  assert.equal(app.w.document.querySelectorAll('.progress-track [aria-current="step"]').length, 1);
});

test('reaction question keeps the large centered scenario within the question and preserves its answer', async t => {
  const app = await open(t, { step: 9 });
  assert.ok(app.$('.onboarding.scenario-page #question-form .market-scenario'));
  assert.equal(app.$('.onboarding > .market-scenario'), null);
  assert.ok(app.$('.hero-description'));
  const title = app.$('#question-title');
  const chart = app.$('.market-chart');
  app.choose('worried');
  assert.equal(app.$('.market-chart'), chart);
  assert.equal(app.$('#question-title'), title);
  app.$('[data-question-index="8"]').click();
  app.$('[data-question-index="9"]').click();
  assert.equal(app.$('input[value="worried"]').checked, true);
  assert.ok(app.$('#question-form .market-scenario'));
});

test('portfolio refinement appears directly below results and opens the conversation', async t => {
  const app = await open(t, { page: 'portfolio', complete: true, answers: completeAnswers() });
  const invitation = app.$('.portfolio-refine');
  assert.ok(invitation);
  assert.equal(invitation.previousElementSibling.className, 'portfolio-grid');
  assert.equal(app.$('#portfolio-refine-title').textContent, 'Affiner mon portefeuille');
  assert.equal(app.$('.portfolio-grid .agent-card'), null);
  assert.match(invitation.textContent, /Agent à connecter/);
  invitation.querySelector('[data-page="assistant"]').click();
  assert.equal(app.saved().page, 'assistant');
  assert.ok(app.$('#chat-input'));
  assert.deepEqual(app.saved().answers, completeAnswers());
});

test('changing a completed profile invalidates earlier result and dependent navigation', async t => {
  const app = await open(t, { step: 8, page: 'questionnaire', complete: true, answers: completeAnswers(), messages: [{role:'user',content:'test'}] });
  const main = app.$('#main');
  app.choose('high');
  assert.equal(app.$('#main'), main); assert.equal(app.saved().complete, false);
  assert.equal(app.$('[data-page="portfolio"]').disabled, true);
  assert.deepEqual(app.saved().messages, []); assert.equal(app.saved().result, null);
});

test('legacy eight-question storage cannot become a completed Word questionnaire', async t => {
  const app = await open(t, { complete: true, page: 'portfolio', answers: { risk:'medium' } }, true);
  assert.equal(app.$('#question-title').textContent, QUESTIONS[0].title);
  assert.equal(app.$('[data-page="portfolio"]').disabled, true);
});

test('typed payload accepts legitimate values and rejects unknown, stale and contradictory data', () => {
  const answers = completeAnswers();
  assert.equal(validateAnswers(answers), true);
  assert.equal(makeQuestionnairePayload(answers).version, QUESTIONNAIRE_VERSION);
  for (const value of [-1, null, '100', Infinity, NaN]) assert.equal(validateAnswers({...answers, emergencyFund:value}), false);
  assert.equal(validateAnswers({...answers, return:'5_6'}), false);
  assert.equal(validateAnswers({...answers, mortgageAmount:-1}), false);
  assert.equal(validateAnswers({...answers, assets:['all','stocks']}), false);
  assert.equal(validateAnswers({...answers, maritalOther:'hidden'}), false);
  assert.equal(validateAnswers({...answers, notes:'texte', noNotes:true}), false);
  assert.equal(validateAnswers({...answers, notes:'<script>not executable</script>'}), true);
  assert.equal(cleanAnswers({...answers, mortgageAmount:0}).mortgageAmount, 0);
  assert.equal(isAnswered(QUESTIONS[14], {}), true);
});

test('source scenario is fictional and illustrations cover each subject without market data', () => {
  const scenario = marketScenario();
  assert.match(scenario, /Bulletin spécial · Mise en situation fictive/);
  for (const text of ['10 000','8 000','2 000','trois mois','sans lien avec une actualité réelle']) assert.ok(scenario.includes(text));
  assert.match(scenario, /market-chart/);
  for (const q of QUESTIONS.filter(q => !q.scenario)) assert.match(questionIllustration(q.id), /<svg/);
  assert.equal(questionIllustration('reaction'), '');
});

test('styles parse and retain an entry animation without opacity-zero page flashes', async () => {
  const dom = new JSDOM('<html><head></head></html>');
  for (const file of ['styles','theme','questionnaire','portfolio','geography']) {
    const css = await readFile(new URL(`../src/${file}.css`,import.meta.url),'utf8');
    const element = dom.window.document.createElement('style'); element.textContent = css;
    dom.window.document.head.append(element); assert.ok(element.sheet.cssRules.length > 0);
    if (file === 'styles') assert.doesNotMatch(css.match(/@keyframes\s+page-in\s*\{[^\n]+/)[0], /opacity\s*:\s*0/);
  }
  dom.window.close();
});

test('the portfolio gives the explanation a main region and keeps demo reasons explicitly unavailable', async t => {
  const app = await open(t, { page: 'portfolio', complete: true, answers: completeAnswers() });
  const studio = app.$('.portfolio-grid > #portfolio-explanation');
  assert.ok(studio);
  assert.equal(studio.getAttribute('aria-labelledby'), 'explanation-title');
  assert.match(studio.textContent, /EXPLICATION NON DISPONIBLE/);
  assert.equal(app.$('.agent-rationale'), null);
  assert.equal(app.$('.profile-card'), null);
  assert.equal(app.w.document.querySelectorAll('.portfolio-context .profile-fact').length, 3);
  assert.equal(app.$('.holdings-card').previousElementSibling.className, 'portfolio-refine');
  assert.equal(app.$('[href="#portfolio-explanation"]').textContent.includes('Comprendre'), true);
  assert.equal(studio.querySelectorAll('[role="tab"]').length,0);
  assert.equal(app.$('#decision-panel-sources'),null);
  assert.equal(app.$('#decision-panel-limits'),null);
  assert.ok(app.$('#decision-panel-overview'));

});

test('the actual explanation and limitations are displayed while internal evidence stays hidden', async t => {
  const result = resetResult();
  result.runId = 'explanation-contract-fixture';
  result.explanation = 'Premier paragraphe de la fixture.\n\nUn second paragraphe <img src=x onerror=alert(1)>.';
  result.evidence = [{ id: 'EX1', source: 'https://example.com/fixture', description: 'Source synthétique uniquement.' }];
  result.limitations = ['Limite synthétique <script>non exécuté</script>.'];
  const requests = [];
  const app = await open(t, { page: 'portfolio', complete: true, answers: completeAnswers() }, false, {
    fetch: async (url, options) => {
      requests.push({ url, options });
      return { ok: true, json: async () => url === '/api/config' ? { agentConnected: true, portfolioConnected: true } : result };
    },
  });
  assert.ok(app.$('.awaiting-explanation'));
  app.$('[data-action="generate-portfolio"]').click();
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(app.$('.has-explanation'));
  const rationale = app.$('.agent-rationale');
  assert.equal(rationale.querySelectorAll('p').length, 2);
  assert.equal([...rationale.querySelectorAll('p')].map(p=>p.textContent).join('\n\n'), result.explanation);
  assert.equal(rationale.querySelector('img'), null);
  assert.match(app.$('.decision-footer').textContent, /explanation-contract-fixture/);
  assert.equal(app.$('.evidence-card'), null, 'no duplicate explanation far below the result');
  assert.equal(app.$('#decision-tab-sources'), null);
  assert.equal(app.$('#decision-panel-sources'), null);
  assert.equal(app.$('.evidence-sources'), null);
  assert.doesNotMatch(app.$('#portfolio-explanation').textContent, /Source synthétique uniquement|https:\/\/example.com\/fixture/);
  assert.deepEqual(app.saved().result.evidence, result.evidence);
  assert.equal(app.$('#decision-panel-sources'),null);
  assert.equal(app.$('#decision-panel-limits'),null);
  assert.deepEqual(app.saved().result.evidence,result.evidence);
  assert.deepEqual(app.saved().result.limitations,result.limitations);
  assert.equal(requests.filter(r=>r.url==='/api/portfolio').length, 1);
  assert.deepEqual(JSON.parse(requests.find(r=>r.url==='/api/portfolio').options.body).questionnaire, makeQuestionnairePayload(completeAnswers()));
  const reload = await open(t, app.saved());
  assert.equal(reload.$('.agent-rationale').textContent, rationale.textContent);
});

test('clarification prepares a contextual question and only sends it after an explicit submission', async t => {
  const requests = [];
  const app = await open(t, { page: 'portfolio', complete: true, answers: completeAnswers(), result: resetResult() }, false, {
    fetch: async (url, options) => {
      requests.push({url,options});
      return {ok:true,json:async()=>url==='/api/config'?{agentConnected:true,portfolioConnected:false}:{message:'Réponse synthétique de clarification.'}};
    },
  });
  const prompt = app.$('[data-discuss]').dataset.discuss;
  app.$('[data-discuss]').click();
  assert.equal(app.saved().page,'assistant');
  assert.equal(app.$('#chat-input').value,prompt);
  assert.equal(app.w.document.activeElement.id,'chat-input');
  assert.equal(requests.filter(r=>r.url==='/api/agent/chat').length,0);
  app.$('#chat-form').dispatchEvent(new app.w.Event('submit',{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  const sent = requests.find(r=>r.url==='/api/agent/chat');
  assert.ok(sent);
  const body=JSON.parse(sent.options.body);
  assert.equal(body.message,prompt);
  assert.equal(body.portfolio.id,'test-only');
  assert.equal(body.portfolio.positions[0].symbol,'TEST');
  assert.equal(app.saved().messages[1].content,'Réponse synthétique de clarification.');
});

test('each asset question replaces an existing draft with the selected asset context', async t => {
  const app = await open(t,{page:'portfolio',complete:true,answers:completeAnswers()});
  app.$('.holding-link[data-holding="SPY"]').click();
  assert.equal(app.$('#modal').open,true);
  const question=app.$('#modal [data-discuss]').dataset.discuss;
  assert.match(question,/SPY/);
  assert.match(question,/20 %/);
  app.$('#modal [data-discuss]').click();
  assert.equal(app.$('#modal').open,false);
  assert.equal(app.$('#chat-input').value,question);
  assert.equal(app.$('.send-button').disabled,true);
  app.type('#chat-input','Mon brouillon à conserver');
  app.$('[data-page="portfolio"]').click();
  app.$('[data-discuss]').click();
  assert.equal(app.$('#chat-input').value,'Mon brouillon \u00e0 conserver');
  app.$('[data-page="portfolio"]').click();
  app.$('.holding-link[data-holding="NVDA"]').click();
  const assetQuestion=app.$('#modal [data-discuss]').dataset.discuss;
  assert.match(assetQuestion,/NVDA/);
  app.$('#modal [data-discuss]').click();
  assert.equal(app.$('#modal').open,false);
  assert.equal(app.$('#chat-input').value,assetQuestion);
  assert.equal(app.saved().draft,assetQuestion);
  assert.equal(app.w.document.activeElement.id,'chat-input');
  assert.deepEqual(app.saved().messages,[]);
  const reload=await open(t,app.saved());
  assert.equal(reload.$('#chat-input').value,assetQuestion);
});

test('an invalid saved result cannot supply a fabricated explanation to the main explanation region', async t => {
  const result=resetResult();
  result.compliance.passed=false;
  result.explanation='This rejected result must stay invisible.';
  const app=await open(t,{page:'portfolio',complete:true,answers:completeAnswers(),result});
  assert.equal(app.saved().result,null);
  assert.equal(app.$('.agent-rationale'),null);
  assert.equal(app.$('.decision-studio').textContent.includes(result.explanation),false);
  assert.ok(app.$('.awaiting-explanation'));
});
test('a submitted chat message appears immediately before the delayed agent reply without duplicate context', async t => {
  let resolveReply;
  const requests=[];
  const app=await open(t,{page:'assistant',complete:true,answers:completeAnswers(),draft:'Mon message immédiat',messages:[{role:'user',content:'Avant'},{role:'assistant',content:'Réponse précédente'}]},false,{
    fetch:async(url,options)=>{
      if(url==='/api/config')return{ok:true,json:async()=>({agentConnected:true,portfolioConnected:false})};
      requests.push(JSON.parse(options.body));
      return new Promise(resolve=>{resolveReply=resolve;});
    },
  });
  app.$('#chat-form').dispatchEvent(new app.w.Event('submit',{bubbles:true,cancelable:true}));
  assert.equal(app.w.document.querySelectorAll('.message.user').length,2);
  assert.equal(app.$('.message.user:last-of-type p')?.textContent,'Mon message immédiat');
  assert.equal(app.saved().messages.at(-1).content,'Mon message immédiat');
  assert.equal(app.saved().messages.at(-1).delivery,'pending');
  assert.equal(app.$('#chat-input').value,'');
  assert.ok(app.$('.sending'));
  assert.equal(app.$('.send-button').disabled,true);
  app.$('#chat-form').dispatchEvent(new app.w.Event('submit',{bubbles:true,cancelable:true}));
  assert.equal(requests.length,1);
  assert.equal(requests[0].message,'Mon message immédiat');
  assert.deepEqual(requests[0].conversation,[{role:'user',content:'Avant'},{role:'assistant',content:'Réponse précédente'}]);
  resolveReply({ok:true,json:async()=>({message:'Réponse retardée de la fixture.'})});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(app.w.document.querySelectorAll('.message.user').length,2);
  assert.equal(app.saved().messages.at(-1).role,'assistant');
  assert.equal(app.saved().messages.at(-2).delivery,undefined);
  assert.equal(app.$('.sending'),null);
});
test('failed chat stays visible and can be retried in place without erasing a new draft', async t => {
  const requests=[]; const replies=[];
  const app=await open(t,{page:'assistant',complete:true,answers:completeAnswers(),draft:'Question à réessayer'},false,{
    fetch:async(url,options)=>{
      if(url==='/api/config')return{ok:true,json:async()=>({agentConnected:true,portfolioConnected:false})};
      requests.push(JSON.parse(options.body));
      return new Promise(resolve=>replies.push(resolve));
    },
  });
  app.$('#chat-form').dispatchEvent(new app.w.Event('submit',{bubbles:true,cancelable:true}));
  replies[0]({ok:false,status:503});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(app.saved().messages.length,1);
  assert.equal(app.saved().messages[0].delivery,'failed');
  assert.match(app.$('.message.user').textContent,/Question à réessayer/);
  assert.ok(app.$('[data-retry-message]'));
  assert.equal(app.$('.sending'),null);
  app.type('#chat-input','Une autre question en brouillon');
  app.$('[data-retry-message]').click();
  assert.equal(app.saved().messages.length,1);
  assert.equal(app.saved().messages[0].delivery,'pending');
  assert.equal(app.saved().draft,'Une autre question en brouillon');
  assert.equal(requests.length,2);
  assert.deepEqual(requests[1].conversation,[]);
  assert.equal(requests[1].message,'Question à réessayer');
  replies[1]({ok:true,json:async()=>({message:'Réponse après réessai.'})});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(app.saved().messages.length,2);
  assert.equal(app.saved().messages[0].delivery,undefined);
  assert.equal(app.$('#chat-input').value,'Une autre question en brouillon');
});

test('reloading an interrupted message keeps it recoverable without an automatic resend', async t => {
  let sends=0;
  const app=await open(t,{page:'assistant',complete:true,answers:completeAnswers(),messages:[{role:'user',content:'Message interrompu',delivery:'pending'}]},false,{
    fetch:async url=>{
      if(url==='/api/config')return{ok:true,json:async()=>({agentConnected:true,portfolioConnected:false})};
      sends++; return{ok:true,json:async()=>({message:'Réponse de reprise.'})};
    },
  });
  assert.equal(sends,0);
  assert.equal(app.saved().messages[0].delivery,'failed');
  assert.match(app.$('.message.user').textContent,/Message interrompu/);
  app.$('[data-retry-message]').click();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sends,1);
  assert.equal(app.saved().messages.length,2);
  assert.equal(app.saved().messages[0].delivery,undefined);
});

test('network, timeout and invalid chat replies keep the submitted message available for retry', async t => {
  for(const failure of ['network','timeout','invalid']){
    const app=await open(t,{page:'assistant',complete:true,answers:completeAnswers(),draft:'Message conservé'},false,{
      fetch:async url=>{
        if(url==='/api/config')return{ok:true,json:async()=>({agentConnected:true,portfolioConnected:false})};
        if(failure==='invalid')return{ok:true,json:async()=>({message:''})};
        const error=new Error('Erreur synthétique'); error.name=failure==='timeout'?'TimeoutError':'TypeError'; throw error;
      },
    });
    app.$('#chat-form').dispatchEvent(new app.w.Event('submit',{bubbles:true,cancelable:true}));
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(app.saved().messages.length,1,failure);
    assert.equal(app.saved().messages[0].delivery,'failed',failure);
    assert.equal(app.$('.message.user p').textContent,'Message conservé');
    assert.ok(app.$('[data-retry-message]'));
    assert.equal(app.$('.sending'),null);
    assert.ok(app.$('.chat-error'));
  }
});

test('portfolio introduction is concise and keeps only a short financial notice and demo label', async t => {
  const app=await open(t,{page:'portfolio',complete:true,answers:completeAnswers()});
  assert.equal(app.$('.dashboard-heading h1').textContent,'Votre portefeuille.');
  assert.equal(app.$('.dashboard-heading p'),null);
  assert.equal(app.$('.dashboard-heading .eyebrow'),null);
  assert.doesNotMatch(app.$('.dashboard').textContent,/Des choix\.|Et le pourquoi|Votre répartition, ses raisons|Un aperçu pour explorer|remplacera après intégration/);
  assert.match(app.$('.investment-notice').textContent,/ne constituent pas un conseil financier personnalisé/);
  assert.match(app.$('.demo-banner').textContent,/Allocation illustrative, non personnalisée/);
  assert.ok(app.$('#portfolio-explanation'));
});

test('le portefeuille change seulement après confirmation d’une analyse compatible', async t => {
  const { initial, proposal } = simulationFixture();
  const app = await open(t, { complete: true, page: 'assistant', answers: completeAnswers(), result: initial, proposal });
  assert.equal(app.saved().result.portfolio.positions[0].weight, 20);
  assert.match(app.$('.proposal-card').textContent, /courant reste inchangé/);
  app.$('[data-action="accept-proposal"]').click();
  assert.equal(app.saved().result.portfolio.positions[0].weight, 25);
  assert.equal(app.saved().proposal, null);
});

test('les réserves ne présentent pas de bouton de confirmation et protègent aussi le gestionnaire', async t => {
  const { initial, proposal } = simulationFixture();
  proposal.changeReview.verdict = 'clarification_required';
  proposal.changeReview.cautions = ['Votre horizon doit être précisé.'];
  const app = await open(t, { complete: true, page: 'assistant', answers: completeAnswers(), result: initial, proposal });
  assert.equal(app.$('[data-action="accept-proposal"]'), null);
  const button = app.w.document.createElement('button');
  button.dataset.action = 'accept-proposal'; app.w.document.body.append(button); button.click();
  assert.equal(app.saved().result.portfolio.positions[0].weight, 20);
});

test('une nouvelle demande retire l’ancienne proposition et conserve le portefeuille pendant et après l’analyse', async t => {
  const { initial, proposal } = simulationFixture();
  const app = await open(t, { complete: true, page: 'assistant', answers: completeAnswers(), result: initial, proposal, draft: 'Ajouter AAA 5%' }, false, { config: { agentConnected: true, portfolioConnected: false } });
  let finish;
  app.w.fetch = () => new Promise(resolve => { finish = resolve; });
  app.$('#chat-form').dispatchEvent(new app.w.Event('submit', { bubbles: true, cancelable: true }));
  assert.equal(app.saved().proposal, null);
  assert.equal(app.saved().result.portfolio.positions[0].weight, 20);
  assert.equal(app.$('[data-action="accept-proposal"]'), null);
  finish({ ok: true, json: async () => ({ message: 'Analyse terminée : votre portefeuille reste inchangé.', proposal }) });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.saved().result.portfolio.positions[0].weight, 20);
  assert.equal(app.saved().proposal.portfolio.positions[0].weight, 25);

});
test('Other requires nonblank context in every applicable question and preserves optional project details', async t => {
  for (const [id,key] of [['dependents','dependentsOther'],['annualIncome','incomeOther'],['debt','debtOther'],['goal','goalDetails']]) {
    const step=QUESTIONS.findIndex(q=>q.id===id);
    const answers={...completeAnswers(),[id]:'other'};
    const app=await open(t,{answers,step});
    assert.equal(app.$('#detail-'+key).required,true);
    assert.equal(isAnswered(QUESTIONS[step],answers),false);
    assert.equal(validateAnswers({...answers,[key]:'   '}),false);
    app.next(); assert.equal(app.saved().step,step);
    app.type('#detail-'+key,'Contexte personnel');
    assert.equal(validateAnswers(app.saved().answers),true);
    app.next(); assert.equal(app.saved().step,step+1);
  }
  assert.equal(validateAnswers({...completeAnswers(),goal:'project'}),true);
});

test('allocation explorer groups the actual weights consistently and exposes asset details accessibly', async t => {
 const app=await open(t,{page:'portfolio',complete:true,answers:completeAnswers()});
 const rows=()=>[...app.w.document.querySelectorAll('.allocation-item')];
 assert.equal(rows().length,6);
 assert.equal(app.$('.allocation-switch button').dataset.allocationMode,'assets');
 assert.equal(app.$('[data-allocation-mode="assets"]').getAttribute('aria-pressed'),'true');
 app.$('[data-allocation-mode="groups"]').click();
 assert.deepEqual(rows().map(r=>r.querySelector('b').textContent),['40 %','40 %','10 %','10 %']);
 assert.equal(app.w.document.querySelectorAll('.allocation-arc').length,4);
 assert.deepEqual([...app.w.document.querySelectorAll('.allocation-arc')].map(r=>Number(r.getAttribute('stroke-dasharray').split(' ')[0])),[40,40,10,10]);
 rows()[0].click();assert.equal(app.$('#allocation-value').textContent,'40');assert.equal(app.$('#allocation-label').textContent,'FNB d\u2019actions');
 assert.equal(app.w.document.querySelectorAll('.allocation-arc.is-muted').length,3);
 app.$('[data-allocation-mode="groups"]').click();assert.equal(app.$('#allocation-value').textContent,'100');
 app.$('[data-allocation-mode="assets"]').click();assert.equal(rows().length,6);
 assert.equal(app.$('[data-allocation-mode="assets"]').getAttribute('aria-pressed'),'true');
 const arc=app.$('.allocation-arc');arc.dispatchEvent(new app.w.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
 assert.equal(app.$('#allocation-label').textContent,'XBB.TO');assert.equal(app.$('#allocation-value').textContent,'25');
 app.$('[data-allocation-mode="groups"]').click();assert.equal(rows().length,4);assert.equal(app.$('#allocation-value').textContent,'100');
 assert.equal(app.$('.allocation-footnote'),null); assert.equal(app.$('[data-allocation-reset]'),null);
 const engine=await open(t,{page:'portfolio',complete:true,answers:completeAnswers(),result:resetResult()});
 assert.equal(engine.w.document.querySelectorAll('.allocation-arc').length,1);engine.$('.allocation-item').click();assert.equal(engine.$('#allocation-value').textContent,'100');
});

test('geographic view shows the CSV countries, off-map share, contributors and interactive zoom', async t => {
 const app=await open(t,{page:'portfolio',complete:true,answers:completeAnswers()});
 app.$('[data-allocation-mode="geography"]').click();
 assert.ok(app.$('.geo-world'));
 const rows=[...app.w.document.querySelectorAll('.geo-row')];
 assert.deepEqual(rows.map(x=>x.querySelector('b').textContent),['60 %','30 %','10 %']);
 assert.equal(app.w.document.querySelectorAll('.geo-country').length,176);
 assert.equal(app.w.document.querySelectorAll('.geo-feature').length,2);
 assert.equal(app.w.document.querySelectorAll('.geo-contributors button').length,3);
 const us=app.$('.geo-feature[data-geo-name="États-Unis"]');
 assert.ok(us);
 us.dispatchEvent(new app.w.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
 assert.match(app.$('.geo-detail-heading h3').textContent,/États-Unis/);
 assert.equal(app.w.document.querySelectorAll('.geo-contributors button').length,2);
 assert.match(app.$('.geo-method').textContent,/siège social/);
 app.$('[data-geo-zoom="in"]').click();
 assert.notEqual(app.$('.geo-world').getAttribute('viewBox'),'0 0 800 400');
 app.$('[data-geo-zoom="reset"]').click();assert.equal(app.$('.geo-world').getAttribute('viewBox'),'0 0 800 400');
 const off=rows.find(x=>x.textContent.includes('Sans pays unique'));off.click();
 assert.match(app.$('.geo-detail').textContent,/GLD/);
 assert.equal(app.w.document.querySelectorAll('.geo-country.is-selected').length,0);
 app.$('[data-geo-expand]').click();assert.equal(app.$('#modal').open,true);
 assert.ok(app.$('#modal .geo-world'));
 const modalUS=app.$('#modal .geo-feature[data-geo-name="\u00c9tats-Unis"]');modalUS.dispatchEvent(new app.w.MouseEvent('click',{bubbles:true}));
 assert.equal(app.$('#modal .geo-detail-heading h3').textContent,'\u00c9tats-Unis');
 app.$('#modal [data-geo-zoom="in"]').click();assert.notEqual(app.$('#modal .geo-world').getAttribute('viewBox'),'0 0 800 400');
 app.$('#modal [data-action="close-modal"]').click();assert.equal(app.$('#modal').open,false);
 app.$('[data-allocation-mode="assets"]').click();assert.equal(app.$('.allocation-card .geo-world'),null);assert.equal(app.w.document.querySelectorAll('.allocation-item').length,6);
});

test('an older classification service cannot masquerade as complete geographic data',async t=>{
 const app=await open(t,{page:'portfolio',complete:true,answers:completeAnswers()},false,{exposureData:{categories:exposureFixture.categories}});
 app.$('[data-allocation-mode="geography"]').click();
 assert.ok(app.$('.geo-warning'));
 assert.equal(app.w.document.querySelectorAll('.geo-feature').length,0);
 assert.match(app.$('.geo-row').textContent,/Non renseign/);
 assert.equal(app.$('.geo-row b').textContent,'100 %');
});

test('removed family status and withdrawal detail are discarded without replacing valid answers',async t=>{
 const answers={...completeAnswers(),marital:'partnered',maritalOther:'Old context',withdrawalTiming:'under_1'};
 const app=await open(t,{answers,step:7,complete:true,page:'portfolio',result:resetResult()});
 assert.equal(app.saved().complete,false);assert.equal(app.saved().result,null);
 assert.equal(app.saved().answers.marital,undefined);assert.equal(app.saved().answers.maritalOther,undefined);assert.equal(app.saved().answers.withdrawalTiming,undefined);
 assert.deepEqual(app.saved().answers,completeAnswers());
 assert.equal(QUESTIONS.some(q=>q.id==='marital'),false);
 assert.equal(QUESTIONS.find(q=>q.id==='horizon').details.length,0);
 assert.equal(validateAnswers({...completeAnswers(),withdrawalTiming:'under_1'}),false);
 const ready=await open(t,{answers:completeAnswers(),complete:true,page:'portfolio'});
 assert.doesNotMatch(ready.$('.portfolio-context').textContent,/Retrait envisag/);
 ready.$('[data-page="assistant"]').click();
 assert.equal(ready.$('#chat-input').rows,1);
});
