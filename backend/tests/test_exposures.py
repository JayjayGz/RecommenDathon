"""Pondérations connues, dates, provenance et intégration du nouveau mapping."""
from copy import deepcopy
from datetime import date
from io import BytesIO, StringIO
import csv
import hashlib
import json

import pytest

from alphaforge.application.evidence import release_errors
from alphaforge.application.investor_requests import InvestorRequest
from alphaforge.application.snapshots import DataUnavailable
from alphaforge.application.portfolio_engine import PortfolioEngine
from alphaforge.application.portfolio_review import exposures_for, checked_rejections
from alphaforge.domain.portfolio_review import review_portfolio
from alphaforge.domain.exposures import exposure_review, parse_allocation
from alphaforge.infrastructure.exposure_catalog import parse_exposures
from alphaforge.infrastructure.workflow_storage import S3SnapshotSource
from test_investor_workflow import investor_source, investor_request, questionnaire, french_form, run
from test_orchestrator import source, ROOT


def catalog(as_of=date(2026, 11, 15)):
    data = (ROOT / "dataset/exposures_profile_tickers.csv").read_bytes()
    return parse_exposures(data, {"test": "catalogue fourni"}, as_of)


def test_weighted_stock_and_fund_exposures_do_not_use_fund_labels_as_sectors():
    rows, _ = catalog()
    analysis = exposure_review({"NVDA": .5, "SPY": .5}, rows, {"sectors": ["technology"], "assets": ["stocks"]}, [], {}, {})
    sectors = analysis["dimensions"]["sectors"]
    assert sectors["covered_pct"] == pytest.approx(100)
    gics = next(g for g in sectors["groups"] if g["basis"] == "GICS")
    assert gics["weights_pct"]["Technologie de l'information"] == pytest.approx(68.075)
    assert analysis["preferred_sector_weight_pct"] == pytest.approx(68.075)
    assert len(analysis["dimensions"]["geography"]["groups"]) == 2


def test_unknown_data_and_future_observations_are_not_zero_exposures():
    rows, _ = catalog()
    answers = {"sectors": ["technology"], "assets": []}
    analysis = exposure_review({"QQQ": .5, "SPY": .5}, rows, answers, [], {}, {})
    assert analysis["dimensions"]["sectors"]["covered_pct"] == pytest.approx(50)
    assert analysis["dimensions"]["sectors"]["missing_tickers"] == ["QQQ"]
    future, _ = catalog(date(2025, 3, 1))
    old = exposure_review({"SPY": 1}, future, answers, [], {}, {})
    assert old["dimensions"]["sectors"]["unclassified_pct"] == 100
    assert old["potential_assets"] == [] and future["SPY"]["description_fr"] == ""


def test_bond_sectors_and_asset_classes_keep_their_own_reference_basis():
    rows, _ = catalog()
    analysis = exposure_review({"AGG": .5, "NVDA": .5}, rows, {"sectors": ["technology"]}, [], {}, {})
    assert len(analysis["dimensions"]["sectors"]["groups"]) == 2
    assert analysis["preferred_sector_weight_pct"] == 50
    composition = analysis["dimensions"]["asset_classes"]
    bonds = sum(g["weights_pct"].get("Obligations", 0) for g in composition["groups"])
    assert bonds == pytest.approx(49.84)
    assert analysis["dimensions"]["geography"]["missing_tickers"] == ["AGG"]


@pytest.mark.parametrize("value", ["Actions : 101 %", "Actions : -1 %", "Actions : NaN %", "Actions : 20 %; Actions : 80 %"])
def test_malformed_allocations_are_rejected(value):
    with pytest.raises(ValueError):
        parse_allocation(value)


