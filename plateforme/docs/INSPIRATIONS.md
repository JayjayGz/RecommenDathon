# Références de design et d’expérience utilisateur

Recherche initiale effectuée le 14 novembre 2026, complétée le 15 novembre pour les photographies financières du questionnaire. Ces références servent à orienter la conception de Recommand. Elles ne constituent ni un partenariat avec les marques citées ni une validation de notre prototype.

## Direction visuelle

La direction retenue s’inspire de l’univers éditorial de Wealthsimple : couleurs crème et pierre, texte sombre, grands titres, espaces généreux et présentation calme des données. Les photographies d’architecture de la première version sont remplacées dans le questionnaire par des sujets financiers, détaillés plus bas. Le nom, les textes, les composants et les éléments graphiques de Recommand sont propres au projet. Aucun logo de banque n’est repris.

- [Wealthsimple en français](https://www.wealthsimple.com/fr-ca) : hiérarchie éditoriale, actions principales visibles et présentation progressive des produits.
- [Wealthsimple Classic Portfolio](https://www.wealthsimple.com/en-ca/invest/classic-portfolios) : aperçu du portefeuille, diversification, niveau de risque et détails accessibles séparément.
- [RBC InvestEase — How it works](https://www.rbcinvestease.com/how-it-works.html) : parcours explicite depuis le questionnaire jusqu’à la proposition de portefeuille et au suivi. Recommand reprend la logique du parcours, sans ouverture de compte ni transactions.

## Indices et retours d’usage

L’étude **J.D. Power 2025 Canada Wealth Management Digital Experience Study** place Wealthsimple en tête de la satisfaction numérique dans la catégorie de placement autonome avec **709 points sur 1 000**, devant CIBC Investor’s Edge (665) et RBC Direct Investing (659). TD arrive en tête de la catégorie avec conseil (689). L’étude repose sur 4 686 investisseurs, interrogés de juin à août 2025, et évalue le design, l’information, les performances du système et les outils. Il s’agit d’un indice de satisfaction de ces services, **pas d’un score UX attribué à Recommand**. Les résultats 2025 ne sont pas directement comparables aux éditions antérieures, car l’étude a été remaniée.

Source primaire : [communiqué J.D. Power](https://www.jdpower.com/business/press-releases/2025-canada-wealth-management-digital-experience-study/).

La [revue Wealthsimple de StockBrokers.com du 4 mai 2026](https://www.stockbrokers.com/ca/review/wealthsimple) attribue 5/5 à la facilité d’utilisation, souligne la simplicité de navigation et constate des limites en matière d’outils de recherche avancés. Cette appréciation est celle de l’éditeur de la revue, pas une mesure universelle de l’utilisabilité. Elle soutient le choix d’une interface centrée sur la tâche du client plutôt qu’un écran de courtage surchargé.

Le [guide Progressive Disclosure de Nielsen Norman Group](https://www.nngroup.com/articles/progressive-disclosure/) explique l’intérêt de présenter d’abord les fonctions essentielles et de rendre les détails secondaires accessibles à la demande. Il distingue également le parcours par étapes, pertinent lorsque les étapes sont suffisamment indépendantes.

## Traduction dans Recommand

- Commencer par le questionnaire fourni, sans ajouter de questions issues des sites étudiés.
- Présenter une question à la fois, avec progression lisible, possibilité de revenir et conservation locale de l’avancement.
- Donner un nom et une répartition compréhensible au portefeuille, avant les détails par titre.
- Afficher les pourcentages et une visualisation de l’allocation côte à côte.
- Garder la discussion avec le futur agent proche du portefeuille pour faciliter l’itération.
- Identifier clairement les données de démonstration et l’absence de connexion à un agent tant que votre équipe ne l’a pas branché.
- Préserver une navigation cohérente sur ordinateur et téléphone, les libellés explicites et les commandes accessibles au clavier.

Ces choix constituent une interprétation de conception. Aucun test utilisateur externe ni classement UX du prototype n’a été réalisé.

## Photographies du questionnaire — révision du 15 novembre 2026

Les pages [Placements de Wealthsimple](https://www.wealthsimple.com/fr-ca/invest), [How it works de RBC InvestEase](https://www.rbcinvestease.com/how-it-works.html) et [Betterment](https://www.betterment.com/) ont été consultées pour cette révision. RBC relie explicitement le parcours au risque et à l'horizon ; Betterment accompagne ses produits de visuels de comptes et de placements ; Wealthsimple présente ses portefeuilles et leurs objectifs. Notre interprétation : illustrer le sujet précis de chaque question, avec une photographie financière et une légende descriptive. Aucun logo, visuel propriétaire ni capture de compte de ces concurrents n'est réutilisé.

Le visuel dépend de l'identifiant de la question, pas de sa section ni de la réponse choisie. Une sélection ne change donc pas la photo et n'oriente pas son message selon le choix de l'utilisateur. Les courbes et montants photographiés ne sont pas des données utilisées par Recommand : le panneau indique « Photographie d'illustration ».

| Question | Fichier local | Sujet et auteur | Source |
| --- | --- | --- | --- |
| Tolérance au risque | `assets/risk-markets.jpg` | Courbe de marché avec variations — Markus Winkler | [Unsplash](https://unsplash.com/photos/stock-market-chart-displayed-on-laptop-screen-IrRbSND5EUc) |
| Réaction à une baisse | `assets/reaction-volatility.jpg` | Écrans d'analyse avec baisse des cours — Jakub Żerdzicki | [Unsplash](https://unsplash.com/photos/stock-charts-are-displayed-on-multiple-screens-VM_6EtTAfDQ) |
| Rendement souhaité | `assets/return-savings.jpg` | Piles de pièces — Markus Kammermann | [Unsplash](https://unsplash.com/photos/stacks-of-silver-coins-in-a-row-NxBUw0TXpBo) |
| Horizon de placement | `assets/horizon-time.jpg` | Montre et pièces — Mateusz Matusiak | [Unsplash](https://unsplash.com/photos/a-clock-and-some-coins-noPuwoAOkmQ) |
| Revenus prévisibles | `assets/income-budget.jpg` | Calculatrice et enveloppes de budget — Cht Gsml | [Unsplash](https://unsplash.com/photos/calculator-and-notepad-with-pencil-on-white-surface-8IXVKMfCGOo) |
| Secteurs | `assets/sectors-economy.jpg` | Transport et conteneurs, activité économique — Bernd Dittrich | [Unsplash](https://unsplash.com/photos/a-truck-is-parked-in-front-of-a-bunch-of-shipping-containers-Xk1IfNnEhRA) |
| Classes d'actifs | `assets/assets-investing.jpg` | Étude de graphiques et placements — Jakub Żerdzicki | [Unsplash](https://unsplash.com/photos/a-person-sitting-at-a-desk-with-a-calculator-and-a-notebook-LNnmSumlwO4) |
| Exclusions | `assets/preferences-plan.jpg` | Carnet et calculatrice, choix à préciser — Cht Gsml | [Unsplash](https://unsplash.com/photos/desk-with-calculator-notebook-pencil-and-plant-QfQW294I8sQ) |

Les huit pages indiquent la licence Unsplash gratuite (pas Unsplash+). La [licence](https://unsplash.com/license) autorise leur téléchargement et leur utilisation, y compris commerciale. Les fichiers téléchargés sont des JPEG de 1200 pixels de large ; le cadrage d'affichage utilise `object-fit` et `object-position`, sans modifier les fichiers sources. Les huit photos ont été ouvertes et inspectées avant intégration. Leur poids total est d'environ 1,05 Mo. La première image est préchargée dans `index.html` ; la suivante est préchargée pendant le questionnaire. Les polices et photos restent locales pendant le parcours.

## Anciennes photographies conservées, retirées du questionnaire

Les photographies sont conservées localement dans `assets/` afin que leur affichage ne dépende pas d’Internet.

| Fichier | Auteur et photographie | Source |
| --- | --- | --- |
| `assets/architecture.jpg` | Mateusz Bakala, façade géométrique et ombres à Barcelone | [Unsplash](https://unsplash.com/photos/modern-building-with-geometric-shapes-and-shadows-Q4Y8MP_4EGk) |
| `assets/curves.jpg` | Ramiro Pianarosa, façade à balcons courbes | [Unsplash](https://unsplash.com/photos/a-building-with-a-blue-sky-3-lP8tVn4XE) |
| `assets/water.jpg` | Max Anderson, eau calme à Whidbey Island | [Unsplash](https://unsplash.com/photos/calm-body-of-water-o8Z7OTpgDYs) |

Les trois pages sources indiquent un usage sous [licence Unsplash](https://unsplash.com/license), autorisant le téléchargement et l’utilisation gratuite, y compris commerciale. Le crédit est conservé ici par courtoisie et pour la traçabilité.

## Polices locales

Les fichiers WOFF2 proviennent de Google Fonts et sont conservés dans `assets/fonts/`. DM Sans est variable de 400 à 700. Instrument Serif est fourni en romain et en italique. Les sous-ensembles latins incluent les accents français et la ligature œ. Les licences SIL Open Font License accompagnent les fichiers.

- [DM Sans — Google Fonts](https://fonts.google.com/specimen/DM+Sans), [licence source](https://github.com/google/fonts/blob/main/ofl/dmsans/OFL.txt).
- [Instrument Serif — Google Fonts](https://fonts.google.com/specimen/Instrument+Serif), [licence source](https://github.com/google/fonts/blob/main/ofl/instrumentserif/OFL.txt).
