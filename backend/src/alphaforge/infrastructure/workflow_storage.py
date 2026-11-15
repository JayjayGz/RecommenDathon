"""Per-run local/S3 input snapshots and append-only audit artifacts."""
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from alphaforge.application.audit import ARTIFACTS
from alphaforge.application.evidence import canonical
from alphaforge.application.snapshots import DataUnavailable, InputSnapshot
from .exposure_catalog import parse_exposures

MAX_INPUT_BYTES = 64 * 1024 * 1024


def _parse_macro(data, reference, as_of):
    try:
        frame = pd.read_csv(BytesIO(data), keep_default_na=False)
        fields = {"date", "series_id", "value", "unit", "frequency", "label", "source"}
        if not fields <= set(frame.columns):
            raise ValueError("Missing macro columns")
        frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
        if frame.date.isna().any():
            raise ValueError("Missing macro reference dates")
        frame = frame[frame.date <= pd.Timestamp(as_of)].copy()
        if frame.empty:
            raise DataUnavailable("MACRO_CONTEXT_UNAVAILABLE")
        if frame.duplicated(["series_id", "date"]).any():
            raise ValueError("Duplicate macro observations")
        frame["value"] = pd.to_numeric(frame["value"], errors="raise")
        if not np.isfinite(frame.value.to_numpy(dtype=float)).all():
            raise ValueError("Invalid macro values")
        for field in fields - {"date", "value"}:
            if not frame[field].map(lambda v: isinstance(v, str) and bool(v.strip()) and len(v) <= 300).all():
                raise ValueError("Invalid macro metadata")
        if frame.groupby("series_id")[["unit", "frequency"]].nunique().gt(1).any().any():
            raise ValueError("Inconsistent macro units or frequencies")
        if "release_date" in frame:
            frame["release_date"] = pd.to_datetime(frame.release_date.replace("", pd.NaT),
                                                   format="%Y-%m-%d", errors="raise")
            if (frame.release_date.notna() & (frame.release_date < frame.date)).any():
                raise ValueError("Macro release precedes reference date")
        return frame, {**reference, "sha256": hashlib.sha256(data).hexdigest()}
    except DataUnavailable:
        raise
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeError) as error:
        raise DataUnavailable("INVALID_MACRO_SNAPSHOT") from error


