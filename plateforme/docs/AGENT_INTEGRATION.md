# Contrat de connexion de l’agent

Le résultat peut également contenir `analysis` : revue déterministe, couverture
sectorielle des actions directes, concentration, risque historique, règles de
profil, recherche bornée et alternatives vérifiées avec leurs références de
preuve. Le proxy et le normaliseur conservent ces champs après validation.
Les alternatives ont `applied: false` et ne sont pas appliquées automatiquement.
Voir [méthodes, limites et exemple calculé](../../docs/portfolio-review.md).

Le site est un client local. Il ne contient ni agent, ni moteur de recommandation, ni calcul de risque. Deux adaptateurs HTTP transmettent les requêtes aux URL complètes `AGENT_API_URL` (discussion) et `PORTFOLIO_API_URL` (portefeuille initial), configurées côté serveur. Sans URL, le service correspondant retourne HTTP 503, `AGENT_NOT_CONNECTED` ou `PORTFOLIO_NOT_CONNECTED`.

## Routes locales

| Route | Résultat |
| --- | --- |
| `GET /api/health` | `{ "ok": true, "service": "recommand-local" }` |
| `GET /api/config` | `{ "agentConnected": false, "portfolioConnected": false }`. Chaque booléen devient `true` si l’URL correspondante est configurée ; cela ne vérifie pas la disponibilité du service. |
| `POST /api/agent/chat` | Validation de la requête, puis appel de l’URL agent si elle est configurée. |
| `POST /api/portfolio` | Validation des réponses du questionnaire à 16 étapes, puis appel du moteur de portefeuille. |

## Requête

L’endpoint agent reçoit le même objet que le serveur local :

```json
{
  "message": "Je souhaite comprendre cette répartition.",
  "conversation": [
    { "role": "user", "content": "Je souhaite comprendre cette répartition." }
  ],
  "questionnaire": {
    "version": "questionnaire-word-16-v4",
    "answers": {
      "marital": "single",
      "dependents": "none",
      "annualIncome": "under_50k",
      "income": "regular",
      "debt": "none",
      "emergencyFund": 0,
      "goal": "retirement",
      "horizon": "1_2",
      "liquidity": "no",
      "risk": "very_low",
      "reaction": "worried",
      "knowledge": "beginner",
      "sectors": [
        "technology"
      ],
      "assets": [
        "stocks"
      ],
      "exclusions": "none",
      "withdrawalTiming": "under_1"
    }
  },
  "portfolio": {
    "id": "example-contract",
    "name": "Exemple de contrat",
    "positions": [
      { "symbol": "SPY", "name": "FNB S&P 500", "category": "Actions américaines", "group": "Actions", "weight": 60 },
      { "symbol": "XBB.TO", "name": "FNB obligataire", "category": "Obligations canadiennes", "group": "Obligations", "weight": 40 }
    ]
  }
}
```

Cet exemple complet décrit uniquement le contrat. Il n’est pas un profil évalué ou une recommandation mesurée. `questionnaire.answers` contient les identifiants et valeurs brutes produits par les contrats front-end de `src/data.js`. `portfolio` contient le portefeuille actuellement affiché. `conversation` contient l’historique récent ; `message` porte le message courant, sans être ajouté une seconde fois à cet historique par l’interface. Le client conserve jusqu’à 40 messages localement et retire les plus anciens du contexte transmis si la requête dépasse 60 Kio, sans effacer leur copie locale.

Le serveur exige un objet JSON, un message non vide de 5 000 caractères maximum, au plus 100 messages de conversation, des rôles `user` ou `assistant`, des contenus de 10 000 caractères maximum, la version exacte `questionnaire-word-16-v4`, les réponses valides aux 15 questions principales obligatoires, le sous-champ obligatoire `withdrawalTiming` et, si fournis, les champs facultatifs de la seizième étape (notes) et un portefeuille dont les poids positifs totalisent 100 %. Les précisions textuelles facultatives sont `maritalOther`, `dependentsOther`, `incomeOther`, `debtOther`, `goalDetails`, `cryptoDetails`, `exclusionDetails` et `notes` (1 000 caractères chacune). Les autres sous-champs sont `supportMode` (choix), `mortgageAmount` (nombre fini positif ou nul) et `noNotes` (booléen). Les champs conditionnels ne sont acceptés que lorsqu’ils sont visibles selon `src/data.js` ; `noNotes: true` exclut `notes`. L’option conjugale `separated` et le champ `targetAmount` ont été retirés : ils sont rejetés par la validation HTTP. Taille totale maximale de la requête : 64 Ko. Le backend doit également appliquer sa propre validation métier.

