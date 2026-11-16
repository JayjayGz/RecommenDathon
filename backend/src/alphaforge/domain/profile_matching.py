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


def questionnaire_requirements(answers, requirements, assets):
    """Resolve an explicit exclusion list; retain unsupported prose for clarification."""
    from .request_language import fold, asset_aliases

    result = dict(requirements)
    if answers.get("exclusions") != "limits" or result.get("excluded_tickers"):
        return result
    text = answers.get("financial_context", {}).get("exclusions_details", "")
    if not isinstance(text, str) or not text.strip():
        return result
    text = fold(text).strip()
    text = re.sub(r"^(?:(?:je (?:veux|souhaite|voudrais) )?exclure|exclusions?)\s*:?\s*", "", text)
    # Match entire list items, never pick a known ticker out of unsupported prose
    # (e.g. 'SPY et le tabac') or invert a negated/conditional request.
    aliases = {}
    for ticker, asset in assets.items():
        for alias in asset_aliases(ticker, asset):
            aliases.setdefault(fold(alias), set()).add(ticker)
    parts = [part.strip().rstrip('.').strip() for part in re.split(r"[,;\n]|\s+et\s+", text)]
    resolved = [aliases.get(part, set()) for part in parts]
    if resolved and all(len(found) == 1 for found in resolved):
        result["excluded_tickers"] = sorted(set().union(*resolved))
    return result


def match_profile(answers, assessment, requirements, config, assets, exposures=None):
    if (answers["exclusions"] != "none" and not requirements.get("excluded_tickers")
            and not answers.get("_preferences", {}).get("excluded_classes")):
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
    preferences = answers.get("_preferences", {})
    preferred_tickers = set(preferences.get("tickers", []))
    preferred_styles = set(preferences.get("styles", []))
    if not classes:
        raise InvestorInputError("UNSUPPORTED_ASSET_PREFERENCES",
            "Les classes d'actifs demandées ne sont pas disponibles dans le moteur. Choisissez au moins une classe prise en charge ; aucune préférence de remplacement n'a été supposée.")
    from .exposures import SECTORS
    catalog_sectors = set().union(*(SECTORS[s] for s in answers["sectors"]))
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
        measured_sector, measured_coverage = 0., 0.
        if exposures is not None:
            for ticker, weight in weights.items():
                row = exposures.get(ticker, {})
                allocation = row.get("sectors")
                if allocation is not None and row.get("sectors_basis") == "GICS":
                    fractions = allocation["fractions"]
                    measured_sector += weight * sum(v for key, v in fractions.items() if key in catalog_sectors)
                    measured_coverage += weight * sum(fractions.values())
                elif assets[ticker]["asset_class"] == "equity":
                    measured_sector += weight * (assets[ticker]["sector"] in sectors)
                    measured_coverage += weight
        ranking_sector = measured_sector if exposures is not None else sector_score
        ticker_score = sum(w for t, w in weights.items() if t in preferred_tickers)
        candidates.append({"profile_id": p["id"], "style": p["style"],
                           "asset_preference_weight": round(class_score, 8),
                           "direct_sector_preference_weight": round(sector_score, 8),
                           "measured_sector_preference_weight": round(ranking_sector, 8),
                           "sector_coverage_weight": round(measured_coverage, 8),
                           "ticker_preference_weight": round(ticker_score, 8),
                           "style_preference_match": p["style"] in preferred_styles,
                           "score": round(class_score + ranking_sector + ticker_score, 8)})
    if not candidates:
        raise InvestorInputError("NO_COMPATIBLE_REFERENCE_PROFILE",
            "No reference profile matches the explicit band and constraints. No constraints were relaxed.",
            {"risk_band": band, "rejected_candidates": rejected})
    candidates.sort(key=lambda p: (-p["score"], not p["style_preference_match"],
                                   -p["sector_coverage_weight"], p["style"] != "Broad diversifier", p["profile_id"]))
    chosen = candidates[0]
    selected_weights = next(p["weights"] for p in config["profiles"] if p["id"] == chosen["profile_id"])
    unmatched = {"asset_classes": sorted(code for code in answers["assets"] if not any(
                    w > 0 and assets[t]["asset_class"] in CLASS_PREFERENCES[code] for t, w in selected_weights.items())),
                 "tickers": sorted(preferred_tickers - {t for t, w in selected_weights.items() if w > 0}),
                 "styles": sorted(preferred_styles - {chosen["style"]})}
    return {"profile_id": chosen["profile_id"], "risk_band": band, "style": chosen["style"],
            "unmatched_preferences": unmatched,
            "preference_inputs": {"asset_classes": sorted(classes), "direct_stock_sectors": sorted(sectors)},
            "selected_overlap": {"asset_class_weight": chosen["asset_preference_weight"],
                                 "direct_sector_weight": chosen["direct_sector_preference_weight"],
                                 "measured_sector_weight": chosen["measured_sector_preference_weight"],
                                 "ticker_preference_weight": chosen["ticker_preference_weight"]},
            "method": "questionnaire_preference_overlap_v2",
            "ranking_policy": {"formula": "asset_class_weight + measured_sector_weight + preferred_ticker_weight",
                               "style_usage": "explicit_assessment_filter_or_inferred_tiebreak",
                               "sector_source": "dated_catalog_GICS_with_direct_stock_fallback" if exposures is not None else "direct_stocks_only",
                               "optimality_scope": "eligible_reference_profiles_only"},
            "risk_mapping_source": "explicit_assessment" if "risk_band" in assessment else
                policy.get("version", "approved_five_to_three_v1"),
            "candidates": candidates, "rejected_candidates": rejected,
            "reasons": [f"The selected reference profile uses the explicitly matched {band} band.",
                "Les profils admissibles sont comparés par poids dans les classes d'actifs souhaitées, secteurs documentés et actifs explicitement préférés ; un style déduit ne peut pas éliminer un meilleur candidat."],
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
    from .request_language import asset_mentions, asset_aliases, ambiguous, fold, intent, quantities

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
        for alias in asset_aliases(ticker, assets[ticker]):
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
