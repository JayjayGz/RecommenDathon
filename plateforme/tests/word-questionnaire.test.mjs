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

async function open(t, saved = {}, legacy = false) {
  const dom = new JSDOM(html, { url: 'http://localhost:4173', runScripts: 'outside-only' });
  const w = dom.window;
  t.after(() => w.close());
  w.localStorage.setItem(legacy ? 'recommand.platform.v1' : key, JSON.stringify(saved));
  w.scrollTo = () => {};
  w.HTMLElement.prototype.scrollIntoView = () => {};
  w.AbortSignal = AbortSignal;
  w.AbortController = AbortController;
  w.fetch = async () => ({ ok: true, json: async () => ({ agentConnected: false, portfolioConnected: false }) });
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

test('all 16 titles, choices and follow-ups match the selected Word snapshot', () => {
  assert.equal(fixture.source, 'Questionnaire_client_Recommand_20261115_103525.docx');
  assert.match(fixture.sha256, /^[0-9a-f]{64}$/);
  assert.equal(QUESTIONS.length, 16);
  assert.deepEqual(SECTIONS, fixture.sections);
  assert.deepEqual(QUESTIONS, fixture.questions);
  assert.equal(QUESTIONS.some(q => q.id === 'return'), false);
  assert.equal(QUESTIONS.some(q => q.id === 'monthlyExpenses'), false);
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
  app.choose('discussion'); assert.equal(app.$('[data-detail="exclusionDetails"]'),field);
  assert.equal(app.saved().answers.exclusionDetails, 'Précision sur les placements');
  app.choose('none'); assert.equal(app.$('[data-detail="exclusionDetails"]'),null);
  assert.equal(app.saved().answers.exclusionDetails,undefined);
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
  assert.equal(app.$('.profile-card').textContent.includes('Rendement souhaité'), false);
  app.$('[data-page="questionnaire"]').click();
  assert.equal(app.$('#question-title').textContent, QUESTIONS[15].title);
  app.$('[data-action="previous"]').click();
  assert.equal(app.$('input[value="none"]').checked, true);
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
  for (const file of ['styles','theme','questionnaire']) {
    const css = await readFile(new URL(`../src/${file}.css`,import.meta.url),'utf8');
    const element = dom.window.document.createElement('style'); element.textContent = css;
    dom.window.document.head.append(element); assert.ok(element.sheet.cssRules.length > 0);
    if (file === 'styles') assert.doesNotMatch(css.match(/@keyframes\s+page-in\s*\{[^\n]+/)[0], /opacity\s*:\s*0/);
  }
  dom.window.close();
});
