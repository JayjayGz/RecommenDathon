import pytest

import risk

TSLA_3Y = dict(ticker="TSLA", start="2023-11-12", end="2026-11-12")


@pytest.mark.xfail(reason="risk_measures not implemented yet", raises=NotImplementedError)
def test_tsla_volatility():
    m = risk.risk_measures(**TSLA_3Y)
    assert m["volatility_pct"] == pytest.approx(57.8, abs=1.0)


@pytest.mark.xfail(reason="risk_measures not implemented yet", raises=NotImplementedError)
def test_tsla_max_drawdown():
    m = risk.risk_measures(**TSLA_3Y)
    assert m["max_drawdown_pct"] == pytest.approx(-54.2, abs=1.0)
