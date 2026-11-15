from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'livrables'
OUT.mkdir(exist_ok=True)
doc = Document()
s = doc.sections[0]
s.page_width, s.page_height = Inches(8.5), Inches(11)
s.top_margin = s.bottom_margin = Inches(.65)
s.left_margin = s.right_margin = Inches(.8)
normal = doc.styles['Normal']
normal.font.name = 'Calibri'
normal.font.size = Pt(11)
normal.paragraph_format.space_after = Pt(5)
normal.paragraph_format.line_spacing = 1.05
for name, size in [('Title', 22), ('Heading 1', 16), ('Heading 2', 12)]:
    st = doc.styles[name]
    st.font.name = 'Calibri'
    st.font.size = Pt(size)
    st.font.color.rgb = RGBColor(0, 0, 0)
    st.paragraph_format.space_after = Pt(8)
    st.paragraph_format.space_before = Pt(10)

def p(text='', italic=False):
    x = doc.add_paragraph()
    x.add_run(text).italic = italic
    return x

def question(n, title, help='', options=(), multi=False):
    maximum = 9 if 'Quels secteurs' in title else 8 if 'classes d’actifs' in title else 5
    assert len(options) <= maximum, f'Question {n}: trop de propositions'
    doc.add_heading(f'{n}  {title}', level=2)
    if help:
        p(help, True)
    if options:
        p('Plusieurs réponses possibles.' if multi else 'Choisissez une seule réponse.', True)
        for choice in options:
            x = p('☐  ' + choice)
            x.paragraph_format.space_after = Pt(4)
            x.paragraph_format.keep_together = True

def field(label, lines=1):
    p(label)
    for _ in range(lines):
        p('________________________________________________________________________')

def page(title):
    doc.add_page_break()
    doc.add_heading(title, 1)

doc.add_heading('Questionnaire du profil investisseur', 0)
p('Recommand | Questionnaire client')
p('Ce questionnaire recueille votre situation, vos objectifs et vos préférences pour préparer l’analyse de votre profil investisseur. Cochez les réponses qui vous correspondent et remplissez les champs prévus. Les montants sont en dollars canadiens et peuvent être approximatifs.')
p('Simulation éducative uniquement. Aucun rendement n’est garanti. Ce questionnaire ne remplace pas une analyse personnalisée par un professionnel autorisé.', True)
doc.add_heading('Situation familiale', 1)
question(1, 'Quelle est votre situation conjugale ?', options=[
    'Je suis célibataire.', 'Je suis marié(e) ou en union de fait.',
    'Je suis séparé(e), divorcé(e) ou veuf/veuve.', 'Autre situation.'])
field('Si autre, précisez si vous le souhaitez')
question(2, 'Combien de personnes dépendent financièrement de vous ou sont sous votre responsabilité légale ?',
    'Pensez aux enfants, aux proches que vous soutenez ou aux personnes sous votre tutelle. Aucun nom n’est nécessaire.',
    ['Aucune personne.', 'Une personne.', 'Deux personnes ou plus.', 'Autre situation.'])
field('Si autre, précisez si vous le souhaitez')
p('Si vous avez des personnes à charge, assumez-vous principalement ces dépenses ou les partagez-vous ? Précision facultative.')
p('☐  Je les assume principalement.     ☐  Je les partage avec quelqu’un.')

page('Revenus')
question(3, 'Quel est votre revenu annuel personnel avant impôt ?',
    'Incluez salaire, revenus de travail autonome, pension et autres revenus réguliers. Si vos revenus varient, indiquez une estimation annuelle.',
    ['De 0 $ à moins de 50 000 $.', 'De 50 000 $ à moins de 100 000 $.',
     'De 100 000 $ à moins de 150 000 $.', '150 000 $ ou plus.', 'Autre situation.'])
