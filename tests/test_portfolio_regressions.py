"""Deterministic fixtures for proposal failures and correct monthly accounting.

Prices are fabricated and constant except for explicit accounting examples.
They are not claims about historical markets or the real dataset.
"""

from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from alphaforge.domain import backtest as bv
from alphaforge.bootstrap import create_engine

pe = create_engine()


@pytest.fixture
def market(monkeypatch):
    config = json.loads((Path(__file__).resolve().parents[1] / "profiles.json").read_text())
    tickers = {t for profile in config["profiles"] for t in profile["weights"]}
    tickers |= {"TSLA", "GLD", "BTC-USD", "ETH-USD"}
    dates = pd.bdate_range("2025-01-02", periods=64)
    prices = pd.DataFrame([
        {"date": date, "ticker": ticker, "adj_close": 100.0, "currency": "CAD"}
        for ticker in sorted(tickers) for date in dates
    ])
    fx = pd.DataFrame({"date": dates, "usdcad": 1.25})
    monkeypatch.setattr(pe, "_load_data", lambda _: (prices, fx))
    monkeypatch.setattr(pe, "_load_profiles", lambda _: config)
    return config, prices, fx


def test_month_boundary_gain_is_earned():
    prices = pd.DataFrame({"A": [100., 100., 200., 200.]},
                          index=pd.to_datetime(["2026-01-29", "2026-01-30", "2026-02-02", "2026-02-03"]))
    monthly = bv.portfolio_value(prices, {"A": 1.}, "monthly")
    hold = bv.portfolio_value(prices, {"A": 1.}, "none")
    assert monthly.tolist() == pytest.approx([10000, 10000, 20000, 20000])
    assert monthly.tolist() == pytest.approx(hold.tolist())


def test_month_boundary_loss_is_earned():
    prices = pd.DataFrame({"A": [100., 100., 50., 50.]},
                          index=pd.to_datetime(["2026-01-29", "2026-01-30", "2026-02-02", "2026-02-03"]))
    value = bv.portfolio_value(prices, {"A": 1.})
    assert value.tolist() == pytest.approx([10000, 10000, 5000, 5000])
    assert bv.metrics(value)["max_drawdown_pct"] == -50


def test_monthly_rebalances_after_marking_old_units_at_new_close():
    prices = pd.DataFrame({"A": [100., 200., 400., 400.], "B": [100., 100., 100., 200.]},
                          index=pd.to_datetime(["2026-01-29", "2026-01-30", "2026-02-02", "2026-02-03"]))
    assert bv.portfolio_value(prices, {"A": .5, "B": .5}).tolist() == pytest.approx(
        [10000, 15000, 25000, 37500])
    assert bv.portfolio_value(prices, {"A": .5, "B": .5}, "none").iloc[-1] == 30000


@pytest.mark.parametrize("weights", [{"A": -.1, "B": 1.1}, {"A": float("nan"), "B": 1}, {"A": .4, "B": .4}])
def test_backtest_rejects_invalid_weights(weights):
    prices = pd.DataFrame({"A": [100., 100., 100.], "B": [100., 100., 100.]},
                          index=pd.date_range("2026-01-01", periods=3))
    with pytest.raises(ValueError):
        bv.portfolio_value(prices, weights)


def test_flat_prices_remain_flat_through_rebalance(market):
    result = pe.evaluate(4, [])
    assert result["status"] == "PASS" and result["outside_profile"] is False
    assert result["base"]["validation"]["end_value"] == 10000
    assert result["base"]["validation"]["volatility_pct"] == pytest.approx(0)
    assert result["base"]["validation"]["max_drawdown_pct"] == 0
    assert result["base"]["validation"]["period"]["observations"] == 64


def test_raw_stock_request_conflicts_and_maximum_is_uncapped(market):
    result = pe.evaluate(4, [{"ticker": "TSLA", "add_pct": 20}])
    assert result["status"] == "CONFLICT" and result["outside_profile"] is True
    assert result["as_requested"]["weights"]["TSLA"] == .20
    assert result["adjusted"]["weights"]["TSLA"] == .05
    assert result["adjusted"]["validation"]["status"] == "PASS"
    assert result["max_allowed"]["TSLA"] == 5
    assert any(r["code"] == "max_single_stock_pct" for r in result["as_requested"]["validation"]["reasons"])


def test_exact_single_stock_cap_is_valid(market):
    result = pe.evaluate(4, [{"ticker": "TSLA", "add_pct": 5}])
    assert result["status"] == "PASS"
    assert result["as_requested"]["weights"]["TSLA"] == .05


@pytest.mark.parametrize("profile_id", [4, 6, 11])
def test_forbidden_crypto_is_a_conflict_even_with_flat_prices(market, profile_id):
    result = pe.evaluate(profile_id, [{"ticker": "BTC-USD", "add_pct": 1}])
    assert result["status"] == "CONFLICT" and result["outside_profile"] is True
    assert result["as_requested"]["validation"]["checks"]["crypto_allowed"]["passes"] is False
    assert result["adjusted"]["weights"].get("BTC-USD", 0) == 0
    assert result["max_allowed"]["BTC-USD"] == 0


