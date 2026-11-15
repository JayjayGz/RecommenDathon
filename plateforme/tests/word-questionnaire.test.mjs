import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { JSDOM } from 'jsdom';
import { QUESTIONS, SECTIONS, QUESTIONNAIRE_VERSION, cleanAnswers, isAnswered, validateAnswers, makeQuestionnairePayload } from '../src/data.js';
import { marketScenario, questionIllustration } from '../src/illustrations.js';

const fixture = JSON.parse(await readFile(new URL('./fixtures/questionnaire-word.json', import.meta.url), 'utf8'));
const key = 'recommand.platform.word16.v2';
const appUrl = new URL('../src/app.js', import.meta.url);
const html = await readFile(new URL('../index.html', import.meta.url), 'utf8');
const completeAnswers = () => Object.fromEntries([
  ...QUESTIONS.filter(q => !q.optional).map(q => [q.id, q.type === 'number' ? 0 : q.type === 'multi' ? [q.options[0][0]] : q.options[0][0]]),
  ['withdrawalTiming', 'under_1'],
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
  w.fetch = options.fetch || (async () => ({ ok: true, json: async () => ({ agentConnected: false, portfolioConnected: false }) }));
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

test('all 16 questions match the Word snapshot with the explicit user removals', () => {
  assert.equal(fixture.source, 'Questionnaire_client_Recommand_20261115_103525.docx');
  assert.match(fixture.sha256, /^[0-9a-f]{64}$/);
  assert.equal(QUESTIONS.length, 16);
  assert.deepEqual(SECTIONS, fixture.sections);
  const expected = structuredClone(fixture.questions);
  expected.find(q => q.id === 'marital').options = expected.find(q => q.id === 'marital').options.filter(([value]) => value !== 'separated');
  expected.find(q => q.id === 'goal').details = expected.find(q => q.id === 'goal').details.filter(field => field.key !== 'targetAmount');
  const exclusions = expected.find(q => q.id === 'exclusions');
  exclusions.options = exclusions.options.filter(([value]) => value !== 'discussion');
  exclusions.details[0].label = 'Si limites, vos précisions facultatives';
  exclusions.details[0].when.values = ['limits'];
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
    const app = await open(t, { page, step: 6, complete: true, answers: completeAnswers(), draft: 'Brouillon', messages: [{role:'user',content:'Ancienne conversation'}], result: resetResult(), proposal: resetResult() });
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
  assert.equal(app.$('#question-form input:checked'), null);
  const amountOnly = await open(t, { answers: { ...completeAnswers(), targetAmount: 50000 }, complete: true, page: 'portfolio', result: resetResult() });
  assert.equal(amountOnly.saved().complete, false);
  assert.deepEqual(amountOnly.saved().answers, completeAnswers());
  amountOnly.$('[data-question-index="6"]').click();
  assert.equal(amountOnly.$('[data-detail="targetAmount"]'), null);
  amountOnly.choose('project');
  assert.ok(amountOnly.$('[data-detail="goalDetails"]'));
  assert.equal(validateAnswers({ ...completeAnswers(), marital: 'separated' }), false);
  assert.equal(validateAnswers({ ...completeAnswers(), targetAmount: 50000 }), false);
  assert.equal(validateAnswers(completeAnswers()), true);
  const template = JSON.parse(await readFile(new URL('../Questionnaire_client_Recommand.json', import.meta.url), 'utf8'));
  assert.equal(template.questions.find(q => q.id === 'situation_conjugale').options.some(o => o.id === 'situation_conjugale_3'), false);
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

test('the refined conversation shows a compact context, four working suggestions and a labelled draft', async t => {
  const app = await open(t, { page: 'assistant', complete: true, answers: completeAnswers() });
  assert.match(app.$('.assistant-title h1').textContent, /Affinons votre portefeuille/);
  assert.equal(app.$('.conversation-sidebar img'), null);
  assert.equal(app.w.document.querySelectorAll('[data-prompt]').length, 4);
  assert.ok(app.$('.chat-card.is-empty'));
  assert.match(app.$('label[for="chat-input"]').textContent, /Que souhaitez-vous préciser/);
  const suggestion = app.$('[data-prompt]');
  const prompt = suggestion.dataset.prompt;
  suggestion.click();
  assert.equal(app.$('#chat-input').value, prompt);
  assert.equal(app.w.document.activeElement, app.$('#chat-input'));
  assert.equal(app.saved().draft, prompt);
  assert.deepEqual(app.saved().answers, completeAnswers());
  assert.equal(app.$('.send-button').disabled, true);
});

test('single choices preserve main, form, illustration and keyboard focus', async t => {
  const app = await open(t);
  const main = app.$('#main'), form = app.$('#question-form'), art = app.$('.question-illustration');
  const a = app.choose('single');
  assert.equal(app.$('#main'), main); assert.equal(app.$('#question-form'), form);
  assert.equal(app.$('.question-illustration'), art); assert.equal(app.w.document.activeElement, a);
  app.choose('partnered');
  assert.equal(a.checked, false); assert.equal(app.saved().answers.marital, 'partnered');
  assert.equal(app.$('[role="progressbar"]').getAttribute('aria-valuenow'), '1');
  assert.equal(app.$('[role="progressbar"]').getAttribute('aria-valuemax'), '16');
});

test('other details and shared charges keep typed values and remove hidden answers', async t => {
  const app = await open(t, { step: 1 });
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
  const app = await open(t, { step: 5 });
  app.next(); assert.match(app.$('#question-error').textContent, /montant valide/);
  const main = app.$('#main');
  app.type('[data-answer="emergencyFund"]', '-1'); app.next();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[5].title);
  app.type('[data-answer="emergencyFund"]', '0');
  assert.equal(app.$('#main'), main); assert.equal(app.saved().answers.emergencyFund, 0);
  app.next(); assert.equal(app.$('#question-title').textContent, QUESTIONS[6].title);
});

test('horizon follow-up required by the source is captured without losing focus', async t => {
  const app = await open(t, { step: 7 });
  app.choose('10'); app.next();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[7].title);
  const input = app.choose('4_6','withdrawalTiming');
  assert.equal(app.w.document.activeElement, input);
  app.next(); assert.equal(app.$('#question-title').textContent, QUESTIONS[8].title);
});

test('empty fields show examples without saving them as answers or replacing entered values', async t => {
  const amount = await open(t, { step: 5 });
  assert.equal(amount.$('[data-answer="emergencyFund"]').placeholder, 'Ex. : 100');
  assert.equal(amount.$('[data-answer="emergencyFund"]').value, '');
  amount.next(); assert.equal(amount.saved().answers?.emergencyFund, undefined);
  amount.type('[data-answer="emergencyFund"]', '100');
  assert.equal(amount.saved().answers.emergencyFund, 100);
  const debt = await open(t, { step: 4, answers: { mortgageAmount: 24 } });
  assert.equal(debt.$('[data-detail="mortgageAmount"]').placeholder, 'Ex. : 100 000');
  assert.equal(debt.$('[data-detail="mortgageAmount"]').value, '24');
  debt.choose('other');
  assert.ok(debt.$('[data-detail="debtOther"]').placeholder);
  const notes = await open(t, { step: 15 });
  assert.ok(notes.$('[data-answer="notes"]').placeholder);
  assert.equal(notes.$('[data-answer="notes"]').value, '');
});

test('all assets is exclusive, crypto details persist for all and are cleared when irrelevant', async t => {
  const app = await open(t, { step: 13 });
  app.choose('crypto'); const text = app.type('[data-detail="cryptoDetails"]', 'Précision');
  app.choose('bonds'); assert.equal(app.$('[data-detail="cryptoDetails"]'), text);
  app.choose('all'); assert.deepEqual(app.saved().answers.assets, ['all']);
  assert.equal(app.$('[data-detail="cryptoDetails"]'), text);
  app.choose('stocks'); assert.deepEqual(app.saved().answers.assets, ['stocks']);
  assert.equal(app.saved().answers.cryptoDetails, undefined);
});

test('optional final notes can be empty, typed or explicitly declined', async t => {
  const app = await open(t, { step: 15, answers: completeAnswers() });
  app.type('[data-answer="notes"]', 'Mon projet');
  app.$('[data-detail="noNotes"]').click();
  assert.equal(app.$('[data-answer="notes"]').disabled, true);
  assert.equal(app.saved().answers.notes, undefined);
  app.next(); assert.equal(app.saved().complete, true); assert.ok(app.$('.dashboard'));
});

test('exclusion details survive a relevant choice and disappear with no exclusions', async t => {
  const app = await open(t, { step: 14 });
  app.choose('limits'); const field = app.type('[data-detail="exclusionDetails"]','Précision sur les placements');
  assert.equal(app.$('input[value="discussion"]'), null);
  assert.equal(app.$('[data-detail="exclusionDetails"]'),field);
  assert.equal(app.saved().answers.exclusionDetails, 'Précision sur les placements');
  app.choose('none'); assert.equal(app.$('[data-detail="exclusionDetails"]'),null);
  assert.equal(app.saved().answers.exclusionDetails,undefined);
});

test('removed discussion answers are cleared without inventing a replacement', async t => {
  const app = await open(t, { step: 14, complete: true, answers: { ...completeAnswers(), exclusions: 'discussion', exclusionDetails: 'Ancien choix' } });
  assert.equal(app.$('input:checked'), null);
  assert.equal(app.$('[data-detail="exclusionDetails"]'), null);
  assert.equal(app.$('[data-page="portfolio"]').disabled, true);
  const oldAnswers = { ...completeAnswers(), exclusions: 'discussion' };
  assert.equal(validateAnswers(oldAnswers), false);
  assert.equal(cleanAnswers(oldAnswers).exclusions, undefined);
  assert.equal(validateAnswers({ ...completeAnswers(), exclusions: 'limits', exclusionDetails: 'Mes limites' }), true);
});

test('all 16 questions are traversable and answers remain available on return', async t => {
  const app = await open(t);
  for (const q of QUESTIONS) {
    assert.equal(app.$('#question-title').textContent, q.title);
    if (q.type === 'number') app.type('[data-answer="emergencyFund"]', '2500.50');
    else if (q.type !== 'text') app.choose(q.options[0][0]);
    if (q.id === 'horizon') app.choose('1_3','withdrawalTiming');
    app.next();
  }
  assert.equal(app.saved().page, 'portfolio'); assert.ok(app.$('.dashboard'));
  assert.equal(app.$('.portfolio-context').textContent.includes('Rendement souhaité'), false);
  app.$('[data-page="questionnaire"]').click();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[15].title);
  app.$('[data-action="previous"]').click();
  assert.equal(app.$('input[value="none"]').checked, true);
});

test('progress navigation jumps freely and preserves radio and numeric answers', async t => {
  const app = await open(t);
  assert.equal(app.w.document.querySelectorAll('.progress-track button').length, QUESTIONS.length);
  assert.equal(app.$('[aria-current="step"]').dataset.questionIndex, '0');
  app.choose('partnered');
  assert.equal(app.$('[data-question-index="0"]').classList.contains('filled'), true);
  app.$('[data-question-index="5"] span').click();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[5].title);
  assert.equal(app.w.document.activeElement, app.$('#question-title'));
  assert.equal(app.$('[aria-current="step"]').dataset.questionIndex, '5');
  app.type('#main-answer', '100');
  app.$('[data-question-index="0"]').click();
  assert.equal(app.$('input[value="partnered"]').checked, true);
  app.$('[data-question-index="5"]').click();
  assert.equal(app.$('#main-answer').value, '100');
  assert.equal(app.saved().step, 5);
  assert.equal(app.saved().answers.emergencyFund, 100);
  assert.equal(app.$('[role="progressbar"]').getAttribute('aria-valuenow'), '2');
});