field('Si autre, précisez si vous le souhaitez')
question(4, 'Vos revenus sont-ils prévisibles pour les douze prochains mois ?',
    'Salaire, pension ou autres revenus réguliers peuvent être concernés.',
    ['Réguliers — Je prévois des revenus assez stables.',
     'Variables — Ils changent d’un mois à l’autre, mais je peux les estimer.',
     'Fragiles — Une baisse importante ou une interruption est possible.',
     'Inconnus — Je ne sais pas encore.'])

page('Dettes et épargne disponible')
question(5, 'À combien estimez-vous le montant total de vos dettes actuelles ?',
    'Indiquez le solde restant à rembourser, pas vos paiements mensuels. Incluez cartes et marges de crédit, prêts automobiles, étudiants et hypothécaires.',
    ['Aucune dette.', 'Plus de 0 $ à moins de 25 000 $.',
     'De 25 000 $ à moins de 100 000 $.', '100 000 $ ou plus.', 'Autre situation.'])
field('Si autre, précisez si vous le souhaitez')
field('Part approximative correspondant à un prêt hypothécaire, si applicable et connue : __________ $ CA')
question(6, 'Quel montant avez-vous actuellement de côté pour faire face aux imprévus ?',
    'Votre fonds d’urgence correspond à l’argent rapidement accessible pour une dépense imprévue ou une interruption de revenu. N’incluez pas vos limites de crédit. Inscrivez 0 si vous n’avez pas encore de fonds d’urgence.')
p('Montant disponible : ____________________ $ CA')

page('Objectifs et besoins de liquidités')
question(7, 'Quel est votre objectif principal pour cet investissement ?', options=[
    'Préparer ma retraite — Constituer une épargne pour mes besoins futurs.',
    'Financer un projet précis — Par exemple, une propriété, des études ou un projet personnel.',
    'Développer mon patrimoine — Faire croître mon épargne sans projet de dépense précis pour le moment.',
    'Autre objectif — Par exemple, obtenir un complément de revenu.'])
field('Si projet précis ou autre objectif, précisez si vous le souhaitez')
p('Montant que vous aimeriez atteindre, si connu : ____________________ $ CA')
question(8, 'Quel est votre horizon de placement ?', options=[
    '1 à 2 ans.', '5 ans.', '10 ans.', '15 ans et plus.'])
p('Quand pourriez-vous avoir besoin de retirer une partie importante de cet argent ?')
p('☐  Moins d’un an.     ☐  De 1 à 3 ans.     ☐  De 4 à 6 ans.     ☐  7 ans ou plus.')
question(9, 'Si vous aviez une dépense imprévue importante, devriez-vous utiliser cet investissement ?',
    options=['Non.', 'En partie.', 'Oui.', 'Je ne sais pas.'])

page('Tolérance au risque')
question(10, 'Quelle est votre tolérance au risque ?', options=[
    'Très basse.', 'Basse.', 'Moyenne.', 'Élevée.', 'Très élevée.'])
p('La tolérance au risque décrit votre aisance face aux fluctuations et aux pertes possibles. Elle est distincte de votre capacité financière à supporter ces pertes.', True)
question(11, 'Si 10 000 $ investis devenaient, sur une période de 3 mois, 8 000 $, quel en serait l’effet sur votre perception de la bourse ?',
    'Mise en situation fictive. La valeur du placement diminue de 2 000 $.',
    ['Inquiet — Je perdrais confiance et voudrais retirer mon argent.',
     'Hésitant — Je serais stressé et aurais besoin de conseils avant de décider.',
     'Préoccupé — La baisse me dérangerait, mais je pourrais rester investi si le portefeuille me convient toujours.',
     'Serein — J’accepte que de fortes baisses puissent arriver. Je pourrais rester investi, même sans savoir quand ni si la valeur remontera.'])

