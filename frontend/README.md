# Recommand — plateforme locale

Une interface en français pour le Datathon 2026 : questionnaire investisseur, aperçu d’un portefeuille illustratif et espace de discussion prêt à accueillir votre agent.

## Démarrer

Avec Node.js 24 ou plus récent, lancez le serveur depuis `frontend/` avec la commande ci-dessous. Ouvrez **http://localhost:4173** et gardez le serveur ouvert pendant l’utilisation.

Depuis PowerShell, dans ce dossier :

```powershell
npm.cmd start
```

Aucune installation de dépendances et aucune compilation ne sont nécessaires. Le serveur écoute uniquement sur votre ordinateur (`127.0.0.1`). `Ctrl+C` l’arrête. Pour un autre port : `$env:PORT = '4174'; npm.cmd start`.

## Fonctionnement

- Les huit questions et leurs choix proviennent du questionnaire fourni. Les réponses restent dans le stockage local du navigateur ; elles peuvent être exportées ou effacées depuis l’interface.
- Sans moteur configuré, le portefeuille affiché est un **exemple fixe et illustratif**, sans calcul de profil, sans cours de marché et sans recommandation personnalisée. Les réponses ne sont pas utilisées pour inventer une allocation.
- Un moteur de portefeuille externe peut fournir une première recommandation après le questionnaire. Le site vérifie son contrat de réponse ; le moteur demeure responsable des calculs, des preuves et de sa validation de conformité.
- L’agent n’est pas implémenté. Sans configuration, le site indique explicitement qu’il n’est pas connecté et conserve le brouillon localement.
- Les échanges avec un agent configuré transmettent le questionnaire, la conversation et le portefeuille au service choisi. Le service sera responsable de son traitement et de sa conservation.

## Connecter vos services

Définissez l’URL complète de votre endpoint, puis redémarrez le serveur :

```powershell
$env:AGENT_API_URL = 'http://127.0.0.1:8000/chat'
$env:PORTFOLIO_API_URL = 'http://127.0.0.1:8000/portfolio'
npm.cmd start
```

Les deux services sont facultatifs et indépendants. Le premier reçoit les échanges ; le second reçoit le questionnaire complet pour créer un portefeuille initial. L’agent peut également proposer une nouvelle allocation dans une réponse structurée. Le moteur et l’agent ne sont pas implémentés par ce site.

Si nécessaire, définissez `AGENT_API_TOKEN` et `PORTFOLIO_API_TOKEN` dans l’environnement du serveur. Chaque jeton est envoyé comme Bearer au service correspondant et n’est jamais exposé au navigateur. N’inscrivez aucun secret dans les fichiers front-end.

Le contrat exact figure dans [docs/AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md).

## Structure

```text
frontend/
  index.html             Point d’entrée
  src/                   Interface, styles et contrats du questionnaire
  assets/                Images et polices locales
  server.mjs             Serveur HTTP et adaptateurs optionnels
  docs/                  Intégration et sources de conception
```

## Limite de raccordement au profil investisseur

Le schéma existant `../docs/investor-profile-schema.json` attend notamment `risk_tolerance` parmi quatre valeurs et `investment_horizon_years` comme entier. Le questionnaire contient cinq choix de risque et des intervalles de durée. **Aucune correspondance n’a été inventée.** Le site transmet les réponses brutes, versionnées `rendements-seuls-v1`. L’équipe questionnaire/profil devra définir et valider l’adaptateur vers `InvestorProfile` avant toute recommandation réelle.

Simulation et prototype de présentation. Aucun conseil en placement et aucun ordre de transaction.

Le code Python est dans `../src/alphaforge/` ; les CSV sont dans `../dataset/`. Le serveur web ne charge pas ces CSV. Un backend doit adapter le questionnaire au contrat Python puis produire le contrat HTTP ci-dessus. Voir [l’architecture](../docs/architecture.md).
