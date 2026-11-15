"""Bounded engine-checked alternatives and review provenance on one captured snapshot."""
from copy import deepcopy

from .evidence import fingerprint
from alphaforge.domain.exposures import exposure_review
from alphaforge.domain.portfolio_review import (
    REVIEW_METHOD, SEARCH_METHOD, MAX_CANDIDATES, MAX_SUGGESTIONS,
    review_portfolio, transfer_plans, candidate_rejections, choose_suggestions,
)


def exposures_for(evaluation, weights):
    if "asset_exposures" not in evaluation:
        return None
    return exposure_review(weights, evaluation["asset_exposures"], evaluation["questionnaire_answers"],
                           evaluation["allowed_tickers"], evaluation["asset_metadata"], evaluation["constraints"])


def checked_rejections(review, plan, outcome, evaluation, current_exposures):
    reasons = candidate_rejections(review, plan, outcome, evaluation["asset_metadata"], evaluation["allowed_tickers"])
    if reasons or current_exposures is None:
        return reasons
    proposed = exposures_for(evaluation, outcome["weights"])
    before = current_exposures["dimensions"]["sectors"]
    after = proposed["dimensions"]["sectors"]
    if after["covered_pct"] < before["covered_pct"] - 1e-6:
        reasons.append("SECTOR_COVERAGE_WORSENED")
    if proposed["preferred_sector_weight_pct"] < current_exposures["preferred_sector_weight_pct"] - 1e-6:
        reasons.append("SECTOR_PREFERENCE_ALIGNMENT_WORSENED")
    return reasons


def checked_suggestions(review, records, evaluation, current_exposures):
    suggestions = choose_suggestions(review, [r for r in records if not r["rejections"]],
                                     evaluation["asset_metadata"], evaluation["allowed_tickers"])
    if current_exposures is not None:
        for candidate in suggestions:
            candidate_exposures = exposures_for(evaluation, candidate["weights"])
            candidate["exposure_comparison"] = {
                "preferred_sector_weight_pct": {"before": current_exposures["preferred_sector_weight_pct"],
                                                "after": candidate_exposures["preferred_sector_weight_pct"]},
                "sector_covered_pct": {"before": current_exposures["dimensions"]["sectors"]["covered_pct"],
                                       "after": candidate_exposures["dimensions"]["sectors"]["covered_pct"]}}
    return suggestions


def build_analysis(engine, evaluation, selected, manifest, remaining_ms, begin_search=None):
    branch = selected or "as_requested"
    evaluated = evaluation[branch]
    assets = evaluation["asset_metadata"]
    review = review_portfolio(evaluated["weights"], evaluated["validation"], assets, evaluation["profile_match"])
    exposures = exposures_for(evaluation, evaluated["weights"])
    if begin_search:
        begin_search()
    records, status = [], "complete"
    plans = transfer_plans(evaluated["weights"], assets) if selected else []
    if not selected:
        status = "no_passing_portfolio"
    for plan in plans:
        if remaining_ms() < 45000:
            status = "budget_limited"
            break
        try:
            outcome = engine.evaluate_candidate(evaluation["profile_match"]["profile_id"], plan["changes"],
                starting_weights=evaluated["weights"], constraints=evaluation["constraints"], remaining_ms=remaining_ms)
        except TimeoutError:
            status = "budget_limited"
            break
        records.append({"plan": plan, "outcome": outcome,
                        "rejections": checked_rejections(review, plan, outcome, evaluation, exposures)})
    return {"method": REVIEW_METHOD, "manifest_hash": fingerprint(manifest), "reviewed_branch": branch,
            "review": review, "search": {"method": SEARCH_METHOD, "status": status,
                "max_candidates": MAX_CANDIDATES, "max_suggestions": MAX_SUGGESTIONS, "candidates": records},
            "suggestions": checked_suggestions(review, records, evaluation, exposures),
            **({"exposures": exposures} if exposures is not None else {})}


def public_analysis(package):
    """Only qualifying alternatives leave the audit boundary."""
    public = deepcopy({key: value for key, value in package.items() if key != "search"})
    public["search"] = {**{key: value for key, value in package["search"].items() if key != "candidates"},
                        "evaluated_candidates": len(package["search"]["candidates"])}
    return public


def analysis_errors(package, evaluation, selected, manifest):
    """Rebuild derived findings and selection before releasing any optional candidate."""
    try:
        branch = selected or "as_requested"
        evaluated, assets = evaluation[branch], evaluation["asset_metadata"]
        expected = review_portfolio(evaluated["weights"], evaluated["validation"], assets, evaluation["profile_match"])
        expected_exposures = exposures_for(evaluation, evaluated["weights"])
        errors = []
        if package["method"] != REVIEW_METHOD or package["manifest_hash"] != fingerprint(manifest):
            errors.append("STALE_REVIEW")
        if package["reviewed_branch"] != branch or package["review"] != expected:
            errors.append("REVIEW_FACT_MISMATCH")
        if package.get("exposures") != expected_exposures:
            errors.append("EXPOSURE_REVIEW_MISMATCH")
        if expected_exposures is not None and "exposures" not in manifest["inputs"]:
            errors.append("MISSING_EXPOSURE_PROVENANCE")
        search, candidates = package["search"], package["search"]["candidates"]
        plans = transfer_plans(evaluated["weights"], assets) if selected else []
        if (search["method"] != SEARCH_METHOD or search["max_candidates"] != MAX_CANDIDATES
                or search["max_suggestions"] != MAX_SUGGESTIONS or len(candidates) > len(plans)
                or [c["plan"] for c in candidates] != plans[:len(candidates)]):
            errors.append("INVALID_SUGGESTION_SEARCH")
        if search["status"] not in {"complete", "budget_limited", "no_passing_portfolio"}:
            errors.append("INVALID_SEARCH_STATUS")
        if (search["status"] == "complete" and len(candidates) != len(plans)) or (
                (search["status"] == "no_passing_portfolio") != (selected is None)):
            errors.append("INCOMPLETE_SUGGESTION_SEARCH")
        for candidate in candidates:
            if candidate["rejections"] != checked_rejections(expected, candidate["plan"], candidate["outcome"], evaluation, expected_exposures):
                errors.append("CANDIDATE_CHECK_MISMATCH")
        if package["suggestions"] != checked_suggestions(expected, candidates, evaluation, expected_exposures):
            errors.append("UNVERIFIED_SUGGESTION")
        return errors
    except (ValueError, KeyError, TypeError, AttributeError):
        return ["INVALID_PORTFOLIO_ANALYSIS"]
