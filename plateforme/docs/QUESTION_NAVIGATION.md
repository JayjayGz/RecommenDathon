# Navigation et priorité des questions

Demande : rendre les 16 traits cliquables, les agrandir légèrement au survol et donner la majorité de l'espace aux questions.

Présentation, propriétaire principal ; référence chargée : infrastructure. Leçon L-011 appliquée à la conservation des mises à jour sur place. Entrées : questionnaire existant et réponses locales ; aucun changement du contrat, des questions ou de l'interprétation financière.

Modifications : `src/app.js` utilise des boutons de navigation nommés, un état `aria-current`, des titres natifs et le focus sur la question ouverte. La progression accessible est séparée de la navigation. Les réponses numériques et les choix restent enregistrés entre les sauts ; le contrôle final recherche toujours les réponses obligatoires manquantes. `src/theme.css` fournit des zones cliquables de 28 px de haut, le survol, le focus visible et le respect du réglage de réduction des animations.

`src/questionnaire.css` donne environ 70 % de la largeur disponible aux questions sur ordinateur et réduit le titre d'introduction. L'illustration latérale est compacte ; sur mobile elle reste après le formulaire. Le scénario de baisse conserve son contenu et une illustration proportionnellement secondaire.

Contrôles réellement exécutés : `node --test --test-isolation=none tests/*.test.mjs` dans `plateforme/` : 18 réussis, 0 échec. Deux nouveaux cas vérifient la navigation avec conservation des réponses et l'impossibilité de contourner les réponses obligatoires. Les styles sont analysés par les régressions existantes. Le serveur actif sur le port 4173 fournit les nouveaux fichiers. L'accès au navigateur a renvoyé « The browser access host is unavailable » : aucune inspection visuelle ni simulation de survol dans un navigateur n'est revendiquée.

Statut : complete pour les modifications et contrôles DOM/HTTP. Prochain propriétaire : utilisateur pour rafraîchir la page et vérifier le rendu à sa taille d'écran. Aucun calcul financier, appel AWS, commit ou déploiement.

## Consistent reaction-question layout

The user clarified that the fictional bulletin must remain large and centered. The initial sidebar interpretation is superseded. The reaction page keeps its central one-column composition with an outer maximum width of 1180px, normal question heading sizes, smaller bulletin text and a chart capped at 300px. On mobile the bulletin stacks its text and chart. All question text, figures and answers are unchanged.

Presentation owner; lesson L-018 updated to the correction. Status complete. Validation: 21 DOM/API/CSS tests passed, including centered scenario placement, stable chart on selection and retained answer on return. No browser visual review or zoom measurement. Next owner: user to refresh and inspect the page.

Latest clarification: leave the same space on the right as on other questions. The scenario-specific outer width and single-column grid are removed. The bulletin stays inside the standard question column; no small sidebar illustration is introduced. All 21 existing regressions pass; visual browser review remains unavailable.
