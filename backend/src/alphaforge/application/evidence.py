"""Deterministic facts and limitations for the existing proposal evaluation API."""
import hashlib
import json
import math

DISCLAIMER = "Educational simulation, not investment advice. Historical results do not predict future performance."
LIMITATIONS = [
    "This assessment uses reference-profile policy; questionnaire matching and ESG/sector screening are not implemented.",
    "Prices use adjusted closes, CAD conversion with prior available FX, and common observation dates.",
    "The engine assumes 252 observations per year; a cadence check rejects clearly sparse history but does not certify a trading calendar.",
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
                        "method": "proposal_workflow_v1"})

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
        add(f"{branch}.period", period, "dates_and_count",
            f"The {branch} simulation spans {period['first_date']} to {period['last_date']} "
            f"with {period['observations']} common observations in CAD.", validation["method"])
        for metric in ("annual_growth_pct", "volatility_pct", "max_drawdown_pct"):
            value = validation[metric]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Nonfinite or missing metric")
            add(f"{branch}.{metric}", value, "percent",
                f"The {branch} historical {metric} is {value:g}%.", validation["method"])
        for name, check in validation["checks"].items():
            if check["passes"] is not True:
                add(f"{branch}.checks.{name}", check, "policy_check",
                    f"The {branch} allocation fails the implemented {name} check "
                    f"(observed {check['value']}, limit {check['limit']}).", "profile_policy")
    if selected_branch:
        selected = evaluation[selected_branch]
        for ticker, weight in sorted(selected["weights"].items()):
            add(f"selected.weights.{ticker}", weight, "fraction",
                f"The passing allocation assigns {weight * 100:g}% to {ticker}.", "PortfolioEngine.evaluate")
    limitations = LIMITATIONS + [f"Input snapshot as-of date: {manifest['as_of']}; later observations are excluded."]
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
        if (validation.get("status") != "PASS" or validation.get("passes") is not True or
                not validation.get("checks") or
                any(c.get("passes") is not True for c in validation["checks"].values())):
            errors.append("PORTFOLIO_CHECK_FAILED")
        if (not weights or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0
                               for v in weights.values()) or abs(sum(weights.values()) - 1) > 1e-6):
            errors.append("INVALID_WEIGHTS")
    return errors
