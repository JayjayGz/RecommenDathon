"""Rebuild Friday closing snapshots from hashed market responses, never means.

Yahoo daily closes are used for shares/ETFs and supported closing indices.
Crypto prices are Bitstamp USD last trades in hourly bars ending at or before
Friday 16:00 America/Toronto. Unsupported 16:00 snapshots stay explicitly
missing unless the caller explicitly selects the official-close policy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from extend_weekly_history import COLUMNS, NUMERIC, PRICE, sha256, validate_prices

VERSION = 'friday-1600-toronto-last-observed-v1'
TZ = 'America/Toronto'
SUPPORTED_INDICES = {'^DJI', '^GSPC', '^IXIC', '^N225'}


def verified_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding='utf-8'))
    for record in manifest['sources']:
        if record['status'] != 'complete':
            raise ValueError(f"Failed source: {record['ticker']}")
        if sha256(Path(record['path'])) != record['sha256']:
            raise ValueError(f"Changed source: {record['path']}")
    return manifest


def friday_last(daily: pd.DataFrame, start: str, as_of: str, *, validate_ohlc: bool = True) -> pd.DataFrame:
    """Select one actual whole daily row, never a mean or columnwise last()."""
    rows = daily.copy()
    rows['date'] = pd.to_datetime(rows.date, errors='raise')
    if rows.duplicated(['ticker', 'date']).any():
        raise ValueError('Duplicate daily ticker/date')
    rows = rows.loc[rows.date.between(pd.Timestamp(start), pd.Timestamp(as_of))].copy()
    rows['source_date'] = rows.date.dt.strftime('%Y-%m-%d')
    rows['date'] = rows.date + pd.to_timedelta((4 - rows.date.dt.dayofweek) % 7, unit='D')
    rows = rows.loc[rows.date <= pd.Timestamp(as_of)]
    rows = rows.sort_values(['ticker', 'source_date']).groupby(['ticker', 'date'], sort=True).tail(1)
    # Invalid selected rows fail rather than being replaced by earlier values.
    if validate_ohlc:
        validate_prices(rows)
    else:
        # FX vendor OHLC can be internally inconsistent. Preserve quoted fields
        # with explicit findings, never change measured values to pass bounds.
        if not np.isfinite(rows[NUMERIC].to_numpy(dtype=float)).all():
            raise ValueError('Missing or nonfinite source values')
        if (rows[PRICE] <= 0).any().any() or (rows.volume < 0).any():
            raise ValueError('Nonpositive close/price or negative volume')
        if (rows.groupby('ticker').currency.nunique() != 1).any():
            raise ValueError('Mixed source currencies')
    return rows.sort_values(['ticker', 'date']).reset_index(drop=True)


def crypto_at_1600(hourly: pd.DataFrame, start: str, as_of: str) -> pd.DataFrame:
    """Use the provider's candle close ending at 16:00, never a later close."""
    bars = hourly.copy()
    bars['bar_start_utc'] = pd.to_datetime(bars.bar_start_utc, utc=True)
    if bars.duplicated(['ticker', 'bar_start_utc']).any():
        raise ValueError('Duplicate crypto hourly candle')
    bars['bar_end_utc'] = bars.bar_start_utc + pd.Timedelta(hours=1)
    bars = bars.sort_values(['ticker', 'bar_end_utc'])
    targets = pd.date_range(start, as_of, freq='W-FRI', tz=TZ) + pd.Timedelta(hours=16)
    frames = []
    for ticker, group in bars.groupby('ticker', sort=True):
        for target in targets:
            utc = target.tz_convert('UTC')
            # A zero-volume candle may contain a last price published by the
            # exchange. Copy that exact quote; never construct a forward fill.
            # If the required candle is absent, the observation stays absent.
            eligible = group.loc[group.bar_end_utc == utc]
            if eligible.empty:
                continue
            chosen = eligible.iloc[-1].to_dict()
            chosen.update(date=target.tz_localize(None).normalize(),
                          source_date=chosen['bar_start_utc'].tz_convert(TZ).date().isoformat(),
                          target_timestamp=target.isoformat(),
                          bar_start_utc=chosen['bar_start_utc'].isoformat(),
                          bar_end_utc=chosen['bar_end_utc'].isoformat(),
                          lag_hours=float((utc - chosen['bar_end_utc']).total_seconds() / 3600),
                          adj_close=np.nan)
            # No adjusted-price field is supplied by Bitstamp. It stays missing
            # instead of manufacturing adj_close = close.
            frames.append(chosen)
    if not frames:
        raise ValueError('No crypto prices before Friday 16:00')
    result = pd.DataFrame(frames).sort_values(['ticker', 'date']).reset_index(drop=True)
    # Validate actual source columns without claiming an adjusted source price.
    check = result.assign(adj_close=result.close)
    validate_prices(check)
    return result


