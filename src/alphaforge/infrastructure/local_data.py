"""Local CSV/JSON adapter. Default paths do not depend on the shell directory."""
import functools
import json
from pathlib import Path
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = REPOSITORY_ROOT / "dataset"
DEFAULT_PROFILES_PATH = REPOSITORY_ROOT / "profiles.json"


class LocalPortfolioRepository:
    @functools.lru_cache(maxsize=4)
    def load_data(self, data_dir=None):
        folder = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
        # CSV fields are addressed by header name, independent of column order.
        prices = pd.read_csv(folder / "prices_daily.csv", parse_dates=["date"])
        fx = pd.read_csv(folder / "fx_usdcad_daily.csv", parse_dates=["date"]).sort_values("date")
        return prices, fx

    @functools.lru_cache(maxsize=4)
    def load_profiles(self, profiles_path=None):
        path = Path(profiles_path) if profiles_path is not None else DEFAULT_PROFILES_PATH
        return json.loads(path.read_text(encoding="utf-8"))

    def write_profiles(self, config, out=None):
        path = Path(out) if out is not None else DEFAULT_PROFILES_PATH
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        self.load_profiles.cache_clear()
