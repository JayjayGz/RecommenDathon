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
                        "method": "proposal_evidence_v2_sorted_checks"})

    match = evaluation.get("profile_match")
    if match:
        mapping_description = ("the explicitly supplied assessed risk band" if match["risk_mapping_source"] == "explicit_assessment"
                               else "the configured questionnaire-to-band mapping")
        add("profile_match", {"id": match["profile_id"], "band": match["risk_band"], "style": match["style"]},
            "reference_profile", f"Reference profile {match['profile_id']} ({match['style']}) was matched "
            f"in the {match['risk_band']} band using {mapping_description}.", "profiles.json")
        for index, reason in enumerate(match["reasons"]):
            add(f"profile_match.reason.{index}", reason, "matching_reason", reason, match["method"])
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
        add("funding_policy", evaluation["funding_policy"], "method",
            "Additions are funded proportionally from other non-bond holdings. Bond edits change the requested bond; other evaluated bond weights are preserved before rounding. Weights are rounded to whole percentages and any residual goes to the largest evaluated bond holding, with ticker order breaking ties. An adjusted alternative is a checked proposal, not a guarantee that the requested weight can be included.",
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
                    f"Bond macro context: {row['label']} ({row['series_id']}) reports {row['value']:g} {row['unit']} "
                    f"for reference date {row['reference_date']}; {availability}. This observation does not change portfolio weights.",
                    "macro_rates.csv")

    status = evaluation["status"]
    add("requested.status", status, "status", f"The requested proposal has assessment status {status}.",
        "PortfolioEngine.evaluate/as_requested")
    add("selected_branch", selected_branch, "branch",
        (f"The {selected_branch} allocation passed the implemented profile checks." if selected_branch else
         "No evaluated allocation is released as a passing portfolio."), "PortfolioEngine.evaluate")
    for branch in ("as_requested", "adjusted"):
        item = evaluation.get(branch)
        if not item:
            continue
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
                    f"{ticker} is {asset['name']}, classified as {asset['asset_class']} in {asset['sector']} by the dataset.",
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
    limitations = (LIMITATIONS[1:] + match["limitations"] if match else LIMITATIONS) + [
        f"Input snapshot as-of date: {manifest['as_of']}; later observations are excluded."]
    if evaluation.get("macro_context"):
        limitations += evaluation["macro_context"]["limitations"]
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
