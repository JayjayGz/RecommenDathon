# Investor-facing explanation

Le mapping amont et les faits d’exposition sont désormais décrits dans
[Expositions et questionnaire](expositions-et-questionnaire.md). Le résumé
présente la couverture sectorielle connue, les descriptions sourcées et les
pistes non appliquées ; il conserve la distinction entre score de référence,
admissibilité numérique et avis préalable à une modification.

## Analyse des modifications après le questionnaire

Toute modification reçoit un avis préalable relié aux réponses du questionnaire :
catégorie d’actif, secteur des actions directes, tolérance au risque, horizon,
retraits, tensions explicites et limites structurées. Les indicateurs calculés
permettent ensuite d’expliquer les compromis historiques. Une hausse du risque,
une différence de préférence ou une demande nécessitant un ajustement appelle
une clarification ; ces réserves ne changent ni les plafonds du moteur ni le
score de risque. Les intérêts sectoriels restent des préférences.

Le résultat `changeReview` distingue `compatible`, `clarification_required` et
`not_retained`. Il porte toujours `applied: false` et une confirmation requise.
Seul un avis compatible avec le portefeuille de départ encore affiché permet
le bouton « Confirmer cette modification ». Les autres résultats restent des
analyses à préciser. Une ancienne proposition est retirée dès qu’une nouvelle
demande est envoyée. Sans montant, un avis qualitatif est fourni puis le montant
à simuler est demandé ; aucun poids n’est inventé.

Les fonds peuvent correspondre à une catégorie choisie, mais leur contenu
sectoriel reste une limite explicite faute de données détaillées. Cet avis est
éducatif : la compatibilité avec les critères vérifiés ne constitue pas une
validation de la situation financière complète. Les conclusions et leurs
éléments sont reconstruits au contrôle de sortie et conservés dans l’audit.

Le résumé rappelle désormais la demande et compare les poids de départ aux poids
réellement proposés, y compris les suppressions et les positions utilisées en
contrepartie. Il distingue la demande acceptée de l’alternative ajustée, signale
une répartition inchangée après arrondi et indique explicitement lorsqu’aucune
proposition ne peut être retenue.

La croissance annualisée, les fluctuations annualisées et la plus forte baisse
sont comparées uniquement lorsque les périodes complètes, la devise et les
méthodes de simulation coïncident. Dans le cas contraire, le résumé indique que
l’effet du changement ne peut pas être isolé. Les indicateurs de départ sont
ajoutés aux preuves contrôlées pour les demandes de modification. Les variations
observées concernent l’ensemble du portefeuille et ne sont pas attribuées à un
seul actif. Les avertissements et les contrôles existants sont conservés.

Les régressions couvrent l’ajout, la suppression, l’alternative ajustée, des
indicateurs de risque évoluant en sens opposés, des périodes différentes et
l’absence de changement effectif. Les calculs financiers restent inchangés.

Questionnaire and personalization results use a deterministic French summary of
the checked evaluation, shared by the portfolio page and chat. It explains the
allocation, historical growth and largest observed decline in ordinary language.
Conflicting requests explicitly distinguish the adjusted alternative from the
original request; no passing allocation is promised when none exists. One checked
concentration alternative may be mentioned, with its unapplied status and trade-off.

The summary flags explicit combinations of normalized questionnaire answers:
high risk with worry about losses or a near-term withdrawal; a long horizon with
a near-term withdrawal; low risk with crypto interest; uncertain income without
an emergency reserve. These observations invite clarification in neutral language.
They do not score financial risk capacity, change the risk band or modify weights.
Missing answers are never interpreted as zero balances or contradictions. No
detected tension is a statement about these checks alone, not overall suitability.

Sources, evidence identifiers and technical method details are omitted from the
displayed response. The existing evidence bundle, model ordering validation,
bounded retries, reconstruction checks and audit records are retained. Technical
evidence remains in the structured integration contract for existing consumers;
the frontend no longer renders it as a sources section. The summary is generated
from validated evaluation values after the release checks and before audit storage.
The legacy explicit-profile developer API retains its technical rendering.

Four French limitations explain what cannot be established: future outcomes and
complete market risks; full financial suitability; costs, taxes, resale liquidity
and company fundamentals; underlying fund overlap and guaranteed ethical/sector
exclusions. The UI displays them separately, without repeating the backend methods.

Development handoff: explanation is the primary owner; evidence and compliance
support the presentation boundary. Inputs are validated questionnaire answers,
checked evaluations and unchanged source data. Outputs are `investor_summary.py`,
the orchestrator view, frontend result display and summary regressions. Integration
maintainer is the next owner; no deployment or live-model acceptance is implied.

Status: complete locally. Verification: full offline backend suite, 305 passed,
2 skipped, 2 expected failures and 17 passing subtests; connected local pipeline,
20 checks passed across 14 audited real-data runs. Node syntax, questionnaire HTTP
test and workflow structure checks passed. These are deterministic development
checks; no independent review, graphical browser verification or live Bedrock call
was performed for this change. Lesson L-029 records the user correction.
