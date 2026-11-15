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
            for t in same_group:
                w[t] += removed * (w[t] / pool_total)
            continue

        ticker, requested = change["ticker"], change["add_pct"]
        if ticker not in valid_tickers:
            notes.append(f"{ticker}: not in dataset")
            continue
        if ticker in BONDS:
            notes.append(f"{ticker}: bonds are protected, change not applied")
            continue

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
            for t in pool:
                w[t] -= delta * (pool[t] / pool_total)
            w[ticker] = current + delta

    rounded = round_weights(w)
    return {t: v / 100 for t, v in rounded.items()}, notes


def apply_changes(profile, changes, data_dir="alphaforge_starter", profiles_path="profiles.json"):
    """Apply proposed changes with band caps enforced. Returns {"weights", "notes"}."""
    weights, notes = _apply(profile, changes, enforce_caps=True,
                             data_dir=data_dir, profiles_path=profiles_path)
    return {"weights": weights, "notes": notes}


def validate(weights, band, start=None, end=None, rebalance="monthly",
              data_dir="alphaforge_starter", profiles_path="profiles.json"):
    """Backtest weights (fractions summing to 1) and check them against band limits.

    Default period: last 5 years of data in data_dir. Currency: CAD throughout
    (see backtest_viewer.cad_prices). Only days when every holding traded.
    """
    prices, fx = _load_data(data_dir)
    end_ts = pd.Timestamp(end) if end else prices["date"].max()
    start_ts = pd.Timestamp(start) if start else end_ts - pd.DateOffset(years=5)

    df = bv.price_table(prices, fx, list(weights), start_ts, end_ts)
    value = bv.portfolio_value(df, weights, rebalance)
    metrics = {k: _plain(v) for k, v in bv.metrics(value).items()}

    limits = _load_profiles(profiles_path)["band_limits"][band]
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
    return {**metrics, "checks": checks, "passes": all(c["passes"] for c in checks.values())}


def evaluate(profile_id, changes, data_dir="alphaforge_starter", profiles_path="profiles.json"):
    """The function agents call: base vs. as-requested (no caps) vs. adjusted (capped)."""
    profile = get_profile(profile_id, profiles_path)
    band = profile["band"]

    def run(enforce_caps):
        weights, notes = _apply(profile, changes, enforce_caps, data_dir, profiles_path)
        return {"weights": weights, "validation": validate(weights, band, data_dir=data_dir,
                                                             profiles_path=profiles_path)}, notes

    base = {"weights": profile["weights"],
            "validation": validate(profile["weights"], band, data_dir=data_dir, profiles_path=profiles_path)}
    as_requested, pre_cap_notes = run(enforce_caps=False)
    adjusted, cap_notes = run(enforce_caps=True)

    notes = list(pre_cap_notes)
    notes += [n for n in cap_notes if n not in notes]
    outside_profile = not as_requested["validation"]["passes"]

    max_allowed = {}
    if outside_profile:
        for i, change in enumerate(changes):
            if "ticker" in change and change.get("add_pct", 0) > 0:
                requested = change["add_pct"]
                found = 0
                for x in range(requested, -1, -1):
                    trial = changes[:i] + [{**change, "add_pct": x}] + changes[i + 1:]
                    weights, _ = _apply(profile, trial, enforce_caps=True,
                                         data_dir=data_dir, profiles_path=profiles_path)
                    if validate(weights, band, data_dir=data_dir, profiles_path=profiles_path)["passes"]:
                        found = x
                        break
                max_allowed[change["ticker"]] = found

    return {"base": base, "as_requested": as_requested, "adjusted": adjusted,
            "notes": notes, "outside_profile": outside_profile, "max_allowed": max_allowed}
