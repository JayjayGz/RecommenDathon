"""French investor view of checked results; detailed evidence stays in the audit."""
from .french import SECTORS

DISCLAIMER_FR = "Simulation éducative, sans conseil en placement. Les résultats passés ne prédisent pas les résultats futurs."

PUBLIC_LIMITATIONS = [
    "L’analyse ne prévoit ni les rendements futurs ni les pertes possibles. L’historique disponible peut sous-estimer certains risques et ne couvre pas tous les actifs du marché.",
    "Elle ne permet pas de confirmer que ce portefeuille convient à votre situation financière complète, ni de mesurer votre capacité réelle à supporter une perte.",
    "Les frais, la fiscalité, la facilité de revente et la situation financière des entreprises ne sont pas évalués.",
    "Les répartitions disponibles restent partielles et datées. Le détail des titres des fonds et leurs chevauchements n’est pas établi ; les exclusions éthiques ou sectorielles ne peuvent pas être garanties.",
]


def questionnaire_observations(answers):
    """Flag explicit tensions, without inventing a risk score or financial capacity."""
    risk = answers.get("risk")
    high = risk in {"high", "very_high"}
    context = answers.get("financial_context", {})
    observations = []
    if high and answers.get("reaction") in {"worried", "hesitant"}:
        observations.append("Votre tolérance au risque élevée contraste avec votre inquiétude face aux baisses. Clarifiez la perte que vous seriez prêt à accepter avant de retenir cette répartition.")
    if high and (answers.get("horizon") == "1_2" or context.get("delai_retrait") in {"moins_1_an", "1_3_ans"}):
        observations.append("Un risque élevé et un retrait proche peuvent être difficiles à concilier : une baisse pourrait survenir au moment où vous avez besoin de l’argent. Clarifiez la part à garder disponible.")
    elif answers.get("horizon") in {"10", "15_plus"} and context.get("delai_retrait") in {"moins_1_an", "1_3_ans"}:
        observations.append("Votre horizon long et votre retrait prévu à court terme appellent une précision : quelle part de l’épargne doit rester disponible ?")
    if context.get("fonds_urgence") == 0 and answers.get("income") in {"variable", "fragile"}:
        observations.append("L’absence de fonds d’urgence, combinée à des revenus incertains, peut rendre une vente forcée plus probable. Examinez d’abord votre besoin de réserve disponible.")
    if risk in {"very_low", "low"} and "crypto" in answers.get("assets", []):
        observations.append("Votre intérêt pour les cryptomonnaies contraste avec votre faible tolérance au risque. Précisez si vous acceptez leurs fortes variations ou souhaitez les écarter.")
    return observations


