# Vue Geographie du portefeuille

## Source et methode

La troisieme vue, a cote de Par actif et Par categorie, utilise uniquement les repartitions numeriques de repartition_geographique dans dataset/exposures_profile_tickers.csv. Pour chaque position, sa contribution a une zone est : poids du titre en pourcentage du portefeuille multiplie par pourcentage de cette zone dans le CSV, divise par 100. Les contributions sont additionnees par zone, sans modifier les poids du portefeuille.

Le champ pays_ou_zone_visee reste un contexte qualitatif dans le detail. Il ne sert pas a inventer des pourcentages. base_repartition_geographique, date_repartition_geographique et limites_repartitions sont presentes dans le detail de la zone. Les informations d'un domicile social ou de l'objectif d'un fonds ne deviennent pas des mesures de revenus ou d'activites par pays.

Les valeurs Aucun pays sont placees dans Sans pays unique, hors des polygones de pays : or, crypto et devises ne sont pas attribues artificiellement a un pays. Une serie Sans objet pour une allocation reste Non applicable. Une information absente, non numerique, invalide ou ne totalisant pas 100 pour cent devient Non renseigne. Les positions concernees restent dans le total. Les pays omis des contours simplifi?s restent consultables dans la liste si leur ventilation est fournie.

Le CSV de demonstration produit Canada 60 %, Etats-Unis 30 %, Sans pays unique 10 %. Ce resultat depend des six poids de demonstration existants ; aucune allocation nouvelle n'est proposee. Les pourcentages ne sont pas des rendements et la surface des pays n'est pas une mesure de leurs poids.

## Carte et interactions

La carte est construite a partir des 177 entites Natural Earth 110m, avec 176 contours affiches apres omission de l'Antarctique. Projection equirectangulaire, formes et positions des etiquettes issues du fichier geographique ; aucune frontiere dessinee de memoire. Les pays renseignes sont selectionnables au clic ou par Entree/Espace ; les lignes donnent egalement acces aux zones hors carte. La selection affiche les titres contributeurs, leurs poids et les bases de mesure. Zoom, retour Monde et vue Agrandir restent locaux et ne declenchent aucune transaction ou envoi a l'agent.

Donnees cartographiques : https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson . Licence domaine public : https://www.naturalearthdata.com/about/terms-of-use/ . Le fichier brut reste dans assets/world-countries.geojson et la generation reproductible dans scripts/build_world_map.py produit src/world-map.js. Le serveur ne publie pas directement les CSV financiers.

## Transport et handoff

GET /api/asset-categories conserve categories/source/sha256 et ajoute geographies (expositions chiffre?es, zone visee, base, date et limites par symbole). La lecture reste cote serveur. Le navigateur signale l'absence de ce nouveau champ au lieu de supposer une ventilation. Le serveur deja ouvert doit etre redemarre pour charger cette route et son lecteur actualises. Aucun dataset existant, calcul de portefeuille Python ou allocation n'est modifie.

Proprietaire principal : Router presentation/integration. Appuis : data (lecture des champs et distinction quantifie/qualitatif), infrastructure (extension du lecteur/transport), evidence (source cartographique, empreintes, limites). Sorties : geography.js, geography.css, app.js, world-map.js, lecteur CSV, index.html, tests et documentation. Statut complete pour implementation et controles locaux ; prochain proprietaire : utilisateur pour redemarrage du serveur et previsualisation avec donnees.

## Verifications

node --test --test-isolation=none plateforme/tests/*.test.mjs : 45 tests passent. Les cas couvrent les 82 symboles du vrai CSV, le domicile NVDA different de sa zone Monde, la demonstration 60/30/10, un fonds synthetique multi-pays, les valeurs invalides et manquantes, le clic/clavier, le zoom, la vue Agrandir et le retour aux autres vues. Les fixtures de fonds multi-pays sont synthetiques, pas des informations de marche.

Un premier controle DOM a detecte une declaration de fonction erronee avec un signe + initial ; la declaration a ete corrigee et le parcours rejoue. L'extension Agrandir a ensuite revele une assertion qui cherchait aussi dans une boite de dialogue fermee ; elle controle maintenant la carte visible dans le panneau principal. Les deux parcours passent avec leurs cas valides voisins.

Chrome a affiche le nouvel onglet, le fond cartographique, les controles et les lignes de detail. Son ancien serveur ne fournissant pas encore les donnees, cette capture verifie seulement le rendu de l'etat indisponible ; les ventilations et interactions avec donnees sont verifiees dans les tests DOM et HTTP. Aucune verification visuelle mobile ou nouvelle capture de la vue Agrandir n'est revendiquee. Aucun appel agent reel, commit, push ou deploiement.

CSV SHA-256 : 12f605c26e31cb6ecdbaedc0fc3fbdca02f2f145db1b56893678481055bf0dcb
Natural Earth SHA-256 : 6866c877d39cba9c357620878839b336d569f8c662d3cfab4cb1dbe2d39c977f

Un cas supplementaire verifie qu’un ancien endpoint fournissant seulement les categories declenche aussi l’avertissement geographique, plutot que d’afficher des donnees supposees completes.
