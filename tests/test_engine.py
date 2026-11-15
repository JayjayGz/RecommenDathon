import pytest

import portfolio_engine as pe

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
    allowed = result["max_allowed"]["TSLA"]
    assert 0 <= allowed["requested_pct"] <= 20
    assert allowed["realized_pct"] == pytest.approx(5.0, abs=0.5)


def test_robert_base_metrics():
    profile = pe.get_profile(ROBERT)
    v = pe.validate(profile["weights"], profile["band"])
    assert v["volatility_pct"] == pytest.approx(4.7, abs=0.3)
    assert v["max_drawdown_pct"] == pytest.approx(-9.4, abs=0.3)


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


def test_unknown_ticker_gives_note_and_leaves_weights_unchanged():
    profile = pe.get_profile(ROBERT)
    result = pe.apply_changes(profile, [{"ticker": "NOTREAL", "add_pct": 10}])
    assert any("not in dataset" in n for n in result["notes"])
    for t, v in profile["weights"].items():
        assert result["weights"].get(t, 0) == pytest.approx(v, abs=0.01)


def test_unknown_ticker_marked_unsupported_not_silently_passed():
    profile = pe.get_profile(ROBERT)
    result = pe.evaluate(ROBERT, [{"ticker": "NOTREAL", "add_pct": 10}])
    assert result["unsupported"] == ["NOTREAL"]


def test_small_disallowed_crypto_still_fails_validation():
    # Regression: validate() used to only check vol/drawdown/single-stock, so a
    # small crypto add on a profile with crypto_allowed=False could pass even
    # though crypto isn't allowed at all for that profile.
    profile = pe.get_profile(6)  # medium band, crypto_allowed False
    assert profile["crypto_allowed"] is False
    result = pe.evaluate(6, [{"ticker": "BTC-USD", "add_pct": 2}])
    assert result["as_requested"]["validation"]["checks"]["max_crypto_pct"]["passes"] is False
    assert result["outside_profile"] is True


def test_extreme_request_never_produces_negative_weights():
    # Regression: an uncapped request larger than the available non-bond
    # holdings used to push weights (including bonds) negative.
    profile = pe.get_profile(ROBERT)
    result = pe.evaluate(ROBERT, [{"ticker": "TSLA", "add_pct": 100}])
    for view in ("as_requested", "adjusted"):
        for t, v in result[view]["weights"].items():
            assert v >= 0, f"{view} has negative weight for {t}: {v}"