def investor_summary(evaluation, selected, answers):
    """Use validated evaluation values only; never let model prose alter the verdict."""
    paragraphs = []
    change_review = evaluation.get("change_review")
    if change_review:
        paragraphs.append("Analyse préalable : les poids présentés sont uniquement simulés, à examiner avant toute confirmation. Aucun ajout n’est appliqué automatiquement.")
        paragraphs.append(change_review["conclusion"])
        if change_review["strengths"]:
            paragraphs.append("Éléments favorables : " + " ".join(change_review["strengths"]))
        if change_review["cautions"]:
            paragraphs.append("Points à examiner : " + " ".join(change_review["cautions"]))
        if change_review["limitations"]:
            paragraphs.append("Limites de cet avis : " + " ".join(change_review["limitations"]))
    elif selected == "as_requested":
        paragraphs.append("La répartition respecte les critères de risque vérifiés. Cela ne suffit pas à confirmer qu’elle répond à tous vos besoins.")
    elif selected:
        paragraphs.append("La modification demandée dépasse au moins une limite vérifiée. La répartition présentée est une alternative ajustée qui respecte ces limites ; elle ne reprend pas intégralement votre demande.")
    else:
        paragraphs.append("Aucune répartition évaluée ne respecte toutes les limites vérifiées. Aucun portefeuille n’est proposé en l’état.")
    failed = evaluation.get("as_requested", {}).get("validation", {}).get("checks", {})
    reasons = {"max_single_stock_pct": "une position en actions trop importante", "max_asset_weight_pct": "une position trop importante", "max_crypto_pct": "une part de cryptomonnaies trop importante", "max_crypto_weight_pct": "une part de cryptomonnaies trop importante", "max_gold_pct": "une part d’or trop importante", "crypto_allowed": "des cryptomonnaies non autorisées pour le profil retenu", "excluded_tickers": "un placement que vous avez demandé d’exclure", "max_volatility_pct": "des fluctuations historiques trop fortes", "max_drawdown_pct": "une baisse historique trop importante"}
    failures = [reasons.get(key, "une limite de risque ou de composition non respectée") for key, check in sorted(failed.items()) if check.get("passes") is False]
    if failures:
        paragraphs.append("La demande présente " + ", ".join(dict.fromkeys(failures)) + ".")
    paragraphs.extend(change_analysis(evaluation, selected))
    review = evaluation.get("portfolio_analysis", {}).get("review", {})
    classes = review.get("asset_class_weights_pct", {})
    labels = {"equity": "actions détenues directement", "etf_equity": "fonds d’actions", "etf_bond": "fonds obligataires", "etf_commodity": "fonds de matières premières", "crypto": "cryptomonnaies"}
    if selected and classes:
        split = ", ".join(f"{number(value)} % en {labels.get(key, 'autres placements')}" for key, value in sorted(classes.items()) if value)
        subject = "La répartition simulée comprend" if change_review else "Votre portefeuille comprend"
        paragraphs.append(f"{subject} {split}. Les actions cherchent la croissance mais peuvent fortement baisser ; les obligations peuvent atténuer les fluctuations, sans garantir le capital.")
    if selected:
        validation = evaluation[selected]["validation"]
        paragraphs.append(f"Sur la période du {validation['period']['first_date']} au {validation['period']['last_date']}, la simulation affiche une croissance annualisée de {number(validation['annual_growth_pct'])} % et une plus forte baisse de {number(validation['max_drawdown_pct'])} %. Cette baisse mesure le recul depuis un sommet pendant la période observée, pas une perte maximale future.")
    observations = questionnaire_observations(answers)
    if observations and not change_review:
        paragraphs.append("Points à clarifier : " + " ".join(observations))
    elif not change_review:
        paragraphs.append("Les réponses examinées ne font pas ressortir de contradiction explicite dans les combinaisons vérifiées. Cela ne valide pas à lui seul votre capacité à prendre ce risque.")
    mapping = evaluation.get("profile_match", {}).get("questionnaire_mapping")
    if mapping:
        paragraphs.append("Le profil de référence tient compte de votre réaction aux pertes, de vos connaissances, de votre horizon et de la stabilité de vos revenus, en plus de la tolérance au risque déclarée. Ce classement ne remplace pas une évaluation financière complète.")
    exposures = evaluation.get("portfolio_analysis", {}).get("exposures")
    if exposures:
        sectors = exposures["dimensions"]["sectors"]
        if sectors["covered_pct"]:
            paragraphs.append(f"Les répartitions sectorielles disponibles couvrent {number(sectors['covered_pct'])} % du portefeuille. La part mesurée dans vos secteurs d’intérêt représente {number(exposures['preferred_sector_weight_pct'])} % du portefeuille ; la part non documentée ne vaut pas zéro.")
            for insight in exposures["insights"]:
                if insight["kind"] == "largest_measured_sector":
                    paragraphs.append(f"Le principal secteur d’actions mesuré est {SECTORS.get(insight['sector'], insight['sector'])} : {number(insight['weight_pct'])} % du portefeuille, en incluant les fonds dont la répartition est disponible.")
        else:
            paragraphs.append("Les répartitions sectorielles ne sont pas disponibles à la date de l’analyse ; aucune exposition manquante n’est supposée.")
        potential = exposures["potential_assets"][:2]
        if potential:
            choices = "; ".join(f"{p['ticker']} ({SECTORS.get(p['sector'], p['sector'])}) : {p['description_fr']}" for p in potential)
            paragraphs.append("Pistes à étudier selon vos intérêts : " + choices + " Ces pistes ne sont ni pondérées ni simulées, peuvent recouper des fonds déjà détenus et ne sont pas appliquées.")
    suggestions = evaluation.get("portfolio_analysis", {}).get("suggestions", [])
    if suggestions:
        changes = suggestions[0]["changes"]
        description = ", ".join(f"{c['ticker']} : {number(c['add_pct'])} points de pourcentage" for c in changes)
        paragraphs.append(f"Une option à examiner réduit la concentration entre les positions : {description}. Elle n’est pas appliquée et ne garantit pas une meilleure performance.")
    paragraphs.append(DISCLAIMER_FR)
    return "\n\n".join(paragraphs), list(PUBLIC_LIMITATIONS)


