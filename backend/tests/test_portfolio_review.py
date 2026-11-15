"""Review facts, bounded engine alternatives and fail-closed release controls."""
from copy import deepcopy
from datetime import date
import json
import shutil
import subprocess

import pytest

from alphaforge.application.evidence import canonical, release_errors
from alphaforge.application.orchestrator import RecommendationOrchestrator
from alphaforge.application.portfolio_engine import PortfolioEngine
from alphaforge.application.portfolio_review import build_analysis, analysis_errors
from alphaforge.domain.portfolio_review import review_portfolio, transfer_plans, candidate_rejections
from test_investor_workflow import investor_source, investor_request, run
from test_orchestrator import source, MemoryAudit, FakeLLM, ROOT


def test_review_precedes_explanation_and_retains_selected_weights(investor_source):
    llm = FakeLLM()
    result, records = run(investor_source, llm=llm)
    assert result.status == "PASS"
    evaluation = records["decisions"]
    analysis = evaluation["portfolio_analysis"]
    review = analysis["review"]
    assert review["asset_class_weights_pct"] == {"etf_bond": 70, "etf_equity": 30}
    assert review["sectors"] == {"scope": "direct_stocks_only", "weights_pct": {}, "covered_pct": 0, "unclassified_pct": 100}
    assert review["diversification"] == {"holding_count": 4, "largest_ticker": "XBB.TO",
        "largest_weight_pct": 45, "holding_hhi": .31, "effective_holdings": 3.225806}
    assert review["profile_fit"]["status"] == "PASS" and review["selection"]["optimized"] is False
    assert review["selection"]["reference_asset_class_weights_pct"] == review["asset_class_weights_pct"]
    assert result.payload["portfolio"]["weights"] == evaluation["as_requested"]["weights"] == review["weights"]
    states = records["result"]["states"]
    assert [states.index(s) for s in ["EVALUATE_PORTFOLIO", "REVIEW_PORTFOLIO", "CHECK_SUGGESTIONS", "BUILD_EVIDENCE", "GENERATE_EXPLANATION", "CHECK_RELEASE", "SAVE_AUDIT"]] == sorted(
        states.index(s) for s in ["EVALUATE_PORTFOLIO", "REVIEW_PORTFOLIO", "CHECK_SUGGESTIONS", "BUILD_EVIDENCE", "GENERATE_EXPLANATION", "CHECK_RELEASE", "SAVE_AUDIT"])
    claims = json.loads(llm.calls[0]["prompt"])["statements"]
    assert {e["field"] for e in claims} >= {"review.selection", "review.sectors", "review.findings", "suggestion.search", "suggestion.C3"}
    assert analysis["manifest_hash"] == result.payload["evidence"]["manifest_hash"]
    assert len(analysis["search"]["candidates"]) == 3
    [suggestion] = analysis["suggestions"]
    assert suggestion["weights"] == {"SPY": .15, "XBB.TO": .40, "XIU.TO": .15, "ZST.TO": .30}
    assert suggestion["comparison"]["holding_hhi"] == {"before": .31, "after": .295}
    assert suggestion["validation"]["passes"] and suggestion["applied"] is False
    [cited] = result.payload["recommendation"]["analysis"]["suggestions"][0]["evidence_ids"]
    assert next(e for e in claims if e["id"] == cited)["field"] == "suggestion.C3"
    # Canonical disk serialization must preserve every derived fact and evidence ID.
    restored = json.loads(canonical(records))
    assert release_errors(restored["evidence"], restored["data_manifest"], restored["decisions"], "as_requested") == []


def test_direct_stock_sector_coverage_does_not_invent_etf_lookthrough(investor_source):
    _, records = run(investor_source)
    evaluation = records["decisions"]
    weights = {"NVDA": .05, "AAPL": .05, "XBB.TO": .40, "ZST.TO": .25, "SPY": .25}
    review = review_portfolio(weights, evaluation["as_requested"]["validation"], evaluation["asset_metadata"], evaluation["profile_match"])
    assert review["sectors"]["covered_pct"] == 10
    assert review["sectors"]["unclassified_pct"] == 90
    assert sum(review["sectors"]["weights_pct"].values()) == 10
    assert review["listing_currency_weights_pct"] == {"CAD": 65, "USD": 35}
    assert all(f["kind"] == "observation" for f in review["findings"] if f["id"].startswith("position_concentration"))


