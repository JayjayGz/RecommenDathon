# Correction du questionnaire — 15 novembre 2026

Rôle principal : Router, présentation/intégration. Entrées : branche `plateforme`, `src/app.js`, `src/styles.css`, `src/data.js`, huit questions existantes, signalement utilisateur du flash blanc et des photos hors sujet. Aucun changement au contrat de réponses, au moteur ou aux calculs. Prochain propriétaire : équipe présentation pour la vérification visuelle sur son navigateur, puis utilisateur pour ses modifications et son éventuel push.

## Défauts et causes

- Au changement d'un radio ou d'une case, l'ancien gestionnaire appelait `render()`, remplaçait `#app` et recréait `.page-enter`. L'animation `page-in` partait de `opacity:0`, révélant le fond clair pendant 450 ms. Le reproducer DOM sur `git show HEAD:plateforme/src/app.js` a confirmé que choisir `medium` remplaçait `#main`. Le signalement utilisateur constitue la preuve du flash visuel ; le test confirme son mécanisme, pas une capture vidéo.
- L'ancien `visualPanel(section)` associait quatre sections à des façades et un paysage d'eau. Des questions différentes partageaient donc une photo sans lien financier concret. Le remplacement se fait par identifiant de question : huit fichiers et huit légendes. Recherche, sources et licences : [INSPIRATIONS.md](INSPIRATIONS.md).

## Sorties

`src/app.js` actualise seulement les sélections, coches, détails conditionnels, erreurs et indicateurs de progression. La page, les contrôles actifs et la photo restent montés. Un champ libre encore pertinent conserve son nœud et sa saisie ; les précisions devenues sans objet sont retirées. Modifier un profil terminé invalide toujours l'ancien résultat et verrouille les pages dépendantes. `src/styles.css` garde le contenu visible dès la première frame de navigation et renforce le contraste des légendes sur les nouvelles photos. `index.html` précharge la photo de risque ; l'application précharge la suivante.

Les photos financières locales, les crédits, `package.json`/lockfile, `tests/questionnaire.test.mjs` et les leçons L-011/L-012 complètent la correction. `node_modules/` est ignoré. Les anciennes photos sont conservées mais ne sont plus appelées par le questionnaire.

## Vérifications et transmission

- `cd plateforme; npm.cmd test` : 7 tests DOM réussis. Radio et cas voisin (autre radio), erreur sans réponse et correction, multichoix et détails conservés/supprimés, cryptoactifs/exclusions, profil terminé invalidé, parcours des huit questions et retour, huit photos locales distinctes avec alternatives textuelles et fichiers JPEG vérifiés (présence, taille non nulle, signature), animation sans opacité zéro.
- `node --check plateforme/src/app.js`, `node --check plateforme/server.mjs`, `git diff --check` : réussis.
- Smoke HTTP du serveur existant sur le port temporaire 4187 : 11 routes réussies (page, JS, CSS, huit photos), octets servis identiques aux fichiers locaux par SHA-256 et MIME JPEG vérifié. Serveur arrêté après le contrôle. La première tentative sur l'ancien aperçu 4173 a retourné `ECONNREFUSED` ; le contrôle a donc démarré son propre serveur pour vérifier les fichiers actuels.
- Les huit JPEG ont été ouverts et inspectés ; aucun actif d'un concurrent n'a été copié.
- Limite : la vérification visuelle du site dans Chrome n'a pas été possible. Computer Use a bloqué la session car il ne pouvait pas identifier l'URL courante avec assez de certitude. Les tests jsdom ne mesurent pas le rendu, le contraste réel ou l'animation image par image.

Statut : `complete` pour la correction et les contrôles déterministes ; rendu navigateur restant à vérifier. Ce sont des checks automatisés, pas une revue indépendante. Aucun commit, push ni déploiement effectué.
