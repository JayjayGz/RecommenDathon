"""Prepare matching/personalization inputs and the existing frontend result view."""
from copy import deepcopy

from .contracts import RecommendationRequest
from .snapshots import DataUnavailable
from alphaforge.domain import profile_mapping
from alphaforge.domain.profile_matching import (InvestorInputError, investible_universe,
                                               match_profile, resolve_message, questionnaire_requirements)


def validate_requested_assets(request, assets, interpret=None):
    """Resolve user edits against the universe before matching or engine calls."""
    changes = [c.to_dict() for c in request.changes]
    if request.message is not None:
        try:
            changes = [resolve_message(request.message, assets, request.conversation, interpret=interpret)]
        except InvestorInputError as error:
            if error.code == "ALLOCATION_AMOUNT_REQUIRED":
                from .change_review import unweighted_asset_review
                ticker = error.details["ticker"]
                raise InvestorInputError(error.code,
                    unweighted_asset_review(request.normalized_answers()[0], ticker, assets[ticker], request.requirements,
                                           operation=error.details.get("operation")),
                    error.details) from error
            raise
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


def prepare_investor(request, snapshot, changes, interpretation=None, exposures=None):
    answers, missing = request.normalized_answers()
    if missing:
        raise InvestorInputError("QUESTIONNAIRE_INCOMPLETE",
            "Le questionnaire est incomplet. Veuillez remplir les réponses obligatoires avant de demander un portefeuille.",
            {"missing_answers": missing})
    assessment = dict(request.assessment)
    if interpretation is not None:
        blocking = [f for f in interpretation["findings"] if f["blocking"]]
        if blocking:
            code = ("EXCLUSIONS_NEED_CLARIFICATION" if all(
                f["field"].endswith("exclusions_details") or f["field"] == "exclusionDetails" for f in blocking)
                else "QUESTIONNAIRE_NEEDS_CLARIFICATION")
            raise InvestorInputError(code,
                " ".join(dict.fromkeys(f["message"] for f in blocking)),
                {"clarifications": [{"code": f["code"], "field": f["field"]} for f in blocking]})
        answers = deepcopy(interpretation["answers"])
    mapping = None
    if answers.get("knowledge") is not None:
        mapped = profile_mapping.to_assessment(answers)
        mapping = {"method": "capacity_tolerance_style_v1", "capacity_score": profile_mapping.capacity_score(answers),
                   "tolerance_score": profile_mapping.tolerance_score(answers),
                   "risk_level": profile_mapping.risk_level(answers), "mapped_assessment": mapped,
                   "explicit_overrides": dict(assessment)}
        # A derived style is a tie-break preference, never a filter that discards
        # other admissible templates before their actual holdings are compared.
        assessment = {"risk_band": mapped["risk_band"], **assessment}
        answers.setdefault("_preferences", {}).setdefault("styles", []).append(mapped["preferred_style"])
    requirements = questionnaire_requirements(answers, request.requirements, snapshot.assets)
    if interpretation is not None:
        combined = set(requirements.get("excluded_tickers", [])) | set(interpretation["requirements"].get("excluded_tickers", []))
        if combined:
            requirements["excluded_tickers"] = sorted(combined)
    match = match_profile(answers, assessment, requirements, snapshot.profiles, snapshot.assets,
                          exposures if answers.get("knowledge") is not None else None)
    match["assessment_used"] = deepcopy(assessment)
    match["requirements_used"] = deepcopy(requirements)
    if requirements.get("excluded_tickers") != request.requirements.get("excluded_tickers"):
        match["questionnaire_exclusions"] = {"method": "exact_catalogue_list_v1",
                                             "excluded_tickers": requirements["excluded_tickers"]}
    if mapping:
        match["questionnaire_mapping"] = mapping
        if "risk_band" not in request.assessment:
            match["risk_mapping_source"] = mapping["method"]
        match["reasons"].append("La bande de référence provient des scores de tolérance et de capacité du module fourni ; les évaluations explicites restent identifiées séparément.")
        match["limitations"][1] = "Les scores de référence utilisent les connaissances, la réaction aux pertes, la tolérance déclarée, l’horizon et la stabilité des revenus. Ils ne valident pas la capacité financière complète et ne prévoient aucun rendement."
    if interpretation is not None:
        match["questionnaire_understanding"] = deepcopy(interpretation)
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
        **requirements,
        "crypto_tickers": sorted(t for t, a in snapshot.assets.items() if a["asset_class"] == "crypto"),
        "etf_tickers": sorted(t for t, a in snapshot.assets.items() if a["asset_class"].startswith("etf_")),
        "bond_tickers": sorted(t for t, a in snapshot.assets.items() if a["asset_class"] == "etf_bond"),
    }
    if "crypto" not in answers["assets"]:
        constraints["max_crypto_weight_pct"] = 0
    match["operation"] = "personalize" if changes or request.current_weights is not None else "match"
    match["reference_weights"] = profile["weights"]
    match["starting_weights_source"] = "submitted_current_portfolio" if request.current_weights is not None else "matched_reference"
    return effective, profile, dict(weights), constraints, match


def frontend_recommendation(run_id, public, match, assets):
    """Only called after evidence and release checks have accepted a portfolio."""
    from .french import STYLES, evidence_description
    weights = public["portfolio"]["weights"]
    positions = [{"symbol": ticker, "name": assets[ticker]["name"],
                  "category": assets[ticker]["sector"], "group": assets[ticker]["asset_class"],
                  "weight": round(weight * 100, 8)} for ticker, weight in sorted(weights.items()) if weight > 0]
    entries = public["evidence"]["entries"]
    result = {"runId": run_id,
              "portfolio": {"id": str(match["profile_id"]), "name": STYLES.get(match["style"], "Portefeuille simulé"), "positions": positions},
              "explanation": public["explanation"],
              "evidence": [{"id": e["id"], "source": e["source"], "description": evidence_description(e)} for e in entries],
              "limitations": public["limitations"], "compliance": public["compliance"]}
    if "change_review" in public:
        result["changeReview"] = deepcopy(public["change_review"])
    analysis = public.get("portfolio_analysis")
    if analysis:
        ids = {e["field"]: e["id"] for e in entries}
        suggestions = []
        for candidate in analysis["suggestions"]:
            candidate_positions = [{"symbol": t, "name": assets[t]["name"], "category": assets[t]["sector"],
                                    "group": assets[t]["asset_class"], "weight": round(w * 100, 8)}
                                   for t, w in sorted(candidate["weights"].items()) if w > 0]
            suggestions.append({**candidate, "portfolio": {"id": candidate["id"], "name": "Autre répartition pour examiner la concentration",
                                                           "positions": candidate_positions},
                                "evidence_ids": [ids[f"suggestion.{candidate['id']}"]]})
        result["analysis"] = {"method": analysis["method"], "manifest_hash": analysis["manifest_hash"],
                              "review": analysis["review"],
                              "evidence_ids": [e["id"] for e in entries if e["field"].startswith("review.")],
                              "search": deepcopy(analysis["search"]),
                              "suggestions": suggestions}
        if "exposures" in analysis:
            result["analysis"]["exposures"] = deepcopy(analysis["exposures"])
    # Keep the transport within the existing frontend contract; never truncate facts.
    if len(entries) > 100 or len(result["explanation"]) > 10000:
        raise DataUnavailable("FRONTEND_RESPONSE_TOO_LARGE")
    return result
