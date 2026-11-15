"""Input snapshot port: calculations and audit must reference identical bytes."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol
import pandas as pd


class DataUnavailable(ValueError):
    def __init__(self, code="DATA_UNAVAILABLE"):
        super().__init__(code)
        self.code = code


@dataclass
class InputSnapshot:
    prices: pd.DataFrame
    fx: pd.DataFrame
    profiles: dict
    manifest: dict

    def load_data(self, data_dir=None):
        return self.prices.copy(deep=True), self.fx.copy(deep=True)

    def load_profiles(self, profiles_path=None):
        return deepcopy(self.profiles)

    def check_holdings(self, profile, changes):
        """The existing engine annualizes at 252 observations/year; reject weekly data."""
        tickers = set(profile["weights"]) | {c.ticker for c in changes}
        for ticker in tickers:
            rows = self.prices[self.prices.ticker == ticker]
            if len(rows) < 3:
                raise DataUnavailable("MISSING_HOLDING_HISTORY")
            gaps = rows.date.sort_values().diff().dt.total_seconds().dropna() / 86400
            if gaps.median() > 3:
                raise DataUnavailable("UNSUPPORTED_OBSERVATION_FREQUENCY")


class SnapshotSource(Protocol):
    def load(self, as_of) -> InputSnapshot: ...
