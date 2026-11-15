"""Avis éducatif déterministe sur une modification, distinct de son application."""
from alphaforge.domain.portfolio_review import CONVENTIONS, review_portfolio
from alphaforge.domain.profile_matching import CLASS_PREFERENCES, SECTOR_PREFERENCES
from alphaforge.domain.exposures import SECTORS

from .investor_summary import questionnaire_observations

METHOD = "questionnaire_change_review_v1"
CLASS_LABELS = {"equity": "actions détenues directement", "etf_equity": "fonds d’actions",
                "etf_bond": "fonds obligataires", "etf_commodity": "fonds de matières premières",
                "crypto": "cryptomonnaies"}
RISK_LABELS = {"low": "faible", "medium": "modérée", "high": "élevée"}


def asset_observations(answers, ticker, metadata, exposure=None):
    """Examiner les intérêts déclarés sans supposer un poids ou une performance."""
    classes = set().union(*(CLASS_PREFERENCES[a] for a in answers["assets"]))
    sectors = set().union(*(SECTOR_PREFERENCES[s] for s in answers["sectors"]))
    class_match = metadata["asset_class"] in classes
    sector_match = metadata["sector"] in sectors if metadata["asset_class"] == "equity" else None
    if exposure and exposure.get("sectors") and exposure["sectors_basis"] == "GICS":
        preferred = set().union(*(SECTORS[s] for s in answers["sectors"]))
        sector_match = any(v > 0 and s in preferred for s, v in exposure["sectors"]["fractions"].items())
    strengths, cautions, limitations = [], [], []
    label = CLASS_LABELS[metadata["asset_class"]]
    if exposure and exposure.get("description_fr"):
        strengths.append(f"Activités de {ticker} selon le catalogue : {exposure['description_fr']}")
    if class_match:
        strengths.append(f"{ticker} appartient aux {label}, une catégorie qui correspond à vos intérêts déclarés.")
    else:
        cautions.append(f"{ticker} appartient aux {label}, une catégorie absente de vos préférences. Confirmez si vous souhaitez élargir ces préférences avant d’envisager l’ajout.")
    if sector_match is True:
        strengths.append(f"Le secteur de {ticker} correspond à un secteur choisi dans le questionnaire.")
    elif sector_match is False:
        cautions.append(f"Le secteur de {ticker} ne correspond pas aux secteurs choisis. Cette différence appelle une clarification ; vos préférences ne constituent pas une interdiction.")
    else:
        limitations.append(f"Le contenu détaillé de {ticker} n’est pas disponible : sa cohérence avec vos préférences sectorielles et vos exclusions d’activités ne peut pas être confirmée.")
    context = answers.get("financial_context", {})
    if (metadata["asset_class"] != "etf_bond" and (answers.get("horizon") == "1_2"
            or context.get("delai_retrait") in {"moins_1_an", "1_3_ans"})):
        cautions.append(f"Votre horizon ou votre retrait prévu est proche. Avant d’ajouter {ticker}, précisez la part de l’épargne qui doit rester disponible pour éviter de devoir vendre pendant une baisse.")
    return class_match, sector_match, strengths, cautions, limitations


def unweighted_asset_review(answers, ticker, metadata, requirements=None, operation=None):
    """Donner un premier avis puis demander le montant à simuler, sans l’inventer."""
    if operation == "reduce":
        return "\n\n".join([
            f"Analyse préalable de {metadata['name']} ({ticker}) : aucune modification n’est appliquée.",
            "Sans montant, l’effet de la réduction sur la concentration, les fluctuations et les baisses du portefeuille ne peut pas être évalué.",
            f"Quelle réduction souhaitez-vous simuler pour {ticker}, en points de pourcentage entiers ? Ce montant servira à l’analyse et ne sera pas appliqué automatiquement.",
            "Simulation éducative, sans conseil en placement. Les résultats passés ne prédisent pas les résultats futurs."
        ])
    _, _, strengths, cautions, limitations = asset_observations(answers, ticker, metadata)
    if ticker in (requirements or {}).get("excluded_tickers", []):
        cautions.insert(0, f"Vous avez explicitement exclu {ticker}. Cet ajout ne peut pas être retenu tant que cette exclusion s’applique.")
    cautions.extend(questionnaire_observations(answers))
    return "\n\n".join([
        f"Analyse préalable de {metadata['name']} ({ticker}) : aucun ajout n’est appliqué.",
        *strengths, *dict.fromkeys(cautions), *limitations,
        "Avis : cet intérêt seul ne suffit pas à justifier l’ajout. Sans montant, l’effet sur la concentration, les fluctuations et les baisses du portefeuille ne peut pas être évalué.",
        f"Quelle augmentation souhaitez-vous simuler pour {ticker}, en points de pourcentage ? Ce montant servira à l’analyse et ne sera pas appliqué automatiquement.",
        "Simulation éducative, sans conseil en placement. Les résultats passés ne prédisent pas les résultats futurs."
    ])