def _parse_snapshot(objects, as_of):
    """Parse named fields without rewriting files; hash the actual downloaded bytes."""
    try:
        prices = pd.read_csv(BytesIO(objects["prices"][0]))
        fx = pd.read_csv(BytesIO(objects["fx"][0]))
        profiles = json.loads(objects["profiles"][0])
        assets = {}
        if "universe" in objects:
            universe = pd.read_csv(BytesIO(objects["universe"][0]), keep_default_na=False)
            fields = ["ticker", "name", "asset_class", "currency", "sector"]
            if not set(fields) <= set(universe.columns) or universe.empty or universe.ticker.duplicated().any():
                raise ValueError("Invalid asset universe")
            for row in universe[fields].to_dict("records"):
                if any(not isinstance(v, str) or not v.strip() or len(v) > 200 for v in row.values()):
                    raise ValueError("Invalid asset metadata")
                if not re.fullmatch(r"[A-Z0-9.^=-]{1,24}", row["ticker"]):
                    raise ValueError("Invalid universe ticker")
                assets[row["ticker"]] = row
        if not {"date", "ticker", "adj_close", "currency"} <= set(prices.columns):
            raise ValueError("Missing price columns")
        if not {"date", "usdcad"} <= set(fx.columns):
            raise ValueError("Missing FX columns")
        for frame in (prices, fx):
            frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
            if frame.date.isna().any():
                raise ValueError("Missing dates")
        prices = prices[prices.date <= pd.Timestamp(as_of)].copy()
        fx = fx[fx.date <= pd.Timestamp(as_of)].copy().sort_values("date")
        if prices.empty or fx.empty or prices.duplicated(["ticker", "date"]).any() or fx.date.duplicated().any():
            raise ValueError("Empty or duplicate observations")
        if prices.ticker.isna().any() or prices.currency.isna().any():
            raise ValueError("Invalid asset identifiers or currencies")
        if prices.groupby("ticker").currency.nunique().gt(1).any():
            raise ValueError("Inconsistent currency")
        for series in (prices.adj_close, fx.usdcad):
            if not np.isfinite(series.to_numpy(dtype=float)).all() or (series <= 0).any():
                raise ValueError("Invalid prices or rates")
        if not isinstance(profiles, dict) or not isinstance(profiles.get("profiles"), list):
            raise ValueError("Invalid profile config")
        if not isinstance(profiles.get("band_limits"), dict):
            raise ValueError("Missing band limits")
        if "questionnaire_matching" in profiles:
            policy = profiles["questionnaire_matching"]
            if not isinstance(policy, dict) or not isinstance(policy.get("version"), str) or not policy["version"]:
                raise ValueError("Invalid matching policy version")
            mapping = policy.get("risk_map")
            if (not isinstance(mapping, dict) or set(mapping) != {"very_low", "low", "medium", "high", "very_high"}
                    or any(not isinstance(v, str) or v not in {"low", "medium", "high"} for v in mapping.values())):
                raise ValueError("Invalid questionnaire risk mapping")
        for band in ("low", "medium", "high"):
            limits = profiles["band_limits"][band]
            for name in ("max_volatility_pct", "max_drawdown_pct", "max_single_stock_pct"):
                limit = limits[name]
                if type(limit) not in (int, float) or not np.isfinite(limit):
                    raise ValueError("Invalid policy limit")
            if (limits["max_volatility_pct"] < 0 or not -100 <= limits["max_drawdown_pct"] <= 0
                    or not 0 <= limits["max_single_stock_pct"] <= 100):
                raise ValueError("Invalid policy bounds")
        for profile in profiles["profiles"]:
            if (type(profile["id"]) is not int or type(profile["crypto_allowed"]) is not bool
                    or profile["band"] not in {"low", "medium", "high"}
                    or not isinstance(profile["weights"], dict) or not profile["weights"]):
                raise ValueError("Invalid reference profile")
            for ticker, weight in profile["weights"].items():
                if (not re.fullmatch(r"[A-Z0-9.^=-]{1,24}", ticker)
                        or type(weight) not in (int, float) or not np.isfinite(weight) or weight < 0):
                    raise ValueError("Invalid reference weights")
            if abs(sum(profile["weights"].values()) - 1) > 1e-6:
                raise ValueError("Invalid reference total")
        ids = [p["id"] for p in profiles["profiles"]]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate profile IDs")
        manifest = {"as_of": as_of.isoformat(), "method": "adjusted_close_cad_common_dates_v2",
                    "inputs": {},
                    "price_window": {"first_date": prices.date.min().date().isoformat(),
                                     "last_date": prices.date.max().date().isoformat(),
                                     "rows": len(prices)},
                    "fx_window": {"first_date": fx.date.min().date().isoformat(),
                                  "last_date": fx.date.max().date().isoformat()}}
        for name, (data, reference) in objects.items():
            manifest["inputs"][name] = {**reference, "sha256": hashlib.sha256(data).hexdigest()}
        return InputSnapshot(prices, fx, deepcopy(profiles), manifest, assets)
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeError) as error:
        raise DataUnavailable("INVALID_INPUT_SNAPSHOT") from error


class LocalSnapshotSource:
    def __init__(self, data_dir, profiles_path):
        self.paths = {"prices": Path(data_dir) / "prices_weekly.csv",
                      "fx": Path(data_dir) / "fx_usdcad_daily.csv", "profiles": Path(profiles_path)}
        self.universe_path = Path(data_dir) / "assets_universe.csv"
        self.macro_path = Path(data_dir) / "macro_rates.csv"
        self.exposures_path = Path(data_dir) / "exposures_profile_tickers.csv"

    def load(self, as_of, include_universe=False):
        objects = {}
        paths = {**self.paths, **({"universe": self.universe_path} if include_universe else {})}
        try:
            for name, path in paths.items():
                with path.open("rb") as stream:
                    data = stream.read(MAX_INPUT_BYTES + 1)
                if len(data) > MAX_INPUT_BYTES:
                    raise DataUnavailable("INPUT_TOO_LARGE")
                objects[name] = (data, {"path": str(path.resolve())})
        except OSError as error:
            raise DataUnavailable("ASSET_UNIVERSE_UNAVAILABLE" if name == "universe" else "DATA_UNAVAILABLE") from error
        return _parse_snapshot(objects, as_of)

    def load_macro(self, as_of):
        try:
            with self.macro_path.open("rb") as stream:
                data = stream.read(MAX_INPUT_BYTES + 1)
            if len(data) > MAX_INPUT_BYTES:
                raise DataUnavailable("INPUT_TOO_LARGE")
        except OSError as error:
            raise DataUnavailable("MACRO_CONTEXT_UNAVAILABLE") from error
        return _parse_macro(data, {"path": str(self.macro_path.resolve())}, as_of)

    def load_exposures(self, as_of):
        try:
            with self.exposures_path.open("rb") as stream:
                data = stream.read(MAX_INPUT_BYTES + 1)
            if len(data) > MAX_INPUT_BYTES:
                raise DataUnavailable("INPUT_TOO_LARGE")
        except OSError as error:
            raise DataUnavailable("EXPOSURE_CATALOG_UNAVAILABLE") from error
        return parse_exposures(data, {"path": str(self.exposures_path.resolve())}, as_of)