test('jumping to the last question cannot bypass required answers', async t => {
  const app = await open(t);
  app.$('[data-question-index="15"]').click();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[15].title);
  app.next();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[0].title);
  assert.equal(app.saved().step, 0);
  assert.equal(app.$('[data-page="portfolio"]').disabled, true);
  assert.notEqual(app.saved().complete, true);
  assert.equal(app.w.document.querySelectorAll('.progress-track [aria-current="step"]').length, 1);
});

test('reaction question keeps the large centered scenario within the question and preserves its answer', async t => {
  const app = await open(t, { step: 10 });
  assert.ok(app.$('.onboarding.scenario-page #question-form .market-scenario'));
  assert.equal(app.$('.onboarding > .market-scenario'), null);
  assert.ok(app.$('.hero-description'));
  const title = app.$('#question-title');
  const chart = app.$('.market-chart');
  app.choose('worried');
  assert.equal(app.$('.market-chart'), chart);
  assert.equal(app.$('#question-title'), title);
  app.$('[data-question-index="9"]').click();
  app.$('[data-question-index="10"]').click();
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
  const app = await open(t, { step: 9, page: 'questionnaire', complete: true, answers: completeAnswers(), messages: [{role:'user',content:'test'}] });
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
  assert.equal(isAnswered(QUESTIONS[15], {}), true);
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
  for (const file of ['styles','theme','questionnaire','portfolio']) {
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
  assert.equal(app.w.document.querySelectorAll('.portfolio-context .profile-fact').length, 4);
  assert.equal(app.$('.holdings-card').previousElementSibling.className, 'portfolio-refine');
  assert.equal(app.$('[href="#portfolio-explanation"]').textContent.includes('Comprendre'), true);
  const tabs = [...studio.querySelectorAll('[role="tab"]')];
  assert.equal(tabs.length, 3);
  tabs[1].click();
  assert.equal(app.$('#decision-panel-sources').hidden, false);
  assert.equal(app.$('#decision-panel-overview').hidden, true);
  assert.equal(tabs[1].getAttribute('aria-selected'), 'true');
  const browserShortcut = new app.w.KeyboardEvent('keydown', { key: 'End', ctrlKey: true, bubbles: true, cancelable: true });
  tabs[1].dispatchEvent(browserShortcut);
  assert.equal(browserShortcut.defaultPrevented, false);
  assert.equal(app.$('#decision-panel-sources').hidden, false);
  tabs[1].dispatchEvent(new app.w.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
  assert.equal(app.w.document.activeElement.id, 'decision-tab-limits');
  assert.equal(app.$('#decision-panel-limits').hidden, false);
  tabs[2].dispatchEvent(new app.w.KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
  assert.equal(app.w.document.activeElement.id, 'decision-tab-overview');
  assert.equal(app.$('#decision-panel-overview').hidden, false);
  assert.match(app.$('#decision-panel-limits').textContent, /Aucune performance ni adéquation/);
});

test('the agent explanation, sources and limitations are displayed from the actual portfolio response', async t => {
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
  app.$('#decision-tab-sources').click();
  assert.equal(app.$('#decision-panel-sources').hidden, false);
  assert.equal(app.$('#decision-panel-sources a').href, 'https://example.com/fixture');
  assert.equal(app.$('#decision-panel-sources a').rel, 'noopener noreferrer');
  assert.match(app.$('#decision-panel-sources').textContent, /Source synthétique uniquement/);
  app.$('#decision-tab-limits').click();
  assert.equal(app.$('#decision-panel-limits li').textContent, result.limitations[0]);
  assert.equal(app.$('#decision-panel-limits script'), null);
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

test('each position can prepare a precise question while an existing draft is preserved', async t => {
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
  app.$('.holding-link[data-holding="NVDA"]').click();
  app.$('#modal [data-discuss]').click();
  assert.equal(app.$('#modal').open,false);
  assert.equal(app.$('#chat-input').value,'Mon brouillon à conserver');
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