Pour `POST /api/portfolio`, envoyez seulement `{ "questionnaire": { "version": "questionnaire-word-16-v4", "answers": { ... } } }` avec le même contrat de réponses. Aucun profil de risque n’est déduit par le serveur.

## Réponse

```json
{ "message": "Texte de réponse de votre agent." }
```

`message` est une chaîne non vide de 10 000 caractères maximum. L’agent peut ajouter un champ facultatif `proposal` contenant exactement le résultat structuré décrit ci-dessous. Une proposition invalide fait échouer toute la réponse (`502 AGENT_INVALID_RESPONSE`). Une proposition valide reste soumise à la présentation et à l’acceptation prévues par l’interface ; le serveur ne réalise aucune transaction.

## Résultat structuré du portefeuille

`POST /api/portfolio` attend ce type de réponse. Le champ `proposal` d’une réponse de discussion utilise le même objet complet. **L’exemple suivant est hypothétique et sert uniquement à montrer le protocole : aucune simulation, preuve ou conformité réelle n’a été exécutée pour ces valeurs.**

```json
{
  "runId": "contract-example-only",
  "portfolio": {
    "id": "contract-portfolio-only",
    "name": "Exemple hypothétique de réponse",
    "positions": [
      { "symbol": "SPY", "name": "FNB S&P 500", "category": "Actions américaines", "group": "Actions", "weight": 60, "color": "#303e32" },
      { "symbol": "XBB.TO", "name": "FNB obligataire", "category": "Obligations canadiennes", "group": "Obligations", "weight": 40, "color": "#b6aa90" }
    ]
  },
  "explanation": "Exemple de texte explicatif renvoyé par le moteur ; ce texte ne décrit aucun calcul exécuté.",
  "evidence": [
    { "id": "EXAMPLE-ONLY", "source": "Exemple de contrat, sans jeu de données exécuté", "description": "Le vrai moteur doit fournir une source et une description vérifiables pour chaque preuve." }
  ],
  "limitations": ["Exemple hypothétique de protocole, sans recommandation réelle."],
  "compliance": { "passed": true }
}
```

La réponse est contrôlée par la même fonction `validateRecommendation` de `src/integration.js` côté serveur et navigateur : 1 à 40 positions, symboles uniques, noms et catégories présents, poids strictement positifs et au plus 100 %, total 100 % (tolérance 0,001 point), couleur facultative hexadécimale, identifiant d’exécution, explication, au moins une preuve (`id`, `source`, `description`), tableau de limites, et `compliance.passed === true`. La réponse JSON est limitée à 64 Ko. Le serveur ne relaie que les champs documentés.

**Ces contrôles vérifient la forme du contrat. Ils ne prouvent ni les calculs, ni les sources, ni la conformité.** Le moteur doit exécuter les contrôles métier, produire ses preuves et enregistrer son audit avant de renvoyer `passed: true`. Une réponse absente ou invalide ne devient jamais une recommandation réelle.

Les erreurs sont explicites : 400/413/415 pour une requête invalide, 503 si le service est absent ou mal configuré, 502 si le service échoue ou répond hors contrat, 504 après 30 secondes sans réponse. Le navigateur ne reçoit ni URL privée, ni jeton, ni détail technique du service. Les codes utilisent le préfixe `AGENT_` ou `PORTFOLIO_` selon la route.

## Configuration

`AGENT_API_URL` et `PORTFOLIO_API_URL` acceptent des URL HTTP ou HTTPS sans identifiants inclus dans l’URL. `AGENT_API_TOKEN` et `PORTFOLIO_API_TOKEN`, facultatifs, ajoutent l’en-tête `Authorization: Bearer …` uniquement au service correspondant. Gardez ces valeurs dans l’environnement du serveur. Le serveur est limité à `127.0.0.1` et refuse les origines Web autres que les deux adresses locales attendues. Aucun appel AWS n’est ajouté.

