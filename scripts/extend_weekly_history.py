"""Append missing selected assets using supplied daily data, never synthetic history.

No network calls. The source weekly file is never written by this builder.
Output retains its original bytes as a prefix and appends the new observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

NUMERIC = ['open', 'high', 'low', 'close', 'adj_close', 'volume']
COLUMNS = ['ticker', 'date', *NUMERIC, 'currency']
PRICE = NUMERIC[:-1]
VERSION = 'weekly-arithmetic-mean-wfri-v1'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_prices(frame: pd.DataFrame) -> None:
    if frame.empty:
        raise ValueError('No observations available')
    if not set(COLUMNS).issubset(frame.columns):
        raise ValueError('Missing price columns')
    if frame[['ticker', 'date', 'currency']].isna().any().any():
        raise ValueError('Missing identity, date or currency')
    if frame.duplicated(['ticker', 'date']).any():
        raise ValueError('Duplicate ticker/date')
    if not np.isfinite(frame[NUMERIC].to_numpy(dtype=float)).all():
        raise ValueError('Missing or nonfinite numeric values')
    if (frame[PRICE] <= 0).any().any() or (frame.volume < 0).any():
        raise ValueError('Nonpositive price or negative volume')
    if (frame.high < frame[['open', 'close']].max(axis=1) - 1e-6).any():
        raise ValueError('High is below open/close')
    if (frame.low > frame[['open', 'close']].min(axis=1) + 1e-6).any():
        raise ValueError('Low is above open/close')
    if (frame.high < frame.low).any():
        raise ValueError('High below low')
    if (frame.groupby('ticker').currency.nunique() != 1).any():
        raise ValueError('Mixed currencies for one ticker')


def weekly_means(daily: pd.DataFrame, start: str, as_of: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    start_date, cutoff = pd.Timestamp(start), pd.Timestamp(as_of)
    if start_date > cutoff:
        raise ValueError('Start must be on or before as_of')
    values = daily.copy()
    values['date'] = pd.to_datetime(values['date'], errors='raise')
    if values.date.isna().any():
        raise ValueError('Invalid date')
    values = values.loc[values.date.between(start_date, cutoff)].copy()
    validate_prices(values)
    frames, coverage = [], []
    for ticker, group in values.groupby('ticker', sort=True):
        group = group.sort_values('date')
        indexed = group.set_index('date')
        # Saturday through Friday, right-closed, labeled Friday. Only observed
        # days participate; no forward-fill, pre-inception rows or interpolation.
        result = indexed[NUMERIC].resample('W-FRI', closed='right', label='right').mean()
        counts = indexed['close'].resample('W-FRI', closed='right', label='right').count()
        result = result.loc[(counts > 0) & (result.index <= cutoff)].round(4)
        if result.empty:
            raise ValueError(f'No completed weekly bucket for {ticker}')
        result = result.reset_index()
        result['ticker'] = ticker
        result['currency'] = group.currency.iloc[0]
        frames.append(result[COLUMNS])
        used = group.loc[group.date <= result.date.max()]
        gaps = pd.date_range(result.date.min(), result.date.max(), freq='W-FRI').difference(result.date)
        coverage.append(dict(ticker=ticker, currency=group.currency.iloc[0],
                             first_daily_date=used.date.min().date().isoformat(),
                             last_daily_date=used.date.max().date().isoformat(),
                             daily_rows=len(used), first_week=result.date.min().date().isoformat(),
                             last_week=result.date.max().date().isoformat(), weekly_rows=len(result),
                             empty_weeks=len(gaps), zero_volume_daily_rows=int((used.volume == 0).sum()),
                             history_starts_after_requested_start=bool(used.date.min() > start_date + pd.Timedelta(days=7))))
    combined = pd.concat(frames, ignore_index=True)
    validate_prices(combined)
    return combined, pd.DataFrame(coverage)


def extend(selection: Path, weekly: Path, daily: Path, output_dir: Path,
           start: str = '2016-01-01', as_of: str = '2026-11-15') -> dict:
    sources = {name: {'path': str(path.resolve()), 'sha256': sha256(path)}
               for name, path in [('selection', selection), ('weekly', weekly), ('daily', daily)]}
    original = weekly.read_bytes()
    base = pd.read_csv(weekly, parse_dates=['date'])
    selected = pd.read_csv(selection, dtype={'ticker': str})
    if list(base.columns) != COLUMNS:
        raise ValueError('Unexpected weekly column order')
    if base.duplicated(['ticker', 'date']).any():
        raise ValueError('Existing weekly file has duplicate keys')
    if selected.ticker.isna().any() or selected.ticker.duplicated().any():
        raise ValueError('Missing/duplicate selection symbol')
    missing = sorted(set(selected.ticker) - set(base.ticker))
    if not missing:
        raise ValueError('No selected tickers are missing; nothing to append')
    history = pd.read_csv(daily, parse_dates=['date'])
    if set(missing) - set(history.ticker):
        raise ValueError(f'Daily history missing for {set(missing) - set(history.ticker)}')
    additions, coverage = weekly_means(history.loc[history.ticker.isin(missing)], start, as_of)
    if set(additions.ticker) != set(missing):
        raise ValueError('Not all missing symbols produced weekly observations')
    # Match period convention against existing overlapping non-crypto examples.
    controls = {}
    for ticker in ['MSFT', 'QQQ', 'GLD']:
        if ticker not in set(history.ticker) & set(base.ticker):
            continue
        control, _ = weekly_means(history.loc[history.ticker == ticker], start, as_of)
        joined = control.merge(base.loc[base.ticker == ticker], on=['ticker', 'date', 'currency'], suffixes=('_mean', '_existing'))
        if joined.empty:
            raise ValueError('No overlapping control weeks')
        price_error = max(float((joined[f'{c}_mean'] - joined[f'{c}_existing']).abs().max()) for c in PRICE)
        volume_error = float((joined.volume_mean - joined.volume_existing).abs().max())
        if price_error > 0.00011 or volume_error > 0.00011:
            raise ValueError(f'Existing weekly convention differs for {ticker}')
        controls[ticker] = dict(weeks=len(joined), max_price_difference=price_error,
                                max_volume_difference=volume_error, price_tolerance=0.00011)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / 'top100_hebdo_2016_complet.csv'
    if output.resolve() in {weekly.resolve(), daily.resolve(), selection.resolve()}:
        raise ValueError('Output must not overwrite an input')
    appended_text = additions.to_csv(index=False, header=False, date_format='%Y-%m-%d', float_format='%.4f', lineterminator='\n')
    output.write_bytes(original + (b'' if original.endswith(b'\n') else b'\n') + appended_text.encode('utf-8'))
    coverage_file = output_dir / 'top100_hebdo_2016_couverture_ajouts.csv'
    coverage.to_csv(coverage_file, index=False)
    reread = pd.read_csv(output, parse_dates=['date'])
    assert output.read_bytes().startswith(original)
    assert reread.iloc[:len(base)].equals(base)
    assert len(reread) == len(base) + len(additions)
    assert not reread.duplicated(['ticker', 'date']).any()
    assert set(selected.ticker).issubset(set(reread.ticker))
    assert set(reread.ticker) == set(base.ticker) | set(missing)
    assert (additions.date.dt.dayofweek == 4).all()
    assert additions.date.max() <= pd.Timestamp(as_of)
    for name, path in [('selection', selection), ('weekly', weekly), ('daily', daily)]:
        assert sha256(path) == sources[name]['sha256'], f'Input changed during processing: {name}'
    manifest = dict(method=VERSION, requested_start=start, as_of=as_of, input_files=sources,
                    source_kind='Supplied local daily history; no live download or independently verified market provenance',
                    aggregation={'columns': NUMERIC, 'operation': 'arithmetic mean per observed daily value',
                                 'week': 'W-FRI; Saturday through Friday; right-closed; right-labeled',
                                 'price_decimals': 4, 'volume': 'mean daily volume, not weekly total',
                                 'currencies': 'original listing currency; no FX conversion',
                                 'missing_history': 'no fill or interpolation; exclude unobserved weeks and future-labeled new buckets'},
                    added_tickers=missing, selected_tickers=len(selected), selected_covered=len(selected),
                    original_rows=len(base), added_rows=len(additions), total_rows=len(reread),
                    original_tickers=int(base.ticker.nunique()), total_tickers=int(reread.ticker.nunique()),
                    coverage=coverage.to_dict('records'), convention_controls=controls,
                    preserved_original_future_labels=base.loc[base.date > pd.Timestamp(as_of), ['ticker', 'date']].assign(date=lambda x: x.date.dt.strftime('%Y-%m-%d')).to_dict('records'),
                    limitations=['Existing weekly rows are preserved byte-for-byte, not recomputed or certified.',
                                 'Some assets have no supplied history as far back as 2016.',
                                 'Existing future Friday labels may refer to an incomplete week; do not assume final observations.',
                                 'Weekly OHLC values are averages of daily OHLC, not traditional first/max/min/last weekly candles.',
                                 'Adjusted prices inherit the supplied snapshot; no split or dividend adjustment is reapplied.',
                                 'Averages of historical adjusted prices are not executable trade prices.'],
                    outputs={'weekly': {'path': str(output.resolve()), 'sha256': sha256(output)},
                             'coverage': {'path': str(coverage_file.resolve()), 'sha256': sha256(coverage_file)}},
                    checks={'all_34_selected_present': True, 'original_bytes_preserved': True,
                            'duplicate_ticker_dates': 0, 'new_future_labels': 0,
                            'new_numeric_values_finite': True, 'new_ohlc_bounds_valid': True})
    manifest_file = output_dir / 'top100_hebdo_2016_manifest.json'
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--weekly', type=Path, required=True)
    parser.add_argument('--daily', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--start', default='2016-01-01')
    parser.add_argument('--as-of', default='2026-11-15')
    args = parser.parse_args()
    result = extend(args.selection, args.weekly, args.daily, args.output_dir, args.start, args.as_of)
    print(json.dumps({k: result[k] for k in ['added_tickers', 'original_rows', 'added_rows', 'total_rows', 'total_tickers', 'checks']}, ensure_ascii=False, indent=2))
