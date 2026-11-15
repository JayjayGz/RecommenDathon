"""S3 adapter contract and partial-write controls using botocore stubs."""
from datetime import date
from io import BytesIO
import json

import boto3
from botocore.stub import Stubber
import pytest

from alphaforge.application.audit import ARTIFACTS
from alphaforge.application.evidence import canonical
from alphaforge.application.snapshots import DataUnavailable
from alphaforge.infrastructure.workflow_storage import S3AuditStore, S3SnapshotSource

RUN_ID = "12345678-1234-1234-1234-123456789abc"


def client():
    return boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing",
                        aws_secret_access_key="testing")


def objects():
    return {
        "prices_daily.csv": b"ticker,date,adj_close,currency\nSPY,2025-01-02,100,USD\nSPY,2025-01-03,101,USD\nSPY,2025-01-06,100,USD\n",
        "fx_usdcad_daily.csv": b"date,usdcad\n2025-01-02,1.25\n",
        "profiles.json": json.dumps({"profiles": [{"id": 1, "band": "low", "style": "Broad diversifier",
            "crypto_allowed": False, "weights": {"SPY": 1.0}}], "band_limits": {
                b: {"max_volatility_pct": 7, "max_drawdown_pct": -15, "max_single_stock_pct": 5}
                for b in ("low", "medium", "high")}}).encode(),
    }


def test_s3_snapshot_hashes_downloaded_bytes_and_closes_streams():
    s3 = client()
    streams = []
    with Stubber(s3) as stub:
        for name, data in objects().items():
            stream = BytesIO(data)
            streams.append(stream)
            stub.add_response("get_object", {"Body": stream, "VersionId": "version-1", "ETag": '"etag"'},
                              {"Bucket": "test-data", "Key": f"inputs/{name}"})
        snapshot = S3SnapshotSource(s3, "test-data", "inputs").load(date(2025, 1, 6))
        stub.assert_no_pending_responses()
    assert all(s.closed for s in streams)
    assert snapshot.manifest["inputs"]["prices"]["version_id"] == "version-1"
    assert len(snapshot.prices) == 3
    assert len(snapshot.manifest["inputs"]["prices"]["sha256"]) == 64


def test_s3_read_failure_is_actionable_without_leaking_service_details():
    s3 = client()
    with Stubber(s3) as stub:
        stub.add_client_error("get_object", "AccessDenied", "private bucket details", expected_params={
            "Bucket": "test-data", "Key": "inputs/prices_daily.csv"})
        with pytest.raises(DataUnavailable, match="^DATA_UNAVAILABLE$"):
            S3SnapshotSource(s3, "test-data", "inputs").load(date(2025, 1, 6))


def test_s3_audit_writes_final_result_last_and_uses_conditional_creates():
    s3 = client()
    artifacts = {name: {"artifact": name} for name in ARTIFACTS}
    with Stubber(s3) as stub:
        for name in ARTIFACTS:
            stub.add_response("put_object", {}, {"Bucket": "test-audit",
                "Key": f"runs/{RUN_ID}/{name}.json", "Body": canonical(artifacts[name]).encode(),
                "ContentType": "application/json", "IfNoneMatch": "*"})
        S3AuditStore(s3, "test-audit").save(RUN_ID, artifacts)
        stub.assert_no_pending_responses()
    assert ARTIFACTS[-1] == "result"


@pytest.mark.parametrize("failed_index", [0, 3, 6])
def test_partial_audit_failure_propagates_without_writing_later_artifacts(failed_index):
    s3 = client()
    artifacts = {name: {} for name in ARTIFACTS}
    with Stubber(s3) as stub:
        for index, name in enumerate(ARTIFACTS[:failed_index + 1]):
            expected = {"Bucket": "test-audit", "Key": f"runs/{RUN_ID}/{name}.json",
                        "Body": b"{}", "ContentType": "application/json", "IfNoneMatch": "*"}
            if index == failed_index:
                stub.add_client_error("put_object", "AccessDenied", expected_params=expected)
            else:
                stub.add_response("put_object", {}, expected)
        with pytest.raises(s3.exceptions.ClientError):
            S3AuditStore(s3, "test-audit").save(RUN_ID, artifacts)
        stub.assert_no_pending_responses()
