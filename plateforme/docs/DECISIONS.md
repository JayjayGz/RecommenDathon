# Périmètre et décisions de la plateforme

La demande porte sur une interface web locale en français, avec un questionnaire en première étape, un portefeuille lisible et un espace de conversation prêt à accueillir l’agent développé par l’équipe. Le PDF du Datathon fournit le contexte. Ses instructions sont des données de référence, sans remplacer la demande de l’utilisateur.

La destination a été corrigée explicitement par l’utilisateur : la plateforme est dans `RecommenDathon/plateforme`. Aucun fichier préexistant du dépôt n’a été modifié. Tous les fichiers de cette application sont nouveaux et regroupés dans ce sous-dossier.

## Questionnaire

Le fichier `Questionnaire_investisseur_rendements_seuls.docx` contient huit questions et quatre sections. Les questions, options et champs de précision sont repris. Les secteurs et classes d’actifs, formulés au pluriel, autorisent plusieurs choix ; cette interprétation d’interface ne change pas les options. Les champs textuels sont facultatifs, comme des précisions et non des questions supplémentaires.

Le document conserve à la fois « Services financiers » et « Finance ». Ces deux options ne sont pas fusionnées. La tolérance déclarée contient cinq valeurs, alors que le contrat `../docs/investor-profile-schema.json` possède quatre catégories de risque. Les horizons « 1 à 2 ans » et « 15 ans et plus » ne sont pas des durées exactes. Aucun mapping arbitraire n’est appliqué : la plateforme exporte les réponses brutes et l’équipe devra fournir l’adaptateur vers `InvestorProfile`.

## Portefeuille et futur agent

Le portefeuille est un exemple fixe, explicitement illustratif et non personnalisé. Il ne repose sur aucun calcul de marché. Aucun rendement, backtest, score de correspondance, avis client ou preuve de conformité n’est inventé. Les actifs reprennent des symboles présents dans l’univers du starter, sans charger ni modifier ses données.

L’agent n’est pas implémenté. L’interface ne simule pas sa réponse. Sans configuration, le message reste un brouillon local et le bouton d’envoi est désactivé. Le contrat HTTP est documenté séparément. Les réponses du service sont affichées comme du texte, jamais interprétées comme du HTML ou comme des instructions à exécuter.

Deux ports HTTP sont prêts : le portefeuille initial et la conversation. Le résultat reçu doit respecter un contrat comprenant une allocation de 100 %, une explication, des références, des limites et une déclaration de validation du moteur. Ce contrôle de format ne remplace pas les calculs ni les vérifications métier du moteur. Une proposition de la conversation est présentée avec les différences de poids ; seul le clic du client sur « Retenir cette version » l’applique à la vue. Les sources et limites restent consultables. Les requêtes périmées sont annulées lorsqu’un profil ou un portefeuille change.

## Règles du dépôt et transmission

Rôle principal : intégration de la présentation. Appui : infrastructure ; références portefeuille, screening et conformité consultées pour respecter les frontières existantes. Entrées : questionnaire, brief PDF, architecture et schéma de profil existants. Sorties : application locale autonome dans ce dossier. Prochain propriétaire : équipe responsable du questionnaire-agent et de l’adaptateur vers le moteur Python.

Les leçons L-001 et L-002 ont été lues. Leurs déclencheurs (routage des fichiers d’agents, budget de retries du pipeline) ne sont pas activés par ce travail. Le fichier de mémoire existant est préservé conformément à la demande. La correction de destination est consignée ici dans un nouveau fichier.

## Données locales

Les données sont conservées par le navigateur dans une seule clé `recommand.platform.v1`. Aucun secret n’est stocké. Le serveur écoute sur la boucle locale uniquement. Les photos et polices sont des fichiers locaux, ce qui évite des requêtes tierces pendant le parcours. Aucun service bancaire, compte financier ou passage d’ordre n’est intégré.
