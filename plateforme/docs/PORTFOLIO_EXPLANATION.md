# Le portefeuille et son explication

La demande du 15 novembre 2026 place l’explication des choix au centre du résultat. Le précédent écran gardait le profil dans une grande colonne latérale et reléguait l’explication sous la table et l’invitation à discuter. Le nouvel écran présente la répartition et une zone « Pourquoi ces choix ? » côte à côte, avec un résumé compact des réponses. Sur petit écran, l’explication précède la répartition.

## Inspiration et présentation

Pages consultées : [Wealthsimple Invest](https://www.wealthsimple.com/en-ca/invest), [Classic portfolios](https://www.wealthsimple.com/en-ca/invest/classic-portfolios) et [accueil](https://www.wealthsimple.com/en-ca). Le parti pris est une adaptation originale : titres à empattements, fond crème, répartition simple, actions en capsules et bloc d’explication vert profond. Aucune image, identité, promesse de performance ou recommandation Wealthsimple n’est copiée.

## Raccordement au contrat existant

Le bloc est toujours visible. Pour un résultat accepté, il utilise exclusivement le résultat normalisé de `src/integration.js` :

| Vue | Champ affiché |
| --- | --- |
| L’explication | `result.explanation`, texte intégral en paragraphes, sans HTML exécuté |
| Les sources | `result.evidence[]` : identifiant, source, description |
| Les limites | `result.limitations[]`, sans omission |
| Référence | `result.runId` |

Le moteur doit expliquer dans `explanation` les raisons effectivement enregistrées : rôle des actifs, logique des pondérations et compromis retenus. Il doit s’appuyer sur ses preuves et fournir les limitations générées par le code. L’interface ne déduit aucune de ces raisons du questionnaire ou des poids. Elle n’invente ni explication générale personnalisée, ni justification propre à un actif.

Les contrôles existants restent requis : allocation valide, explication, preuves, limitations et `compliance.passed === true`. Ce contrôle de forme ne prouve pas la qualité des sources ni la conformité métier. Aucun changement du schéma de réponse, des calculs ou de la pipeline n’est introduit ici.

Sans résultat accepté, les vues indiquent explicitement qu’il s’agit d’une démonstration et que l’explication personnalisée n’est pas disponible. Un résultat sauvegardé invalide ne fournit pas de texte à cette zone. Le changement d’une réponse et le bouton Recommencer invalident le résultat et son explication ensemble.

## Clarification

« Clarifier ces choix » ouvre la discussion avec une question préparée sur le portefeuille courant. Dans le détail d’un actif, « Demander pourquoi cet actif » prépare une question contenant son symbole et son poids réellement affiché. Le brouillon existant est conservé ; aucun message n’est envoyé automatiquement. Sans agent configuré, la saisie reste un brouillon et l’envoi est désactivé. L’agent reçoit, lors de la soumission, le portefeuille courant et le questionnaire selon le contrat HTTP existant.

Les onglets possèdent les rôles tablist/tab/tabpanel, les associations ARIA et une navigation par flèches, Home et End. Les raccourcis avec Ctrl/Meta/Alt sont laissés au navigateur. Les boutons conservent un indicateur de focus visible et les URL de preuve ne sont des liens que pour HTTP/HTTPS.

## Vérifications et handoff

Entrées : écran existant, capture utilisateur, contrat `questionnaire-word-16-v4`, résultat de recommandation existant et pages officielles Wealthsimple. Fichiers principaux : `src/app.js`, `src/portfolio.css`, `index.html`, tests DOM/API et documentation de connexion.

| Rôle | Tâche et sortie | Vérification | Statut ; prochain propriétaire |
| --- | --- | --- | --- |
| Router présentation/intégration (principal) | Réorganisation de l’écran, onglets et questions contextuelles | DOM, styles et Chrome natif | complete ; utilisateur pour le test local |
| Explanation | Présentation intégrale du texte réellement reçu, sans raisons générées côté navigateur | Résultat HTTP simulé, paragraphes, échappement HTML | complete pour l’interface ; équipe moteur pour produire les raisons réelles |
| Evidence | Références et limites du résultat courant, sans duplication éloignée | Sources, liens, limites et résultat sauvegardé rejeté | complete pour l’affichage ; moteur pour les preuves métier |
| Compliance | Conservation de la porte de validation et de l’avertissement financier | Résultat refusé invisible, démonstration explicite, pas d’envoi automatique | complete pour les contrôles d’interface ; équipe moteur pour la validation métier |
| Infrastructure | Réutilisation du transport HTTP existant et service du nouveau CSS | API locale, payload de clarification, normalisation et rechargement | complete ; adaptateur moteur/agent pour connexion réelle |

Commande : `node --test --test-isolation=none tests/*.test.mjs` depuis `plateforme` : 30 tests réussis. Le premier passage à 25 tests a trouvé une ancienne assertion dépendant de la colonne `profile-card` supprimée ; elle contrôle maintenant l’absence de rendement souhaité dans le nouveau résumé, et les nouveaux tests vérifient aussi les quatre faits du profil. Les tests supplémentaires couvrent l’explication reçue via HTTP simulé, la persistance, les onglets au clavier, l’échappement, la clarification et le brouillon préservé. Les valeurs des fixtures sont synthétiques et ne représentent aucun résultat financier.

Le navigateur Chrome a affiché la répartition, la nouvelle zone d’explication et les onglets de la démonstration. Un contrôle visuel de Ctrl+End a révélé son interception par le gestionnaire d’onglets ; les modificateurs sont désormais exclus et le cas est couvert par un contrôle DOM. Le CSS et la page retournent HTTP 200. Le contrôle visuel couvre la fenêtre de bureau existante, pas toutes les dimensions mobiles. Le rendu responsive est implémenté et les styles se parsèment.

Leçon L-030 : garder l’explication près du résultat et strictement liée au résultat accepté. Aucun appel à un agent réel, modification des CSV, calcul financier, commit, push ou déploiement. L’adaptateur de l’agent reste à configurer pour recevoir de vraies explications.