def yahoo_daily(manifest: dict) -> tuple[pd.DataFrame, dict, list]:
    rows, metadata, discarded = [], {}, []
    for source in manifest['sources']:
        result = json.loads(Path(source['path']).read_bytes())['chart']['result'][0]
        meta = result['meta']
        ticker = source['ticker']
        if meta['symbol'] != ticker or not meta.get('currency'):
            raise ValueError('Unexpected source identity/currency')
        metadata[ticker] = dict(kind=meta['instrumentType'], currency=meta['currency'],
                                timezone=meta['exchangeTimezoneName'], source=source)
        quote = result['indicators']['quote'][0]
        adjusted = result['indicators'].get('adjclose', [{}])[0].get('adjclose', [])
        for index, timestamp in enumerate(result['timestamp']):
            date = pd.Timestamp(timestamp, unit='s', tz='UTC').tz_convert(meta['exchangeTimezoneName']).date().isoformat()
            values = {c: quote[c][index] for c in ['open', 'high', 'low', 'close', 'volume']}
            values['adj_close'] = adjusted[index] if index < len(adjusted) else None
            if all(values[c] is None for c in ['open', 'high', 'low', 'close']):
                discarded.append(dict(ticker=ticker, date=date, reason='Source has no OHLC observations'))
                continue
            rows.append(dict(ticker=ticker, date=date, currency=meta['currency'], **values,
                             source_path=source['path'], source_sha256=source['sha256'],
                             source_timestamp=int(timestamp), source_index=index))
    return pd.DataFrame(rows), metadata, discarded


def bitstamp_hourly(manifest: dict) -> pd.DataFrame:
    rows = []
    for source in manifest['sources']:
        data = json.loads(Path(source['path']).read_bytes())['data']
        if data['pair'] != source['ticker'].replace('-', '/'):
            raise ValueError('Unexpected Bitstamp pair')
        for index, row in enumerate(data['ohlc']):
            timestamp = int(row['timestamp'])
            if not source['requested_start'] <= timestamp <= source['requested_end']:
                raise ValueError('Unexpected crypto candle interval')
            rows.append(dict(ticker=source['ticker'], currency='USD',
                             bar_start_utc=pd.Timestamp(timestamp, unit='s', tz='UTC'),
                             **{c: float(row[c]) for c in ['open', 'high', 'low', 'close', 'volume']},
                             source_path=source['path'], source_sha256=source['sha256'],
                             source_timestamp=timestamp, source_index=index))
    return pd.DataFrame(rows)


