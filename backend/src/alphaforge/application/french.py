"""French investor-facing messages. Machine identifiers and audit facts stay intact."""
MESSAGES = {
    'EXCLUSIONS_NEED_CLARIFICATION': 'Précisez les symboles exacts des actifs à exclure. Les exclusions d’activités ou ESG en texte libre ne peuvent pas être certifiées avec ces données.',
    'MISSING_ASSET_UNIVERSE': 'Le catalogue des actifs est indisponible. Aucune comparaison n’a été effectuée.',
    'RISK_MAPPING_REQUIRED': 'Cette réponse ne correspond à aucun profil de risque configuré. Une clarification est nécessaire.',
    'UNKNOWN_EXCLUSION': 'Un symbole à exclure est absent du catalogue. Précisez son symbole exact.',
    'NO_COMPATIBLE_REFERENCE_PROFILE': 'Aucun portefeuille de référence ne respecte le profil et les contraintes indiqués. Aucune contrainte n’a été assouplie.',
    'ASSET_NOT_IN_UNIVERSE': 'Un actif demandé est absent du catalogue. Indiquez son symbole exact ; aucun actif inconnu ne sera ajouté.',
    'UNSUPPORTED_ASSET_CLASS': 'Cet élément du catalogue ne peut pas être détenu dans ce portefeuille.',
    'MISSING_HOLDING_HISTORY': 'L’historique de prix nécessaire manque pour certains actifs. Aucune proposition n’a été validée.',
    'ASSET_CURRENCY_MISMATCH': 'Les devises des prix et du catalogue ne concordent pas. Aucune conversion n’a été supposée.',
}


def input_message(error):
    # Parser, questionnaire and preliminary review messages are already French.
    return MESSAGES.get(error.code, str(error))


STYLES = {'Broad diversifier': 'Diversification élargie', 'Home country': 'Orientation nationale',
          'Growth and innovation': 'Croissance et innovation', 'Income and stability': 'Revenu et stabilité',
          'Responsible (ESG)': 'Responsable (ESG)'}

SECTORS = {'Information Technology': 'technologies de l’information', 'Health Care': 'santé',
           'Financials': 'services financiers', 'Energy': 'énergie', 'Industrials': 'industrie',
           'Materials': 'matériaux', 'Real Estate': 'immobilier', 'Real estate (REIT)': 'immobilier (FPI)',
           'Consumer Staples': 'consommation de base', 'Consumer Discretionary': 'consommation discrétionnaire',
           'Communication Services': 'services de communication', 'Utilities': 'services publics',
           'Semiconductors': 'semi-conducteurs', 'Biotechnology': 'biotechnologie',
           'Gold miners': 'mines d’or', 'Industrial metals': 'métaux industriels'}


def evidence_description(entry):
    # Evidence details are kept verbatim in the private bundle; the public source
    # catalog uses a French description of its role, without machine translation
    # of numbers, identifiers or externally supplied asset names.
    field = entry['field']
    if field.startswith('review.'):
        return 'Constat vérifié sur la composition du portefeuille.'
    if field.startswith('suggestion.'):
        return 'Comparaison vérifiée d’une autre répartition simulée.'
    if field.startswith('macro.'):
        return 'Observation datée du contexte obligataire, sans modification automatique des poids.'
    if field == 'change_review':
        return entry['sentence']
    if field.startswith('profile_match.'):
        return 'Critère vérifié de rapprochement avec le portefeuille de référence.'
    if field == 'requested_changes':
        return 'Variations demandées en points de pourcentage, distinctes de poids cibles.'
    if field == 'funding_policy':
        return 'Méthode de financement des ajouts et règles d’arrondi.'
    if field.startswith('conditional_maximum.'):
        return 'Limite conditionnelle vérifiée pour l’ajout demandé ; les limites séparées ne se combinent pas.'
    metric = {'annual_growth_pct': 'croissance annualisée historique', 'volatility_pct': 'volatilité historique',
              'max_drawdown_pct': 'plus forte baisse historique', 'period': 'période et nombre d’observations',
              'annualization': 'convention d’annualisation', 'weights': 'poids simulés'}
    suffix = field.rsplit('.', 1)[-1]
    return 'Élément vérifié : ' + metric.get(suffix, 'résultat ou contrainte de la simulation') + '.'