## Adaptation vers InvestorProfile

Le schéma existant du dépôt parent exige `profile_id`, `base_currency`, `risk_tolerance` et `investment_horizon_years`. Ses quatre niveaux de risque ne correspondent pas directement aux cinq choix du questionnaire ; les horizons du questionnaire sont des intervalles, pas des années exactes. Le contrat actuel conserve les réponses brutes et ne fabrique pas cette correspondance. L’équipe responsable du questionnaire/profil doit fournir un adaptateur validé avant de lancer la pipeline. Les recommandations réelles restent soumises aux contrôles de preuve et de conformité du dépôt.

Rôle chargé : infrastructure. Références lues : `AGENTS.md`, `agents/infrastructure-agent.md`, architecture, responsabilités, protocole de correction et leçons L-001/L-002. Leurs déclencheurs (routage de fichiers d’agents, réparations d’explications) ne sont pas engagés par cet adaptateur. Aucun fichier existant de mémoire ou de routage n’a été modifié.

## Emplacement et raccordement Python

Le site est dans `plateforme/`. Le moteur de calcul se construit avec `from alphaforge.bootstrap import create_engine` ; ses méthodes Python ne sont pas des endpoints HTTP. Les CSV restent côté backend dans `dataset/`, avec `prices_daily.csv` comme fichier de prix. Aucun chargement des CSV n’est fait dans le navigateur. Le mapping du questionnaire, les handlers HTTP, les preuves et la validation de conformité restent à implémenter avant de brancher les services. Voir [l’architecture](../../docs/architecture.md) et [le contrat investisseur](../../docs/investor-profile-schema.json).
## Source du questionnaire

Le Word sélectionné, son empreinte et les règles de changement de version sont décrits dans [QUESTIONNAIRE_WORD.md](QUESTIONNAIRE_WORD.md). Les identifiants sont des valeurs brutes de formulaire ; ils ne constituent pas une correspondance vers un profil de risque métier.

## Affichage de l’explication et clarification

La page portefeuille expose directement `explanation`, `evidence`, `limitations` et `runId` du résultat accepté dans le bloc « Pourquoi ces choix ? ». Le texte est conservé intégralement et échappé ; aucune justification n’est calculée par l’interface. Les raisons de sélection, de pondération et les compromis effectivement enregistrés doivent être formulés par le moteur dans `explanation`. Le schéma HTTP reste inchangé.

Les actions de clarification préparent un brouillon lié au portefeuille courant ou à une position précise. Elles ne déclenchent aucun envoi automatique et conservent un brouillon déjà saisi. L’envoi explicite utilise le même contrat `POST /api/agent/chat`. Sans résultat accepté, la zone annonce la démonstration et l’absence d’explication personnalisée. Détails et vérifications : [PORTFOLIO_EXPLANATION.md](PORTFOLIO_EXPLANATION.md).

## Affichage immédiat des messages

Dès la soumission, le message utilisateur apparaît et est sauvegardé localement avec `delivery: pending`. L’interface ajoute ensuite uniquement la réponse de l’agent. Un échec conserve la bulle avec un bouton Réessayer ; le réessai réutilise cette bulle et préserve un autre brouillon éventuel. Après rechargement, un envoi interrompu devient un échec réessayable, sans renvoi automatique.

`delivery` est une métadonnée locale, exclue du transport. Le champ `message` contient le message courant ; `conversation` contient seulement les messages précédents aboutis, au format `{ role, content }`. Le message courant n’y est pas dupliqué. Aucun mécanisme d’idempotence serveur n’est ajouté. Détails et vérifications : [CHAT_DELIVERY.md](CHAT_DELIVERY.md).

## Fusion des changements locaux

Les ajouts backend (`analysis` et lancement local) sont conserves avec le contrat UI v4 et le chat immediat. Le delai du chat reste de 130 secondes. L’adaptateur Python existe deja pour v2 ; la mention historique indiquant que tout le mapping reste a implementer ne decrit donc pas cet adaptateur. Sa compatibilite v4 reste a traiter : `word_questionnaire.py` exige encore v2. Aucun raccordement de bout en bout n’est certifie par cette resolution de conflits.
