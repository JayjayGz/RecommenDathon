"""Auditable reference matching and bounded intent parsing; no model or I/O."""
import re

INVESTIBLE_CLASSES = {"equity", "etf_equity", "etf_bond", "etf_commodity", "crypto"}
CLASS_PREFERENCES = {"stocks": {"equity"}, "bonds": {"etf_bond"},
                     "funds": {"etf_equity", "etf_bond", "etf_commodity"},
                     "crypto": {"crypto"}, "cash": set(), "equity_funds": {"etf_equity"},
                     "commodity_funds": {"etf_commodity"}, "commodity_futures": set(), "fx": set()}
SECTOR_PREFERENCES = {
    "technology": {"Information Technology", "Semiconductors"},
    "health": {"Health Care", "Biotechnology"},
    "financial_services": {"Financials"}, "finance": {"Financials"},
    "materials": {"Gold miners", "Industrial metals"}, "real_estate": {"Real estate (REIT)"},
    "consumer": {"Consumer Staples", "Consumer Discretionary"}, "other": set(),
    "energy": {"Energy"}, "industrials": {"Industrials"},
    "communications": {"Communication Services"}, "utilities": {"Utilities"},
}
APPROVED_RISK_MAP = {"very_low": "low", "low": "low", "medium": "medium", "high": "high", "very_high": "high"}


class InvestorInputError(ValueError):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.details = code, details or {}


def investible_universe(assets):
    return {t for t, a in assets.items() if a["asset_class"] in INVESTIBLE_CLASSES}


def match_profile(answers, assessment, requirements, config, assets):
    if answers["exclusions"] != "none" and not requirements.get("excluded_tickers"):
        raise InvestorInputError("EXCLUSIONS_NEED_CLARIFICATION",
            "Please provide the exact excluded tickers. Free-text activity or ESG exclusions cannot be certified from this dataset.")
    if not assets:
        raise InvestorInputError("MISSING_ASSET_UNIVERSE", "Asset metadata is required to compare reference portfolios.")
    policy = config.get("questionnaire_matching", {})
    # Approved by the user for this questionnaire integration; no scoring of
    # financial situation, desired returns or demographics is invented here.
    risk_map = policy.get("risk_map", APPROVED_RISK_MAP)
    band = assessment.get("risk_band", risk_map.get(answers["risk"]))
    if band not in {"low", "medium", "high"}:
        raise InvestorInputError("RISK_MAPPING_REQUIRED",
            "This risk answer has no configured mapping. Supply an explicit assessed risk_band or an agreed questionnaire_matching policy.")
    excluded = set(requirements.get("excluded_tickers", []))
    if excluded - set(assets):
        raise InvestorInputError("UNKNOWN_EXCLUSION", "An excluded ticker is absent from the asset metadata.",
                                 {"tickers": sorted(excluded - set(assets))})
    classes = set().union(*(CLASS_PREFERENCES[a] for a in answers["assets"]))
    sectors = set().union(*(SECTOR_PREFERENCES[s] for s in answers["sectors"]))
    candidates, rejected = [], []
    for p in config["profiles"]:
        if p["band"] != band:
            continue
        weights = {t: w for t, w in p["weights"].items() if w > 0}
        reasons = []
        if set(weights) - investible_universe(assets):
            reasons.append("missing_or_noninvestible_metadata")
        if excluded & set(weights):
            reasons.append("excluded_ticker")
        crypto = sum(w for t, w in weights.items() if assets.get(t, {}).get("asset_class") == "crypto")
        if crypto > 0 and "crypto" not in answers["assets"]:
            reasons.append("crypto_not_requested")
        if max(weights.values()) * 100 > requirements.get("max_asset_weight_pct", 100) + 1e-8:
            reasons.append("max_asset_weight_pct")
        if crypto * 100 > requirements.get("max_crypto_weight_pct", 100) + 1e-8:
            reasons.append("max_crypto_weight_pct")
        if "preferred_style" in assessment and p["style"] != assessment["preferred_style"]:
            reasons.append("different_requested_style")
        if reasons:
            rejected.append({"profile_id": p["id"], "reasons": reasons})
            continue
        class_score = sum(w for t, w in weights.items() if assets[t]["asset_class"] in classes)
        sector_score = sum(w for t, w in weights.items()
                           if assets[t]["asset_class"] == "equity" and assets[t]["sector"] in sectors)
        candidates.append({"profile_id": p["id"], "style": p["style"],
                           "asset_preference_weight": round(class_score, 8),
                           "direct_sector_preference_weight": round(sector_score, 8),
                           "score": round(class_score + sector_score, 8)})
    if not candidates:
        raise InvestorInputError("NO_COMPATIBLE_REFERENCE_PROFILE",
            "No reference profile matches the explicit band and constraints. No constraints were relaxed.",
            {"risk_band": band, "rejected_candidates": rejected})
    candidates.sort(key=lambda p: (-p["score"], p["style"] != "Broad diversifier", p["profile_id"]))
    chosen = candidates[0]
    return {"profile_id": chosen["profile_id"], "risk_band": band, "style": chosen["style"],
            "preference_inputs": {"asset_classes": sorted(classes), "direct_stock_sectors": sorted(sectors)},
            "selected_overlap": {"asset_class_weight": chosen["asset_preference_weight"],
                                 "direct_sector_weight": chosen["direct_sector_preference_weight"]},
            "method": "reference_metadata_overlap_v1",
            "risk_mapping_source": "explicit_assessment" if "risk_band" in assessment else
                policy.get("version", "approved_five_to_three_v1"),
            "candidates": candidates, "rejected_candidates": rejected,
            "reasons": [f"The selected reference profile uses the explicitly matched {band} band.",
                "Candidates are ranked by the sum of portfolio weights in requested asset classes and direct-stock sectors; ties prefer Broad diversifier, then the lowest profile ID."],
            "limitations": [
                "This is reference-template matching, not a validated investor-risk assessment or a claim of optimal suitability.",
                "Family situation, dependants, income, debt, emergency funds, goals, liquidity, horizon, experience and loss reaction are retained as context; this matcher does not infer financial risk capacity or forecast returns.",
                "Asset-class interests are preferences, not an exclusive allowlist; sector matching does not look through ETFs.",
                "Cash products, commodity futures, currency trading, free-text preferences and ESG or activity-based exclusions are not certified by this matcher.",
            ]}