def build_change_review(evaluation, selected):
    """Ne crée ni nouvelle limite de risque ni ordre d’achat."""
    answers = evaluation["questionnaire_answers"]
    match = evaluation["profile_match"]
    before = evaluation["base"]["weights"]
    after = evaluation[selected]["weights"] if selected else None
    strengths, cautions, limitations, assets = [], [], [], []
    for change in evaluation["requested_changes"]:
        ticker = change.get("ticker", change.get("exclude"))
        metadata = evaluation["asset_metadata"][ticker]
        adding = change.get("add_pct", 0) > 0
        class_match, sector_match, pros, cons, limits = asset_observations(
            answers, ticker, metadata, evaluation.get("asset_exposures", {}).get(ticker))
        assets.append({"ticker": ticker, "asset_class": metadata["asset_class"],
                       "class_preference_match": class_match, "sector_preference_match": sector_match,
                       "before_pct": round(before.get(ticker, 0) * 100, 8),
                       "after_pct": round(after.get(ticker, 0) * 100, 8) if after is not None else None})
        if not adding:
            continue
        strengths.extend(pros)
        cautions.extend(cons)
        limitations.extend(limits)
    cautions.extend(questionnaire_observations(answers))
    base_metrics = evaluation["base"]["validation"]
    metrics = evaluation[selected]["validation"] if selected else None
    comparable = bool(metrics and base_metrics.get("status") in {"PASS", "CONFLICT"}
                      and all(base_metrics.get(k) == metrics.get(k) for k in CONVENTIONS))
    if metrics:
        strengths.append(f"La simulation proposée respecte les limites vérifiées du profil de risque à tolérance {RISK_LABELS[match['risk_band']]}.")
        if base_metrics.get("status") in {"PASS", "CONFLICT"}:
            base_review = review_portfolio(before, base_metrics, evaluation["asset_metadata"], match)
            candidate_review = evaluation["portfolio_analysis"]["review"]
            concentration_before = base_review["diversification"]["holding_hhi"]
            concentration_after = candidate_review["diversification"]["holding_hhi"]
            if concentration_after > concentration_before:
                cautions.append("La concentration entre les positions augmente. Ajouter un actif ne suffit donc pas à améliorer la répartition ; le montant proposé doit être réexaminé.")
            elif concentration_after < concentration_before:
                strengths.append("La concentration entre les positions diminue, sans que cela démontre une meilleure diversification des placements sous-jacents.")
        if comparable:
            if metrics["volatility_pct"] > base_metrics["volatility_pct"]:
                cautions.append("Les fluctuations historiques augmentent par rapport au portefeuille actuel. Le respect du plafond de risque ne suffit pas à justifier ce risque supplémentaire.")
            if metrics["max_drawdown_pct"] < base_metrics["max_drawdown_pct"]:
                cautions.append("La baisse historique devient plus profonde. Il faut examiner ce compromis au regard de votre réaction aux pertes et de votre besoin de retrait.")
        else:
            cautions.append("La comparaison historique avant/après n’est pas disponible sur des périodes et des méthodes identiques ; l’intérêt du changement reste à clarifier.")
    if selected == "adjusted":
        cautions.append("La demande initiale dépasse une limite vérifiée. L’alternative simulée ne reprend pas intégralement l’ajout demandé ; une nouvelle décision est nécessaire.")
    changed = bool(after is not None and any(abs(before.get(t, 0) - after.get(t, 0)) > 1e-8
                                           for t in set(before) | set(after)))
    if not selected or not changed:
        verdict = "not_retained"
        conclusion = "Avis : ne pas retenir cette modification en l’état. " + (
            "Aucune répartition évaluée ne respecte toutes les limites." if not selected else
            "La simulation ne produit aucun changement effectif de répartition.")
    elif cautions:
        verdict = "clarification_required"
        conclusion = "Avis : clarifier les points ci-dessous avant de retenir l’ajout ou la modification. Le respect des limites calculées ne suffit pas à établir sa cohérence avec vos besoins."
    else:
        verdict = "compatible"
        conclusion = "Avis : cette modification est compatible avec les critères vérifiés et peut être envisagée dans la simulation, sous réserve de votre confirmation explicite. Cela ne confirme pas son adéquation à votre situation financière complète."
    return {"method": METHOD, "verdict": verdict, "applied": False,
            "confirmation_required": True, "baseline_weights_pct": {t: round(w * 100, 8) for t, w in sorted(before.items()) if w > 0},
            "assets": assets, "strengths": list(dict.fromkeys(strengths)),
            "cautions": list(dict.fromkeys(cautions)), "limitations": list(dict.fromkeys(limitations)),
            "conclusion": conclusion}
