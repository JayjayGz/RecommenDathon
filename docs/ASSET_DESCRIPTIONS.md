# Descriptions des actifs pour l’agent

`dataset/asset_descriptions.csv` contient une fiche pour chacune des 132 entrées actuelles de `dataset/assets_universe.csv`, dans le même ordre. Jointure : `ticker` ; `asset_id`, `name` et `asset_class` sont repris du fichier de référence, sans modifier ce dernier. Le fichier est en CSV séparé par des virgules, UTF-8 avec BOM pour les accents dans Excel.

Chaque description comporte deux phrases et au plus 37 mots. Les colonnes sont `asset_id`, `ticker`, `name`, `asset_class`, `pays_ou_zone_visee`, `description_fr` et `date_consultation`.

La géographie désigne les marchés servis pour une entreprise, l’exposition recherchée pour un fonds ou un indice, et les monnaies comparées pour une paire de change. Elle ne correspond pas nécessairement au lieu de cotation, à la domiciliation ou à une répartition chiffrée des revenus. Les réseaux crypto sont internationaux. Les séries de taux sont explicitement distinguées des prix et produits achetables ; les indices ne sont pas présentés comme des actions. Le VIX est décrit parce qu’il figure dans l’univers, sans modifier son exclusion du fichier de prix.

Les sources consultées le 15 novembre 2026 sont les pages et rapports des entreprises, les fiches et prospectus des émetteurs de FNB, la documentation des réseaux crypto, CME Group, les fournisseurs d’indices, la BCE, la Banque du Canada et FRED. Chaque ligne possède son URL. Certains noms de l’univers peuvent différer d’un nouveau nom commercial chez l’émetteur ; les identifiants fournis sont conservés. La date de consultation n’est pas une garantie que les faits resteront inchangés.

Pour l’agent : utiliser ces fiches pour expliquer la nature, l’activité et l’exposition d’un actif. Elles ne contiennent ni rendement attendu, ni score d’adéquation, ni raison calculée de sélection. Le lien avec les objectifs du client et la justification des pondérations doivent provenir du profil et des preuves de calcul du portefeuille. Ne pas transformer une exposition qualitative en contrainte géographique chiffrée. Le fichier n’est pas encore raccordé automatiquement à un agent ou à une route d’API.

## Reproduction et contrôles

`python scripts/build_asset_descriptions.py` reconstruit le CSV depuis les descriptions et références documentées dans le script. Il refuse un symbole manquant, supplémentaire ou dupliqué, une description dépassant trois phrases ou 65 mots, un champ vide ou une URL de source mal formée. Il vérifie aussi le rechargement exact du CSV et l’absence de modification de l’univers.

Résultat réel : 132 lignes, 132 symboles uniques, aucun manquant, aucun champ vide ; maximum deux phrases et 37 mots. Les contrôles déterministes portent sur la couverture et le format, pas sur une certification indépendante des affirmations des émetteurs.

- Univers source SHA-256 : `1ecd0fb4b82f67bdaf4a4e0d1b055c12f10fc2299100d49e3ee2497c14d5f726`.
- CSV descriptif SHA-256 : `762b4993904b65683347e1847c94ac92f075866f4a086827c3198c4e5c4394c5`.

Transmission : données, propriétaire principal, création du CSV à partir de l’univers et des sources, statut complete ; evidence, support, URLs, date et empreintes, statut complete. Prochain propriétaire : intégration de l’agent pour joindre les fiches par ticker et associer les explications aux preuves du portefeuille. Aucun prix, classement de risque, allocation, résultat financier ou déploiement modifié.
