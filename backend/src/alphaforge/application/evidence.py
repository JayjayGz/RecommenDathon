"""Deterministic facts and limitations for the existing proposal evaluation API."""
import hashlib
import json
import math

DISCLAIMER = "Educational simulation, not investment advice. Historical results do not predict future performance."
LIMITATIONS = [
    "This assessment uses reference-profile policy; questionnaire matching and ESG/sector screening are not implemented.",
    "Prices use adjusted closes, CAD conversion with prior available FX, and common observation dates.",
    "Annualization uses 52 observations per year for weekly history and 252 for daily history; cadence checks do not certify a trading calendar.",
    "Monthly rebalancing occurs at the first observed close of each month after valuing existing holdings; weekly history omits intraweek moves and drawdowns.",
    "Asset selection may contain survivorship bias; adjusted historical prices can be revised.",
    "No transaction costs, taxes, liquidity model, fundamentals or publication-aware macro strategy are included.",
    "This deterministic release check is not a legal suitability or compliance determination.",
]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def build_evidence(run_id, manifest, evaluation, selected_branch):
    manifest_hash = fingerprint(manifest)
    entries = []

    def add(field, value, unit, sentence, source):
        entries.append({"id": f"{run_id}:E{len(entries) + 1}", "field": field,
                        "value": value, "unit": unit, "sentence": sentence,
                        "source": source, "manifest_hash": manifest_hash,
                        "method": "proposal_evidence_v3_portfolio_review"})

    match = evaluation.get("profile_match")
    if match:
        mapping_description = ("the explicitly supplied assessed risk band" if match["risk_mapping_source"] == "explicit_assessment"
                               else "the configured questionnaire-to-band mapping")
        add("profile_match", {"id": match["profile_id"], "band": match["risk_band"], "style": match["style"]},
            "reference_profile", f"Reference profile {match['profile_id']} ({match['style']}) was matched "
            f"in the {match['risk_band']} band using {mapping_description}.", "profiles.json")
        for index, reason in enumerate(match["reasons"]):
            add(f"profile_match.reason.{index}", reason, "matching_reason", reason, match["method"])
        if "questionnaire_mapping" in match:
            add("profile_match.questionnaire_mapping", match["questionnaire_mapping"], "mapping_scores",
                "La correspondance utilise le minimum des scores de capacité et de tolérance du questionnaire ; ce classement de référence ne constitue pas une évaluation financière complète.",
                "domain.profile_mapping/capacity_tolerance_style_v1")
        overlap = match["selected_overlap"]
        add("profile_match.overlap", {"preferences": match["preference_inputs"], **overlap}, "matching_weights",
            f"The selected template has {overlap['asset_class_weight'] * 100:g}% in the requested asset classes "
            f"and {overlap['direct_sector_weight'] * 100:g}% in directly held stocks in the requested sectors. "
            "These overlaps explain its template ranking; they do not establish future performance or investor suitability.",
            "profiles.json_and_assets_universe.csv")
        descriptions = []
        for change in evaluation["requested_changes"]:
            if "exclude" in change:
                descriptions.append(f"exclude {change['exclude']}")
            else:
                verb = "add" if change["add_pct"] >= 0 else "reduce"
                descriptions.append(f"{verb} {abs(change['add_pct']):g} percentage points {'to' if verb == 'add' else 'from'} {change['ticker']}")
        changes_description = "; ".join(descriptions) if descriptions else "no allocation edits"
        add("requested_changes", evaluation["requested_changes"], "percentage_point_edits",
            f"Requested edits: {changes_description}. Additions are percentage-point changes, not target total weights.",
            "validated_personalization_request")
        if "change_review" in evaluation:
            review = evaluation["change_review"]
            add("change_review", review, "questionnaire_change_assessment", review["conclusion"],
                "questionnaire_and_checked_portfolio_evaluation")
        add("funding_policy", evaluation["funding_policy"], "method",
            "Additions use proportional non-bond funding; unedited bonds are preserved before whole-percent rounding. Residual goes to the largest bond (ticker breaks ties). Adjusted proposals do not guarantee requested weights.",
            "domain.proposals.apply_proposal")
        add("starting_weights_source", match["starting_weights_source"], "source",
            "This assessment starts from " + ("the submitted current portfolio" if match["starting_weights_source"] == "submitted_current_portfolio" else "the matched reference portfolio") +
            "; its weights and every new proposal are re-evaluated against the matched profile's current policy and snapshot.",
            "validated_personalization_request")
        for index, note in enumerate(evaluation["notes"]):
            add(f"adjustment.{index}", note, "actual_decision", note, "domain.proposals.apply_proposal")
        for ticker, maximum in sorted(evaluation["max_allowed"].items()):
            result_description = (f"the searched conditional maximum addition is {maximum} percentage points"
                                  if maximum is not None else "no passing addition was found")
            add(f"conditional_maximum.{ticker}", maximum, "additional_percentage_points",
                f"For {ticker}, {result_description} within the requested range. Separate maxima cannot be combined.",
                "PortfolioEngine.evaluate/uncapped_trials")
        macro = evaluation.get("macro_context")
        if macro:
            add("macro.bond_scope", macro["applies_to_tickers"], "bond_tickers",
                "Macro observations apply only to bond assets evaluated in this request: " +
                ", ".join(macro["applies_to_tickers"]) + ". Equities and other supported asset classes are checked using price history.",
                "assets_universe.csv")
            for row in macro["series"]:
                availability = (f"a release date of {row['release_date']} is supplied"
                                if row["release_date"] else "publication timing is unverified")
                add(f"macro.{row['series_id']}", row, "macro_dataset_observation",
                    f"Bond context {row['series_id']}: {row['value']:g} {row['unit']} at {row['reference_date']}; "
                    f"{availability}. No allocation effect.",
                    "macro_rates.csv")

    status = evaluation["status"]
    add("requested.status", status, "status", f"The requested proposal has assessment status {status}.",
        "PortfolioEngine.evaluate/as_requested")
    add("selected_branch", selected_branch, "branch",
        (f"The {selected_branch} allocation passed the implemented profile checks." if selected_branch else
         "No evaluated allocation is released as a passing portfolio."), "PortfolioEngine.evaluate")
    branches = ("base", "as_requested", "adjusted") if evaluation.get("requested_changes") else ("as_requested", "adjusted")
    for branch in branches:
        item = evaluation.get(branch)
        if not item:
            continue
        if branch == "adjusted" and selected_branch != "adjusted" and item == evaluation.get("as_requested"):
            continue  # The same weights/metrics need one set of claims, not duplicated prose.
        validation = item["validation"]
        if validation.get("status") not in {"PASS", "CONFLICT"}:
            continue
        period = validation["period"]
        add(f"{branch}.annualization", {"frequency": validation["observation_frequency"],
                                      "observations_per_year": validation["annualization_observations"]},
            "observation_convention",
            f"The {branch} metrics use {validation['observation_frequency']} observations "
            f"and {validation['annualization_observations']} observations per year.",
            validation["annualization_method"])
        add(f"{branch}.period", period, "dates_and_count",
            f"The {branch} simulation spans {period['first_date']} to {period['last_date']} "
            f"with {period['observations']} common observations in CAD.", validation["method"])
        for metric in ("annual_growth_pct", "volatility_pct", "max_drawdown_pct"):
            value = validation[metric]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Nonfinite or missing metric")
            add(f"{branch}.{metric}", value, "percent",
                f"The {branch} historical {metric} is {value:g}%.", validation["method"])
        for name, check in sorted(validation["checks"].items()):
            if check["passes"] is not True:
                add(f"{branch}.checks.{name}", check, "policy_check",
                    f"The {branch} allocation fails the implemented {name} check "
                    f"(observed {check['value']}, limit {check['limit']}).", "profile_policy")
    if selected_branch:
        selected = evaluation[selected_branch]
        for ticker, weight in sorted(selected["weights"].items()):
            add(f"selected.weights.{ticker}", weight, "fraction",
                f"The passing allocation assigns {weight * 100:g}% to {ticker}.", "PortfolioEngine.evaluate")
            if match:
                asset = evaluation["asset_metadata"][ticker]
                add(f"selected.asset.{ticker}", asset, "dataset_asset_metadata",
                    f"{ticker}: classified as {asset['asset_class']}, sector {asset['sector']} in the dataset.",
                    "assets_universe.csv")
                previous = evaluation["base"]["weights"].get(ticker, 0)
                if abs(previous - weight) > 1e-8:
                    add(f"selected.change.{ticker}", {"before": previous, "after": weight}, "weight_fractions",
                        f"The proposed weight of {ticker} changes from {previous * 100:g}% to {weight * 100:g}%.",
                        "PortfolioEngine.evaluate/base_and_selected")
        if match:
            for ticker, previous in sorted(evaluation["base"]["weights"].items()):
                if previous > 0 and ticker not in selected["weights"]:
                    add(f"selected.removed.{ticker}", {"before": previous, "after": 0}, "weight_fractions",
                        f"The proposed allocation removes the previous {previous * 100:g}% position in {ticker}.",
                        "PortfolioEngine.evaluate/base_and_selected")
    analysis = evaluation.get("portfolio_analysis")
    if analysis:
        review = analysis["review"]
        if "exposures" in analysis:
            add("review.exposures", analysis["exposures"], "weighted_catalog_exposures",
                "Les expositions et pistes d’actifs proviennent des répartitions datées du catalogue, pondérées par le portefeuille. Les données inconnues restent explicites et les pistes ne sont ni pondérées ni appliquées.",
                "exposures_profile_tickers.csv/evaluated_weights")
        split = lambda values: ", ".join(f"{k}: {v:g}%" for k, v in sorted(values.items())) or "none"
        selection = review["selection"]
        add("review.selection", selection, "reference_allocation_rules",
            f"The {selection['risk_band']} reference template uses {split(selection['reference_asset_class_weights_pct'])}. "
            "These are reference rules, not individually optimized weights.", "profiles.json/assets_universe.csv")
        add("review.composition", {"asset_classes": review["asset_class_weights_pct"],
                                   "listing_currencies": review["listing_currency_weights_pct"]}, "percent",
            f"Evaluated asset classes: {split(review['asset_class_weights_pct'])}. "
            f"Listing currencies: {split(review['listing_currency_weights_pct'])}; these are not underlying currency exposures.",
            "assets_universe.csv/evaluated_weights")
        sectors = review["sectors"]
        add("review.sectors", sectors, "direct_stock_sector_percent",
            f"Secteurs des actions directes : {split(sectors['weights_pct'])} ; {sectors['unclassified_pct']:g}% n’est pas attribué à une action directe. "
            "Les répartitions de fonds disponibles sont analysées séparément dans les expositions du catalogue.", "assets_universe.csv/evaluated_weights")
        d = review["diversification"]
        add("review.diversification", d, "listed_position_concentration",
            f"There are {d['holding_count']} listed holdings; largest is {d['largest_ticker']} at {d['largest_weight_pct']:g}%. "
            f"Holding HHI is {d['holding_hhi']:g}, equivalent to {d['effective_holdings']:.3f} equal-weight positions, not underlying securities.",
            "portfolio_review_v1/evaluated_weights")
        add("review.findings", {"findings": review["findings"], "profile_fit": review["profile_fit"], "risk": review["risk"]},
            "deterministic_findings", f"Profile-check result: {review['profile_fit']['status']}. "
            "Unequal holding weights are observations, not an additional risk threshold. Historical metrics and failed checks govern profile fit.",
            "PortfolioEngine.validate/portfolio_review_v1")
        search = analysis["search"]
        add("suggestion.search", {k: v for k, v in search.items() if k != "candidates"}, "bounded_search",
            f"Optional search is {search['status']}: {len(search['candidates'])} same-class held-asset candidates evaluated; "
            f"{len(analysis['suggestions'])} qualify. This is a bounded search, not an optimal allocation. Candidates are independent and not applied.",
            search["method"])
        for suggestion in analysis["suggestions"]:
            comparison = suggestion["comparison"]
            changes = ", ".join(f"{c['ticker']} {c['add_pct']:+g}pp" for c in suggestion["changes"])
            metrics = "; ".join(f"{m}: {comparison[m]['before']:g}% to {comparison[m]['after']:g}%"
                                for m in ("annual_growth_pct", "volatility_pct", "max_drawdown_pct"))
            add(f"suggestion.{suggestion['id']}", suggestion, "engine_checked_optional_alternative",
                f"Candidate {suggestion['id']} requests {changes}. Holding HHI falls from "
                f"{comparison['holding_hhi']['before']:g} to {comparison['holding_hhi']['after']:g}; {metrics}. "
                "All checks pass; asset-class totals are preserved. This independent alternative has not been applied.",
                "PortfolioEngine.evaluate_candidate/portfolio_review_v1")
    limitations = (LIMITATIONS[1:] + match["limitations"] if match else LIMITATIONS) + [
        f"Input snapshot as-of date: {manifest['as_of']}; later observations are excluded."]
    if evaluation.get("macro_context"):
        limitations += evaluation["macro_context"]["limitations"]
    if analysis:
        limitations += analysis["review"]["limitations"]
        if "exposures" in analysis:
            limitations += analysis["exposures"]["limitations"]
    return {"run_id": run_id, "manifest_hash": manifest_hash, "entries": entries,
            "limitations": limitations, "disclaimer": DISCLAIMER}


