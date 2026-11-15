# Thème du site

La référence est la capture Wealthsimple fournie par l'utilisateur : fond crème, texte noir, titres à empattements, navigation blanche arrondie et actions en capsules. Le site conserve la marque Recommand, les photographies financières et ses interactions.

Le thème est défini dans `src/theme.css`, chargé après les styles de structure. Il couvre le questionnaire, le portefeuille, la conversation et les dialogues. Les points de rupture adaptent la navigation et la typographie aux petites largeurs. `index.html` et le favicon reprennent la palette crème et noir. Les couleurs des séries du graphique d'allocation restent celles des données existantes.

Rôle : Router, présentation/intégration. Entrées : capture utilisateur et application locale de la branche `plateforme`. Leçons chargées : L-001, L-011, L-012 ; L-011 s'applique à la préservation de l'affichage sans flash. Sorties : `src/theme.css`, lien et couleur navigateur dans `index.html`, favicon. Aucun changement aux questions, aux réponses, aux calculs ou aux API.

Vérification : `npm.cmd test` réussit avec 7 tests. La navigation, la conservation des réponses, les champs conditionnels et le maintien du DOM lors des choix sont couverts par ces contrôles déterministes. Le navigateur natif a été sélectionné, mais l'ouverture de l'aperçu a été bloquée par Computer Use : l'outil ne pouvait pas déterminer l'URL courante avec assez de certitude. Le rendu visuel et la mise en page mobile ne sont donc pas certifiés par une vérification navigateur.

Statut : complete pour l'implémentation et les contrôles déterministes. Prochain propriétaire : présentation, pour l'appréciation visuelle dans le navigateur. Aucun commit, push ni déploiement effectué.
