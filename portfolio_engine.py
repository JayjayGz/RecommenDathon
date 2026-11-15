"""Shared calculation layer the agents call as tools.

Plain Python only: no LLM calls, no network, deterministic. Reuses price loading,
backtesting and metrics from backtest_viewer.py, and the asset classification
(ETFS, CRYPTO) and whole-percent rounding from build_portfolios.py, so the rules
stay in one place.

profiles.json is read-only here: this module never writes to it.
Educational simulation with fictional profiles. Not financial advice.
"""

import functools
import json
import math
from numbers import Real

import pandas as pd

import backtest_viewer as bv
from build_portfolios import CRYPTO, ETFS, round_weights

BONDS = {"XBB.TO", "ZST.TO", "AGG"}

# Caps not already covered by profiles.json's band_limits (single-stock cap comes
# from there). Team assumptions: see docs/portfolio_rules.md.
EXTRA_CAPS = {
    "low":    {"gold": 10, "crypto": 0},
    "medium": {"gold": 15, "crypto": 3},
    "high":   {"gold": 15, "crypto": 10},
}

TOLERANCE = 1e-8


class ProposalError(ValueError):
    """An unsupported or unfundable proposal, rather than a successful no-op."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _check_weights(weights):
    if not isinstance(weights, dict) or not weights:
        raise ProposalError("INVALID_WEIGHTS", "Weights must be a nonempty ticker-to-fraction map")
    if any(not isinstance(t, str) or not t for t in weights):
        raise ProposalError("INVALID_WEIGHTS", "Every holding needs a ticker")
    if any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v)
           or v < 0 for v in weights.values()):
        raise ProposalError("INVALID_WEIGHTS", "Weights must be finite and nonnegative; shorting is unsupported")
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-6, rel_tol=0):
        raise ProposalError("INVALID_WEIGHTS", "Weights must sum to one")


def _check_changes(changes, valid_tickers):
    if not isinstance(changes, list):
        raise ProposalError("INVALID_CHANGE", "changes must be a list")
    for change in changes:
        if not isinstance(change, dict):
            raise ProposalError("INVALID_CHANGE", "Each change must be an object")
        if set(change) == {"exclude"}:
            ticker = change["exclude"]
        elif set(change) == {"ticker", "add_pct"}:
            ticker, amount = change["ticker"], change["add_pct"]
            if (isinstance(amount, bool) or not isinstance(amount, Real)
                    or not math.isfinite(amount) or not float(amount).is_integer()
                    or not -100 <= amount <= 100):
                raise ProposalError("INVALID_CHANGE", "add_pct must be a whole percentage-point change between -100 and 100")
            if isinstance(ticker, str) and ticker in BONDS:
                raise ProposalError("PROTECTED_BOND", "Direct bond changes are unsupported by this engine's funding policy")
        else:
            raise ProposalError("INVALID_CHANGE", "Use either {exclude} or {ticker, add_pct}")
        if not isinstance(ticker, str) or ticker not in valid_tickers:
            raise ProposalError("UNKNOWN_TICKER", f"{ticker!r}: not in dataset")


def _failed(status, code, message):
    return {"status": status, "passes": False, "checks": {},
            "errors": [{"code": code, "message": message}]}


@functools.lru_cache(maxsize=4)
def _load_profiles(profiles_path):
    with open(profiles_path) as f:
        return json.load(f)


@functools.lru_cache(maxsize=4)
def _load_data(data_dir):
    return bv.load_data(data_dir)


def _plain(value):
    """numpy scalar -> plain Python, so results are JSON-serializable."""
    return value.item() if hasattr(value, "item") else value


def get_profile(profile_id, profiles_path="profiles.json"):
    """Copy of one of the 15 base profiles: id, band, style, crypto_allowed, weights."""
    if type(profile_id) is not int:
        raise ValueError("profile_id must be an integer")
    config = _load_profiles(profiles_path)
    for p in config["profiles"]:
        if p["id"] == profile_id:
            return {"id": p["id"], "band": p["band"], "style": p["style"],
                    "crypto_allowed": p["crypto_allowed"], "weights": dict(p["weights"])}
    raise ValueError(f"No profile with id {profile_id}")


def _category_cap(ticker, band, crypto_allowed):
    """Cap (in percentage points) for ticker's own weight, or None if uncapped."""
    if ticker in CRYPTO:
        return EXTRA_CAPS[band]["crypto"] if crypto_allowed else 0
    if ticker == "GLD":
        return EXTRA_CAPS[band]["gold"]
    if ticker in ETFS:
        return None  # broad ETF, no per-ticker cap
    return None  # filled in by caller with the band's single-stock limit