def test_combined_crypto_cap_is_checked_after_redistribution(market):
    result = pe.evaluate(13, [{"ticker": "BTC-USD", "add_pct": 13}])
    assert result["as_requested"]["validation"]["checks"]["max_crypto_pct"]["passes"] is False
    assert result["adjusted"]["validation"]["checks"]["max_crypto_pct"]["passes"] is True
    combined = sum(result["adjusted"]["weights"].get(t, 0) for t in pe.CRYPTO)
    assert combined <= .10 + 1e-8


def test_gold_cap_included_in_final_verdict(market):
    result = pe.evaluate(4, [{"ticker": "GLD", "add_pct": 11}])
    assert result["status"] == "CONFLICT"
    assert result["as_requested"]["validation"]["checks"]["max_gold_pct"]["passes"] is False
    assert result["adjusted"]["weights"]["GLD"] == .10
    assert result["max_allowed"]["GLD"] == 10


def test_unfundable_request_does_not_create_negative_weights(market):
    result = pe.evaluate(4, [{"ticker": "TSLA", "add_pct": 100}])
    assert result["status"] == "INVALID_REQUEST" and result["outside_profile"] is None
    assert result["as_requested"]["weights"] is None
    assert result["as_requested"]["validation"]["errors"][0]["code"] == "INSUFFICIENT_FUNDS"
    assert all(w >= 0 for w in result["adjusted"]["weights"].values())


@pytest.mark.parametrize("change", [
    {"ticker": "NOTREAL", "add_pct": 10}, {"exclude": "NOTREAL"},
    {"ticker": "XBB.TO", "add_pct": -20}, {"ticker": "TSLA", "add_pct": 20.5},
    {"ticker": "TSLA", "add_pct": float("inf")}, {"ticker": "TSLA", "add_pct": True},
    {"ticker": [], "add_pct": 5}, {"ticker": "TSLA"}, {"ticker": "TSLA", "add_pct": 5, "extra": 1},
])
def test_invalid_request_is_never_a_successful_noop(market, change):
    result = pe.evaluate(4, [change])
    assert result["status"] == "INVALID_REQUEST"
    assert result["outside_profile"] is None
    assert result["as_requested"]["weights"] is None
    assert result["as_requested"]["validation"]["passes"] is False


def test_cannot_sell_more_than_held(market):
    result = pe.evaluate(4, [{"ticker": "RY.TO", "add_pct": -20}])
    assert result["status"] == "INVALID_REQUEST"
    assert result["as_requested"]["validation"]["errors"][0]["code"] == "INSUFFICIENT_HOLDING"


def test_exclude_last_bond_reports_error_instead_of_rounding_crash(market):
    result = pe.evaluate(4, [{"exclude": "XBB.TO"}, {"exclude": "ZST.TO"}])
    assert result["status"] == "INVALID_REQUEST"
    assert result["as_requested"]["validation"]["errors"][0]["code"] == "NO_REDISTRIBUTION_POOL"


def test_invalid_weights_do_not_reach_backtest(market, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Backtest must not run for invalid weights")
    monkeypatch.setattr(bv, "portfolio_value", unexpected)
    result = pe.validate({"XBB.TO": -.25, "TSLA": 1.25}, "low", crypto_allowed=False)
    assert result["status"] == "INVALID_REQUEST"


def test_missing_crypto_permission_needs_information(market):
    result = pe.validate({"XBB.TO": .99, "BTC-USD": .01}, "high")
    assert result["status"] == "MISSING_INFO" and result["passes"] is False


def test_missing_data_never_returns_pass(market, monkeypatch):
    def missing(_):
        raise FileNotFoundError("fixture prices unavailable")
    monkeypatch.setattr(pe, "_load_data", missing)
    result = pe.evaluate(4, [])
    assert result["status"] == "MISSING_INFO" and result["outside_profile"] is None


def test_no_feasible_maximum_is_null_not_an_invented_zero(market):
    result = pe.evaluate(4, [{"ticker": "TSLA", "add_pct": 20}, {"ticker": "BTC-USD", "add_pct": 1}])
    assert result["max_allowed"]["TSLA"] is None  # the other request still violates crypto permission
    assert result["max_allowed"]["BTC-USD"] is None  # the other request still violates the stock cap


def test_profiles_and_request_are_not_mutated(market):
    config = market[0]
    original = deepcopy(config)
    changes = [{"ticker": "TSLA", "add_pct": 20}]
    before = deepcopy(changes)
    pe.evaluate(4, changes)
    assert changes == before and config == original


def test_too_short_history_needs_information(market):
    prices, fx = market[1:]
    # A one-day requested window must not generate NaN risk claims.
    result = pe.validate({"XBB.TO": 1.}, "low", start=prices.date.min(),
                         end=prices.date.min() + pd.Timedelta(days=1), crypto_allowed=False)
    assert result["status"] == "MISSING_INFO"


def test_nonfinite_prices_are_rejected():
    prices = pd.DataFrame({"A": [100., np.nan, 110.]}, index=pd.date_range("2026-01-01", periods=3))
    with pytest.raises(ValueError):
        bv.portfolio_value(prices, {"A": 1.})
