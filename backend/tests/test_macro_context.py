"""Dataset macro checks never introduce publication look-ahead or weight rules."""
from datetime import date
from io import BytesIO
import hashlib
import shutil
import subprocess

import pytest

from alphaforge.application.snapshots import DataUnavailable
from alphaforge.application.evidence import release_errors
from alphaforge.domain.macro_context import macro_context
from alphaforge.infrastructure.workflow_storage import _parse_macro, S3SnapshotSource
from test_investor_workflow import investor_source, source, run, investor_request, questionnaire, ROOT
import json

HEADER = "date,series_id,value,unit,frequency,label,source"


def test_macro_filters_future_reference_dates_and_hashes_actual_bytes():
    data = (HEADER + "\n2025-01-01,TEST,-0.5,percent,monthly,Test rate,Fixture\n"
            "2025-04-01,TEST,999,percent,monthly,Test rate,Fixture\n").encode()
    frame, reference = _parse_macro(data, {"key": "data/macro_rates.csv"}, date(2025, 3, 1))
    context = macro_context(frame, date(2025, 3, 1))
    assert reference["sha256"] == hashlib.sha256(data).hexdigest()
    assert len(frame) == 1 and context["series"][0]["value"] == -.5
    assert context["series"][0]["publication_timing"] == "unverified"
    assert context["series"][0]["allocation_effect"] == "none"


def test_future_release_is_not_presented_as_available_context():
    data = (HEADER + ",release_date\n"
        "2025-01-01,CPI,100,index,monthly,Test CPI,Fixture,2025-02-15\n"
        "2025-02-01,CPI,999,index,monthly,Test CPI,Fixture,2025-03-15\n").encode()
    frame, _ = _parse_macro(data, {}, date(2025, 3, 1))
    context = macro_context(frame, date(2025, 3, 1))
    assert context["series"][0]["value"] == 100 and context["excluded_future_releases"] == 1
    assert context["series"][0]["release_date"] == "2025-02-15"


@pytest.mark.parametrize("rows", [
    "2025-01-01,TEST,inf,percent,monthly,Test rate,Fixture\n",
    "2025-01-01,TEST,1,percent,monthly,Test rate,Fixture\n2025-01-01,TEST,2,percent,monthly,Test rate,Fixture\n",
    "2025-01-01,TEST,1,percent,monthly,Test rate,Fixture\n2025-02-01,TEST,2,index,monthly,Test rate,Fixture\n",
])
def test_invalid_macro_data_is_rejected(rows):
    with pytest.raises(DataUnavailable, match="INVALID_MACRO_SNAPSHOT"):
        _parse_macro((HEADER + "\n" + rows).encode(), {}, date(2025, 3, 1))


def test_macro_is_required_after_asset_and_price_validation(investor_source):
    investor_source.macro_path.unlink()
    # An unknown asset is rejected without touching macro inputs.
    outcome, _ = run(investor_source, investor_request(message="Add NONEXISTENT-XYZ 5%"))
    assert outcome.payload["error"]["code"] == "ASSET_NOT_IN_UNIVERSE"
    outcome, records = run(investor_source, investor_request(message="Add NVDA 5%"))
    assert outcome.payload["error"]["code"] == "MACRO_CONTEXT_UNAVAILABLE"
    assert "portfolio" not in outcome.payload and not records["llm_calls"]


def test_changed_macro_context_is_audited_but_does_not_invent_weight_changes(investor_source):
    first, one = run(investor_source, investor_request(message="Add NVDA 5%"))
    investor_source.macro_path.write_text(HEADER + "\n2025-02-01,TEST_POLICY,100,percent,monthly,Fictional policy rate,Synthetic fixture\n", encoding="utf-8")
    second, two = run(investor_source, investor_request(message="Add NVDA 5%"))
    assert first.payload["portfolio"]["weights"] == second.payload["portfolio"]["weights"]
    assert one["data_manifest"]["inputs"]["macro"]["sha256"] != two["data_manifest"]["inputs"]["macro"]["sha256"]
    assert first.payload["evidence"]["manifest_hash"] != second.payload["evidence"]["manifest_hash"]
    assert "100 percent" in second.payload["explanation"]
    assert set(second.payload["macro_context"]["applies_to_tickers"]) == {"XBB.TO", "ZST.TO"}
    assert "NVDA" not in second.payload["macro_context"]["applies_to_tickers"]


def test_no_bond_holdings_skip_macro_loading(investor_source):
    investor_source.macro_path.unlink()
    outcome, records = run(investor_source, investor_request(portfolio={"positions": [{"symbol": "SPY", "weight": 100}]}))
    # Existing proposal funding requires a reference bond rounding reserve; this
    # test verifies input routing, not a new all-equity allocation policy.
    assert "macro" not in records["data_manifest"]["inputs"]
    assert "CHECK_MACRO_CONTEXT" not in records["result"]["states"]
    assert outcome.payload.get("error", {}).get("code") != "MACRO_CONTEXT_UNAVAILABLE"


def test_release_gate_rejects_macro_context_scoped_to_equities(investor_source):
    _, records = run(investor_source, investor_request(message="Add NVDA 5%"))
    records["decisions"]["macro_context"]["applies_to_tickers"] = ["NVDA"]
    assert "MACRO_SCOPE_MISMATCH" in release_errors(records["evidence"], records["data_manifest"], records["decisions"], "as_requested")


def test_s3_macro_read_closes_stream_and_records_actual_key():
    stream = BytesIO((HEADER + "\n2025-01-01,TEST,1,percent,monthly,Test rate,Fixture\n").encode())
    class Client:
        def get_object(self, **kwargs):
            assert kwargs == {"Bucket": "test-bucket", "Key": "data/macro_rates.csv"}
            return {"Body": stream, "VersionId": "macro-v1"}
    frame, reference = S3SnapshotSource(Client(), "test-bucket", "data").load_macro(date(2025, 3, 1))
    assert stream.closed and reference["version_id"] == "macro-v1"
    assert len(frame) == 1 and len(reference["sha256"]) == 64


def test_all_reference_styles_fit_frontend_contract_with_real_macro_catalog(investor_source):
    # Returns are still fictional flat-price controls; this only replays response size.
    investor_source.macro_path.write_bytes((ROOT / "dataset/macro_rates.csv").read_bytes())
    config = json.loads(investor_source.paths["profiles"].read_text())
    recommendations = []
    for profile in config["profiles"]:
        form = questionnaire(profile["band"])
        form["answers"]["assets"].append("crypto")
        outcome, records = run(investor_source, investor_request(questionnaire=form,
            assessment={"preferred_style": profile["style"]}))
        assert outcome.status == "PASS", (profile["id"], outcome.payload)
        public = outcome.payload["recommendation"]
        assert len(public["explanation"]) <= 10000 and len(public["evidence"]) <= 100
        assert records["data_manifest"]["inputs"]["macro"]["sha256"]
        recommendations.append(public)
    if shutil.which("node"):
        script = """import assert from 'node:assert/strict';
import {validateRecommendation,normalizeRecommendation} from './plateforme/src/integration.js';
let s='';for await(const c of process.stdin)s+=c;
for(const result of JSON.parse(s)){
 assert.equal(validateRecommendation(result),true,`profile ${result.portfolio.id}`);
 assert.deepEqual(normalizeRecommendation(result).analysis,result.analysis);
}
"""
        check = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(recommendations),
                               text=True, cwd=ROOT, capture_output=True)
        assert check.returncode == 0, check.stderr
