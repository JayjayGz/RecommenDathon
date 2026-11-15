"""Currency guards also protect direct engine and reference-builder callers."""
import pandas as pd
import pytest

from alphaforge.domain.market_data import cad_prices


@pytest.mark.parametrize("currencies", [["JPY", "JPY"], ["CAD", "USD"], ["CAD", None]])
def test_conversion_rejects_unsupported_or_inconsistent_currency(currencies):
    prices, fx = frames(currencies)
    with pytest.raises(ValueError, match="unsupported or inconsistent currency"):
        cad_prices(prices, fx, "TEST")


def frames(currencies):
    dates = pd.to_datetime(["2025-01-02", "2025-01-03"])
    return (pd.DataFrame({"ticker": "TEST", "date": dates, "adj_close": [100., 120.],
                          "currency": currencies}),
            pd.DataFrame({"date": dates[:1], "usdcad": [1.25]}))


@pytest.mark.parametrize("currency, expected", [("CAD", [100., 120.]), ("USD", [125., 150.])])
def test_supported_conversion_uses_preceding_fx(currency, expected):
    prices, fx = frames([currency, currency])
    assert cad_prices(prices, fx, "TEST").tolist() == expected
