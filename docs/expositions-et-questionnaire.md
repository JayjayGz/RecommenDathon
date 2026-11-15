# Correspondance du questionnaire et analyse des expositions

Le questionnaire actuel du site (`questionnaire-word-16-v4`) et le formulaire
français normalisent désormais les connaissances avec la tolérance, la réaction
aux pertes, l’horizon et la stabilité des revenus. `domain/profile_mapping.py`
fournit les scores et le style : minimum des trois signaux de tolérance, minimum
des deux signaux de capacité, puis minimum des deux résultats. Le classement de
référence porte la méthode `capacity_tolerance_style_v1` dans l’audit. Ce score
fourni par le projet n’est pas présenté comme une validation financière complète.

Les évaluations explicites restent des dérogations identifiées dans les preuves.
Les signaux ESG et de préférence nationale ne sont pas inventés à partir du
texte libre. L’ancien format à huit réponses ne contenant pas les connaissances
conserve son mapping historique ; il peut transmettre ce champ complémentaire
pour utiliser le nouveau module. Le backend accepte également le contrat Word
v2 historique ; les réponses retirées du formulaire v4 restent interdites en v4.

L’analyse investisseur charge obligatoirement `dataset/exposures_profile_tickers.csv`
par le port de stockage, en local ou depuis le préfixe S3 existant. Le manifeste
conserve l’empreinte des octets et, pour S3, la version de l’objet lorsqu’elle est
disponible. Un catalogue absent, dupliqué ou mal formé empêche cette analyse ; les
actifs absents du catalogue restent explicitement sans répartition connue.

`weighted_catalog_exposures_v1` pondère les répartitions par les poids évalués.
Les secteurs GICS et les catégories obligataires restent séparés. Les données
géographiques restent regroupées par leur base exacte : domicile de l’entreprise,
domicile des sociétés d’un indice et objectif d’un fonds ne sont pas assimilés à
une répartition des revenus. Les compositions par classes d’actifs conservent
également leur base. La date d’observation et la date de consultation doivent
toutes deux précéder ou égaler la date d’analyse. Ces métadonnées servent à
décrire le portefeuille à cette date ; elles ne sont pas réinjectées dans les
rendements historiques ni utilisées comme prévision.

Une répartition manquante reste inconnue. Une somme publiée inférieure à 100 %
laisse le reliquat inconnu. Un dépassement d’arrondi jusqu’à 0,1 point est ramené
proportionnellement à 100 % pour l’agrégation, en conservant les pourcentages
sources et l’indicateur de correction dans l’audit. Un dépassement supérieur
est refusé. Les données CSV sources ne sont pas modifiées.

L’analyse fournit les expositions mesurées, leur couverture et des pistes
qualitatives fondées sur les secteurs choisis, les descriptions et les actifs
admis par le jeu de données. Au plus trois pistes d’actions non détenues sont
classées d’abord par l’exposition sectorielle actuellement mesurée, puis par
ticker. Elles restent `to_study`, sans poids ni simulation ni application. Elles
ne démontrent ni l’absence de chevauchement avec les fonds ni un rendement futur.

Les alternatives chiffrées continuent d’utiliser la recherche bornée existante
et le moteur de risque. Les expositions ajoutent deux motifs de rejet : diminution
de la couverture sectorielle connue ou diminution du poids mesuré dans les
secteurs choisis. Elles ne remplacent aucune limite de risque existante. Le
contrôle de sortie reconstruit les expositions, les rejets et les alternatives ;
le résumé français et les données structurées partagent les mêmes faits vérifiés.
La confirmation explicite reste nécessaire pour retenir une modification.

Responsabilité principale : portefeuille ; appui : données, sélection, preuves,
explication, infrastructure et conformité. Entrées : questionnaire normalisé,
profils fournis, métadonnées, catalogue daté et résultats du moteur. Sorties :
analyse structurée, résumé français, preuves et régressions. Prochain propriétaire :
intégration de l’application. Aucun déploiement n’est impliqué par ces changements.
