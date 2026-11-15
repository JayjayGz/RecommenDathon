# Complément des historiques hebdomadaires

Demande : ajouter les actifs de `asset_selection.csv` absents de `top100_hebdo_2016 (2).csv`, avec les moyennes hebdomadaires à partir du 1er janvier 2016. Date limite des nouveaux calculs : 15 novembre 2026 ; dernier vendredi couvert pour les ajouts : 13 novembre 2026.

## Résultat vérifié

- Sélection : 34 symboles distincts. Avant ajout : 9 présents, 25 absents.
- Fichier initial : 55 859 lignes, 99 symboles distincts.
- Ajouts : 13 541 lignes hebdomadaires pour les 25 symboles manquants.
- Fichier complété : 69 400 lignes, 124 symboles distincts ; les 34 sélectionnés sont présents.
- Les octets d'origine sont conservés en préfixe du résultat. Aucun recalcul des anciens actifs ; les nouvelles séries sont ajoutées en fin de fichier, triées entre elles par symbole et date.

## Données et méthode

L'historique quotidien fourni dans le dépôt, `historique_actifs_2011.csv`, contient déjà tous les symboles recherchés. Aucun téléchargement de cours n'a été effectué. Sa provenance de marché n'a pas été vérifiée indépendamment : le manifeste identifie précisément le fichier local et son empreinte.

Pour chaque actif manquant, les observations quotidiennes du 1er janvier 2016 au 15 novembre 2026 sont groupées du samedi au vendredi et datées du vendredi (`W-FRI`, fermeture et libellé à droite). On calcule la moyenne arithmétique des valeurs observées de chaque colonne `open`, `high`, `low`, `close`, `adj_close` et `volume`, arrondie à quatre décimales. Le volume représente donc un volume quotidien moyen, pas un volume hebdomadaire total. Les colonnes OHLC sont des moyennes quotidiennes, pas les premières/maximales/minimales/dernières cotations d'une bougie hebdomadaire traditionnelle.

Les périodes sans observation restent absentes. Aucun remplissage, interpolation, conversion de devise ou nouvel ajustement de fractionnement/dividende. Les semaines étiquetées après la date limite ne sont pas ajoutées. Les moyennes du cours ajusté sont conservées pour les traitements qui en ont besoin ; ce ne sont pas des prix d'exécution.

La méthode reproduit la convention des séries existantes MSFT, QQQ et GLD sur 567 semaines chacune. Les volumes correspondent exactement ; les prix diffèrent au plus de 0,0001, à la précision du fichier source. Détail dans `top100_hebdo_2016_manifest.json`. La sémantique de regroupement est documentée dans la [documentation pandas de resample](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.resample.html).

## Limites constatées

| Actif ajouté | Première observation quotidienne disponible |
| --- | --- |
| VCNS.TO | 1er février 2018 |
| VBAL.TO | 1er février 2018 |
| VGRO.TO | 1er février 2018 |
| ESGV | 20 septembre 2018 |
| XESG.TO | 4 avril 2019 |

Leur historique antérieur n'est pas inventé. Les autres 20 ajouts commencent dans la première semaine de cotation de 2016. Le tableau de couverture donne toutes les bornes et les décomptes. Les 106 observations quotidiennes à volume zéro sont conservées et dénombrées ; aucun prix invalide, infini, manquant ou hors bornes OHLC n'a été constaté dans les 65 145 observations sources des ajouts.

Huit lignes du fichier d'origine sont étiquetées au 20 novembre 2026 (devises et cryptoactifs). Elles sont préservées à l'identique ; ce libellé peut désigner une semaine en cours et ne prouve pas une série finale connue au 15 novembre. Elles doivent être traitées comme une limite de la source, sans supposer des données futures disponibles en backtest. Aucun des ajouts n'a de libellé futur.

## Contrôles et transmission

Commandes exécutées : `python scripts/test_extend_weekly_history.py` (4 tests réussis) et `python scripts/extend_weekly_history.py` avec les trois fichiers locaux, `--start 2016-01-01 --as-of 2026-11-15`. Les contrôles sur fichiers réels vérifient la présence des 34 actifs, la conservation des lignes et octets existants, les devises, l'unicité symbole/date, les prix et les bornes de dates. Les empreintes SHA-256 des entrées et sorties sont dans le manifeste. Les tests utilisent aussi des moyennes calculables à la main, la frontière du vendredi, un début d'historique tardif, des semaines absentes et des observations invalides rejetées.

| Rôle | Tâche et sorties | Contrôles | Statut et prochain propriétaire |
| --- | --- | --- | --- |
| Données principal | Moyennes hebdomadaires et CSV complété depuis les fichiers locaux ; aucune histoire pré-2016 ou antérieure aux observations disponibles | 4 tests, données réelles, couverture des 34 symboles | complete ; propriétaire des calculs/backtests pour l'usage |
| Infrastructure | Script reproductible, sauvegarde originale et publication du fichier vérifié | Comparaison des empreintes avant écriture et après copie ; remplacement atomique | complete après publication ; utilisateur pour récupérer le CSV |
| Evidence | Manifeste, source locale et limites réelles | Lecture des fichiers et contrôles déterministes, pas de revue indépendante | complete ; propriétaire des calculs pour propager les limites |

Aucun backtest, simulation financière, appel AWS, commit, push ou déploiement effectué. Pour reproduire l'ajout après remplacement du fichier demandé, utiliser comme entrée hebdomadaire la sauvegarde `avant_ajouts` indiquée dans le manifeste.