def _apply(profile, changes, enforce_caps, data_dir, profiles_path):
    """Shared logic for apply_changes() and evaluate()'s as-requested/adjusted passes."""
    band, crypto_allowed = profile["band"], profile["crypto_allowed"]
    stock_cap = _load_profiles(profiles_path)["band_limits"][band]["max_single_stock_pct"]
    prices, _ = _load_data(data_dir)
    valid_tickers = set(prices["ticker"].unique())
    _check_changes(changes, valid_tickers)
    _check_weights(profile["weights"])

    w = {t: v * 100 for t, v in profile["weights"].items()}
    notes = []

    for change in changes:
        if "exclude" in change:
            ticker = change["exclude"]
            if ticker not in w:
                notes.append(f"{ticker}: not held, nothing to exclude")
                continue
            removed = w.pop(ticker)
            same_group = [t for t in w if (t in BONDS) == (ticker in BONDS)]
            pool_total = sum(w[t] for t in same_group)
            if pool_total <= TOLERANCE:
                raise ProposalError("NO_REDISTRIBUTION_POOL", f"Cannot exclude {ticker}: no remaining holding in its funding group")
            for t in same_group:
                w[t] += removed * (w[t] / pool_total)
            continue

        ticker, requested = change["ticker"], int(change["add_pct"])

        current = w.get(ticker, 0)
        if not enforce_caps:
            delta = requested
        else:
            if ticker in CRYPTO and not crypto_allowed:
                notes.append(f"{ticker}: crypto not allowed for this profile, applied 0%")
                delta = 0
            else:
                cap = _category_cap(ticker, band, crypto_allowed)
                if ticker in CRYPTO:
                    other = sum(w.get(t, 0) for t in CRYPTO if t != ticker)
                    cap = max(cap - other, 0)  # combined cap across both crypto tickers
                elif cap is None and ticker not in ETFS:
                    cap = stock_cap
                desired = current + requested
                applied = min(desired, cap) if (requested > 0 and cap is not None) else max(desired, 0)
                delta = applied - current
                if requested > 0 and cap is not None and applied < desired:
                    label = "combined crypto cap" if ticker in CRYPTO else \
                             "gold cap" if ticker == "GLD" else "single-stock cap"
                    notes.append(f"{ticker}: requested {requested:g}%, applied {delta:g}% "
                                 f"({band} band {label})")

        if delta != 0:
            pool = {t: w[t] for t in w if t not in BONDS and t != ticker}
            pool_total = sum(pool.values())
            if current + delta < -TOLERANCE:
                raise ProposalError("INSUFFICIENT_HOLDING", f"Cannot sell {abs(delta):g} points of {ticker}; only {current:g} held")
            if pool_total <= TOLERANCE or delta > pool_total + TOLERANCE:
                raise ProposalError("INSUFFICIENT_FUNDS", f"Cannot fund {delta:g} points of {ticker} from the other non-bond holdings")
            for t in pool:
                w[t] = max(0.0, w[t] - delta * (pool[t] / pool_total))
            w[ticker] = max(0.0, current + delta)

    if not any(w.get(t, 0) > 0 for t in BONDS):
        raise ProposalError("NO_ROUNDING_RESERVE", "The engine's rounding policy requires a bond holding")
    rounded = round_weights(w)
    weights = {t: v / 100 for t, v in rounded.items()}
    _check_weights(weights)
    if any(abs(rounded.get(t, 0) - w.get(t, 0)) > TOLERANCE for t in BONDS):
        notes.append("Whole-percent rounding assigned its residual to the largest bond holding")
    return weights, notes


def apply_changes(profile, changes, data_dir="alphaforge_starter", profiles_path="profiles.json"):
    """Apply caps. Invalid requests raise ProposalError; evaluate() returns statuses.

    This transforms weights only; it does not establish historical risk fit.
    """
    weights, notes = _apply(profile, changes, enforce_caps=True,
                             data_dir=data_dir, profiles_path=profiles_path)
    return {"weights": weights, "notes": notes}


