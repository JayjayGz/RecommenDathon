# Questionnaire Word dans le site

Le document explicitement sélectionné par l'utilisateur est `Questionnaire_client_Recommand_20261115_103525.docx`. Son SHA-256 est `621694f066b0f89d3f7d6ed9fd9e2b2d53f3b05dccd647ae03afed75201147e2`. La lecture réelle du document confirme 16 questions principales et sept sections, sans question de rendement ni de dépenses mensuelles.

Les titres et choix sont extraits dans `src/data.js`, avec un instantané de contrôle dans `tests/fixtures/questionnaire-word.json`. Les sous-champs du Word sont conservés : autres situations, partage des charges, part hypothécaire, objectif et montant visé, délai de retrait, cryptoactifs, exclusions et notes finales. Les champs explicitement facultatifs restent facultatifs ; le délai de retrait accompagne la réponse d'horizon. Zéro est une réponse numérique valide au fonds d'urgence. L'option Toutes est exclusive des autres catégories. Aucun mapping financier n'est déduit des réponses.

Le contrat brut passe de `rendements-seuls-v1` à `questionnaire-word-16-v2`. Le navigateur utilise une nouvelle clé locale `recommand.platform.word16.v2` ; les anciens résultats ne sont pas repris. Les anciennes données restent sous leur ancienne clé. Le serveur valide les mêmes champs typés que le navigateur et rejette les champs inconnus, invalides, cachés ou contradictoires. Les équipes questionnaire et moteur doivent prendre en charge cette nouvelle version avant une connexion réelle. Le schéma métier InvestorProfile et la politique d'allocation ne sont pas modifiés.

`src/illustrations.js` fournit les dessins SVG locaux associés aux sujets : foyer, budget, revenus, réserve, objectifs, calendrier, risque, connaissances, secteurs, catégories et exclusions. L'encadré de baisse reproduit la composition de la capture utilisateur : bandeau rose, fond sombre, 10 000 dollars vers 8 000 dollars, courbes et grosse flèche descendante. Le graphique est une illustration originale de la situation fictive ; il n'est ni le bitmap original ni une série historique. Aucun nombre nouveau ni rendement prévisionnel n'est ajouté.

Rôle principal : Router présentation et contrat questionnaire. Appuis chargés : screening, portfolio, compliance et infrastructure. Leçons chargées : L-001 à L-012 ; L-011 protège les mises à jour du formulaire sur place. L-012 est remplacée, dans ce périmètre, par la demande explicite d'illustrations plutôt que de photographies. Les calculs, l'allocation, les preuves, la conformité des résultats et AWS restent hors de cette modification.

Vérifications : `cd plateforme; npm.cmd test` donne 15 tests réussis, incluant le parcours complet, la fidélité à l'instantané Word, le maintien du DOM et du focus, les montants nuls et invalides, les sous-champs, Toutes, la migration de stockage et les routes HTTP valides/invalides. Les CSS se parsèment et l'animation d'entrée conserve le contenu visible. Une première invocation a encore exécuté les tests de l'ancien contrat à 8 questions ; ils ont été remplacés par les mêmes scénarios adaptés au Word, complétés par les cas numériques et HTTP. Le premier test HTTP a utilisé un port zéro interdit par la configuration du serveur ; il réserve désormais un port libre valide. Aucun appel réseau à un agent ou à AWS n'a été effectué.

Limite : Computer Use a signalé un arrêt utilisateur par Échap et le navigateur connecté est indisponible. La prévisualisation n'a donc pas été inspectée visuellement. Les contrôles DOM et CSS ne certifient pas la mise en page à l'écran.

Statut : complete pour l'intégration et les contrôles déterministes. Prochain propriétaire : équipe questionnaire/moteur pour l'adaptation au nouveau contrat, présentation pour la vérification visuelle. Aucun commit, push ou déploiement effectué.

## Saisie des montants et exemples

R?le Router pr?sentation. Correction du 15 novembre 2026 : les fl?ches natives des champs num?riques sont masqu?es pour WebKit et Firefox, tout en conservant le type num?rique et sa validation. Des exemples gris clair sont affich?s par des placeholders dans les montants, les champs Autre et les pr?cisions. Ils ne deviennent jamais des r?ponses et ne remplacent pas les valeurs d?j? saisies. Les tests passent d?sormais ? 16, notamment le champ vide, le montant sauvegard? de 24 et une saisie r?elle de 100. Le?on L-014 ; statut complete pour la correction et les contr?les DOM, sans v?rification visuelle navigateur. Prochain propri?taire : pr?sentation pour le contr?le ? l??cran.

## User override: remove discussion choice

