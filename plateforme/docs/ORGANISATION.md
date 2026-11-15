# Organisation du site

Tous les fichiers propres au site sont dans `plateforme/` : page HTML, JavaScript, styles, images, polices, questionnaire JSON, serveur HTTP local, tests, dépendances de développement, documentation web et outil d'import du questionnaire dans `scripts/`.

Depuis la racine du projet :

```powershell
cd plateforme
npm.cmd start
```

Tests : `npm.cmd test` dans le même dossier. Le site écoute normalement sur http://localhost:4173.

Le dossier `frontend/` a été fusionné dans `plateforme/` : 22 fichiers déplacés sans collision avec les 18 fichiers de site déjà présents. Les empreintes avant correction de la documentation sont dans `migration-source-hashes.json`. Les fichiers d'exécution, ressources et JSON restent identiques. Le script d'import Word est maintenant `plateforme/scripts/import_questionnaire_word.py` et conserve la même racine de projet.

Les anciens conflits de fusion de la documentation et de `.gitignore` ont été résolus en conservant les deux contenus. Les deux variantes du fichier de leçons ont été réunies avec des identifiants uniques ; l'original est conservé dans `memory/lessons-before-website-merge.txt`. Les références des notes web ont été adaptées.

Rôle infrastructure : consolidation et chemins, statut complete. Contrôles : 16 tests DOM/API réussis ; 12 routes publiques HTTP réussies ; contrôle de deux routes privées ; JSON original de 16 questions conservé ; structure du workflow validée. Leçon L-017. Prochain propriétaire : utilisateur pour lancer le site. Ces contrôles ne constituent pas une revue visuelle du navigateur.

Les calculs Python restent dans `backend/` et les données financières dans `dataset/`. Aucun calcul, contenu du questionnaire, réponse enregistrée, contrat HTTP, déploiement ou historique Git n'a été modifié par ce déplacement.