def fallback_draft(bundle):
    return {"claim_ids": [e["id"] for e in bundle["entries"]]}


def validate_draft(draft, bundle):
    """Model may order vetted sentences, never supply unverified free-form claims."""
    if not isinstance(draft, dict) or set(draft) != {"claim_ids"}:
        return ["EXPECTED_CLAIM_IDS_ONLY"]
    ids = draft["claim_ids"]
    expected = [e["id"] for e in bundle["entries"]]
    if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
        return ["INVALID_CLAIM_IDS"]
    if len(ids) != len(expected) or set(ids) != set(expected):
        return ["UNKNOWN_DUPLICATE_OR_MISSING_CLAIM"]
    return []


def render(draft, bundle):
    entries = {e["id"]: e for e in bundle["entries"]}
    return "\n".join([bundle["disclaimer"]] +
                     [f"{entries[i]['sentence']} [{i}]" for i in draft["claim_ids"]] +
                     ["Limitations:"] + bundle["limitations"])


def release_errors(bundle, manifest, evaluation, selected_branch):
    errors = []
    if evaluation.get("profile_match") and evaluation.get("requested_changes"):
        from .change_review import build_change_review
        try:
            if evaluation.get("change_review") != build_change_review(evaluation, selected_branch):
                errors.append("INVALID_CHANGE_REVIEW")
        except (KeyError, ValueError, TypeError):
            errors.append("INVALID_CHANGE_REVIEW")
    if evaluation.get("profile_match") and not evaluation.get("portfolio_analysis"):
        errors.append("MISSING_PORTFOLIO_ANALYSIS")
    if evaluation.get("portfolio_analysis") is not None:
        from .portfolio_review import analysis_errors
        errors += analysis_errors(evaluation["portfolio_analysis"], evaluation, selected_branch, manifest)
    macro = evaluation.get("macro_context")
    if macro and (not macro.get("applies_to_tickers") or any(
            evaluation.get("asset_metadata", {}).get(ticker, {}).get("asset_class") != "etf_bond"
            for ticker in macro["applies_to_tickers"])):
        errors.append("MACRO_SCOPE_MISMATCH")
    if evaluation["status"] == "PASS" and selected_branch != "as_requested":
        errors.append("INCONSISTENT_VERDICT")
    if bundle != build_evidence(bundle["run_id"], manifest, evaluation, selected_branch):
        errors.append("UNSUPPORTED_OR_CHANGED_EVIDENCE")
    if bundle["manifest_hash"] != fingerprint(manifest):
        errors.append("STALE_EVIDENCE")
    if any(e["manifest_hash"] != bundle["manifest_hash"] for e in bundle["entries"]):
        errors.append("STALE_CLAIM")
    if selected_branch:
        selected = evaluation[selected_branch]
        validation = selected["validation"]
        weights = selected["weights"]
        if evaluation.get("profile_match") and set(weights) - set(evaluation["allowed_tickers"]):
            errors.append("ASSET_OUTSIDE_DATASET")
        if (validation.get("status") != "PASS" or validation.get("passes") is not True or
                not validation.get("checks") or
                any(c.get("passes") is not True for c in validation["checks"].values())):
            errors.append("PORTFOLIO_CHECK_FAILED")
        if (not weights or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0
                               for v in weights.values()) or abs(sum(weights.values()) - 1) > 1e-6):
            errors.append("INVALID_WEIGHTS")
    return errors
