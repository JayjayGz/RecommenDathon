"""Input snapshot port: calculations and audit must reference identical bytes."""
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Protocol
import pandas as pd
from alphaforge.domain.market_data import observation_convention


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
    assets: dict = field(default_factory=dict)

    def load_data(self, data_dir=None):
        return self.prices.copy(deep=True), self.fx.copy(deep=True)

    def load_profiles(self, profiles_path=None):
        return deepcopy(self.profiles)

    def check_holdings(self, profile, changes):
        """Validate required holdings and record their actual observation convention."""
        tickers = set(profile["weights"]) | {c.ticker for c in changes}
        conventions = set()
        for ticker in sorted(tickers):
            rows = self.prices[self.prices.ticker == ticker]
            if not rows.currency.isin(["CAD", "USD"]).all():
                raise DataUnavailable("UNSUPPORTED_HOLDING_CURRENCY")
            if len(rows) < 3:
                raise DataUnavailable("MISSING_HOLDING_HISTORY")
            try:
                conventions.add(observation_convention(rows.date))
            except ValueError as error:
                raise DataUnavailable("UNSUPPORTED_OBSERVATION_FREQUENCY") from error
            if len(conventions) > 1:
                raise DataUnavailable("UNSUPPORTED_OBSERVATION_FREQUENCY")
        frequency, annualization = conventions.pop()
        self.manifest.update(observation_frequency=frequency, annualization_observations=annualization,
                             annualization_method="observed_cadence_v1", required_tickers=sorted(tickers))


class SnapshotSource(Protocol):
    def load(self, as_of, include_universe=False) -> InputSnapshot: ...
    def load_macro(self, as_of) -> tuple[pd.DataFrame, dict]: ...
