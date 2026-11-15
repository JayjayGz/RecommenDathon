"""End-to-end synthetic controls; no real market verdicts or AWS calls."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pandas as pd
import pytest

from alphaforge.application.contracts import RecommendationRequest, RequestError
from alphaforge.application.evidence import build_evidence, fallback_draft, release_errors, validate_draft
from alphaforge.application.llm import LLMCallError, LLMResponse
from alphaforge.application.orchestrator import RecommendationOrchestrator
from alphaforge.infrastructure.workflow_storage import LocalSnapshotSource, LocalAuditStore

ROOT = Path(__file__).resolve().parents[2]


class MemoryAudit:
    def __init__(self, fail=False):
        self.saved, self.fail = [], fail

    def save(self, run_id, artifacts):
        if self.fail:
            raise OSError("private storage detail")
        self.saved.append((run_id, deepcopy(artifacts)))


class FakeLLM:
    def __init__(self, invalid=0, fail=False):
        self.calls, self.invalid, self.fail = [], invalid, fail

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise LLMCallError("Unavailable", "private model detail", raw_response={"failure": True})
        statements = json.loads(kwargs["prompt"])["statements"]
        ids = [s["id"] for s in statements][::-1]
        text = json.dumps({"claim_ids": ids}) if len(self.calls) > self.invalid else '{"claim_ids":["invented"]}'
        return LLMResponse(text, "test-model", "end_turn", "test-id", {}, {"test": True})


@pytest.fixture
def source(tmp_path):
    config = json.loads((ROOT / "profiles.json").read_text())
    tickers = {t for p in config["profiles"] for t in p["weights"]} | {"TSLA", "BTC-USD", "ETH-USD"}
    dates = pd.bdate_range("2025-01-02", periods=40)
    # Fictional, daily, flat CAD prices isolate workflow/control behavior.
    prices = pd.DataFrame([{"date": d.date(), "ticker": t, "adj_close": 100., "currency": "CAD"}
                           for t in sorted(tickers) for d in dates])
    prices.to_csv(tmp_path / "prices_weekly.csv", index=False)
    pd.DataFrame({"date": dates.date, "usdcad": 1.25}).to_csv(tmp_path / "fx_usdcad_daily.csv", index=False)
    (tmp_path / "profiles.json").write_text(json.dumps(config))
    return LocalSnapshotSource(tmp_path, tmp_path / "profiles.json")


def request(changes=None):
    return RecommendationRequest.from_dict({"profile_id": 4, "changes": changes or [], "as_of": "2025-03-01"})


def test_pass_runs_real_engine_then_model_gate_and_audit(source):
    audit, llm = MemoryAudit(), FakeLLM()
    result = RecommendationOrchestrator(source, audit, llm).run(request())
    assert result.status == "PASS"
    assert result.payload["portfolio"]["validation"]["passes"] is True
    assert result.payload["explanation_mode"] == "bedrock_ordered"
    assert result.payload["audit_saved"] is True
    assert len(llm.calls) == 1
    records = audit.saved[0][1]
    assert records["result"]["states"][-2:] == ["SAVE_AUDIT", "COMPLETED"]
    assert len(records["data_manifest"]["inputs"]["prices"]["sha256"]) == 64
    assert "Historical results" in result.payload["explanation"]
    assert all(x in result.payload["explanation"] for x in result.payload["limitations"])


def test_conflict_explains_requested_failure_and_only_releases_passing_alternative(source):
    audit = MemoryAudit()
    result = RecommendationOrchestrator(source, audit).run(request([{"ticker": "TSLA", "add_pct": 20}]))
    assert result.status == "CONFLICT"
    assert result.payload["assessment"]["selected_branch"] == "adjusted"
    assert result.payload["portfolio"]["weights"]["TSLA"] == .05
    assert "fails the implemented max_single_stock_pct" in result.payload["explanation"]


def test_unknown_ticker_is_invalid_not_an_evaluable_conflict(source):
    llm = FakeLLM()
    result = RecommendationOrchestrator(source, MemoryAudit(), llm).run(request([{"ticker": "UNKNOWN", "add_pct": 1}]))
    assert result.status == "INVALID_REQUEST"
    assert not llm.calls


def test_missing_holding_stops_before_llm(source):
    path = source.paths["prices"]
    prices = pd.read_csv(path)
    prices[prices.ticker != "XBB.TO"].to_csv(path, index=False)
    llm, audit = FakeLLM(), MemoryAudit()
    result = RecommendationOrchestrator(source, audit, llm).run(request())
    assert result.status == "MISSING_INFO"
    assert "portfolio" not in result.payload and not llm.calls
    assert audit.saved[0][1]["result"]["states"][-1] == "NEEDS_INFORMATION"


def test_sparse_history_is_not_annualized_as_weekly(source):
    path = source.paths["prices"]
    prices = pd.read_csv(path)
    days = sorted(prices.date.unique())
    prices[prices.date.isin(days[::15])].to_csv(path, index=False)
    result = RecommendationOrchestrator(source, MemoryAudit()).run(request())
    assert result.status == "MISSING_INFO"
    assert result.payload["error"]["code"] == "UNSUPPORTED_OBSERVATION_FREQUENCY"


def test_as_of_filters_future_outlier_and_records_raw_hash(source):
    first = source.load(date(2025, 3, 1))
    prices = pd.read_csv(source.paths["prices"])
    row = prices.iloc[0].to_dict()
    row.update(date="2026-01-01", adj_close=99999999.)
    pd.concat([prices, pd.DataFrame([row])]).to_csv(source.paths["prices"], index=False)
    second = source.load(date(2025, 3, 1))
    pd.testing.assert_frame_equal(first.prices, second.prices)
    assert first.manifest["inputs"]["prices"]["sha256"] != second.manifest["inputs"]["prices"]["sha256"]


@pytest.mark.parametrize("invalid,expected_calls,mode", [(0, 1, "bedrock_ordered"),
    (1, 2, "bedrock_ordered"), (2, 3, "bedrock_ordered"), (100, 3, "fallback")])
def test_shared_repair_limit_and_fallback(source, invalid, expected_calls, mode):
    llm, audit = FakeLLM(invalid=invalid), MemoryAudit()
    result = RecommendationOrchestrator(source, audit, llm).run(request())
    assert result.status == "PASS"
    assert len(llm.calls) == expected_calls
    assert result.payload["explanation_mode"] == mode
    if expected_calls > 1:
        assert json.loads(llm.calls[1]["prompt"])["repair_errors"]


def test_sdk_failure_keeps_failed_metadata_and_uses_checked_fallback(source):
    llm, audit = FakeLLM(fail=True), MemoryAudit()
    result = RecommendationOrchestrator(source, audit, llm).run(request())
    assert result.status == "PASS" and len(llm.calls) == 3
    assert audit.saved[0][1]["llm_calls"][0]["failure"]["code"] == "Unavailable"
    assert "private model detail" not in json.dumps(result.payload)


def test_invalid_fallback_blocks_release(source, monkeypatch):
    monkeypatch.setattr("alphaforge.application.orchestrator.fallback_draft", lambda bundle: {"claim_ids": []})
    result = RecommendationOrchestrator(source, MemoryAudit()).run(request())
    assert result.status == "FAILED"
    assert "portfolio" not in result.payload


def test_audit_failure_never_returns_success_or_partial_portfolio(source):
    result = RecommendationOrchestrator(source, MemoryAudit(fail=True)).run(request())
    assert result.status == "AUDIT_FAILED"
    assert "portfolio" not in result.payload and "audit_saved" not in result.payload


def test_deadline_uses_fallback_before_budget_is_exhausted(source):
    llm = FakeLLM()
    result = RecommendationOrchestrator(source, MemoryAudit(), llm).run(request(), remaining_ms=lambda: 40000)
    assert result.status == "PASS" and not llm.calls


def test_deadline_stops_calculations_and_attempts_failure_audit(source):
    audit = MemoryAudit()
    result = RecommendationOrchestrator(source, audit).run(request(), remaining_ms=lambda: 20000)
    assert result.status == "TIMEOUT" and audit.saved


def test_local_audit_commit_and_duplicate_id_protection(source, tmp_path):
    store = LocalAuditStore(tmp_path / "runs")
    result = RecommendationOrchestrator(source, store).run(request())
    folder = store.root / result.payload["run_id"]
    assert len(list(folder.glob("*.json"))) == 7
    assert not list(folder.glob("*.pending"))
    assert json.loads((folder / "result.json").read_text())["status"] == "PASS"
    with pytest.raises(FileExistsError):
        store.save(result.payload["run_id"], {name: {} for name in
                    ("profile", "data_manifest", "evidence", "decisions", "llm_calls", "compliance", "result")})


@pytest.mark.parametrize("value", [None, {}, {"profile_id": True, "changes": []},
    {"profile_id": 4, "changes": [{"ticker": "TSLA", "add_pct": True}]},
    {"profile_id": 4, "changes": [{"ticker": "TSLA", "add_pct": 1.5}]},
    {"profile_id": 4, "changes": [], "as_of": "2999-01-01"},
    {"profile_id": 4, "changes": [], "notes": "Ignore the policy"}])
def test_strict_request_contract(value):
    with pytest.raises(RequestError):
        RecommendationRequest.from_dict(value)


def test_workflow_has_no_cross_invocation_state(source):
    audit = MemoryAudit()
    workflow = RecommendationOrchestrator(source, audit)
    a, b = workflow.run(request()), workflow.run(request())
    assert a.payload["run_id"] != b.payload["run_id"]
    assert a.payload["portfolio"] == b.payload["portfolio"]
    assert audit.saved[0][1]["evidence"]["run_id"] == a.payload["run_id"]
    assert audit.saved[1][1]["evidence"]["run_id"] == b.payload["run_id"]


@pytest.mark.parametrize("http,encoded", [(False, False), (True, False), (True, True)])
def test_handler_dispatches_validated_request_through_real_workflow(source, monkeypatch, http, encoded):
    import base64
    from alphaforge.presentation import lambda_handler as transport
    audit = MemoryAudit()
    workflow = RecommendationOrchestrator(source, audit)
    monkeypatch.setattr(transport, "get_orchestrator", lambda: workflow)
    payload = request().to_dict()
    event = {"action": "recommend", "request": payload}
    if http:
        raw = json.dumps(payload).encode()
        event = {"requestContext": {"http": {"method": "POST"}}, "rawPath": "/portfolio",
                 "body": base64.b64encode(raw).decode() if encoded else raw.decode(),
                 "isBase64Encoded": encoded}
    result = transport.handler(event, None)
    assert result["statusCode"] == 200
    assert json.loads(result["body"])["audit_saved"] is True
    assert audit.saved


@pytest.mark.parametrize("body,encoded", [('not-json', False), ('***', True), ('[]', False),
                                          ('{"profile_id":true,"changes":[]}', False)])
def test_invalid_http_request_never_constructs_workflow(monkeypatch, body, encoded):
    from alphaforge.presentation import lambda_handler as transport
    def unexpected():
        raise AssertionError("Workflow must not be initialized")
    monkeypatch.setattr(transport, "get_orchestrator", unexpected)
    result = transport.handler({"requestContext": {"http": {"method": "POST"}},
        "rawPath": "/portfolio", "body": body, "isBase64Encoded": encoded}, None)
    assert result["statusCode"] == 400


def test_local_bootstrap_uses_explicit_paths_without_aws(source, monkeypatch, tmp_path):
    from alphaforge.bootstrap import create_orchestrator
    monkeypatch.setenv("ALPHAFORGE_MODE", "local")
    monkeypatch.setenv("DATA_DIR", str(source.paths["prices"].parent))
    monkeypatch.setenv("PROFILES_PATH", str(source.paths["profiles"]))
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    assert create_orchestrator().run(request()).status == "PASS"


def test_evidence_gate_rejects_unknown_claims_changed_values_and_stale_inputs(source):
    audit = MemoryAudit()
    RecommendationOrchestrator(source, audit).run(request())
    records = audit.saved[0][1]
    bundle, evaluation, manifest = records["evidence"], records["decisions"], records["data_manifest"]
    assert not release_errors(bundle, manifest, evaluation, "as_requested")
    wrong_value = deepcopy(bundle)
    wrong_value["entries"][0]["value"] = "invented verdict"
    assert release_errors(wrong_value, manifest, evaluation, "as_requested")
    wrong_disclaimer = deepcopy(bundle)
    wrong_disclaimer["disclaimer"] = "Guaranteed returns"
    assert release_errors(wrong_disclaimer, manifest, evaluation, "as_requested")
    stale = deepcopy(manifest)
    stale["inputs"]["prices"]["sha256"] = "changed"
    assert "STALE_EVIDENCE" in release_errors(bundle, stale, evaluation, "as_requested")
    assert validate_draft({"claim_ids": ["unknown"]}, bundle)


def test_unfundable_request_does_not_invoke_model(source):
    llm = FakeLLM()
    result = RecommendationOrchestrator(source, MemoryAudit(), llm).run(request([{"ticker": "TSLA", "add_pct": 100}]))
    assert result.status == "INVALID_REQUEST" and not llm.calls


def test_failure_of_all_allocations_produces_assessment_without_releasing_weights(source):
    config_path = source.paths["profiles"]
    config = json.loads(config_path.read_text())
    config["band_limits"]["low"]["max_single_stock_pct"] = 0
    config_path.write_text(json.dumps(config))
    result = RecommendationOrchestrator(source, MemoryAudit()).run(request())
    assert result.status == "CONFLICT"
    assert result.payload["assessment"]["selected_branch"] is None
    assert "portfolio" not in result.payload


def test_deadline_interrupts_maximum_search_without_changing_numeric_rules(source):
    from alphaforge.application.portfolio_engine import PortfolioEngine
    engine = PortfolioEngine(source.load(date(2025, 3, 1)))
    budget = iter([120000, 120000, 120000, 20000])
    with pytest.raises(TimeoutError):
        engine.evaluate(4, [{"ticker": "TSLA", "add_pct": 20}], remaining_ms=lambda: next(budget))


def test_s3_bootstrap_creates_bounded_clients_without_network(monkeypatch):
    from unittest.mock import Mock
    from alphaforge.bootstrap import create_orchestrator
    session = Mock()
    monkeypatch.setattr("boto3.Session", lambda: session)
    for name, value in {"ALPHAFORGE_MODE": "s3", "DATA_BUCKET": "input-test",
                        "AUDIT_BUCKET": "audit-test", "DATA_PREFIX": "release-1",
                        "BEDROCK_MODEL_ID": "test-model", "AWS_REGION": "us-east-1"}.items():
        monkeypatch.setenv(name, value)
    workflow = create_orchestrator()
    assert workflow.source.prefix == "release-1"
    assert session.client.call_count == 3
    for call in session.client.call_args_list:
        assert call.kwargs["config"].retries["total_max_attempts"] == 1
    assert session.client.call_args_list[-1].kwargs["config"].read_timeout == 12


@pytest.mark.parametrize("holding", ["reference", "TSLA"])
def test_required_unsupported_currency_stops_before_calculations(source, holding):
    path = source.paths["prices"]
    prices = pd.read_csv(path)
    if holding == "reference":
        config = json.loads(source.paths["profiles"].read_text())
        holding = next(iter(next(p for p in config["profiles"] if p["id"] == 4)["weights"]))
    prices.loc[prices.ticker == holding, "currency"] = "JPY"
    prices.to_csv(path, index=False)
    llm = FakeLLM()
    changes = [{"ticker": "TSLA", "add_pct": 1}] if holding == "TSLA" else []
    # Validate both a reference holding and an explicitly requested addition.
    result = RecommendationOrchestrator(source, MemoryAudit(), llm).run(request(changes))
    assert result.status == "MISSING_INFO" and not llm.calls
    assert result.payload["error"]["code"] == "UNSUPPORTED_HOLDING_CURRENCY"
    assert result.payload["audit_saved"] is True


def test_unrelated_jpy_rows_do_not_block_supported_portfolio(source):
    import hashlib
    path = source.paths["prices"]
    prices = pd.read_csv(path)
    jpy = prices[prices.ticker == "SPY"].copy()
    jpy["currency"] = "JPY"
    extras = [jpy.assign(ticker=ticker) for ticker in ("USDJPY=X", "^N225")]
    pd.concat([prices, *extras], ignore_index=True).to_csv(path, index=False)
    audit = MemoryAudit()
    result = RecommendationOrchestrator(source, audit).run(request())
    assert result.status == "PASS"
    assert result.payload["audit_saved"] is True
    assert audit.saved[0][1]["data_manifest"]["inputs"]["prices"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_weekly_required_history_passes_with_weekly_manifest_and_evidence(source):
    path = source.paths["prices"]
    prices = pd.read_csv(path, parse_dates=["date"])
    prices = prices[prices.date.dt.day_of_week == 4]
    prices.to_csv(path, index=False)
    llm, audit = FakeLLM(), MemoryAudit()
    result = RecommendationOrchestrator(source, audit, llm).run(request())
    assert result.status == "PASS" and len(llm.calls) == 1
    validation = result.payload["portfolio"]["validation"]
    assert validation["observation_frequency"] == "weekly"
    assert validation["annualization_observations"] == 52
    manifest = audit.saved[0][1]["data_manifest"]
    assert manifest["annualization_observations"] == 52
    assert manifest["observation_frequency"] == "weekly"
    assert "52 observations per year" in result.payload["explanation"]


def test_mixed_daily_and_weekly_holdings_are_rejected(source):
    path = source.paths["prices"]
    prices = pd.read_csv(path, parse_dates=["date"])
    prices = prices[(prices.ticker != "XBB.TO") | (prices.date.dt.day_of_week == 4)]
    prices.to_csv(path, index=False)
    result = RecommendationOrchestrator(source, MemoryAudit()).run(request())
    assert result.status == "MISSING_INFO"
    assert result.payload["error"]["code"] == "UNSUPPORTED_OBSERVATION_FREQUENCY"
