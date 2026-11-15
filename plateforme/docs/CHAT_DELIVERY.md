# Message visible dès la soumission

Correction du 15 novembre 2026 : le message utilisateur était ajouté à l’historique en même temps que la réponse de l’agent, après l’attente HTTP. Le test avec une réponse différée a reproduit le défaut : une seule ancienne bulle utilisateur était présente alors que deux étaient attendues.

L’interface ajoute, sauvegarde et affiche désormais la bulle utilisateur avant l’appel réseau. La saisie est vidée pour un nouveau message et l’état d’attente apparaît. À réception, seule la bulle assistant est ajoutée. Un double envoi pendant l’attente est bloqué.

En cas d’erreur HTTP, de connexion, de délai dépassé ou de réponse invalide, le message reste visible avec Réessayer. Le réessai utilise la même bulle, sans écraser une autre question en brouillon. Une conversation rechargée avec un message encore en attente le rend réessayable ; aucun renvoi automatique n’a lieu. Les gardes existantes empêchent une ancienne réponse de réapparaître après remise à zéro.

Les statuts locaux `delivery: pending/failed` ne sont jamais envoyés à l’agent. Le contexte exclut les messages non aboutis et conserve le message courant uniquement dans `message`. Le contrat HTTP reste inchangé. Un réessai est une nouvelle requête explicite : cette correction ne garantit pas l’idempotence du traitement distant après une coupure réseau.

La demande d’allègement de l’écran portefeuille remplace le slogan, le surtitre et le sous-titre par « Votre portefeuille ». L’avertissement financier et la mention d’allocation illustrative sont raccourcis. Le résumé des réponses, la zone d’explication, les sources et les limites restent disponibles.

## Handoff

Propriétaire : Router présentation et infrastructure ; frontière compliance conservée pour la mention financière et les résultats acceptés. Entrées : gestionnaire de chat et contrat HTTP existants, correction utilisateur et capture. Fichiers : `src/app.js`, `src/theme.css`, tests et documentation de connexion. Statut : complete. Prochain propriétaire : utilisateur pour le test local ; équipe agent pour le traitement distant.

Vérifications : `node --test --test-isolation=none tests/*.test.mjs` depuis `plateforme` : 35 tests réussis. Les cas supplémentaires contrôlent l’affichage avant une réponse différée, le contexte sans doublon, le réessai, la préservation d’un autre brouillon, le rechargement et les erreurs réseau/délai/format. Les tests existants de reset pendant une requête passent aussi. Le premier lancement sans isolation désactivée a rencontré `spawn EPERM` ; le mode local habituel a permis la reproduction puis la vérification. Leçon L-031.

Vérification DOM et HTTP locale, sans envoi à un agent réel ni capture d’un échange réel. Aucun calcul, CSV, service cloud, commit, push ou déploiement modifié.


## Saisie libre

Correction utilisateur : les quatre suggestions de messages sont retirees, ainsi que leur gestionnaire de clic. Le texte d’accueil invite directement a saisir un message. Le brouillon, l’envoi immediat et les questions contextuelles depuis le portefeuille restent disponibles. Role presentation/infrastructure ; lecon L-030 ; statut complete ; prochain proprietaire : utilisateur pour le test local.