page('Connaissances et préférences de placement')
question(12, 'Comment décririez-vous vos connaissances en placement ?', options=[
    'Débutant — Je découvre les placements et les marchés financiers.',
    'Quelques connaissances — Je connais les principaux types de placements.',
    'Bonne compréhension — Je comprends leurs risques et les principes de diversification.',
    'Expérience approfondie — Je connais plusieurs produits et suis régulièrement les marchés.'])
question(13, 'Quels secteurs vous intéressent particulièrement ?', options=[
    'Technologie — Informatique, logiciels et semi-conducteurs.',
    'Santé — Médicaments, soins de santé et biotechnologie.',
    'Finance — Banques, assurances et services financiers.',
    'Énergie — Pétrole et gaz.',
    'Immobilier — Via un FNB immobilier.',
    'Industrie — Transport, aéronautique et équipements industriels.',
    'Consommation — Alimentation, commerce et biens de consommation.',
    'Communications — Télécommunications, médias et divertissement.',
    'Services aux collectivités — Services publics.'], multi=True)
question(14, 'Quelles sont les classes d’actifs qui vous intéressent le plus ?', options=[
    'Actions — Titres de sociétés canadiennes et américaines.',
    'FNB d’actions — Fonds diversifiés ou sectoriels.',
    'Revenu fixe — Via des FNB obligataires.',
    'Immobilier et matières premières — Via des fonds cotés.',
    'Cryptoactifs — Bitcoin, Ether, XRP, Litecoin et Bitcoin Cash.',
    'Contrats à terme sur matières premières — Pétrole, gaz, or, argent et cuivre.',
    'Devises — Paires de devises, dont EUR/USD et USD/CAD.',
    'Toutes les catégories ci-dessus.'], multi=True)
p('Si vous cochez « Toutes les catégories ci-dessus », il n’est pas nécessaire de cocher les autres choix.', True)
field('Si cryptoactifs, vos précisions facultatives')

page('Exclusions et précisions complémentaires')
question(15, 'Y a-t-il des placements ou des activités que vous ne voulez pas dans votre portefeuille ?', options=[
    'Aucune — Je n’ai aucune exclusion particulière.',
    'Limites — Oui, je veux exclure certains placements ou certaines activités.',
    'Discussion — J’aimerais comprendre les possibilités avant de préciser mes limites.'])
field('Si limites ou discussion, vos précisions facultatives', 3)
question(16, 'Avez-vous d’autres précisions à apporter pour nous aider à comprendre votre situation ?',
    'Vous pouvez préciser un projet à venir, une dépense importante, un changement familial ou professionnel, une contrainte ou une préoccupation concernant vos placements. N’inscrivez aucun numéro de compte ni renseignement bancaire confidentiel. Réponse facultative.')
field('Vos précisions', 5)
p('☐  Je n’ai rien à ajouter.')
p('Références utilisées pour la formulation', True)
for text in [
    'AMF — Votre profil d’investisseur : https://lautorite.qc.ca/grand-public/outils-et-calculateurs/calculateurs/votre-profil-dinvestisseur',
    'OCRI — Understanding Risk : https://www.ciro.ca/office-investor/understanding-risk',
    'ACFC — Établir un fonds d’urgence : https://www.canada.ca/fr/agence-consommation-matiere-financiere/services/epargnes-investissements/etablir-fonds-durgence.html',
]:
    x = p(text)
    for r in x.runs:
        r.font.size = Pt(8)

footer = s.footer.paragraphs[0]
footer.alignment = 2
footer.add_run('Page ')
fld = OxmlElement('w:fldSimple')
fld.set(qn('w:instr'), 'PAGE')
footer._p.append(fld)
doc.core_properties.title = 'Questionnaire du profil investisseur'
doc.core_properties.author = 'Recommand'
doc.core_properties.subject = 'Situation du client objectifs contraintes et préférences de placement'
dest = OUT / 'Questionnaire_client_Recommand.docx'
for root in (doc.styles.element, doc.element):
    for border in root.xpath('.//w:pBdr'):
        border.getparent().remove(border)
doc.save(dest)
print(dest)
