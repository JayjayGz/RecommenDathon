"""Extract only questionnaire text from the explicitly selected source Word."""
import hashlib
import json
import re
from pathlib import Path
from docx import Document

root = Path(__file__).resolve().parents[2]
source = Path(r'C:/Users/alibe/Downloads/Questionnaire_client_Recommand_20261115_103525.docx')
sections, questions = [], []
for paragraph in Document(source).paragraphs:
    text = paragraph.text.strip()
    if text == 'Références utilisées pour la formulation':
        break
    if paragraph.style.name == 'Heading 1':
        sections.append(text)
    elif paragraph.style.name == 'Heading 2':
        number, title = re.match(r'(\d+)\s+(.+)', text).groups()
        questions.append(dict(number=int(number), title=title, section=len(sections)-1, paragraphs=[]))
    elif questions and text and not set(text) == {'_'}:
        questions[-1]['paragraphs'].append(text)
assert len(questions) == 16
ids = ['marital', 'dependents', 'annualIncome', 'income', 'debt', 'emergencyFund',
       'goal', 'horizon', 'liquidity', 'risk', 'reaction', 'knowledge', 'sectors', 'assets', 'exclusions', 'notes']
values = [
    ['single', 'partnered', 'separated', 'other'], ['none', 'one', 'many', 'other'],
    ['under_50k', '50_100k', '100_150k', '150k_plus', 'other'], ['regular', 'variable', 'fragile', 'unknown'],
    ['none', 'under_25k', '25_100k', '100k_plus', 'other'], [], ['retirement', 'project', 'wealth', 'other'],
    ['1_2', '5', '10', '15_plus'], ['no', 'partly', 'yes', 'unknown'],
    ['very_low', 'low', 'medium', 'high', 'very_high'], ['worried', 'hesitant', 'concerned', 'calm'],
    ['beginner', 'basic', 'good', 'advanced'],
    ['technology', 'health', 'finance', 'energy', 'real_estate', 'industry', 'consumer', 'communications', 'utilities'],
    ['stocks', 'equity_funds', 'bonds', 'alternatives', 'crypto', 'futures', 'fx', 'all'],
    ['none', 'limits', 'discussion'], []]
output = []
for i, q in enumerate(questions):
    # Main options are only standalone checkbox paragraphs, before any follow-up.
    labels = []
    for text in q['paragraphs']:
        if text.startswith('☐  ') and text.count('☐') == 1:
            labels.append(text[3:].strip())
        elif labels:
            break
    if i == 15:
        labels = []
    assert len(labels) == len(values[i]), (i, labels)
    item = dict(id=ids[i], section=q['section'], title=q['title'],
                type='multi' if i in (12, 13) else 'number' if i == 5 else 'text' if i == 15 else 'single',
                options=list(map(list, zip(values[i], labels))))
    before = []
    for text in q['paragraphs']:
        if text.startswith('☐') or text.startswith('Montant disponible') or text in ('Choisissez une seule réponse.', 'Plusieurs réponses possibles.'):
            break
        before.append(text)
    if before:
        item['help'] = '\n'.join(before)
    if i == 9:
        item['help'] = q['paragraphs'][-1]
    if i == 15:
        item['help'] = q['paragraphs'][0]
        item['optional'] = True
    item['details'] = []
    output.append(item)

def detail(q, key, label, kind='text', values=None, when=None, required=False):
    field = dict(key=key, label=label, type=kind, required=required)
    if values: field['options'] = values
    if when: field['when'] = when
    output[q-1]['details'].append(field)

for q, key in [(1,'maritalOther'),(2,'dependentsOther'),(3,'incomeOther'),(5,'debtOther')]:
    detail(q,key,'Si autre, précisez si vous le souhaitez',when={'field':ids[q-1],'values':['other']})
detail(2,'supportMode','Si vous avez des personnes à charge, assumez-vous principalement ces dépenses ou les partagez-vous ? Précision facultative.',
       'single', [['main','Je les assume principalement.'],['shared','Je les partage avec quelqu’un.']],
       {'field':'dependents','values':['one','many','other']})
detail(5,'mortgageAmount','Part approximative correspondant à un prêt hypothécaire, si applicable et connue', 'number')
detail(7,'goalDetails','Si projet précis ou autre objectif, précisez si vous le souhaitez',when={'field':'goal','values':['project','other']})
detail(7,'targetAmount','Montant que vous aimeriez atteindre, si connu', 'number')
detail(8,'withdrawalTiming','Quand pourriez-vous avoir besoin de retirer une partie importante de cet argent ?', 'single',
       [['under_1','Moins d’un an.'],['1_3','De 1 à 3 ans.'],['4_6','De 4 à 6 ans.'],['7_plus','7 ans ou plus.']], required=True)
detail(14,'cryptoDetails','Si cryptoactifs, vos précisions facultatives',when={'field':'assets','values':['crypto','all']})
detail(15,'exclusionDetails','Si limites ou discussion, vos précisions facultatives',when={'field':'exclusions','values':['limits','discussion']})
detail(16,'noNotes','Je n’ai rien à ajouter.', 'boolean')
output[9]['layout'] = 'risk'
output[10]['scenario'] = True
output[12]['layout'] = output[13]['layout'] = 'grid'
fixture = dict(source=source.name, sha256=hashlib.sha256(source.read_bytes()).hexdigest(), sections=sections, questions=output)
folder = root / 'plateforme/tests/fixtures'
folder.mkdir(exist_ok=True)
(folder / 'questionnaire-word.json').write_text(json.dumps(fixture, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
# Keep the Word snapshot intact; apply the user's explicit UI override afterward.
output[14]['options'] = [option for option in output[14]['options'] if option[0] != 'discussion']
output[14]['details'][0]['label'] = 'Précisez ce que vous voulez exclure (obligatoire)'
output[14]['details'][0]['when']['values'] = ['limits']
# "Limites" without saying what to exclude cannot be applied by the engine.
output[14]['details'][0]['required'] = True
output[0]['options'] = [option for option in output[0]['options'] if option[0] != 'separated']
output[6]['details'] = [field for field in output[6]['details'] if field['key'] != 'targetAmount']

for question in output:
    for field in question['details']:
        if field['key'] in ['maritalOther', 'dependentsOther', 'incomeOther', 'debtOther']:
            field['required'] = True
            field['label'] = 'Pr\u00e9cisez votre situation (obligatoire)'
        if field['key'] == 'goalDetails':
            field['requiredWhen'] = {'field': 'goal', 'values': ['other']}
            field['label'] = 'Pr\u00e9cisez votre objectif (obligatoire si Autre)'

output = [question for question in output if question['id'] != 'marital']
for question in output:
    question['details'] = [field for field in question['details'] if field['key'] != 'withdrawalTiming']

data = root / 'plateforme/src/data.js'
old = data.read_text(encoding='utf-8')
demo = old[old.index('export const DEMO_PORTFOLIO'):old.index('export function fieldVisible')]
helpers = old[old.index('export function fieldVisible'):]
header = '// Source exclusive : ' + source.name + '\n'
header += "export const QUESTIONNAIRE_VERSION = 'questionnaire-word-15-v5';\n"
header += 'export const SECTIONS = ' + json.dumps(sections, ensure_ascii=False) + ';\n'
header += 'export const QUESTIONS = ' + json.dumps(output, ensure_ascii=False, indent=2) + ';\n\n'
data.write_text((header + demo + helpers).rstrip() + '\n', encoding='utf-8')
print('Extracted 16 source questions and exact main options; source SHA-256:',fixture['sha256'])
