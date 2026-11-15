"""Deterministic, holding-level review; no ETF look-through or invented risk scores."""
from collections import defaultdict
from copy import deepcopy
import math

from .proposals import _check_weights

REVIEW_METHOD = "portfolio_review_v1"
SEARCH_METHOD = "same_class_held_transfers_v1"
MAX_CANDIDATES = 6
MAX_SUGGESTIONS = 2
METRICS = ("annual_growth_pct", "volatility_pct", "max_drawdown_pct")
CONVENTIONS = ("period", "observation_frequency", "annualization_observations", "annualization_method",
               "rebalance", "method", "currency")
LIMITATIONS = [
    "Sectors cover direct stocks only; ETF constituents and overlap are unavailable. Unclassified is not a sector.",
    "Holding concentration does not measure underlying diversification or independent risk. Unequal weights are not a policy violation.",
    "Same-class alternatives can change underlying exposures. Comparisons use rounded engine metrics. Concentration reduction is not suitability, optimization or a forecast.",
]


def asset_class_weights(weights, assets):
    totals = defaultdict(float)
    for ticker, weight in sorted(weights.items()):
        if weight > 0:
            totals[assets[ticker]["asset_class"]] += weight
    return {key: round(value * 100, 6) for key, value in sorted(totals.items())}


def transfer_plans(weights, assets):
    """At most six independent 1/3/5-point transfers within held asset classes."""
    groups = defaultdict(list)
    for ticker, weight in sorted(weights.items()):
        if weight > 0:
            groups[assets[ticker]["asset_class"]].append(ticker)
    pairs = []
    for asset_class, tickers in sorted(groups.items()):
        if len(tickers) < 2:
            continue
        source = sorted(tickers, key=lambda t: (-weights[t], t))[0]
        target = sorted(tickers, key=lambda t: (weights[t], t))[0]
        maximum = math.floor((weights[source] - weights[target]) * 50 + 1e-8)
        if maximum >= 1:
            pairs.append((-(weights[source] - weights[target]), asset_class, source, target, maximum))
    plans = []
    for _, asset_class, source, target, maximum in sorted(pairs):
        for points in (1, 3, 5):
            if points > maximum:
                continue
            plans.append({"id": f"C{len(plans) + 1}", "issue_id": f"position_concentration.{asset_class}",
                          "asset_class": asset_class, "from_ticker": source, "to_ticker": target,
                          "transfer_points": points,
                          "changes": [{"ticker": source, "add_pct": -points},
                                      {"ticker": target, "add_pct": points}]})
            if len(plans) == MAX_CANDIDATES:
                return plans
    return plans


def review_portfolio(weights, validation, assets, match):
    _check_weights(weights)
    active = {t: w for t, w in sorted(weights.items()) if w > 0}
    if any(type(validation.get(m)) not in (int, float) or not math.isfinite(validation[m]) for m in METRICS):
        raise ValueError("Portfolio review requires finite historical metrics")
    sectors, currencies = defaultdict(float), defaultdict(float)
    for ticker, weight in active.items():
        asset = assets[ticker]
        currencies[asset["currency"]] += weight * 100
        if asset["asset_class"] == "equity":
            sectors[asset["sector"]] += weight * 100
    covered = sum(sectors.values())
    hhi = sum(w * w for w in active.values())
    largest = sorted(active, key=lambda t: (-active[t], t))[0]
    checks = deepcopy(validation["checks"])
    failures = sorted(k for k, v in checks.items() if v.get("passes") is not True)
    groups = asset_class_weights(active, assets)
    findings = [{"id": "profile_fit", "kind": "conflict" if failures else "pass",
                 "failed_checks": failures},
                {"id": "sector_coverage", "kind": "limitation" if covered < 100 - 1e-6 else "information",
                 "covered_pct": round(covered, 6), "unclassified_pct": round(100 - covered, 6)}]
    for plan in transfer_plans(active, assets):
        if not any(f["id"] == plan["issue_id"] for f in findings):
            findings.append({"id": plan["issue_id"], "kind": "observation",
                             "asset_class": plan["asset_class"], "largest_ticker": plan["from_ticker"],
                             "comparison_ticker": plan["to_ticker"],
                             "weight_gap_pct": round((active[plan["from_ticker"]] - active[plan["to_ticker"]]) * 100, 6)})
    return {"method": REVIEW_METHOD, "weights": active, "asset_class_weights_pct": groups,
            "listing_currency_weights_pct": {k: round(v, 6) for k, v in sorted(currencies.items())},
            "sectors": {"scope": "direct_stocks_only", "weights_pct": {k: round(v, 6) for k, v in sorted(sectors.items())},
                        "covered_pct": round(covered, 6), "unclassified_pct": round(100 - covered, 6)},
            "diversification": {"holding_count": len(active), "largest_ticker": largest,
                                "largest_weight_pct": round(active[largest] * 100, 6),
                                "holding_hhi": round(hhi, 10), "effective_holdings": round(1 / hhi, 6)},
            "risk": {**{m: validation[m] for m in METRICS},
                     **{key: deepcopy(validation[key]) for key in CONVENTIONS}},
            "profile_fit": {"status": "CONFLICT" if failures else "PASS", "checks": checks, "failed_checks": failures},
            "selection": {"profile_id": match["profile_id"], "risk_band": match["risk_band"], "style": match["style"],
                          "risk_mapping_source": match["risk_mapping_source"],
                          "reference_asset_class_weights_pct": asset_class_weights(match["reference_weights"], assets),
                          "starting_weights_source": match["starting_weights_source"], "optimized": False},
            "findings": findings, "limitations": list(LIMITATIONS)}