def build(previous: Path, selection: Path, yahoo_path: Path, crypto_path: Path,
          output: Path, unavailable: str = 'missing', start: str = '2016-01-01',
          as_of: str = '2026-11-15') -> dict:
    yahoo = verified_manifest(yahoo_path)
    crypto = verified_manifest(crypto_path)
    previous_hash = sha256(previous)
    original = pd.read_csv(previous, parse_dates=['date'])
    selected = set(pd.read_csv(selection).ticker)
    daily, meta, discarded = yahoo_daily(yahoo)
    if set(meta) != set(original.ticker):
        raise ValueError('Downloaded Yahoo universe differs from requested universe')
    unsupported = sorted(t for t, m in meta.items() if m['kind'] not in {'EQUITY', 'ETF', 'CRYPTOCURRENCY'}
                         and t not in SUPPORTED_INDICES)
    regular = sorted(set(meta) - set(unsupported) - {t for t, m in meta.items() if m['kind'] == 'CRYPTOCURRENCY'})
    shares = friday_last(daily.loc[daily.ticker.isin(regular)], start, as_of)
    shares['provider'] = 'Yahoo Finance'
    shares['price_policy'] = 'last available regular-session close in this Friday-ending week'
    shares.loc[shares.ticker == '^N225', 'price_policy'] = 'last Tokyo session close available before Friday 16:00 Toronto'
    shares['bar_interval'] = '1d'
    shares['target_timestamp'] = shares.date.dt.tz_localize(TZ).add(pd.Timedelta(hours=16)).map(lambda d: d.isoformat())
    hourly = bitstamp_hourly(crypto)
    coins = crypto_at_1600(hourly, start, as_of)
    coins['provider'] = 'Bitstamp official exchange API'
    coins['price_policy'] = 'dernier cours horaire publié par Bitstamp'
    coins['bar_interval'] = '1h'
    if set(coins.ticker) != {t for t, m in meta.items() if m['kind'] == 'CRYPTOCURRENCY'}:
        raise ValueError('Some requested crypto has no verified price')
    exceptions = friday_last(daily.loc[daily.ticker.isin(unsupported)], start, as_of, validate_ohlc=False)
    bad_bounds = ((exceptions.high < exceptions[['open', 'close']].max(axis=1) - 1e-6) |
                  (exceptions.low > exceptions[['open', 'close']].min(axis=1) + 1e-6) |
                  (exceptions.high < exceptions.low))
    source_bounds_findings = exceptions.loc[bad_bounds, ['ticker', 'date', 'open', 'high', 'low', 'close', 'source_path', 'source_index']].copy()
    source_bounds_findings['date'] = source_bounds_findings.date.dt.strftime('%Y-%m-%d')
    exceptions['source_ohlc_bounds_warning'] = bad_bounds
    exceptions['provider'] = 'Yahoo Finance'
    exceptions['bar_interval'] = '1d'
    exceptions['price_policy'] = ('dernier cours de clôture quotidien publié par Yahoo Finance'
                                  if unavailable == 'official-close' else 'missing: daily close cannot verify Friday 16:00 Toronto')
    exceptions['target_timestamp'] = None
    if unavailable == 'missing':
        exceptions[NUMERIC] = np.nan
    combined = pd.concat([shares, coins, exceptions], ignore_index=True).sort_values(['ticker', 'date']).reset_index(drop=True)
    combined['date'] = pd.to_datetime(combined.date)
    if combined.duplicated(['ticker', 'date']).any() or set(combined.ticker) != set(original.ticker):
        raise ValueError('Output has duplicate keys or changed universe')
    if not selected.issubset(set(combined.ticker)):
        raise ValueError('A selected ticker is absent')
    if (combined.date.dt.dayofweek != 4).any() or combined.date.max() > pd.Timestamp(as_of):
        raise ValueError('Non-Friday or future week in output')
    # All populated output fields must refer to a single actual source row.
    output.mkdir(parents=True, exist_ok=True)
    weekly_path = output / 'top100_hebdo_2016_complet.csv'
    combined[COLUMNS].to_csv(weekly_path, index=False, date_format='%Y-%m-%d', lineterminator='\n')
    audit_path = output / 'top100_hebdo_2016_sources_lignes.csv'
    audit_columns = ['ticker', 'date', 'provider', 'price_policy', 'bar_interval', 'source_date',
                     'target_timestamp', 'bar_start_utc', 'bar_end_utc', 'lag_hours',
                     'source_path', 'source_sha256', 'source_timestamp', 'source_index', 'source_ohlc_bounds_warning']
    combined[audit_columns].to_csv(audit_path, index=False, date_format='%Y-%m-%d', lineterminator='\n')
    coverage = []
    for ticker, group in combined.groupby('ticker', sort=True):
        priced = group.loc[group.close.notna()]
        expected = pd.date_range(start, as_of, freq='W-FRI')
        coverage.append(dict(ticker=ticker, kind=meta[ticker]['kind'], currency=meta[ticker]['currency'],
                             provider=group.provider.iloc[0], rows=len(group), verified_prices=len(priced),
                             missing_prices=int(group.close.isna().sum()),
                             first_price_week=priced.date.min().date().isoformat() if len(priced) else None,
                             last_price_week=priced.date.max().date().isoformat() if len(priced) else None,
                             weeks_without_price=len(expected.difference(priced.date)),
                             price_method='official_daily_close' if ticker in unsupported else ('crypto_hourly_close' if meta[ticker]['kind']=='CRYPTOCURRENCY' else 'regular_session_close'),
                             prior_session_rows=int((group.source_date != group.date.dt.strftime('%Y-%m-%d')).sum()),
                             crypto_missing_adjusted_close=bool(meta[ticker]['kind'] == 'CRYPTOCURRENCY')))
    coverage_path = output / 'top100_hebdo_2016_couverture.csv'
    pd.DataFrame(coverage).to_csv(coverage_path, index=False)
    reloaded = pd.read_csv(weekly_path, parse_dates=['date'], float_precision='round_trip')
    for column in NUMERIC:
        np.testing.assert_allclose(reloaded[column], combined[column], rtol=0, atol=0, equal_nan=True)
    assert sha256(previous) == previous_hash
    manifest = dict(method=VERSION, requested_start=start, as_of=as_of, timezone=TZ,
                    label='Dernier cours hebdomadaire',
                    price_methods={'shares_etfs': 'last available regular-session close in the Friday-ending week',
                                   'crypto': 'Bitstamp published hourly close for the candle ending Friday 16:00 America/Toronto; DST handled',
                                   'other_markets': 'last daily Close published by Yahoo in the Friday-ending week'},
                    previous={'path': str(previous.resolve()), 'sha256': previous_hash, 'rows': len(original)},
                    inputs={str(p.resolve()): sha256(p) for p in [selection, yahoo_path, crypto_path]},
                    sources={'yahoo': yahoo['provider'], 'crypto': crypto['provider']},
                    other_markets_policy=unavailable, official_daily_close_tickers=unsupported,
                    total_rows=len(combined), tickers=int(combined.ticker.nunique()), selected_tickers=len(selected),
                    selection_covered=len(selected & set(combined.ticker)),
                    verified_close_rows=int(combined.close.notna().sum()), missing_close_rows=int(combined.close.isna().sum()),
                    crypto_source_zero_volume_hourly_rows=int((hourly.volume == 0).sum()),
                    crypto_selected_zero_volume_candles=int((coins.volume == 0).sum()),
                    crypto_last_bar_lag_hours_max=float(coins.lag_hours.max()),
                    source_ohlc_bounds_findings=source_bounds_findings.to_dict('records'),
                    discarded_empty_daily_source_rows=discarded, coverage=coverage,
                    checks={'no_averages_used': True, 'source_hashes_verified': True, 'duplicates': 0,
                            'all_requested_tickers_present': True, 'future_labels': 0,
                            'csv_roundtrip_exact': True, 'input_averages_not_modified_by_builder': True},
                    limitations=['No prices generated before the first source observation or through unobserved weeks.',
                                 'Crypto uses actual Bitstamp USD trades; exchange prices differ from Yahoo aggregate quotes.',
                                 'Crypto close is the exact published close of the hourly candle ending at the cutoff, not an hourly average; zero-volume source quotes are preserved.',
                                 'Bitstamp does not provide adj_close; this field stays empty for crypto.',
                                 'Yahoo OHLC/volume describe the selected daily session; crypto OHLC/volume describe the selected hour, not a weekly candle.',
                                 'Yahoo close inherits Yahoo historical split adjustments; adj_close also inherits dividend adjustments.',
                                 'Prior-session fallback uses only the same observed week; dates are explicit in the line-source audit.',
                                 'Nikkei uses its Tokyo session close; FX/futures/VIX use the daily Close field supplied by Yahoo.',
                                 'Some Yahoo FX OHLC rows have source inconsistencies: close/open outside the reported high/low. Values are preserved and each is flagged, not silently repaired.',
                                 'Backtests/returns must be recomputed after this change; missing fields must be handled explicitly.'],
                    outputs={name: {'path': str(p.resolve()), 'sha256': sha256(p)}
                             for name, p in [('weekly', weekly_path), ('audit', audit_path), ('coverage', coverage_path)]})
    (output / 'top100_hebdo_2016_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--yahoo-manifest', type=Path, required=True)
    parser.add_argument('--crypto-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--unavailable', choices=['missing', 'official-close'], default='missing')
    args = parser.parse_args()
    result = build(args.previous, args.selection, args.yahoo_manifest, args.crypto_manifest, args.output, args.unavailable)
    print(json.dumps({k: result[k] for k in ['total_rows', 'tickers', 'selection_covered', 'verified_close_rows', 'missing_close_rows', 'checks']}, indent=2))