def resolve_message(message, assets, conversation=(), interpret=None):
    """Normalize one explicit edit into the language-independent stage contract.

    Optional semantic interpretation can select an operation only; Python owns
    identity, amounts, units, ambiguity checks and all financial validation.
    """
    from .request_language import asset_mentions, ambiguous, fold, intent, quantities

    def unclear():
        return InvestorInputError("AMBIGUOUS_PERSONALIZATION_REQUEST",
            "Précisez une seule modification : ajout, réduction ou exclusion. "
            "Exemple de syntaxe : ajouter TD.TO de 5 points de pourcentage. "
            "Un poids cible, une négation ou une condition nécessite une clarification.")

    if ambiguous(message):
        raise unclear()
    found = asset_mentions(message, assets)
    amounts = quantities(message)
    text = fold(message)
    action = intent(message)
    # Only a quantity-only reply may borrow identity AND direction from the last
    # user turn. Assistant/model text never establishes an investment instruction.
    quantity_only = len(amounts) == 1 and not (
        text[:amounts[0][0].start()] + text[amounts[0][0].end():]).strip(" .!?")
    if not found and quantity_only:
        last = next((m["content"] for m in reversed(conversation) if m["role"] == "user"), None)
        if last is not None:
            if ambiguous(last) or intent(last) in {"conflict", "exclude"}:
                raise unclear()
            found = asset_mentions(last, assets)
            action = intent(last) or "add"
    if not found:
        raise InvestorInputError("ASSET_NOT_IN_UNIVERSE",
            "Indiquez le symbole exact ou le nom complet d’un actif du catalogue. Aucun actif inconnu ne sera ajouté.")
    # Mask names and quantities so 'et un' and an official name containing 'and'
    # do not masquerade as instructions for a second asset.
    masked = text
    for ticker in found:
        for alias in (ticker, assets[ticker]["name"]):
            masked = masked.replace(fold(alias), " ")
    for match, _ in quantities(masked)[::-1]:
        masked = masked[:match.start()] + " " + masked[match.end():]
    if len(found) != 1 or re.search(r"\b(?:et|and|ou|or|puis)\b", masked):
        raise unclear()
    ticker = next(iter(found))
    if ticker not in investible_universe(assets):
        raise InvestorInputError("UNSUPPORTED_ASSET_CLASS",
            "Cet élément du catalogue est une série de référence et ne peut pas être détenu dans ce portefeuille.",
            {"ticker": ticker})
    if action == "conflict":
        raise unclear()
    if action == "exclude":
        if amounts:
            raise unclear()
        return {"exclude": ticker}
    if (len(amounts) != 1 or not str(amounts[0][1]).isdigit()
            or len(str(amounts[0][1])) > 3 or not 1 <= int(amounts[0][1]) <= 100):
        raise InvestorInputError("ALLOCATION_AMOUNT_REQUIRED",
            "Précisez une variation entière de 1 à 100 points de pourcentage. Aucun montant ne sera supposé.",
            {"ticker": ticker, "requires": "add_pct", "operation": action})
    # A bare ticker plus quantity remains supported. Other unrecognized prose
    # requires semantic interpretation, rather than silently defaulting to a buy.
    if action is None and not masked.strip(" .!?:,;"):
        action = "add"
    if action is None and interpret is not None:
        action = interpret(message, ticker)
    if action not in {"add", "reduce"}:
        raise unclear()
    amount = int(amounts[0][1])
    return {"ticker": ticker, "add_pct": -amount if action == "reduce" else amount}
