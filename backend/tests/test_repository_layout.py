"""Layer boundaries and storage behavior after the repository migration."""
import ast
import json
from pathlib import Path

import pandas as pd
import pytest

from alphaforge.application.reference_portfolios import build_profiles
from alphaforge.bootstrap import create_engine
from alphaforge.domain.reference_portfolios import BANDS, STYLES
from alphaforge.infrastructure.local_data import (
    DEFAULT_DATA_DIR, DEFAULT_PROFILES_PATH, LocalPortfolioRepository,
)

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def test_layer_imports_and_domain_io_boundaries():
    for layer in ("domain", "application"):
        files = list((BACKEND / "src/alphaforge" / layer).glob("*.py"))
        assert files, f"Missing {layer} modules"
        for file in files:
            tree = ast.parse(file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    assert not module.startswith(("alphaforge.infrastructure", "alphaforge.presentation")), file
                    if layer == "domain":
                        assert not module.startswith("alphaforge.application"), file
                if layer == "domain" and isinstance(node, ast.Call):
                    name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                    assert name not in {"open", "read_csv", "to_csv", "read_text", "write_text"}, file


def test_default_paths_and_profile_loading_ignore_shell_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert DEFAULT_DATA_DIR == ROOT / "dataset"
    assert DEFAULT_PROFILES_PATH == ROOT / "profiles.json"
    assert create_engine().get_profile(4)["id"] == 4


@pytest.mark.parametrize("price_csv", [
    "ticker,date,adj_close,currency\nA,2025-01-02,100,CAD\n",
    "date,ticker,adj_close,currency\n2025-01-02,A,100,CAD\n",
])
def test_price_column_order_and_explicit_repository_paths(tmp_path, price_csv):
    (tmp_path / "prices_weekly.csv").write_text(
        price_csv, encoding="utf-8")
    (tmp_path / "fx_usdcad_daily.csv").write_text(
        "date,usdcad\n2025-01-02,1.25\n", encoding="utf-8")
    repository = LocalPortfolioRepository()
    prices, fx = repository.load_data(tmp_path)
    assert prices.iloc[0]["ticker"] == "A"
    assert prices.iloc[0]["date"] == pd.Timestamp("2025-01-02")
    assert prices.iloc[0]["adj_close"] == 100
    assert fx.iloc[0]["usdcad"] == 1.25
    out = tmp_path / "profiles.json"
    repository.write_profiles({"profiles": []}, out)
    assert repository.load_profiles(out) == {"profiles": []}


def test_missing_holdings_return_information_request(tmp_path):
    # A usable CSV is insufficient when the requested profile holdings are absent.
    (tmp_path / "prices_weekly.csv").write_text(
        "date,ticker,adj_close,currency\n2025-01-02,TSLA,100,CAD\n", encoding="utf-8")
    (tmp_path / "fx_usdcad_daily.csv").write_text(
        "date,usdcad\n2025-01-02,1.25\n", encoding="utf-8")
    result = create_engine().evaluate(4, [], data_dir=tmp_path)
    assert result["status"] == "MISSING_INFO"
    assert result["outside_profile"] is None
    assert result["base"]["validation"]["passes"] is False


def test_reference_builder_uses_port_and_preserves_flat_market_control():
    tickers = {ticker for band in BANDS.values() for ticker in band["bonds"]}
    tickers |= {ticker for style in STYLES.values() for groups in style.values()
                for _, names in groups for ticker in names}
    tickers |= {"GLD", "BTC-USD", "ETH-USD"}
    dates = pd.bdate_range("2025-01-02", periods=64)

    class MemoryRepository:
        saved = None

        def load_data(self, data_dir):
            prices = pd.DataFrame([
                {"date": date, "ticker": ticker, "adj_close": 100., "currency": "CAD"}
                for ticker in tickers for date in dates
            ])
            return prices, pd.DataFrame({"date": dates, "usdcad": 1.25})

        def write_profiles(self, config, out):
            self.saved = json.loads(json.dumps(config))

    repository = MemoryRepository()
    config, table = build_profiles(repository)
    assert repository.saved == config
    assert len(config["profiles"]) == len(table) == 15
    for profile in config["profiles"]:
        assert abs(sum(profile["weights"].values()) - 1) < 1e-8
        assert profile["validation"]["passes"] is True
        assert profile["validation"]["end_value"] == 10000
