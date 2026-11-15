import ast
import json
from pathlib import Path
from docx import Document

root = Path(__file__).resolve().parents[1]
tree = ast.parse((root / 'docs/build_questionnaire.py').read_text(encoding='utf-8'))
ids = ['situation_conjugale', 'personnes_a_charge', 'revenu_annuel', 'stabilite_revenus',
       'dettes', 'fonds_urgence', 'objectif_investissement', 'horizon', 'besoin_imprevu',
       'tolerance_risque', 'reaction_baisse', 'connaissances', 'secteurs', 'classes_actifs',
       'exclusions', 'precisions_finales']
questions = []
section = 'Situation familiale'
for node in tree.body:
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        continue
    call = node.value
    if not isinstance(call.func, ast.Name):
        continue
    if call.func.id == 'page':
        section = ast.literal_eval(call.args[0])
    if call.func.id != 'question':
        continue
    args = [ast.literal_eval(arg) for arg in call.args]
    kw = {item.arg: ast.literal_eval(item.value) for item in call.keywords}
    number, label = args[:2]
    options = kw.get('options', args[3] if len(args) > 3 else [])
    q = dict(numero=number, id=ids[number - 1], section=section, libelle=label,
             type='choix_multiple' if kw.get('multi') else 'choix_unique', reponse=None)
    if len(args) > 2 and args[2]:
        q['aide'] = args[2]
    if options:
        q['options'] = [dict(id=f'{q["id"]}_{i}', libelle=text) for i, text in enumerate(options, 1)]
    else:
        q['type'] = 'montant' if number == 6 else 'texte_libre'
    questions.append(q)

def field(id, libelle, type='texte_libre', **extra):
    return dict(id=id, libelle=libelle, type=type, reponse=None, **extra)

for number in [1, 2, 3, 5]:
    q = questions[number - 1]
    q['champs_complementaires'] = [field(q['id'] + '_autre', 'Si autre, précisez si vous le souhaitez',
        facultatif=True, afficher_si={'question_id': q['id'], 'option_id': q['options'][-1]['id']})]
questions[1]['champs_complementaires'].append(field('partage_charges',
    'Si vous avez des personnes à charge, assumez-vous principalement ces dépenses ou les partagez-vous ?',
    'choix_unique', facultatif=True, options=[
        {'id': 'principalement', 'libelle': 'Je les assume principalement.'},
        {'id': 'partagees', 'libelle': 'Je les partage avec quelqu’un.'}]))
questions[4]['champs_complementaires'].append(field('dette_hypothecaire',
    'Part approximative correspondant à un prêt hypothécaire, si applicable et connue',
    'montant', devise='CAD', minimum=0, facultatif=True))
questions[5].update(devise='CAD', minimum=0)
questions[6]['champs_complementaires'] = [
    field('objectif_details', 'Si projet précis ou autre objectif, précisez si vous le souhaitez', facultatif=True),
    field('objectif_montant', 'Montant que vous aimeriez atteindre, si connu', 'montant', devise='CAD', minimum=0, facultatif=True)]
questions[7]['champs_complementaires'] = [field('delai_retrait',
    'Quand pourriez-vous avoir besoin de retirer une partie importante de cet argent ?', 'choix_unique',
    options=[{'id': id, 'libelle': label} for id, label in [
        ('moins_1_an', 'Moins d’un an.'), ('1_3_ans', 'De 1 à 3 ans.'),
        ('4_6_ans', 'De 4 à 6 ans.'), ('7_ans_plus', '7 ans ou plus.')]])]
questions[9]['aide'] = 'La tolérance au risque décrit votre aisance face aux fluctuations et aux pertes possibles. Elle est distincte de votre capacité financière à supporter ces pertes.'
questions[13]['consigne'] = 'Si vous cochez « Toutes les catégories ci-dessus », il n’est pas nécessaire de cocher les autres choix.'
questions[13]['option_toutes_id'] = questions[13]['options'][-1]['id']
questions[13]['champs_complementaires'] = [field('crypto_details', 'Si cryptoactifs, vos précisions facultatives', facultatif=True,
    afficher_si={'question_id': 'classes_actifs', 'option_ids': ['classes_actifs_5', 'classes_actifs_8'], 'operateur': 'au_moins_une'})]
questions[14]['champs_complementaires'] = [field('exclusions_details', 'Si limites ou discussion, vos précisions facultatives', facultatif=True,
    afficher_si={'question_id': 'exclusions', 'option_ids': ['exclusions_2', 'exclusions_3'], 'operateur': 'au_moins_une'})]
questions[15].update(facultatif=True, champ_rien_a_ajouter=field('rien_a_ajouter', 'Je n’ai rien à ajouter.', 'booleen'))

data = dict(titre='Questionnaire du profil investisseur', langue='fr-CA', devise='CAD',
    consignes='Ce questionnaire recueille votre situation, vos objectifs et vos préférences pour préparer l’analyse de votre profil investisseur. Les montants peuvent être approximatifs.',
    avertissement='Simulation éducative uniquement. Aucun rendement n’est garanti. Ce questionnaire ne remplace pas une analyse personnalisée par un professionnel autorisé.',
    questions=questions)
dest = root / 'livrables/Questionnaire_client_Recommand.json'
dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Compare the exported questions and choices with the actual latest Word.
word = Document(root / 'livrables/Questionnaire_client_Recommand.docx')
paragraphs = [p.text for p in word.paragraphs]
assert len(questions) == 16
assert [q['numero'] for q in questions] == list(range(1, 17))
assert len({q['id'] for q in questions}) == 16
for q in questions:
    assert any(q['libelle'] in text for text in paragraphs), q['id']
    for option in q.get('options', []):
        assert '☐  ' + option['libelle'] in paragraphs, option['id']
text = dest.read_text(encoding='utf-8')
assert 'https://' not in text and 'Références utilisées' not in text
assert 'préfère ne pas répondre' not in text
assert len(json.loads(text)['questions']) == 16
print('PASS: JSON valid; 16 questions and all main options match latest Word; no references or refusal option.')
print(dest)