def test_source_hash_and_duplicate_rejection():
    data = (ROOT / "dataset/exposures_profile_tickers.csv").read_bytes()
    _, reference = parse_exposures(data, {}, date(2026, 11, 15))
    assert reference["sha256"] == hashlib.sha256(data).hexdigest()
    rows = list(csv.DictReader(StringIO(data.decode("utf-8-sig")))); rows.append(rows[0])
    stream = StringIO(); writer = csv.DictWriter(stream, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    with pytest.raises(DataUnavailable, match="INVALID_EXPOSURE_CATALOG"):
        parse_exposures(stream.getvalue().encode(), {}, date(2026, 11, 15))


def test_s3_exposures_are_hashed_and_the_body_is_closed():
    data = (ROOT / "dataset/exposures_profile_tickers.csv").read_bytes()
    body = BytesIO(data)
    class Client:
        def get_object(self, **kwargs):
            assert kwargs == {"Bucket": "test", "Key": "snapshot/exposures_profile_tickers.csv"}
            return {"Body": body, "VersionId": "version-test", "ETag": "etag-test"}
    rows, reference = S3SnapshotSource(Client(), "test", "snapshot").load_exposures(date(2026, 11, 15))
    assert body.closed and "SPY" in rows and reference["version_id"] == "version-test"


def test_exposures_and_unapplied_potential_assets_reach_the_public_result(investor_source):
    outcome, audit = run(investor_source, investor_request(as_of="2026-11-15"))
    assert outcome.status == "PASS"
    exposures = outcome.payload["recommendation"]["analysis"]["exposures"]
    assert exposures["dimensions"]["sectors"]["covered_pct"] == pytest.approx(15)
    assert exposures["potential_assets"]
    assert all(p["status"] == "to_study" and p["applied"] is False for p in exposures["potential_assets"])
    assert all(p["ticker"] not in outcome.payload["portfolio"]["weights"] for p in exposures["potential_assets"])
    assert "Pistes à étudier" in outcome.payload["message"]
    assert "exposures" in audit["data_manifest"]["inputs"]
    evaluation = deepcopy(audit["decisions"])
    evaluation["portfolio_analysis"]["exposures"]["preferred_sector_weight_pct"] = 99
    assert "EXPOSURE_REVIEW_MISMATCH" in release_errors(audit["evidence"], audit["data_manifest"], evaluation, "as_requested")


def test_missing_catalog_stops_analysis_instead_of_inventing_exposures(investor_source):
    investor_source.exposures_path = ROOT / "dataset/catalogue-absent-pour-test.csv"
    outcome, _ = run(investor_source)
    assert outcome.status == "MISSING_INFO" and "recommendation" not in outcome.payload
    assert outcome.payload["error"]["code"] == "EXPOSURE_CATALOG_UNAVAILABLE"


def test_suggestion_cannot_trade_away_the_selected_sector_even_when_risk_passes(investor_source):
    _, audit = run(investor_source, investor_request(as_of="2026-11-15"))
    evaluation = audit["decisions"]
    snapshot = investor_source.load(date(2026, 11, 15), include_universe=True)
    target = next(t for t in sorted(set(snapshot.prices.ticker))
                  if snapshot.assets[t]["asset_class"] == "equity"
                  and evaluation["asset_exposures"].get(t, {}).get("sectors")
                  and "Technologie de l'information" not in evaluation["asset_exposures"][t]["sectors"]["fractions"])
    weights = {"NVDA": .05, target: .01, "XBB.TO": .5, "ZST.TO": .44}
    engine = PortfolioEngine(snapshot)
    validation = engine.validate(weights, "low", crypto_allowed=False, constraints=evaluation["constraints"])
    review = review_portfolio(weights, validation, snapshot.assets, evaluation["profile_match"])
    plan = {"asset_class": "equity", "changes": [{"ticker": "NVDA", "add_pct": -1}, {"ticker": target, "add_pct": 1}]}
    outcome = engine.evaluate_candidate(1, plan["changes"], weights, evaluation["constraints"])
    assert outcome["validation"]["passes"] is True
    reasons = checked_rejections(review, plan, outcome, evaluation, exposures_for(evaluation, weights))
    assert "SECTOR_PREFERENCE_ALIGNMENT_WORSENED" in reasons


def test_full_questionnaire_mapping_uses_knowledge_reaction_and_capacity(investor_source):
    form = french_form()
    questions = {q["id"]: q for q in form["questions"]}
    for key, value in {"tolerance_risque": 5, "reaction_baisse": 4, "connaissances": 4, "horizon": 4}.items():
        questions[key]["reponse"] = f"{key}_{value}"
    questions["classes_actifs"]["reponse"] = ["classes_actifs_8"]
    outcome, _ = run(investor_source, investor_request(questionnaire=form))
    assert outcome.status == "PASS" and outcome.payload["profile_match"]["profile_id"] == 13
    assert outcome.payload["profile_match"]["questionnaire_mapping"]["risk_level"] == 6
    questions["connaissances"]["reponse"] = "connaissances_1"
    cautious, _ = run(investor_source, investor_request(questionnaire=form))
    assert cautious.payload["profile_match"]["risk_band"] == "low"
    assert cautious.payload["profile_match"]["profile_id"] == 3


def test_current_browser_v4_contract_preserves_option_ids_and_rejects_removed_values():
    answers = {"marital": "other", "dependents": "none", "annualIncome": "under_50k", "income": "regular",
               "debt": "none", "emergencyFund": 5000, "goal": "wealth", "horizon": "10", "withdrawalTiming": "7_plus",
               "liquidity": "no", "risk": "high", "reaction": "calm", "knowledge": "good",
               "sectors": ["technology"], "assets": ["stocks"], "exclusions": "none"}
    request = InvestorRequest.from_dict({"questionnaire": {"version": "questionnaire-word-16-v4", "answers": answers}})
    normalized, missing = request.normalized_answers()
    assert not missing and normalized["knowledge"] == "good"
    assert normalized["financial_context"]["situation_conjugale"] == "situation_conjugale_4"
    from alphaforge.application.contracts import RequestError
    for removed in ({"marital": "separated"}, {"exclusions": "discussion"}, {"targetAmount": 10000}):
        with pytest.raises(RequestError):
            InvestorRequest.from_dict({"questionnaire": {"version": "questionnaire-word-16-v4", "answers": {**answers, **removed}}})