The user explicitly removed the Discussion option from the exclusions question. Runtime answers now use `questionnaire-word-16-v3`; only `none` and `limits` are accepted for exclusions, and the optional detail field is shown only for limits. The local JSON template is synchronized. The original Word snapshot stays intact; tests apply this one explicit override when comparing it with the UI. The importer applies the override after saving the original snapshot. The browser keeps its existing storage key so compatible answers are retained; the removed choice and its hidden details are discarded without selecting a replacement, invalidating completion when necessary. The post-portfolio agent discussion remains available.

Owner: presentation/contract integration; reference lesson L-013. Checks: 20 DOM/API tests passed, including removed saved answers rejected and legitimate limits accepted. Status: complete; next owner: user to refresh the local questionnaire. No financial interpretation or allocation changed.

## Corrections utilisateur et interface — version v4

Le contrat courant est `questionnaire-word-16-v4`. À la demande explicite de l’utilisateur, le choix « Je suis séparé(e), divorcé(e) ou veuf/veuve » et le montant visé (`targetAmount`, `objectif_montant` dans le modèle JSON) sont retirés. L’instantané Word d’origine reste intact ; les tests et l’importeur appliquent ces corrections après extraction, en plus du retrait antérieur de Discussion. Les réponses compatibles sont conservées. Les valeurs supprimées sont nettoyées et les anciens résultats dépendants sont invalidés ; aucune réponse de remplacement n’est choisie.

Le bouton Recommencer est disponible dans l’en-tête des trois pages. Il efface les réponses, le brouillon, la conversation, les propositions et les résultats, supprime les anciennes clés locales de cette application, puis revient à la première question. Les requêtes en cours sont annulées et leurs réponses tardives ne restaurent pas l’ancien profil. Les données d’autres applications sont préservées.

L’espace de discussion conserve le thème crème et noir : titre plus mesuré, résumé latéral compact sans image décorative, quatre suggestions cliquables et libellé de saisie visible. L’accueil vide ne crée plus de défilement interne. Un agent non connecté reste clairement indisponible ; les suggestions préparent seulement un brouillon.

Handoff : Router présentation/contrat, appui infrastructure et revue des limites compliance. Entrées : contrat Word existant et corrections explicites utilisateur ; aucune interprétation financière ajoutée. Sorties : `src/app.js`, `src/data.js`, `src/theme.css`, modèle JSON, importeur, tests et documentation. Leçons appliquées : L-011, L-013, L-014 ; nouvelle leçon L-035 sur la remise à zéro globale. Statut : complete. Prochain propriétaire : utilisateur pour tester, équipe questionnaire/moteur pour l’adaptation métier de la version v4.

Vérifications exécutées : `node --test --test-isolation=none tests/*.test.mjs` dans `plateforme` : 25 tests réussis, 0 échec. Les tests couvrent les trois pages, le rechargement après remise à zéro, les anciennes clés, une réponse tardive de discussion/portefeuille, les champs retirés et les cas valides voisins. L’ancienne attente de fidélité intégrale au Word a d’abord échoué sur le choix retiré ; elle compare désormais la source intacte avec les corrections utilisateur explicites. Un premier contrôle du libellé de saisie a détecté son absence après une substitution de texte ; le libellé a été ajouté et le cas rejoué avec succès. Chrome a été actualisé et l’espace de discussion inspecté visuellement via capture native : titre, résumé, quatre suggestions et zone de saisie visibles, sans barre de défilement interne sur l’accueil vide. Ce contrôle visuel ne couvre pas toutes les tailles d’écran. Aucun appel à un agent, simulation, commit, push ou déploiement.

## Retraits supplementaires - contrat v5

Le questionnaire courant contient 15 questions. La question conjugale complete et le sous-champ de delai de retrait sont retires apres extraction du Word original, qui reste intact dans la fixture. La version devient questionnaire-word-15-v5. Les reponses compatibles sont conservees, les champs retires nettoyes et les anciens resultats invalides. Les tests de navigation et de validation utilisent ce contrat courant.

### Compatibilité après résolution du rebase

La résolution combine la nouvelle interface v5 avec les contrôles de confirmation
du portefeuille. Le refus Python `Unsupported questionnaire version` a été
reproduit puis corrigé : le backend accepte maintenant v5, ainsi que les contrats
historiques v2/v4. Les champs conjugaux et le délai de retrait ne sont ni exigés
ni recréés en v5 ; leur envoi est refusé. Les précisions conditionnelles restent
obligatoires. Le parcours HTTP local avec le véritable formulaire v5 retourne
200 : 30 contrôles connectés réussis, 14 exécutions auditées, sans appel AWS/LLM.

Handoff : infrastructure (propriétaire), revue du contrat par screening,
portfolio et compliance ; entrées : module frontend courant et contrats
historiques ; sorties : normaliseur Python, régressions et générateur du contrôle
connecté. Statut : complete ; prochain propriétaire : utilisateur pour redémarrer
son serveur local et recharger le site. Les calculs et limites restent ceux du
moteur existant. Leçon appliquée et enrichie : L-024.
