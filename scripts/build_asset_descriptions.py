"""Build concise French reference descriptions from reviewed public sources.

No LLM calls, investment scoring, pricing edits or inferred eligibility. This
script publishes only a companion CSV, joined to the supplied universe by ticker.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / 'dataset/assets_universe.csv'
OUTPUT = ROOT / 'dataset/asset_descriptions.csv'
REVIEW_DATE = '2026-11-15'

# Company sources: official corporate pages or issuer reports consulted during
# preparation. No current prices, forecasts, rankings or revenue shares are used.
SOURCES = {
 'rbc':'https://www.rbc.com/our-company/',
 'td':'https://www.td.com/ca/en/about-td/corporate-profile/corporate-information',
 'mfc':'https://www.manulife.com/ca/en/about-us/markets',
 'enb':'https://www.enbridge.com/about-us',
 'cnq':'https://www.cnrl.com/about-us/who-we-are/',
 'cnr':'https://www.cn.ca/en/about-cn/',
 'fts':'https://www.fortisinc.com/company/about-fortis/index',
 'atd':'https://corporate.couche-tard.com/where-we-operate',
 'shop':'https://www.shopify.com/about',
 'csu':'https://www.csisoftware.com/acquisition-criteria/',
 'aapl':'https://www.apple.com/',
 'msft':'https://www.microsoft.com/en-us/about',
 'nvda':'https://www.nvidia.com/content/dam/en-zz/Solutions/about-nvidia/corporate-nvidia-in-brief.pdf',
 'googl':'https://abc.xyz/investor/events/event-details/2026/2026-Q2-Earnings-Call-2026-GgTAq7Is0z/default.aspx',
 'amzn':'https://www.aboutamazon.com/what-we-do',
 'tsla':'https://www.tesla.com/manufacturing',
 'jpm':'https://www.jpmorganchase.com/about',
 'jnj':'https://www.jnj.com/our-company',
 'pg':'https://us.pg.com/brands/',
 'xom':'https://corporate.exxonmobil.com/who-we-are',
 'meta':'https://investor.atmeta.com/home/default.aspx',
 'brk':'https://www.berkshirehathaway.com/2024ar/202410-k.pdf',
 'v':'https://corporate.visa.com/content/VISA/visacorporate/global/en/home/about-visa.html',
 'ma':'https://preview.mastercard.com/content/dam/mccom/shared/for-the-world/corporate-impact/pdfs/mastercard-2025-impact-report.pdf',
 'unh':'https://www.unitedhealthgroup.com/uhg/businesses.html',
 'hd':'https://corporate.homedepot.com/page/about-us',
 'cvx':'https://www.chevron.com/what-we-do/energy/oil-and-natural-gas',
 'mrk':'https://www.merck.com/media/company-fact-sheet/',
 'abbv':'https://www.abbvie.com/content/dam/abbvie-com2/pdfs/abbvie-esg-action-report.pdf',
 'ko':'https://investors.coca-colacompany.com/about',
 'pep':'https://www.pepsico.com/docs/pepsico-5v9wci20/media/Files/investors/pepsico-2025-annual-report.pdf',
 'cost':'https://www.costco.com/f/-/about',
 'wmt':'https://corporate.walmart.com/about/location-facts',
 'bac':'https://about.bankofamerica.com/content/dam/about/report-center/esg/2024/Sustainability_at_Bank_of_America_2024_Report.pdf',
 'dis':'https://thewaltdisneycompany.com/app/uploads/2025/05/2024-SSI-Report.pdf',
 'csco':'https://www.cisco.com/site/us/en/about/index.html',
 'adbe':'https://www.adobe.com/about-adobe.html',
 'crm':'https://www.salesforce.com/company/our-story/',
 'nflx':'https://about.netflix.com/en/news/new-documentaries-coming-soon-to-netflix',
 'amd':'https://www.amd.com/en/products.html',
 'intc':'https://www.intel.com/content/www/us/en/foundry/library/fact-sheet.html',
 'orcl':'https://www.oracle.com/corporate/',
 'qcom':'https://www.qualcomm.com/company',
 'ibm':'https://www.ibm.com/responsibility/governance/business-segments-innovation',
 'ba':'https://www.boeing.com/company/global-presence',
 'cat':'https://www.caterpillar.com/en/company.html',
 'gs':'https://www.goldmansachs.com/what-we-do/our-businesses/',
 'wfc':'https://www.wellsfargo.com/assets/pdf/about/investor-relations/sec-filings/2025/10k.pdf',
 't':'https://about.att.com/story/2026/att-corning-engineer-connected-world.html',
 'vz':'https://www.verizon.com/about/sites/default/files/2025-Annual-Report-on-Form-10k.pdf',
 'pfe':'https://www.pfizer.com/about/investors/why-invest/fact-sheet',
 'lly':'https://www.lilly.com/about/key-facts',
 'mcd':'https://corporate.mcdonalds.com/corpmcd/our-company/how-we-operate-internationally.html',
 'nke':'https://about.nike.com/en/company',
 'sbux':'https://about.starbucks.com/press/2026/company-profile/',
 'qqq':'https://www.invesco.com/qqq-etf/en/about.html',
 'gld':'https://www.spdrgoldshares.com/usa/gld/',
 'dbc':'https://www.invesco.com/us/en/financial-products/etfs/invesco-db-commodity-index-tracking-fund.html',
 'arkk':'https://www.ark-funds.com/funds/arkk',
 'smh':'https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/overview',
 'gdx':'https://www.vaneck.com/us/en/investments/gold-miners-etf-gdx-fact-sheet.pdf',
 'xbi':'https://www.ssga.com/library-content/products/factsheets/etfs/us/factsheet-us-en-xbi.pdf',
 'spdr_sectors':'https://www.ssga.com/us/en/individual/capabilities/equities/sector-investing/select-sector-etfs',
 'vti':'https://investor.vanguard.com/investor-resources-education/understanding-investment-types/what-are-equity-stock-funds',
 'voo':'https://investor.vanguard.com/investment-products/etfs/profile/voo',
 'vwo':'https://fund-docs.vanguard.com/FA0964_MX.pdf',
 'vnq':'https://fund-docs.vanguard.com/FA0986_MX.pdf',
 'vea':'https://fund-docs.vanguard.com/FA0936_MX.pdf',
 'bnd':'https://investor.vanguard.com/investment-products/etfs/bond-etf',
 'esgv':'https://fund-docs.vanguard.com/F4393.pdf',
 'schd':'https://www.schwabassetmanagement.com/products/schd',
 'vanguard_ca':'https://www.vanguard.ca/content/dam/intl/americas/canada/en/documents/investing-made-simple_en.pdf',
 'vanguard_ca_equity':'https://fund-docs.vanguard.com/CanadaProspEN.pdf',
 'vdy':'https://www.vanguard.ca/en/insights/dividend-etfs-true-time-tested-income-strategy-for-investors',
 'xwd':'https://www.blackrock.com/gls-download/literature/fact-sheet/xwd-ishares-msci-world-index-etf-fund-fact-sheet-en-ca.pdf',
 'zag':'https://df.bmogam.com/assets/static/etf-profiles-pdfs/BMO%20Aggregate%20Bond%20Index%20ETF_Factsheet_EN_ZAG.pdf',
 'zst':'https://df.bmogam.com/assets/static/etf-profiles-pdfs/BMO-Ultra-Short-Term-Bond-ETF-Factsheet-ZST.pdf',
 'btc':'https://bitcoin.org/en/bitcoin-for-individuals',
 'eth':'https://ethereum.org/en/what-is-ethereum/',
 'xrp':'https://xrpl.org/about',
 'ltc':'https://litecoin.org/',
 'bch':'https://bitcoincash.org/',
 'fx':'https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html',
 'cl':'https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.html',
 'ng':'https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.html',
 'gc':'https://www.cmegroup.com/markets/metals/precious/gold.html',
 'si':'https://www.cmegroup.com/markets/metals/precious/silver.html',
 'hg':'https://www.cmegroup.com/markets/metals/base/copper.html',
 'sp500':'https://www.spglobal.com/spdji/en/indices/equity/sp-500/',
 'spy':'https://www.ssga.com/library-content/products/factsheets/etfs/us/factsheet-us-en-spy.pdf',
 'dia':'https://www.ssga.com/library-content/products/factsheets/etfs/us/factsheet-us-en-dia.pdf',
 'dow':'https://www.spglobal.com/spdji/en/indices/equity/dow-jones-industrial-average/',
 'nasdaq':'https://indexes.nasdaq.com/Index/Overview/COMP',
 'vix':'https://www.cboe.com/tradable-products/vix',
 'nikkei':'https://indexes.nikkei.co.jp/en/nkave',
 'boc':'https://www.bankofcanada.ca/rates/interest-rates/canadian-bonds/',
 'dgs2':'https://fred.stlouisfed.org/series/DGS2',
 'dgs10':'https://fred.stlouisfed.org/series/DGS10',
}

for ticker, (product_id, slug) in {
 'AGG':('239458','ishares-core-total-us-bond-market-etf'),
 'TLT':('239454','ishares-20-year-treasury-bond-etf'),
 'LQD':('239566','ishares-iboxx-investment-grade-corporate-bond-etf'),
 'HYG':('239565','ishares-iboxx-high-yield-corporate-bond-etf'),
 'IEF':('239456','ishares-710-year-treasury-bond-etf'),
 'EEM':('239637','ishares-msci-emerging-markets-etf'),
 'EFA':('239623','ishares-msci-eafe-etf'),
 'IWM':('239710','ishares-russell-2000-etf'),
 'IEMG':('244050','ishares-core-msci-emerging-markets-etf'),
 'EWZ':('239612','ishares-msci-brazil-capped-etf'),
 'EWJ':('239665','ishares-msci-japan-etf'),
 'SLV':('239855','ishares-silver-trust-fund'),
 'URTH':('239696','ishares-msci-world-etf'),
 'FXI':('239536','ishares-china-largecap-etf'),
 'IVV':('239726','ishares-core-sp-500-etf'),
}.items():
    SOURCES[ticker.lower()] = f'https://www.ishares.com/us/products/{product_id}/{slug}'

for ticker in ['XIU','XBB','XEC','XEF','XESG','XIC','XIT','XRB','XSB']:
    SOURCES[ticker.lower()] = f'https://www.blackrock.com/ca/investors/en/literature/etf-summary/{ticker.lower()}-facts-en-ca.pdf'

# ticker | geographic exposure (not listing country) | max. 3 sentences | source key
CURATED = '''RY.TO|Canada, États-Unis et autres marchés internationaux|Banque canadienne offrant des services aux particuliers et aux entreprises, de la gestion de patrimoine et des activités de marchés de capitaux. Elle est présente au Canada, aux États-Unis et dans d’autres marchés internationaux.|rbc
TD.TO|Canada et États-Unis, avec activités internationales|Banque canadienne active dans les services bancaires, la gestion de patrimoine, l’assurance et les marchés de capitaux. Ses activités de détail visent surtout le Canada et les États-Unis.|td
MFC.TO|Canada, États-Unis et Asie; gestion d’actifs mondiale|Groupe canadien spécialisé dans l’assurance et la gestion de patrimoine et d’actifs. Il exerce principalement au Canada, en Asie et aux États-Unis, où il utilise notamment la marque John Hancock.|mfc
ENB.TO|Amérique du Nord; certaines activités en Europe|Entreprise d’infrastructures énergétiques exploitant des pipelines, des réseaux de distribution de gaz et des activités renouvelables. Ses réseaux desservent principalement le Canada et les États-Unis.|enb
CNQ.TO|Canada, secteur britannique de la mer du Nord et Afrique extracôtière|Producteur canadien de pétrole et de gaz naturel. Ses activités se concentrent dans l’Ouest canadien, avec une présence dans le secteur britannique de la mer du Nord et au large de l’Afrique.|cnq
CNR.TO|Canada et États-Unis|Entreprise ferroviaire canadienne transportant des matières premières, des biens industriels et des marchandises de consommation. Son réseau relie le Canada et le centre des États-Unis à des ports et à des chaînes logistiques nord-américaines.|cnr
FTS.TO|Canada, États-Unis et Caraïbes|Groupe de services publics spécialisé dans les réseaux réglementés d’électricité et de gaz. Ses entreprises desservent le Canada, les États-Unis et les Caraïbes.|fts
ATD.TO|Amérique du Nord, Europe et autres marchés internationaux|Exploitant canadien de magasins de proximité et de stations-service, notamment sous la marque Circle K. Son réseau couvre surtout l’Amérique du Nord et l’Europe, avec une présence dans d’autres marchés.|atd
SHOP.TO|Monde|Plateforme de commerce permettant aux entreprises de vendre en ligne et en magasin. Elle propose notamment des outils de boutique, de paiement et de gestion commerciale à des marchands dans différents pays.|shop
CSU.TO|Monde|Groupe canadien qui acquiert et exploite des entreprises de logiciels spécialisés pour des secteurs précis. Ses solutions servent des organisations publiques et privées dans différents marchés internationaux.|csu
AAPL|Monde|Entreprise technologique proposant notamment l’iPhone, le Mac, l’iPad et des services numériques. Elle vise les consommateurs et les organisations à l’échelle mondiale au moyen d’un écosystème de produits et de services intégrés.|aapl
MSFT|Monde|Entreprise de logiciels, de services infonuagiques et d’outils numériques pour les particuliers et les organisations. Son offre mondiale comprend notamment Windows, Microsoft 365 et les services Azure.|msft
NVDA|Monde|Concepteur de processeurs graphiques et de plateformes de calcul accéléré. Son offre vise mondialement les centres de données, l’intelligence artificielle, les jeux vidéo et d’autres usages informatiques spécialisés.|nvda
GOOGL|Monde|Société mère de Google, active notamment dans la recherche en ligne, la publicité numérique et les services infonuagiques. Ses plateformes servent des utilisateurs et des entreprises à l’échelle mondiale; le symbole correspond aux actions de catégorie A.|googl
AMZN|Monde|Groupe actif dans le commerce en ligne, la logistique et les services infonuagiques AWS. Il dessert les consommateurs et les entreprises dans plusieurs régions du monde.|amzn
TSLA|Amérique du Nord, Europe, Asie et autres marchés|Entreprise concevant des véhicules électriques et des systèmes de stockage et de production d’énergie. Elle vise les marchés internationaux du transport et de l’énergie, avec une production répartie dans plusieurs régions.|tsla
JPM|États-Unis et marchés internationaux|Groupe bancaire américain offrant des services aux particuliers, aux entreprises et aux investisseurs institutionnels. Les marques Chase et J P Morgan desservent le marché américain et une clientèle internationale.|jpm
JNJ|Monde|Groupe de santé spécialisé dans les médicaments innovants et les technologies médicales. Il développe et commercialise ses solutions auprès des professionnels de santé et des patients à l’échelle mondiale.|jnj
PG|Monde|Fabricant de produits de consommation courante pour l’hygiène, l’entretien, les soins et la famille. Ses marques, notamment Pampers, Ariel et Gillette, sont destinées à des consommateurs dans de nombreux pays.|pg
XOM|Monde|Groupe énergétique actif dans le pétrole, le gaz naturel et les produits chimiques. Ses activités relient l’approvisionnement en hydrocarbures à leur transformation en carburants et en matériaux destinés aux marchés mondiaux.|xom
META|Monde|Groupe technologique exploitant notamment Facebook, Instagram et WhatsApp. Ses plateformes visent une clientèle mondiale et relient communication, partage de contenus et publicité numérique.|meta
BRK-B|Principalement États-Unis; activités et participations internationales|Conglomérat américain actif dans l’assurance, le transport ferroviaire, l’énergie et d’autres activités. Il combine des entreprises opérationnelles, surtout aux États-Unis, et des participations cotées; ce symbole désigne ses actions de catégorie B.|brk
V|Monde|Entreprise de technologie des paiements exploitant le réseau Visa. Elle relie consommateurs, commerçants, banques et autres partenaires à l’échelle mondiale pour faciliter les paiements électroniques.|v
MA|Monde|Entreprise de technologie des paiements exploitant le réseau Mastercard et des services associés. Elle facilite les transactions électroniques entre consommateurs, commerçants et institutions financières dans différents pays.|ma
UNH|Principalement États-Unis|Groupe de santé réunissant l’assurance UnitedHealthcare et les services de santé Optum. Son activité vise principalement le système de santé américain et combine couverture médicale, soins et services spécialisés.|unh
HD|États-Unis, Canada et Mexique|Détaillant spécialisé dans les produits et services de rénovation résidentielle. Il dessert les particuliers et les professionnels aux États-Unis, au Canada et au Mexique.|hd
CVX|États-Unis et marchés internationaux|Groupe énergétique actif dans l’exploration et la production de pétrole et de gaz ainsi que dans leur transformation et leur commercialisation. Ses activités sont réparties aux États-Unis et dans plusieurs autres régions du monde.|cvx
MRK|Monde|Groupe de santé proposant des médicaments sur ordonnance, des vaccins et des produits de santé animale. Ses activités s’adressent aux marchés mondiaux de la santé humaine et animale.|mrk
ABBV|Monde|Entreprise biopharmaceutique développant des médicaments et des solutions en immunologie, oncologie, neurosciences et esthétique. Elle commercialise ses produits sur les marchés internationaux de la santé.|abbv
KO|Monde|Groupe de boissons possédant notamment Coca-Cola, Sprite et différentes marques de boissons non alcoolisées. Il dessert les marchés mondiaux au moyen de ses marques et de son système de production et de distribution.|ko
PEP|Monde|Groupe de boissons et de produits alimentaires, notamment des collations. Ses marques comme Pepsi, Gatorade, Lay’s et Quaker visent des consommateurs dans de nombreux pays.|pep
COST|États-Unis, Canada et autres marchés internationaux|Exploitant de magasins-entrepôts accessibles par adhésion. Il vend une large gamme de marchandises aux particuliers et aux entreprises, surtout en Amérique du Nord et dans plusieurs autres marchés.|cost
WMT|États-Unis et autres marchés internationaux|Groupe de distribution vendant des produits alimentaires et des marchandises en magasin et en ligne. Il combine une forte présence aux États-Unis avec des activités dans plusieurs autres pays.|wmt
BAC|Principalement États-Unis; services financiers internationaux|Banque américaine proposant des services bancaires, des crédits, de la gestion de patrimoine et des activités de marchés. Elle dessert surtout les États-Unis, tout en accompagnant des entreprises et des investisseurs internationaux.|bac
DIS|Monde|Groupe de divertissement réunissant contenus audiovisuels, sports et expériences de loisirs. Ses activités comprennent notamment les studios, Disney+, ESPN et les parcs dans plusieurs régions du monde.|dis
CSCO|Monde|Fournisseur d’équipements et de logiciels de réseau, de cybersécurité et de collaboration. Il s’adresse aux entreprises et aux organisations publiques qui construisent et exploitent des infrastructures numériques à l’échelle mondiale.|csco
ADBE|Monde|Éditeur de logiciels de création, de gestion de documents et d’expérience client. Ses outils, notamment Photoshop et Acrobat, servent des créateurs, des particuliers et des entreprises dans de nombreux pays.|adbe
CRM|Monde|Éditeur de logiciels infonuagiques de gestion de la relation client. Il aide les entreprises du monde entier à organiser leurs ventes, leur service client, leur marketing et leurs données.|crm
NFLX|Monde|Service de divertissement proposant des séries, des films et d’autres contenus en diffusion en continu. Son offre s’adresse à des abonnés dans de nombreux pays, avec des productions dans plusieurs langues.|nflx
AMD|Monde|Concepteur de processeurs, de puces graphiques et d’accélérateurs de calcul. Ses produits équipent notamment les ordinateurs, les serveurs et les infrastructures d’intelligence artificielle sur les marchés internationaux.|amd
INTC|Monde|Entreprise de semi-conducteurs concevant des processeurs et proposant des activités de fabrication de puces. Elle vise les marchés mondiaux de l’informatique et des infrastructures numériques.|intc
ORCL|Monde|Fournisseur de bases de données, d’applications d’entreprise et de services infonuagiques. Ses solutions servent des organisations de nombreux secteurs à l’échelle mondiale.|orcl
QCOM|Monde|Entreprise de technologies de communication sans fil et de semi-conducteurs. Elle associe des produits pour appareils connectés et des licences de brevets, auprès de clients internationaux.|qcom
IBM|Monde|Entreprise de logiciels, de conseil et d’infrastructures informatiques. Elle accompagne mondialement les organisations dans l’infonuagique hybride, l’intelligence artificielle et la transformation de leurs systèmes.|ibm
BA|Monde|Constructeur d’avions commerciaux et fournisseur de systèmes de défense, de services et de technologies spatiales. Il dessert des compagnies aériennes, des gouvernements et d’autres clients à l’échelle mondiale.|ba
CAT|Monde|Fabricant de machines de construction et d’exploitation minière, de moteurs et d’équipements énergétiques. Son réseau mondial dessert notamment les secteurs des infrastructures, des ressources et de l’énergie.|cat
GS|États-Unis et marchés internationaux|Groupe financier spécialisé dans la banque d’investissement, les marchés et la gestion d’actifs et de patrimoine. Il accompagne des entreprises, des institutions et des particuliers aux États-Unis et à l’international.|gs
WFC|Principalement États-Unis|Groupe bancaire américain proposant dépôts, crédits, prêts hypothécaires et services d’investissement. Il dessert principalement les particuliers et les entreprises aux États-Unis, avec certaines activités internationales.|wfc
T|Principalement États-Unis|Opérateur de télécommunications spécialisé dans la connectivité mobile et l’internet par fibre. Il dessert principalement les consommateurs et les entreprises du marché américain.|t
VZ|Principalement États-Unis|Opérateur de télécommunications proposant des services mobiles et un accès internet à haut débit. Ses réseaux et ses offres visent principalement les particuliers et les entreprises aux États-Unis.|vz
PFE|Monde|Entreprise pharmaceutique développant et commercialisant des médicaments et des vaccins. Elle intervient sur les marchés internationaux de la santé et mène des activités de recherche pour de nouveaux traitements.|pfe
LLY|Monde|Entreprise pharmaceutique développant des traitements dans plusieurs domaines thérapeutiques. Son activité associe recherche, fabrication et commercialisation de médicaments pour des patients à l’échelle mondiale.|lly
MCD|Monde|Groupe de restauration rapide exploitant la marque McDonald’s. Son réseau international combine des restaurants exploités directement et un modèle de franchises et de licences locales.|mcd
NKE|Monde|Entreprise d’articles de sport proposant chaussures, vêtements et équipements. Elle vise une clientèle mondiale par ses marques, ses canaux de vente directs et ses partenaires de distribution.|nke
SBUX|Monde|Chaîne de cafés proposant boissons, café et produits alimentaires. Ses magasins et ses offres visent des clients dans de nombreux marchés internationaux.|sbux
XIU.TO|Canada|FNB cherchant à suivre l’indice S&P/TSX 60. Il donne accès à de grandes sociétés canadiennes de plusieurs secteurs plutôt qu’à une seule entreprise.|xiu
SPY|États-Unis|FNB cherchant à suivre le S&P 500, indice de grandes entreprises du marché américain. Il offre une exposition répartie sur plusieurs secteurs.|spy
QQQ|Sociétés non financières cotées au Nasdaq, principalement États-Unis|FNB cherchant à suivre l’indice Nasdaq-100. Il regroupe de grandes entreprises non financières cotées au Nasdaq et présente une forte exposition aux activités technologiques et de croissance.|qqq
ESGV|États-Unis|FNB d’actions américaines sélectionnées selon des critères environnementaux, sociaux et de gouvernance. Il couvre des entreprises de différentes tailles selon la méthodologie de son indice, sans constituer une certification individuelle de chaque placement.|esgv
XBB.TO|Marché obligataire canadien|FNB regroupant des obligations du marché canadien. Il vise une exposition diversifiée à la dette gouvernementale et d’entreprises, avec différentes échéances.|xbb
ZST.TO|Marché obligataire en dollars canadiens|FNB d’obligations à très courte échéance libellées en dollars canadiens. Il réunit notamment de la dette d’entreprises et d’administrations publiques; ses parts ne sont pas un dépôt bancaire garanti.|zst
AGG|Marché obligataire américain en dollars américains|FNB couvrant largement le marché obligataire américain de qualité investissement. Il combine notamment des obligations d’État, d’entreprises et des titres adossés à des créances hypothécaires.|agg
TLT|États-Unis|FNB exposé aux obligations du Trésor américain de très longue échéance, généralement supérieure à vingt ans. Il cible la dette publique américaine et reste sensible aux variations des taux d’intérêt.|tlt
GLD|Marché mondial de l’or|Fiducie cotée donnant une exposition au prix de l’or au moyen d’or physique. Elle ne représente pas des actions de sociétés minières; ses frais peuvent créer un écart avec le cours du métal.|gld
BTC-USD|Réseau mondial, sans pays unique|Bitcoin est une monnaie numérique utilisée sur un réseau décentralisé de transferts de valeur. Son exposition n’est pas limitée à un pays et il ne représente pas une participation dans une entreprise.|btc
ETH-USD|Réseau mondial, sans pays unique|Ether est l’actif natif d’Ethereum, un réseau permettant d’exécuter des contrats intelligents et des applications. Il sert notamment au paiement des frais du réseau et n’offre pas une exposition géographique nationale unique.|eth
IWM|États-Unis|FNB cherchant à suivre l’indice Russell 2000. Il donne une exposition aux petites capitalisations américaines, distincte des fonds centrés sur les grandes entreprises.|iwm
DIA|États-Unis|FNB cherchant à suivre le Dow Jones Industrial Average. Il représente un groupe de grandes entreprises américaines, avec une pondération fondée sur le cours des actions.|dia
EEM|Pays émergents|FNB d’actions de grandes et moyennes entreprises de pays émergents. Il vise une exposition internationale aux économies classées émergentes par MSCI.|eem
EFA|Pays développés hors États-Unis et Canada|FNB d’actions de grandes et moyennes entreprises des marchés développés hors États-Unis et Canada. Il couvre notamment l’Europe, l’Australasie et l’Extrême-Orient selon son indice MSCI EAFE.|efa
VTI|États-Unis|FNB couvrant largement le marché des actions américaines. Il donne une exposition à des entreprises de différentes tailles et à plusieurs secteurs plutôt qu’aux seules grandes capitalisations.|vti
VOO|États-Unis|FNB cherchant à suivre le S&P 500. Il donne accès aux grandes capitalisations du marché américain dans un ensemble de secteurs.|voo
XLF|États-Unis|FNB sectoriel exposé aux sociétés financières du S&P 500. Il vise notamment les banques, assurances et autres services financiers du marché américain.|spdr_sectors
XLE|États-Unis|FNB sectoriel exposé aux entreprises énergétiques du S&P 500. Il cible le marché américain de l’énergie, notamment les activités liées au pétrole et au gaz.|spdr_sectors
XLK|États-Unis|FNB sectoriel exposé aux entreprises technologiques du S&P 500. Il cible notamment les logiciels, les équipements informatiques et les semi-conducteurs du marché américain.|spdr_sectors
XLV|États-Unis|FNB sectoriel exposé aux entreprises de santé du S&P 500. Il couvre notamment les médicaments, les équipements et les services de santé du marché américain.|spdr_sectors
SLV|Marché mondial de l’argent métal|Fiducie cotée donnant une exposition au prix de l’argent au moyen de métal physique. Elle ne représente pas un portefeuille d’actions minières et son prix tient compte de frais de fonctionnement.|slv
EWJ|Japon|FNB cherchant à suivre un indice d’actions japonaises. Il donne une exposition diversifiée aux entreprises du Japon, malgré sa cotation en dollars américains.|ewj
FXI|Chine; actions cotées à Hong Kong|FNB ciblant de grandes entreprises chinoises dont les actions sont cotées à Hong Kong. Il donne une exposition au marché chinois sans représenter l’ensemble des actions de Chine continentale.|fxi
EWZ|Brésil|FNB cherchant à suivre un indice d’actions brésiliennes. Il donne accès à différents secteurs de ce marché émergent, malgré sa cotation en dollars américains.|ewz
VWO|Pays émergents|FNB d’actions de pays émergents suivant une méthodologie FTSE. Il inclut des entreprises de différentes tailles et offre une exposition internationale plutôt qu’à un seul pays.|vwo
IEMG|Pays émergents|FNB d’actions de grandes, moyennes et petites capitalisations de pays émergents. Il vise une exposition large à ces marchés selon une méthodologie MSCI.|iemg
ARKK|États-Unis et autres marchés internationaux|FNB géré activement autour du thème de l’innovation de rupture. Il sélectionne des entreprises américaines et étrangères liées à ce thème plutôt que de simplement suivre un grand indice généraliste.|arkk
SMH|Industrie mondiale des semi-conducteurs; titres cotés aux États-Unis|FNB spécialisé dans les fabricants de semi-conducteurs et d’équipements associés. Il inclut des sociétés américaines et étrangères, ce qui donne une exposition sectorielle mondiale plutôt qu’exclusivement américaine.|smh
XBI|États-Unis|FNB spécialisé dans les actions de biotechnologie cotées sur les marchés américains. Son indice utilise une pondération modifiée à poids égaux et couvre des sociétés de différentes tailles.|xbi
GDX|Monde|FNB d’actions d’entreprises de l’industrie aurifère. Il offre une exposition à des sociétés minières internationales plutôt qu’à la détention directe d’or physique.|gdx
VNQ|États-Unis|FNB exposé aux sociétés immobilières américaines, notamment aux fiducies de placement immobilier. Il donne accès à plusieurs segments de l’immobilier coté et ne correspond pas à l’achat direct d’un immeuble.|vnq
IVV|États-Unis|FNB cherchant à suivre le S&P 500. Il donne une exposition aux grandes entreprises du marché américain dans plusieurs secteurs.|ivv
VEA|Pays développés hors États-Unis, Canada inclus|FNB d’actions des marchés développés hors États-Unis. Il couvre notamment le Canada, l’Europe et la région Pacifique, avec des entreprises de différentes tailles.|vea
URTH|Pays développés, États-Unis inclus|FNB cherchant à suivre les actions des pays développés selon l’indice MSCI World. Il inclut les États-Unis et d’autres marchés développés, mais ne constitue pas un fonds couvrant tous les pays émergents.|urth
XWD.TO|Pays développés, États-Unis et Canada inclus|FNB coté au Canada cherchant à suivre l’indice MSCI World. Son exposition porte sur des actions de pays développés; sa cotation en dollars canadiens ne limite pas ses placements au Canada.|xwd
HYG|Obligations d’entreprises en dollars américains|FNB d’obligations d’entreprises à haut rendement libellées en dollars américains. Il cible une qualité de crédit inférieure à la catégorie investissement, avec un risque de défaut plus important.|hyg
LQD|Obligations d’entreprises en dollars américains|FNB d’obligations d’entreprises de qualité investissement libellées en dollars américains. Il peut exposer à des émetteurs de différents pays et ne constitue pas uniquement une exposition aux entreprises américaines.|lqd
IEF|États-Unis|FNB exposé aux obligations du Trésor américain dont l’échéance se situe entre sept et dix ans. Il cible la dette publique américaine de maturité intermédiaire.|ief
DBC|Marchés mondiaux des matières premières|Fonds coté exposé à un ensemble de matières premières au moyen de contrats à terme. Il couvre plusieurs segments, notamment l’énergie, les métaux et les produits agricoles; le roulement des contrats peut influencer ses résultats.|dbc
XRP-USD|Réseau mondial, sans pays unique|XRP est l’actif natif du XRP Ledger, un réseau destiné notamment aux paiements et aux échanges de valeur. Il ne représente pas une action de Ripple et son réseau n’est pas limité à un pays.|xrp
LTC-USD|Réseau mondial, sans pays unique|Litecoin est une monnaie numérique destinée aux paiements entre utilisateurs sur un réseau décentralisé. Elle fonctionne sur une chaîne distincte de Bitcoin et n’offre pas une exposition nationale unique.|ltc
BCH-USD|Réseau mondial, sans pays unique|Bitcoin Cash est une monnaie numérique orientée vers les paiements électroniques entre utilisateurs. Il possède son propre réseau et constitue un actif distinct de Bitcoin, accessible à l’échelle internationale.|bch
EURUSD=X|Zone euro et États-Unis|Paire de change comparant l’euro au dollar américain. Sa cotation exprime le nombre de dollars américains pour un euro et ne représente pas des actions d’entreprises.|fx
USDJPY=X|États-Unis et Japon|Paire de change comparant le dollar américain au yen japonais. Sa cotation exprime le nombre de yens pour un dollar américain et reflète l’évolution relative des deux monnaies.|fx
GBPUSD=X|Royaume-Uni et États-Unis|Paire de change comparant la livre sterling au dollar américain. Sa cotation exprime le nombre de dollars américains pour une livre et ne correspond pas à un portefeuille d’actions britanniques.|fx
USDCAD=X|États-Unis et Canada|Paire de change comparant le dollar américain au dollar canadien. Sa cotation exprime le nombre de dollars canadiens pour un dollar américain et représente un taux de conversion entre les monnaies.|fx
AUDUSD=X|Australie et États-Unis|Paire de change comparant le dollar australien au dollar américain. Sa cotation exprime le nombre de dollars américains pour un dollar australien et ne représente pas des actions australiennes.|fx
CL=F|Référence pétrolière américaine, marché mondial|Série de prix de contrats à terme sur le pétrole brut WTI négociés au NYMEX. Elle représente une exposition au prix du pétrole, avec des effets possibles liés aux échéances et au roulement des contrats.|cl
GC=F|Marché mondial de l’or; contrats négociés aux États-Unis|Série de prix de contrats à terme sur l’or négociés au COMEX. Elle représente une référence de prix du métal et non une action de société minière ou la détention directe de lingots.|gc
SI=F|Marché mondial de l’argent; contrats négociés aux États-Unis|Série de prix de contrats à terme sur l’argent négociés au COMEX. Elle expose au métal précieux et industriel, avec des caractéristiques propres aux contrats à terme.|si
NG=F|Gaz naturel américain, référence Henry Hub|Série de prix de contrats à terme sur le gaz naturel Henry Hub négociés au NYMEX. Cette référence concerne surtout le marché américain du gaz et dépend notamment de ses conditions d’offre et de demande.|ng
HG=F|Marché mondial du cuivre; contrats négociés aux États-Unis|Série de prix de contrats à terme sur le cuivre négociés au COMEX. Elle représente une référence de prix d’un métal utilisé dans l’industrie, la construction et les équipements électriques.|hg
^GSPC|États-Unis|Indice S&P 500 représentant les grandes capitalisations du marché américain. Il sert de référence de marché et ne s’achète pas directement comme une action; des fonds peuvent chercher à le suivre.|sp500
^DJI|États-Unis|Indice Dow Jones Industrial Average regroupant de grandes entreprises américaines et pondéré selon le cours des actions. C’est une référence de marché, distincte des fonds cotés qui cherchent à la reproduire.|dow
^IXIC|Actions cotées au Nasdaq, avec émetteurs américains et internationaux|Indice Nasdaq Composite représentant un large ensemble d’actions cotées au Nasdaq. Il couvre plusieurs secteurs et ne doit pas être confondu avec le Nasdaq-100 suivi par QQQ.|nasdaq
^VIX|Anticipations de volatilité du marché américain|Indice mesurant la volatilité attendue du S&P 500 à partir des prix de ses options. Il constitue un indicateur et non une action achetable directement, ni le prix du S&P 500 lui-même.|vix
^N225|Japon|Indice Nikkei 225 représentant un ensemble de grandes entreprises du marché japonais. Il est pondéré selon le cours des actions et constitue un indice de référence, pas une action achetable directement.|nikkei
BD.CDN.2YR.DQ.YLD|Canada|Série du rendement de référence des obligations du gouvernement canadien à deux ans. Sa valeur est un taux en pourcentage, pas un prix d’obligation ni un produit achetable directement.|boc
BD.CDN.10YR.DQ.YLD|Canada|Série du rendement de référence des obligations du gouvernement canadien à dix ans. Sa valeur est un taux en pourcentage, pas un prix d’obligation ni une promesse de rendement sur un placement particulier.|boc
DGS2|États-Unis|Série du rendement du Trésor américain à échéance constante de deux ans, publiée dans FRED. Elle mesure un taux en pourcentage et ne représente pas le prix d’un titre achetable directement.|dgs2
DGS10|États-Unis|Série du rendement du Trésor américain à échéance constante de dix ans, publiée dans FRED. Elle mesure un taux en pourcentage et ne doit pas être traitée comme un prix de clôture ou un FNB obligataire.|dgs10
BND|Marché obligataire américain|FNB couvrant largement le marché obligataire américain de qualité investissement. Il permet une exposition à de nombreux titres de dette plutôt qu’à une seule obligation.|bnd
SCHD|États-Unis|FNB d’actions américaines orienté vers les entreprises versant des dividendes. Il cherche à suivre l’indice Dow Jones U S Dividend 100, avec une sélection fondée sur sa méthodologie.|schd
VBAL.TO|Canada, États-Unis et autres marchés internationaux|FNB de répartition d’actifs réunissant des actions et des obligations par l’intermédiaire de fonds sous-jacents. Il vise un profil équilibré avec une diversification canadienne et internationale.|vanguard_ca
VCNS.TO|Canada, États-Unis et autres marchés internationaux|FNB de répartition d’actifs combinant des fonds d’actions et d’obligations. Son orientation conservatrice accorde davantage de place aux obligations, tout en conservant une exposition canadienne et internationale.|vanguard_ca
VDY.TO|Canada|FNB d’actions canadiennes orienté vers les sociétés versant des dividendes élevés selon sa méthodologie. Il vise le marché canadien et ne garantit ni le maintien ni le montant des distributions.|vdy
VFV.TO|États-Unis|FNB coté au Canada cherchant à suivre le S&P 500. Ses placements visent les grandes entreprises américaines; la cotation en dollars canadiens ne signifie pas que les entreprises détenues sont canadiennes.|vanguard_ca_equity
VGRO.TO|Canada, États-Unis et autres marchés internationaux|FNB de répartition d’actifs à dominante actions, complété par des obligations. Il assemble des fonds sous-jacents pour une exposition diversifiée au Canada et aux marchés internationaux.|vanguard_ca
XEC.TO|Pays émergents|FNB coté au Canada exposé aux actions des pays émergents selon l’indice MSCI Emerging Markets IMI. Il couvre des entreprises de différentes tailles; la cotation canadienne ne correspond pas à une exposition aux seules entreprises canadiennes.|xec
XEF.TO|Pays développés hors États-Unis et Canada|FNB d’actions des marchés développés hors États-Unis et Canada suivant l’indice MSCI EAFE IMI. Il couvre de grandes, moyennes et petites entreprises, notamment en Europe et dans la région Pacifique.|xef
XESG.TO|Canada|FNB d’actions canadiennes suivant un indice intégrant des critères environnementaux, sociaux et de gouvernance. La sélection dépend de la méthodologie de l’indice et ne garantit pas l’absence de tous les secteurs qu’un client pourrait vouloir exclure.|xesg
XIC.TO|Canada|FNB cherchant à suivre un indice large d’actions canadiennes, le S&P/TSX Capped Composite. Il offre une couverture du marché canadien plus étendue que celle des seules grandes sociétés du S&P/TSX 60.|xic
XIT.TO|Canada|FNB spécialisé dans les entreprises technologiques du marché canadien. Il cherche à suivre l’indice S&P/TSX Capped Information Technology et donne une exposition sectorielle plutôt qu’à l’ensemble du marché.|xit
XRB.TO|Canada|FNB d’obligations canadiennes à rendement réel, dont les modalités sont liées à l’inflation. Il vise une exposition obligataire indexée, tout en restant sensible aux variations des taux réels et de son prix de marché.|xrb
XSB.TO|Canada|FNB d’obligations canadiennes à court terme. Il regroupe de la dette gouvernementale et d’entreprises avec une exposition à des échéances plus courtes que celles d’un fonds obligataire généraliste.|xsb
ZAG.TO|Canada|FNB cherchant à représenter largement le marché obligataire canadien. Il combine des obligations gouvernementales et d’entreprises de qualité investissement, avec différentes échéances.|zag'''


def sentence_count(text: str) -> int:
    return len([s for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s])


def build() -> dict:
    original_hash = hashlib.sha256(UNIVERSE.read_bytes()).hexdigest()
    with UNIVERSE.open(encoding='utf-8-sig', newline='') as stream:
        universe = list(csv.DictReader(stream))
    definitions = {}
    for line in CURATED.splitlines():
        ticker, zone, description, source = line.split('|')
        assert ticker not in definitions, f'Duplicate description: {ticker}'
        assert 1 <= sentence_count(description) <= 3
        assert len(description.split()) <= 65, f'Description too long: {ticker}'
        assert source in SOURCES, f'Missing source: {ticker}'
        definitions[ticker] = (zone, description, SOURCES[source])
    symbols = {row['ticker'] for row in universe}
    assert len(symbols) == len(universe), 'Duplicate universe symbol'
    assert symbols == set(definitions), dict(missing=sorted(symbols-set(definitions)), extra=sorted(set(definitions)-symbols))
    result = []
    for asset in universe:
        zone, text, source = definitions[asset['ticker']]
        assert urlparse(source).scheme == 'https' and urlparse(source).netloc
        result.append(dict(asset_id=asset['asset_id'], ticker=asset['ticker'], name=asset['name'],
                           asset_class=asset['asset_class'], pays_ou_zone_visee=zone,
                           description_fr=text, date_consultation=REVIEW_DATE))
    fields = list(result[0])
    with OUTPUT.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(result)
    with OUTPUT.open(encoding='utf-8-sig', newline='') as stream:
        reloaded = list(csv.DictReader(stream))
    assert reloaded == result, 'CSV round trip differs'
    assert hashlib.sha256(UNIVERSE.read_bytes()).hexdigest() == original_hash
    assert all(all(r.values()) for r in reloaded)
    assert not any(re.search(r'https?://|www\.', value) for row in reloaded for value in row.values())
    report = dict(status='complete', rows=len(result), unique_tickers=len(symbols),
                  description_max_sentences=max(sentence_count(r['description_fr']) for r in result),
                  description_max_words=max(len(r['description_fr'].split()) for r in result),
                  missing_tickers=[], extra_tickers=[], empty_fields=0,
                  universe_sha256=original_hash, csv_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
                  asset_classes=sorted({r['asset_class'] for r in result}),
                  source_domains=len({urlparse(definitions[r['ticker']][2]).netloc for r in result}),
                  output=str(OUTPUT), reviewed_on=REVIEW_DATE)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    build()
