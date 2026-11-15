"""Offline checks of input keys, provenance and missing-object failure behavior."""
from datetime import date
import hashlib
from io import BytesIO
from pathlib import Path

import pytest

from alphaforge.application.snapshots import DataUnavailable
from alphaforge.infrastructure.workflow_storage import S3SnapshotSource


def test_s3_snapshot_reads_data_prefix_and_records_downloaded_bytes():
    objects = {
        "data/prices_daily.csv": b"date,ticker,adj_close,currency\n2025-01-02,TEST,100,CAD\n",
        "data/fx_usdcad_daily.csv": b"date,usdcad\n2025-01-02,1.25\n",
        "data/profiles.json": (Path(__file__).resolve().parents[2] / "profiles.json").read_bytes(),
    }
    calls, bodies = [], []

    class Client:
        def get_object(self, **kwargs):
            calls.append(kwargs)
            body = BytesIO(objects[kwargs["Key"]])
            bodies.append(body)
            return {"Body": body, "VersionId": "fixture-version"}

    snapshot = S3SnapshotSource(Client(), "test-bucket", "data/").load(date(2025, 1, 3))
    assert calls == [{"Bucket": "test-bucket", "Key": key} for key in objects]
    assert all(body.closed for body in bodies)
    reference = snapshot.manifest["inputs"]["prices"]
    assert reference["key"] == "data/prices_daily.csv"
    assert reference["version_id"] == "fixture-version"
    assert reference["sha256"] == hashlib.sha256(objects[reference["key"]]).hexdigest()
    assert snapshot.prices.iloc[0].ticker == "TEST"


def test_s3_missing_object_blocks_snapshot():
    class Client:
        def get_object(self, **kwargs):
            raise OSError("Unavailable object")

    with pytest.raises(DataUnavailable, match="DATA_UNAVAILABLE"):
        S3SnapshotSource(Client(), "test-bucket", "data").load(date(2025, 1, 3))
