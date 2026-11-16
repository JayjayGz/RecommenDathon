# Compréhension du questionnaire et sélection du profil

Le formulaire courant comporte 15 étapes, 62 choix et 9 champs complémentaires.
`QuestionnaireUnderstandingAgent` est une étape exécutée avant la sélection,
distincte du fichier de rôle `agents/questionnaire-agent.md`. Elle conserve chaque
champ normalisé, sa valeur, sa provenance, son utilisation et une empreinte de
l'entrée. Elle examine aussi les précisions de chaque étape et les notes finales.

## Couverture des réponses

| Étape | Utilisation effective | Précisions et limites |
| --- | --- | --- |
| Personnes à charge | Examen des besoins de réserve et contexte explicatif | Aucune, une, plusieurs, Autre et partage des dépenses sont conservés ; aucun score démographique inventé. |
| Revenu annuel | Contexte financier et provenance | Toutes les tranches et Autre restent distincts ; absence de dépenses et de mensualités empêchant de calculer une capacité financière complète. |
| Stabilité des revenus | Score de capacité du module fourni | Régulier, variable, fragile et inconnu suivent la table existante ; un texte explicitement contradictoire demande confirmation. |
| Dettes | Contexte, cohérence du total et de la part hypothécaire | Toutes les tranches et Autre sont examinés ; une hypothèque positive avec « aucune dette » ou supérieure à la borne de la tranche est contradictoire. |
| Fonds d'urgence | Examen de la réserve et explication | Zéro est valide et déclenche une observation ; aucun montant n'est assimilé automatiquement au capital à investir. |
| Objectif | Contexte de projet/retraite/patrimoine ; préférence de style lorsque explicitée | Un complément de revenu explicitement demandé peut départager un style ; aucun rendement cible n'est inventé. |
| Horizon | Score de capacité existant et cohérence avec les notes | Les quatre choix sont conservés ; un retrait décrit avant l'horizon coché exige confirmation. |
| Besoin imprévu | Examen des besoins de liquidité | Les quatre réponses sont conservées ; besoin affirmé ou inconnu signalé, sans inventer le montant à réserver. |
| Tolérance au risque | Minimum des signaux de tolérance du module fourni | Les cinq niveaux restent distincts ; une demande explicite de capital garanti incompatible avec un risque élevé demande clarification. |
| Réaction à une baisse | Minimum des signaux de tolérance existants | Les quatre réactions sont utilisées ; elles ne sont pas écrasées par une préférence sectorielle. |
| Connaissances | Minimum des signaux de tolérance existants | Les quatre niveaux sont utilisés ; une déclaration de débutant incompatible avec la case cochée demande confirmation. |
| Secteurs | Comparaison des secteurs souhaités | Les neuf choix normalisés sont comparés aux répartitions GICS datées des actions et fonds ; métadonnées des actions directes en repli ; expositions inconnues explicites. |
| Classes d'actifs | Comparaison des poids dans les classes souhaitées | Les huit choix, dont Toutes, sont interprétés. Futures et devises restent explicitement indisponibles ; une demande limitée aux classes indisponibles ne reçoit pas un autre portefeuille par défaut. |
| Exclusions | Contraintes impératives transmises au moteur | Symboles, noms du catalogue et refus explicites de classes sont traités. Les listes partiellement reconnues, exclusions d'activité/ESG et exclusions sectorielles non vérifiables nécessitent clarification. |
| Notes finales | Préférences explicites, contradictions ou contexte | Le texte et la confirmation « rien à ajouter » sont tracés. Les instructions visant le système ne modifient jamais le profil. |

Les précisions peuvent enrichir les secteurs/classes souhaités, identifier un actif
préféré ou un style explicitement demandé. Une préférence d'actif reste un critère
de comparaison des modèles, pas une autorisation d'ajouter un poids. Les expressions
conditionnelles, doubles négations et contradictions ne sont pas traduites en
achats ou en scores. L'alias contrôlé Ethereum est résolu vers la ligne crypto
`ETH-USD` seulement si elle existe dans le catalogue ; les symboles inconnus ne
sont jamais substitués.

## Comparaison des profils

La bande de risque reste celle de `domain/profile_mapping.py`, avec les éventuelles
évaluations explicites de l'API identifiées séparément. Le style automatiquement
déduit devient un départage et cesse d'éliminer les autres modèles avant comparaison.
Un style explicitement imposé par `assessment.preferred_style` reste une contrainte.

Après les exclusions, autorisations crypto et plafonds, chaque modèle admissible
reçoit un score déterministe :

`poids dans les classes souhaitées + poids dans les secteurs documentés souhaités + poids dans les actifs explicitement préférés`.

Les égalités sont départagées par le style préféré, la couverture sectorielle
connue, la diversification générale puis l'identifiant. Les composantes, tous les
candidats admissibles, les rejets et les préférences non couvertes sont audités.
Le maximum est celui de cet objectif parmi les modèles de référence disponibles ;
ce n'est pas un optimum de tous les portefeuilles possibles ni une garantie
d'adéquation. Les poids subissent ensuite les simulations, contraintes et contrôles
de libération déjà présents. Le contrat historique sans connaissances conserve
son rapprochement sectoriel par actions directes.

## Modèle de langage et contrôles

L'agent applique les règles déterministes même hors ligne. Une revue sémantique
complémentaire peut utiliser le port LLM existant une seule fois, sous réserve du
budget. Sa sortie doit citer un extrait exact d'un champ réellement reçu. Elle
reste consultative : une interprétation non établie par les règles demande
confirmation et ne modifie pas les scores, les poids ou les contraintes. Les
réponses incorrectes, tronquées, non sourcées et l'indisponibilité du modèle sont
auditées, avec maintien de l'interprétation déterministe.

Le contrôle de libération reconstruit l'interprétation déterministe à partir des
réponses originales et du catalogue ; il vérifie l'empreinte, la couverture, les
préférences, les contradictions et la transmission des exclusions. L'explication
publique présente les recouvrements et les limites, sans publier les notes privées
dans un catalogue de preuves ni transformer un recouvrement en taux de réussite.

## Vérification et handoff

Propriétaire : questionnaire/intégration ; appui screening, portfolio, evidence,
explication et compliance. Entrées : formulaire Word v5 réel et contrats historiques,
tables de scores fournies, profils et catalogue capturés. Sorties : agent de
compréhension, règles pures, classement, audit, explication et tests de couverture.
Les tâches de trois sous-agents ont fourni des recommandations de conception ;
leurs sessions ne disposaient pas d'outils exécutables. L'implémentation et les
contrôles du dépôt ont été réalisés dans la session principale, sans revue
indépendante revendiquée.

Les régressions couvrent chaque choix du module frontend réel, les 1 280
combinaisons des cinq signaux de risque, tous les champs complémentaires ensemble,
les contradictions, les préférences textuelles, les exclusions, l'intégrité de
l'audit et les sorties LLM invalides. Les contrôles connectés passent par le vrai
proxy, le handler Python, les CSV et l'audit disque ; aucun déploiement ni appel
AWS/LLM réel n'est impliqué. Voir les commandes et résultats dans la leçon L-039.
