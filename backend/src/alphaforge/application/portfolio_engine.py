"""Deterministic calculation orchestration through an injected storage port."""
import math
import pandas as pd
from .repositories import PortfolioRepository
from alphaforge.domain import backtest
from alphaforge.domain.market_data import price_table
from alphaforge.domain.proposals import (
    BONDS, EXTRA_CAPS, ProposalError, _check_weights, _check_changes, _failed,
    apply_proposal, assess,
)
from alphaforge.domain.reference_portfolios import CRYPTO


def _plain(value):
    return value.item() if hasattr(value, "item") else value


class PortfolioEngine:
    BONDS = BONDS
    CRYPTO = CRYPTO
    ProposalError = ProposalError

    def __init__(self, repository: PortfolioRepository):
        self.repository = repository

    def _load_profiles(self, profiles_path):
        return self.repository.load_profiles(profiles_path)

    def _load_data(self, data_dir):
        return self.repository.load_data(data_dir)

    def _apply(self, profile, changes, enforce_caps, data_dir, profiles_path):
        config = self._load_profiles(profiles_path)
        prices, _ = self._load_data(data_dir)
        return apply_proposal(profile, changes, enforce_caps, config, set(prices["ticker"].unique()))

    def get_profile(self, profile_id, profiles_path=None):
        """Copy of one of the 15 base profiles: id, band, style, crypto_allowed, weights."""
        if type(profile_id) is not int:
            raise ValueError("profile_id must be an integer")
        config = self._load_profiles(profiles_path)
        for p in config["profiles"]:
            if p["id"] == profile_id:
                return {"id": p["id"], "band": p["band"], "style": p["style"],
                        "crypto_allowed": p["crypto_allowed"], "weights": dict(p["weights"])}
        raise ValueError(f"No profile with id {profile_id}")

    def apply_changes(self, profile, changes, data_dir=None, profiles_path=None):
        """Apply caps. Invalid requests raise ProposalError; self.evaluate() returns statuses.

        This transforms weights only; it does not establish historical risk fit.
        """
        weights, notes = self._apply(profile, changes, enforce_caps=True,
                                 data_dir=data_dir, profiles_path=profiles_path)
        return {"weights": weights, "notes": notes}

    def validate(self, weights, band, start=None, end=None, rebalance="monthly",
                  data_dir=None, profiles_path=None, crypto_allowed=None):
        """Backtest weights (fractions summing to 1) and check them against band limits.

        Default period: last 5 years of data in data_dir. Currency: CAD throughout
        (see domain.market_data.cad_prices). Only days when every holding traded.
        """
        try:
            _check_weights(weights)
        except ProposalError as error:
            return _failed("INVALID_REQUEST", error.code, str(error))
        if band not in EXTRA_CAPS or rebalance not in {"monthly", "none"}:
            return _failed("INVALID_REQUEST", "INVALID_POLICY", "Unknown risk band or rebalancing method")
        if crypto_allowed is not None and type(crypto_allowed) is not bool:
            return _failed("INVALID_REQUEST", "INVALID_POLICY", "crypto_allowed must be a boolean")
        try:
            limits = self._load_profiles(profiles_path)["band_limits"][band]
            prices, fx = self._load_data(data_dir)
            end_ts = pd.Timestamp(end) if end else prices["date"].max()
            start_ts = pd.Timestamp(start) if start else end_ts - pd.DateOffset(years=5)
            if start_ts >= end_ts:
                return _failed("INVALID_REQUEST", "INVALID_PERIOD", "start must precede end")
            active = {t: v for t, v in weights.items() if v > 0}
            df = price_table(prices, fx, list(active), start_ts, end_ts)
            value = backtest.portfolio_value(df, active, rebalance)
            metrics = {k: _plain(v) for k, v in backtest.metrics(value).items()}
            if any(not math.isfinite(metrics[k]) for k in ("volatility_pct", "max_drawdown_pct", "annual_growth_pct")):
                raise ValueError("Risk metrics are not finite")
        except (FileNotFoundError, KeyError, ValueError) as error:
            return _failed("MISSING_INFO", "DATA_UNAVAILABLE", str(error))
        return assess(weights, band, limits, metrics, df, rebalance, crypto_allowed)


    def evaluate(self, profile_id, changes, data_dir=None, profiles_path=None, remaining_ms=None):
        """The function agents call: base vs. as-requested (no caps) vs. adjusted (capped)."""
        def require_time():
            if remaining_ms is not None and remaining_ms() < 25000:
                raise TimeoutError("Evaluation deadline; reserve time for audit")

        require_time()
        try:
            profile = self.get_profile(profile_id, profiles_path)
            prices, _ = self._load_data(data_dir)
            _check_changes(changes, set(prices["ticker"].unique()))
        except (ValueError, FileNotFoundError) as error:
            status = "MISSING_INFO" if isinstance(error, FileNotFoundError) else "INVALID_REQUEST"
            code = "DATA_UNAVAILABLE" if status == "MISSING_INFO" else getattr(error, "code", "INVALID_PROFILE")
            failure = _failed(status, code, str(error))
            return {"status": status, "base": None, "as_requested": {"weights": None, "validation": failure},
                    "adjusted": None, "notes": [], "outside_profile": None, "max_allowed": {},
                    "errors": failure["errors"]}
        band = profile["band"]

        def run(enforce_caps):
            require_time()
            try:
                weights, notes = self._apply(profile, changes, enforce_caps, data_dir, profiles_path)
                return {"weights": weights, "validation": self.validate(weights, band, data_dir=data_dir,
                            profiles_path=profiles_path, crypto_allowed=profile["crypto_allowed"])}, notes
            except ProposalError as error:
                failure = _failed("INVALID_REQUEST", error.code, str(error))
                return {"weights": None, "validation": failure}, [str(error)]

        base = {"weights": profile["weights"],
                "validation": self.validate(profile["weights"], band, data_dir=data_dir, profiles_path=profiles_path,
                                       crypto_allowed=profile["crypto_allowed"])}
        as_requested, pre_cap_notes = run(enforce_caps=False)
        adjusted, cap_notes = run(enforce_caps=True)

        notes = list(pre_cap_notes)
        notes += [n for n in cap_notes if n not in notes]
        status = as_requested["validation"]["status"]
        outside_profile = True if status == "CONFLICT" else False if status == "PASS" else None

        max_allowed = {}
        if outside_profile:
            for i, change in enumerate(changes):
                if "ticker" in change and change.get("add_pct", 0) > 0:
                    if sum(c.get("ticker") == change["ticker"] for c in changes) > 1:
                        continue  # no ambiguous per-ticker maximum for repeated edits
                    requested = int(change["add_pct"])
                    found = None
                    for x in range(requested, -1, -1):
                        require_time()
                        trial = changes[:i] + [{**change, "add_pct": x}] + changes[i + 1:]
                        try:
                            weights, _ = self._apply(profile, trial, enforce_caps=False,
                                                 data_dir=data_dir, profiles_path=profiles_path)
                        except ProposalError:
                            continue
                        if self.validate(weights, band, data_dir=data_dir, profiles_path=profiles_path,
                                    crypto_allowed=profile["crypto_allowed"])["passes"]:
                            found = x
                            break
                    max_allowed[change["ticker"]] = found

        return {"status": status, "base": base, "as_requested": as_requested, "adjusted": adjusted,
                "notes": notes, "outside_profile": outside_profile, "max_allowed": max_allowed}
