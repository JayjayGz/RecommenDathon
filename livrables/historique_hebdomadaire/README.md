# Dernier cours hebdomadaire

Fichier courant : `top100_hebdo_2016_complet.csv`. Les deux copies ouvertes dans Téléchargements sont également mises à jour : **123 actifs, dont les 34 sélectionnés ; 68 804 cours `close` renseignés**. Historique à partir du 1er janvier 2016 selon disponibilité ; dernier vendredi : 13 novembre 2026.

SHA-256 : `16b0fb689b06656b1f61c718d869a8f62135402c4a6103d085d52484f38257e4`.

## Sources et méthode

| Actifs | Dernier cours utilisé |
| --- | --- |
| Actions, FNB et indices de clôture | Dernier `close` de séance quotidienne Yahoo dans la semaine finissant le vendredi ; dernière séance disponible si le vendredi est fermé. Nikkei : séance de Tokyo. |
| Cryptoactifs USD | `close` publié par l'API officielle de Bitstamp pour la bougie horaire se terminant le vendredi à 16 h, heure de Toronto, avec changement d'heure. |
| Devises, contrats à terme et VIX | Dernier `close` quotidien fourni par Yahoo dans la semaine finissant le vendredi, selon le choix de l'utilisateur. |

Les 124 réponses Yahoo et 480 blocs horaires Bitstamp sont conservés dans `clotures_vendredi/sources_yahoo` et `clotures_vendredi/sources_bitstamp`. Leurs manifestes enregistrent URL, date de récupération et SHA-256. Aucun chiffre du fichier quotidien local dont la provenance indépendante n'a pas été établie n'est utilisé dans la nouvelle série.

Aucune moyenne, interpolation, propagation de prix ou valeur inventée. Les dix bougies crypto retenues à volume nul sont des cotations publiées par Bitstamp et copiées telles quelles. Une bougie absente reste absente. Les colonnes OHLC et `volume` décrivent la séance Yahoo ou l'heure Bitstamp retenue ; elles ne constituent pas une bougie hebdomadaire. Les devises restent celles des fournisseurs, sans conversion. `adj_close` conserve les ajustements Yahoo ; ce champ est vide pour les cryptos, car Bitstamp ne le fournit pas.

## Contrôles et limites réelles

`clotures_vendredi/verification.json` enregistre **413 698 champs numériques comparés exactement aux réponses brutes**, sur 69 371 lignes. Les clés actif/date sont uniques, les dates sont des vendredis sans libellé futur au 15 novembre 2026. Les trois CSV publiés et leurs sauvegardes ont des empreintes vérifiées. Les huit tests de `scripts/test_rebuild_weekly_friday.py` passent : dernier cours plutôt que moyenne, frontière du vendredi, historique absent, heures été/hiver, cotation source à volume nul, validation OHLC et empreinte de source modifiée.

90 lignes non actions/FNB présentent des bornes OHLC Yahoo incohérentes avec `open` ou `close`. Les chiffres du fournisseur sont conservés sans correction arbitraire et les lignes sont identifiées dans le manifeste et l'audit. La validation habituelle des bornes reste stricte pour les actions/FNB. Les contrôles sont déterministes ; ils ne constituent pas une certification indépendante des cours.

La couverture détaillée est dans `clotures_vendredi/top100_hebdo_2016_couverture.csv`. Certaines séries commencent après 2016 : les premières observations crypto Bitstamp vont de janvier 2016 à décembre 2017 ; certains FNB commencent en 2018 ou 2019. Aucun historique antérieur n'est inventé. Les cours restent propres au fournisseur et à son marché. Tout calcul de rendement ou backtest dépendant de l'ancien fichier doit être recalculé et traiter explicitement les champs absents.

Les moyennes antérieures sont conservées dans les fichiers `.moyennes_a977af97.csv`, avec `README_moyennes_avant_correction.md` et `top100_hebdo_2016_manifest.moyennes_a977af97.json`.

## Reproduction et transmission

Scripts : `download_friday_sources.py` (`--all-symbols`), `download_crypto_hourly.py`, `rebuild_weekly_friday.py` (`--unavailable official-close`, sauvegarde des moyennes comme `--previous`), `check_friday_history.py`, puis `publish_friday_history.py`. Ils sont dans `scripts/`. La publication refuse de remplacer une copie modifiée depuis la vérification de son empreinte.

| Rôle | Tâche et entrées | Sorties et contrôles | Statut ; prochain propriétaire |
| --- | --- | --- | --- |
| Données, principal | Derniers cours ; univers 124 actifs, sélection 34, réponses Yahoo/Bitstamp | CSV, couverture, audit ; 8 tests et vérification exacte des valeurs renseignées | complete ; propriétaire des rendements/backtests |
| Infrastructure, support | Téléchargements publics, anciennes empreintes et copies autorisées | Réponses brutes, sauvegardes et trois CSV identiques vérifiés | complete ; utilisateur pour récupérer le CSV |
| Evidence, support | Méthodes, sources, heures, ajustements, anomalies et limites | Manifestes, audit par ligne, `verification.json`, leçons L-007 et L-008 | complete ; propriétaire des calculs pour propager les limites |

Au démarrage, rôles data/infrastructure/evidence chargés et leçons L-001 à L-006 examinées selon leur déclencheur ; aucun déclencheur n'était applicable au recalcul. Les nouvelles leçons L-007 et L-008 enregistrent la correction et les vérifications réellement exécutées. Aucune revue indépendante, simulation, opération AWS, modification de l'interface, commit, push ou déploiement dans cette tâche.

Retrait demandé du VIX : 567 lignes supprimées des exports courants ; toutes les autres lignes sont conservées octet pour octet. Les vérifications précédentes sont archivées dans `avant_retrait_vix/`. Aucun autre filtre ni recalcul des cours.

Compl?ment de l?univers : `C:/Users/alibe/Downloads/price_weekly_compelt.csv` est la copie utilisateur courante. Ajout de CNQ.TO, MFC.TO, XBB.TO et XIU.TO depuis les r?ponses Yahoo brutes conserv?es dans `complement_univers/`. 2 268 lignes ajout?es ; toutes les lignes ant?rieures sont conserv?es octet pour octet. Les 34 actifs s?lectionn?s sont dans les 132 entr?es de l?univers ; les 127 entr?es exigeant un prix sont dans le CSV. Les 5 autres sont le VIX exclu et 4 s?ries de taux `bond_yield`, conserv?es dans l?univers sans ?tre pr?sent?es comme des prix. R?les data/infrastructure/evidence : complete pour les cours ; prochaine responsabilit? utilisateur pour la s?paration ?ventuelle des s?ries de taux. M?thodes et empreintes dans `complement_univers/manifest.json`.
