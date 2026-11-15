"""Prepare matching/personalization inputs and the existing frontend result view."""
from copy import deepcopy

from .contracts import RecommendationRequest
from .snapshots import DataUnavailable
from alphaforge.domain.profile_matching import (InvestorInputError, investible_universe,
                                               match_profile, resolve_message)


def validate_requested_assets(request, assets):
    """Resolve user edits against the universe before matching or engine calls."""
    changes = [c.to_dict() for c in request.changes]
    if request.message is not None:
        changes = [resolve_message(request.message, assets, request.conversation)]
    tickers = {c.get("ticker", c.get("exclude")) for c in changes}
    unknown = tickers - set(assets)
    if unknown:
        raise InvestorInputError("ASSET_NOT_IN_UNIVERSE",
            "The requested asset is absent from assets_universe.csv. No calculation was performed.",
            {"tickers": sorted(unknown)})
    unsupported = tickers - investible_universe(assets)
    if unsupported:
        raise InvestorInputError("UNSUPPORTED_ASSET_CLASS",
            "The requested asset exists in the universe but is not a supported portfolio holding.",
            {"tickers": sorted(unsupported)})
    return changes


def prepare_investor(request, snapshot, changes):
    answers, missing = request.normalized_answers()
    if missing:
        raise InvestorInputError("QUESTIONNAIRE_INCOMPLETE",
            "Le questionnaire est incomplet. Veuillez remplir les réponses obligatoires avant de demander un portefeuille.",
            {"missing_answers": missing})
    match = match_profile(answers, request.assessment, request.requirements, snapshot.profiles, snapshot.assets)
    profile = deepcopy(next(p for p in snapshot.profiles["profiles"] if p["id"] == match["profile_id"]))
    effective = RecommendationRequest.from_dict({"profile_id": profile["id"], "changes": changes,
                                                  "as_of": request.as_of.isoformat()})
    baseline = request.current_weights if request.current_weights is not None else profile["weights"]
    weights = {t: w for t, w in baseline.items() if w > 0}
    required = set(weights) | {c.ticker for c in effective.changes}
    outside = required - investible_universe(snapshot.assets)
    if outside:
        raise InvestorInputError("ASSET_NOT_IN_UNIVERSE",
            "I cannot assess these holdings as investible assets using our dataset. No outside asset was substituted.",
            {"tickers": sorted(outside)})
    absent = required - set(snapshot.prices.ticker)
    if absent:
        raise InvestorInputError("MISSING_HOLDING_HISTORY",
            "The matched reference portfolio or requested change needs price history that is missing from this snapshot.",
            {"tickers": sorted(absent), "matched_profile_id": profile["id"]})
    inconsistent = sorted(t for t in required
        if not snapshot.prices.loc[snapshot.prices.ticker == t, "currency"].eq(snapshot.assets[t]["currency"]).all())
    if inconsistent:
        raise InvestorInputError("ASSET_CURRENCY_MISMATCH",
            "Required holding currencies disagree between the price file and asset metadata. No conversion assumptions were substituted.",
            {"tickers": inconsistent})
    constraints = {
        **request.requirements,
        "crypto_tickers": sorted(t for t, a in snapshot.assets.items() if a["asset_class"] == "crypto"),
        "etf_tickers": sorted(t for t, a in snapshot.assets.items() if a["asset_class"].startswith("etf_")),
    }
    if "crypto" not in answers["assets"]:
        constraints["max_crypto_weight_pct"] = 0
    match["operation"] = "personalize" if changes or request.current_weights is not None else "match"
    match["reference_weights"] = profile["weights"]
    match["starting_weights_source"] = "submitted_current_portfolio" if request.current_weights is not None else "matched_reference"
    return effective, profile, dict(weights), constraints, match


def frontend_recommendation(run_id, public, match, assets):
    """Only called after evidence and release checks have accepted a portfolio."""
    weights = public["portfolio"]["weights"]
    positions = [{"symbol": ticker, "name": assets[ticker]["name"],
                  "category": assets[ticker]["sector"], "group": assets[ticker]["asset_class"],
                  "weight": round(weight * 100, 8)} for ticker, weight in sorted(weights.items()) if weight > 0]
    entries = public["evidence"]["entries"]
    result = {"runId": run_id,
              "portfolio": {"id": str(match["profile_id"]), "name": match["style"], "positions": positions},
              "explanation": public["explanation"],
              "evidence": [{"id": e["id"], "source": e["source"], "description": e["sentence"]} for e in entries],
              "limitations": public["limitations"], "compliance": public["compliance"]}
    # Keep the transport within the existing frontend contract; never truncate facts.
    if len(entries) > 100 or len(result["explanation"]) > 10000:
        raise DataUnavailable("FRONTEND_RESPONSE_TOO_LARGE")
    return result