class S3SnapshotSource:
    def __init__(self, client, bucket, prefix):
        self.client, self.bucket, self.prefix = client, bucket, prefix.rstrip("/")

    def load(self, as_of, include_universe=False):
        objects = {}
        files = [("prices", "prices_weekly.csv"), ("fx", "fx_usdcad_daily.csv"), ("profiles", "profiles.json")]
        if include_universe:
            files.append(("universe", "assets_universe.csv"))
        for name, filename in files:
            key = f"{self.prefix}/{filename}"
            try:
                response = self.client.get_object(Bucket=self.bucket, Key=key)
                with response["Body"] as stream:
                    data = stream.read(MAX_INPUT_BYTES + 1)
                if len(data) > MAX_INPUT_BYTES:
                    raise DataUnavailable("INPUT_TOO_LARGE")
                objects[name] = (data, {"bucket": self.bucket, "key": key,
                                       "version_id": response.get("VersionId"),
                                       "etag": response.get("ETag")})
            except DataUnavailable:
                raise
            except Exception as error:
                # This I/O boundary converts SDK/service errors into the application port failure.
                raise DataUnavailable("ASSET_UNIVERSE_UNAVAILABLE" if name == "universe" else "DATA_UNAVAILABLE") from error
        return _parse_snapshot(objects, as_of)

    def load_macro(self, as_of):
        key = f"{self.prefix}/macro_rates.csv"
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            with response["Body"] as stream:
                data = stream.read(MAX_INPUT_BYTES + 1)
            if len(data) > MAX_INPUT_BYTES:
                raise DataUnavailable("INPUT_TOO_LARGE")
        except DataUnavailable:
            raise
        except Exception as error:
            raise DataUnavailable("MACRO_CONTEXT_UNAVAILABLE") from error
        return _parse_macro(data, {"bucket": self.bucket, "key": key,
            "version_id": response.get("VersionId"), "etag": response.get("ETag")}, as_of)


    def load_exposures(self, as_of):
        key = f"{self.prefix}/exposures_profile_tickers.csv"
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            with response["Body"] as stream:
                data = stream.read(MAX_INPUT_BYTES + 1)
            if len(data) > MAX_INPUT_BYTES:
                raise DataUnavailable("INPUT_TOO_LARGE")
        except DataUnavailable:
            raise
        except Exception as error:
            raise DataUnavailable("EXPOSURE_CATALOG_UNAVAILABLE") from error
        return parse_exposures(data, {"bucket": self.bucket, "key": key,
            "version_id": response.get("VersionId"), "etag": response.get("ETag")}, as_of)


def _audit_items(run_id, artifacts):
    if not re.fullmatch(r"[a-f0-9-]{36}", run_id) or set(artifacts) != set(ARTIFACTS):
        raise ValueError("Invalid audit envelope")
    # Serialize all records before the first write; result.json is always last.
    return [(name, canonical(artifacts[name]).encode()) for name in ARTIFACTS]


class LocalAuditStore:
    def __init__(self, root):
        self.root = Path(root)

    def save(self, run_id, artifacts):
        items = _audit_items(run_id, artifacts)
        folder = self.root / run_id
        folder.mkdir(parents=True, exist_ok=False)
        for name, data in items:
            temporary = folder / f"{name}.pending"
            temporary.write_bytes(data)
            temporary.replace(folder / f"{name}.json")


class S3AuditStore:
    def __init__(self, client, bucket):
        self.client, self.bucket = client, bucket

    def save(self, run_id, artifacts):
        for name, data in _audit_items(run_id, artifacts):
            self.client.put_object(Bucket=self.bucket, Key=f"runs/{run_id}/{name}.json",
                                   Body=data, ContentType="application/json", IfNoneMatch="*")