def number(value):
    return f"{value:g}".replace(".", ",")


def change_analysis(evaluation, selected):
    """Expliquer les changements évalués sans attribuer de causalité non mesurée."""
    changes = evaluation.get("requested_changes", [])
    if not changes:
        return []
    descriptions = []
    for change in changes:
        if "exclude" in change:
            descriptions.append(f"exclure {change['exclude']}")
        else:
            delta = change["add_pct"]
            verb = "augmenter" if delta >= 0 else "réduire"
            descriptions.append(f"{verb} {change['ticker']} de {number(abs(delta))} points de pourcentage")
    paragraphs = ["Votre demande : " + "; ".join(descriptions) + "."]
    if not selected:
        paragraphs.append("La modification n’est pas retenue : ni la demande ni l’alternative évaluée ne respecte toutes les limites. Aucun changement n’est appliqué.")
        return paragraphs
    before = evaluation["base"]["weights"]
    after = evaluation[selected]["weights"]
    positions = []
    for ticker in sorted(set(before) | set(after)):
        old, new = before.get(ticker, 0), after.get(ticker, 0)
        if abs(new - old) > 1e-8:
            positions.append(f"{ticker} passe de {number(round(old * 100, 8))} % à {number(round(new * 100, 8))} %")
    if positions:
        label = "Dans l’alternative simulée" if selected == "adjusted" else "Dans la proposition évaluée"
        paragraphs.append(label + ", " + "; ".join(positions) + ". Ces changements décrivent aussi les positions réduites ou renforcées en contrepartie, après arrondi.")
    else:
        paragraphs.append("Les poids restent identiques au portefeuille de départ après les contrôles et les arrondis. La demande ne produit donc aucun changement effectif de répartition.")
    base_metrics = evaluation["base"]["validation"]
    metrics = evaluation[selected]["validation"]
    if base_metrics.get("status") not in {"PASS", "CONFLICT"}:
        paragraphs.append("L’historique du portefeuille de départ ne permet pas de comparer les indicateurs avant et après.")
        return paragraphs
    comparable = all(base_metrics.get(key) == metrics.get(key) for key in (
        "period", "currency", "rebalance", "method", "observation_frequency", "annualization_observations"))
    if not comparable:
        paragraphs.append("Les périodes ou les méthodes des deux simulations diffèrent : leurs indicateurs ne permettent pas d’isoler l’effet du changement de répartition.")
        return paragraphs
    comparisons = []
    for key, label in (("annual_growth_pct", "la croissance annualisée"),
                       ("volatility_pct", "les fluctuations annualisées"),
                       ("max_drawdown_pct", "la plus forte baisse")):
        comparisons.append(f"{label} passe de {number(base_metrics[key])} % à {number(metrics[key])} %")
    paragraphs.append("Sur la même période et avec la même méthode de simulation, " + "; ".join(comparisons) + ".")
    volatility_change = metrics["volatility_pct"] - base_metrics["volatility_pct"]
    drawdown_change = metrics["max_drawdown_pct"] - base_metrics["max_drawdown_pct"]
    if abs(volatility_change) < 1e-8 and abs(drawdown_change) < 1e-8:
        interpretation = "Les deux indicateurs de risque historique restent inchangés."
    else:
        volatility = "augmentent" if volatility_change > 1e-8 else "diminuent" if volatility_change < -1e-8 else "restent stables"
        drawdown = "moins profonde" if drawdown_change > 1e-8 else "plus profonde" if drawdown_change < -1e-8 else "inchangée"
        interpretation = f"Les fluctuations historiques {volatility} et la plus forte baisse est {drawdown}."
    paragraphs.append(interpretation + " Ces constats portent sur l’ensemble de la répartition modifiée et ne prédisent pas son comportement futur.")
    return paragraphs
