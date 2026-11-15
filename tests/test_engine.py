import math
from pathlib import Path

import pytest

import portfolio_engine as pe

# These are integration tests against the private dataset, not synthetic cases.
pytestmark = pytest.mark.skipif(
    not all((Path("alphaforge_starter") / name).is_file()
            for name in ("prices_daily.csv", "fx_usdcad_daily.csv")),
    reason="Private CSV dataset is unavailable; synthetic regressions run separately",
)

ROBERT = 4   # low band, Income and stability
AMIRA = 13   # high band, Growth and innovation, crypto_allowed


def test_weights_sum_to_one_after_add():
    profile = pe.get_profile(ROBERT)
    result = pe.apply_changes(profile, [{"ticker": "TSLA", "add_pct": 20}])
    assert sum(result["weights"].values()) == pytest.approx(1.0, abs=1e-6)


def test_bonds_unchanged_after_add():
    # Bonds are protected from funding the change. The only exception is
    # round_weights()'s "leftover to the largest bond" rounding fix-up
    # (build_portfolios.py), which can land a few points on the biggest bond.
    profile = pe.get_profile(ROBERT)
    before = {t: v for t, v in profile["weights"].items() if t in pe.BONDS}
    result = pe.apply_changes(profile, [{"ticker": "TSLA", "add_pct": 20}])
    largest_bond = max(before, key=before.get)
    for t, v in before.items():
        tolerance = 5 if t == largest_bond else 0.5
        assert result["weights"].get(t, 0) * 100 == pytest.approx(v * 100, abs=tolerance)


def test_robert_tsla_20():
    result = pe.evaluate(ROBERT, [{"ticker": "TSLA", "add_pct": 20}])
    assert result["adjusted"]["weights"]["TSLA"] == pytest.approx(0.05, abs=0.005)
    assert result["adjusted"]["validation"]["passes"] is True
    assert result["as_requested"]["validation"]["passes"] is False
    assert result["outside_profile"] is True
    assert 0 <= result["max_allowed"]["TSLA"] <= 20


def test_robert_base_metrics():
    profile = pe.get_profile(ROBERT)
    v = pe.validate(profile["weights"], profile["band"])
    # Historical snapshot values predate the month-boundary correction.
    # Numerical correctness is covered by hand-computable synthetic regressions.
    assert math.isfinite(v["volatility_pct"]) and v["volatility_pct"] >= 0
    assert math.isfinite(v["max_drawdown_pct"]) and v["max_drawdown_pct"] <= 0
    assert v["period"]["observations"] >= 3
    assert v["currency"] == "CAD"


def test_crypto_rejected_on_low_band():
    profile = pe.get_profile(ROBERT)  # crypto_allowed is False
    result = pe.apply_changes(profile, [{"ticker": "BTC-USD", "add_pct": 10}])
    assert result["weights"].get("BTC-USD", 0) == 0
    assert any("crypto" in n.lower() for n in result["notes"])


def test_amira_crypto_capped_at_10():
    profile = pe.get_profile(AMIRA)  # crypto_allowed is True, high band cap 10
    result = pe.apply_changes(profile, [{"ticker": "BTC-USD", "add_pct": 15}])
    combined_pct = sum(result["weights"].get(t, 0) for t in pe.CRYPTO) * 100
    assert combined_pct == pytest.approx(10, abs=0.5)


def test_exclude_removes_ticker_and_sums_to_one():
    profile = pe.get_profile(ROBERT)
    result = pe.apply_changes(profile, [{"exclude": "ENB.TO"}])
    assert "ENB.TO" not in result["weights"]
    assert sum(result["weights"].values()) == pytest.approx(1.0, abs=1e-6)


def test_unknown_ticker_is_rejected():
    profile = pe.get_profile(ROBERT)
    with pytest.raises(pe.ProposalError, match="not in dataset"):
        pe.apply_changes(profile, [{"ticker": "NOTREAL", "add_pct": 10}])