def test_transfer_search_is_stable_held_only_and_bounded():
    weights = {"A": .30, "B": .10, "C": .25, "D": .05, "E": .25, "F": .05}
    assets = {t: {"asset_class": str(i // 2)} for i, t in enumerate(weights)}
    plans = transfer_plans(weights, assets)
    assert plans == transfer_plans(dict(reversed(list(weights.items()))), assets)
    assert len(plans) == 6
    for plan in plans:
        assert plan["transfer_points"] in {1, 3, 5}
        assert assets[plan["from_ticker"]] == assets[plan["to_ticker"]]
        assert sum(c["add_pct"] for c in plan["changes"]) == 0
    assert transfer_plans({"A": .5, "B": .5}, assets) == []


@pytest.mark.parametrize("mutation,reason", [
    ("engine_fail", "ENGINE_CHECK_FAILED"), ("invalid_weights", "INVALID_CANDIDATE_WEIGHTS"),
    ("new_asset", "ASSET_OUTSIDE_SEARCH_SCOPE"), ("nonfinite", "INVALID_CANDIDATE_METRICS"),
    ("negative_vol", "INVALID_CANDIDATE_METRICS"), ("period", "INCOMPARABLE_BACKTEST"),
    ("rebalance", "INCOMPARABLE_BACKTEST"), ("limits", "CHANGED_CONSTRAINTS"),
    ("classes", "ASSET_CLASS_SPLIT_CHANGED"), ("no_improvement", "CONCENTRATION_NOT_IMPROVED"),
    ("volatility", "HISTORICAL_VOLATILITY_WORSENED"), ("drawdown", "HISTORICAL_DRAWDOWN_WORSENED"),
])
def test_engine_pass_does_not_bypass_improvement_checks(investor_source, mutation, reason):
    _, records = run(investor_source)
    evaluation = records["decisions"]
    analysis = evaluation["portfolio_analysis"]
    record = deepcopy(analysis["search"]["candidates"][-1])
    outcome, review = record["outcome"], analysis["review"]
    v = outcome["validation"]
    if mutation == "engine_fail": v["checks"]["max_volatility_pct"]["passes"] = False
    elif mutation == "invalid_weights": outcome["weights"]["SPY"] = -1
    elif mutation == "new_asset": outcome["weights"]["NVDA"] = outcome["weights"].pop("SPY")
    elif mutation == "nonfinite": v["volatility_pct"] = float("nan")
    elif mutation == "negative_vol": v["volatility_pct"] = -1
    elif mutation == "period": v["period"]["observations"] -= 1
    elif mutation == "rebalance": v["rebalance"] = "none"
    elif mutation == "limits": v["checks"]["max_volatility_pct"]["limit"] += 1
    elif mutation == "classes": outcome["weights"]["SPY"] += .01; outcome["weights"]["XBB.TO"] -= .01
    elif mutation == "no_improvement": outcome["weights"] = deepcopy(review["weights"])
    elif mutation == "volatility": v["volatility_pct"] = review["risk"]["volatility_pct"] + .1
    elif mutation == "drawdown": v["max_drawdown_pct"] = review["risk"]["max_drawdown_pct"] - .1
    assert reason in candidate_rejections(review, record["plan"], outcome, evaluation["asset_metadata"], evaluation["allowed_tickers"])


def test_candidates_rejected_by_engine_stay_in_audit_only(investor_source, monkeypatch):
    original = PortfolioEngine.evaluate_candidate
    def reject(self, *args, **kwargs):
        outcome = original(self, *args, **kwargs)
        outcome["validation"]["checks"]["max_volatility_pct"]["passes"] = False
        return outcome
    monkeypatch.setattr(PortfolioEngine, "evaluate_candidate", reject)
    result, records = run(investor_source)
    assert result.status == "PASS"
    analysis = result.payload["recommendation"]["analysis"]
    assert analysis["suggestions"] == [] and "candidates" not in analysis["search"]
    assert "candidates" not in result.payload["portfolio_analysis"]["search"]
    assert all(c["rejections"] == ["ENGINE_CHECK_FAILED"] for c in records["decisions"]["portfolio_analysis"]["search"]["candidates"])


def test_optional_search_respects_budget_and_no_passing_portfolio(investor_source):
    _, records = run(investor_source)
    evaluation, manifest = records["decisions"], records["data_manifest"]
    engine = PortfolioEngine(investor_source.load(date(2025, 3, 1), include_universe=True))
    package = build_analysis(engine, evaluation, "as_requested", manifest, lambda: 44000)
    assert package["search"]["status"] == "budget_limited" and package["suggestions"] == []
    assert package["search"]["candidates"] == []
    assert analysis_errors(package, evaluation, "as_requested", manifest) == []
    package = build_analysis(engine, evaluation, None, manifest, lambda: 120000)
    assert package["search"]["status"] == "no_passing_portfolio" and not package["suggestions"]
    assert analysis_errors(package, evaluation, None, manifest) == []


def test_exact_candidate_is_not_silently_rewritten_to_pass_caps(investor_source):
    _, records = run(investor_source)
    evaluation = records["decisions"]
    engine = PortfolioEngine(investor_source.load(date(2025, 3, 1), include_universe=True))
    outcome = engine.evaluate_candidate(1, [{"ticker": "NVDA", "add_pct": 6}],
        evaluation["as_requested"]["weights"], evaluation["constraints"])
    assert outcome["weights"]["NVDA"] == .06
    assert outcome["validation"]["status"] == "CONFLICT"
    assert outcome["validation"]["checks"]["max_single_stock_pct"]["passes"] is False


def test_growth_tradeoff_is_reported_without_optimizing_returns(investor_source):
    from alphaforge.domain.portfolio_review import choose_suggestions
    _, records = run(investor_source)
    evaluation = records["decisions"]
    package = evaluation["portfolio_analysis"]
    candidates = deepcopy(package["search"]["candidates"])
    for candidate in candidates:
        candidate["outcome"]["validation"]["annual_growth_pct"] = -1
    [suggestion] = choose_suggestions(package["review"], candidates, evaluation["asset_metadata"], evaluation["allowed_tickers"])
    assert suggestion["comparison"]["annual_growth_pct"] == {"before": 0, "after": -1}


@pytest.mark.parametrize("mutation,reason", [("review", "REVIEW_FACT_MISMATCH"), ("manifest", "STALE_REVIEW"),
    ("suggestion", "UNVERIFIED_SUGGESTION"), ("search", "INVALID_SUGGESTION_SEARCH"), ("rejection", "CANDIDATE_CHECK_MISMATCH")])
def test_release_rejects_tampered_review_or_optional_alternative(investor_source, mutation, reason):
    _, records = run(investor_source)
    p = records["decisions"]["portfolio_analysis"]
    if mutation == "review": p["review"]["sectors"]["covered_pct"] = 100
    elif mutation == "manifest": p["manifest_hash"] = "0" * 64
    elif mutation == "suggestion": p["suggestions"][0]["applied"] = True
    elif mutation == "search": p["search"]["candidates"][0]["plan"]["transfer_points"] = 99
    elif mutation == "rejection": p["search"]["candidates"][0]["rejections"] = ["fake"]
    assert reason in release_errors(records["evidence"], records["data_manifest"], records["decisions"], "as_requested")


def test_review_preserves_shared_model_repairs_and_audit_prerequisite(investor_source):
    llm = FakeLLM(invalid=10)
    result, records = run(investor_source, llm=llm)
    assert result.status == "PASS" and len(llm.calls) == 3 and result.payload["explanation_mode"] == "fallback"
    assert result.payload["recommendation"]["analysis"]["suggestions"]
    failed = RecommendationOrchestrator(investor_source, MemoryAudit(fail=True)).run(investor_request())
    assert failed.status == "AUDIT_FAILED" and "portfolio_analysis" not in failed.payload and "recommendation" not in failed.payload


def test_actual_review_survives_frontend_normalization_and_rejects_false_candidates(investor_source):
    if not shutil.which("node"):
        pytest.skip("Node is needed to execute the actual frontend boundary")
    result, _ = run(investor_source)
    script = """import assert from 'node:assert/strict';
import {validateRecommendation,normalizeRecommendation} from './plateforme/src/integration.js';
let s='';for await(const c of process.stdin)s+=c;const result=JSON.parse(s);
assert.equal(validateRecommendation(result),true);
const normalized=normalizeRecommendation(result);assert.deepEqual(normalized.analysis,result.analysis);
normalized.analysis.review.sectors.covered_pct=100;assert.equal(validateRecommendation(normalized),false);
for(const mutate of [c=>c.applied=true,c=>c.validation.checks.max_volatility_pct.passes=false,
  c=>c.evidence_ids=['invented'],c=>c.comparison.volatility_pct.after=999]){
 const copy=structuredClone(result);mutate(copy.analysis.suggestions[0]);assert.equal(validateRecommendation(copy),false);
}
"""
    check = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(result.payload["recommendation"]),
        text=True, cwd=ROOT, capture_output=True)
    assert check.returncode == 0, check.stderr