def candidate_rejections(review, plan, outcome, assets, allowed_tickers):
    """An engine pass alone is insufficient: require a demonstrated, scoped improvement."""
    validation, weights = outcome.get("validation", {}), outcome.get("weights")
    if (validation.get("status") != "PASS" or validation.get("passes") is not True
            or not validation.get("checks") or any(c.get("passes") is not True for c in validation["checks"].values())):
        return ["ENGINE_CHECK_FAILED"]
    try:
        _check_weights(weights)
    except ValueError:
        return ["INVALID_CANDIDATE_WEIGHTS"]
    if set(weights) - set(review["weights"]) or set(weights) - set(allowed_tickers):
        return ["ASSET_OUTSIDE_SEARCH_SCOPE"]
    if (any(type(validation.get(m)) not in (int, float) or not math.isfinite(validation[m]) for m in METRICS)
            or validation["volatility_pct"] < 0 or not -100 <= validation["max_drawdown_pct"] <= 0
            or validation["annual_growth_pct"] < -100):
        return ["INVALID_CANDIDATE_METRICS"]
    if any(validation.get(key) != review["risk"][key] for key in CONVENTIONS):
        return ["INCOMPARABLE_BACKTEST"]
    if set(validation["checks"]) != set(review["profile_fit"]["checks"]) or any(
            c.get("limit") != review["profile_fit"]["checks"][key].get("limit")
            for key, c in validation["checks"].items()):
        return ["CHANGED_CONSTRAINTS"]
    if asset_class_weights(weights, assets) != review["asset_class_weights_pct"]:
        return ["ASSET_CLASS_SPLIT_CHANGED"]
    reasons = []
    hhi = sum(w * w for w in weights.values())
    same_class = [t for t in review["weights"] if assets[t]["asset_class"] == plan["asset_class"]]
    before_max = max(review["weights"][t] for t in same_class)
    after_max = max(weights.get(t, 0) for t in same_class)
    if hhi >= review["diversification"]["holding_hhi"] - 1e-8 or after_max >= before_max - 1e-8:
        reasons.append("CONCENTRATION_NOT_IMPROVED")
    if validation["volatility_pct"] > review["risk"]["volatility_pct"] + 1e-8:
        reasons.append("HISTORICAL_VOLATILITY_WORSENED")
    if validation["max_drawdown_pct"] < review["risk"]["max_drawdown_pct"] - 1e-8:
        reasons.append("HISTORICAL_DRAWDOWN_WORSENED")
    return reasons


def choose_suggestions(review, candidates, assets, allowed_tickers):
    eligible = []
    for record in candidates:
        plan, outcome = record["plan"], record["outcome"]
        if candidate_rejections(review, plan, outcome, assets, allowed_tickers):
            continue
        weights, validation = outcome["weights"], outcome["validation"]
        hhi = round(sum(w * w for w in weights.values()), 10)
        eligible.append({"id": plan["id"], "issue_id": plan["issue_id"], "objective": "reduce_holding_concentration",
                         "changes": deepcopy(plan["changes"]), "weights": deepcopy(weights),
                         "validation": deepcopy(validation),
                         "comparison": {"holding_hhi": {"before": review["diversification"]["holding_hhi"], "after": hhi},
                                        **{m: {"before": review["risk"][m], "after": validation[m]} for m in METRICS}},
                         "applied": False})
    eligible.sort(key=lambda s: (s["comparison"]["holding_hhi"]["after"], s["id"]))
    selected, issues = [], set()
    for suggestion in eligible:
        if suggestion["issue_id"] not in issues:
            selected.append(suggestion)
            issues.add(suggestion["issue_id"])
        if len(selected) == MAX_SUGGESTIONS:
            break
    return selected