def validate(weights, band, start=None, end=None, rebalance="monthly",
              data_dir="alphaforge_starter", profiles_path="profiles.json", crypto_allowed=None):
    """Backtest weights (fractions summing to 1) and check them against band limits.

    Default period: last 5 years of data in data_dir. Currency: CAD throughout
    (see backtest_viewer.cad_prices). Only days when every holding traded.
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
        limits = _load_profiles(profiles_path)["band_limits"][band]
        prices, fx = _load_data(data_dir)
        end_ts = pd.Timestamp(end) if end else prices["date"].max()
        start_ts = pd.Timestamp(start) if start else end_ts - pd.DateOffset(years=5)
        if start_ts >= end_ts:
            return _failed("INVALID_REQUEST", "INVALID_PERIOD", "start must precede end")
        active = {t: v for t, v in weights.items() if v > 0}
        df = bv.price_table(prices, fx, list(active), start_ts, end_ts)
        value = bv.portfolio_value(df, active, rebalance)
        metrics = {k: _plain(v) for k, v in bv.metrics(value).items()}
        if any(not math.isfinite(metrics[k]) for k in ("volatility_pct", "max_drawdown_pct", "annual_growth_pct")):
            raise ValueError("Risk metrics are not finite")
    except (FileNotFoundError, KeyError, ValueError) as error:
        return _failed("MISSING_INFO", "DATA_UNAVAILABLE", str(error))
    single_stock_pct = max([weights[t] * 100 for t in weights if t not in ETFS and t not in CRYPTO],
                            default=0.0)
    checks = {
        "max_volatility_pct": {"limit": limits["max_volatility_pct"], "value": metrics["volatility_pct"],
                                "passes": metrics["volatility_pct"] <= limits["max_volatility_pct"]},
        "max_drawdown_pct": {"limit": limits["max_drawdown_pct"], "value": metrics["max_drawdown_pct"],
                              "passes": metrics["max_drawdown_pct"] >= limits["max_drawdown_pct"]},
        "max_single_stock_pct": {"limit": limits["max_single_stock_pct"], "value": round(single_stock_pct, 1),
                                  "passes": single_stock_pct <= limits["max_single_stock_pct"]},
    }
    crypto_pct = sum(weights.get(t, 0) for t in CRYPTO) * 100
    gold_pct = weights.get("GLD", 0) * 100
    checks["max_crypto_pct"] = {"limit": EXTRA_CAPS[band]["crypto"], "value": crypto_pct,
                                "passes": crypto_pct <= EXTRA_CAPS[band]["crypto"] + TOLERANCE}
    checks["max_gold_pct"] = {"limit": EXTRA_CAPS[band]["gold"], "value": gold_pct,
                              "passes": gold_pct <= EXTRA_CAPS[band]["gold"] + TOLERANCE}
    checks["crypto_allowed"] = {"limit": crypto_allowed, "value": crypto_pct,
                                 "passes": (crypto_pct == 0 or crypto_allowed is True)}
    missing_permission = crypto_pct > 0 and crypto_allowed is None
    if missing_permission:
        checks["crypto_allowed"]["passes"] = None
    for check in checks.values():
        if check["passes"] is not None:
            check["passes"] = bool(check["passes"])
    passes = all(c["passes"] is True for c in checks.values())
    status = "MISSING_INFO" if missing_permission else "PASS" if passes else "CONFLICT"
    reasons = [{"code": name, **check} for name, check in checks.items() if check["passes"] is not True]
    return {**metrics, "checks": checks, "passes": passes, "status": status, "reasons": reasons,
            "period": {"first_date": df.index[0].date().isoformat(),
                       "last_date": df.index[-1].date().isoformat(), "observations": len(df)},
            "currency": "CAD", "rebalance": rebalance,
            "method": "monthly_first_observed_close_v2" if rebalance == "monthly" else "buy_and_hold_v1"}


def evaluate(profile_id, changes, data_dir="alphaforge_starter", profiles_path="profiles.json"):
    """The function agents call: base vs. as-requested (no caps) vs. adjusted (capped)."""
    try:
        profile = get_profile(profile_id, profiles_path)
        prices, _ = _load_data(data_dir)
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
        try:
            weights, notes = _apply(profile, changes, enforce_caps, data_dir, profiles_path)
            return {"weights": weights, "validation": validate(weights, band, data_dir=data_dir,
                        profiles_path=profiles_path, crypto_allowed=profile["crypto_allowed"])}, notes
        except ProposalError as error:
            failure = _failed("INVALID_REQUEST", error.code, str(error))
            return {"weights": None, "validation": failure}, [str(error)]

    base = {"weights": profile["weights"],
            "validation": validate(profile["weights"], band, data_dir=data_dir, profiles_path=profiles_path,
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
                    trial = changes[:i] + [{**change, "add_pct": x}] + changes[i + 1:]
                    try:
                        weights, _ = _apply(profile, trial, enforce_caps=False,
                                             data_dir=data_dir, profiles_path=profiles_path)
                    except ProposalError:
                        continue
                    if validate(weights, band, data_dir=data_dir, profiles_path=profiles_path,
                                crypto_allowed=profile["crypto_allowed"])["passes"]:
                        found = x
                        break
                max_allowed[change["ticker"]] = found

    return {"status": status, "base": base, "as_requested": as_requested, "adjusted": adjusted,
            "notes": notes, "outside_profile": outside_profile, "max_allowed": max_allowed}
