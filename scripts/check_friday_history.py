"""Verify every populated export value against an actual cached source row."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from extend_weekly_history import NUMERIC, sha256


def check(folder: Path) -> dict:
    manifest = json.loads((folder / 'top100_hebdo_2016_manifest.json').read_text(encoding='utf-8'))
    for output in manifest['outputs'].values():
        if sha256(Path(output['path'])) != output['sha256']:
            raise ValueError('Output hash mismatch')
    prices = pd.read_csv(manifest['outputs']['weekly']['path'], float_precision='round_trip')
    audit = pd.read_csv(manifest['outputs']['audit']['path'], low_memory=False)
    if not prices[['ticker', 'date']].equals(audit[['ticker', 'date']]):
        raise ValueError('Row identity differs between CSV and audit')
    compared = 0
    for path, group in audit.groupby('source_path', sort=False):
        hashes = set(group.source_sha256)
        if hashes != {sha256(Path(path))}:
            raise ValueError('Raw source hash mismatch')
        payload = json.loads(Path(path).read_bytes())
        if 'chart' in payload:
            result = payload['chart']['result'][0]
            quote = result['indicators']['quote'][0]
            adj = result['indicators']['adjclose'][0]['adjclose']
            for row_index, row in group.iterrows():
                source_index = int(row.source_index)
                if row.ticker != result['meta']['symbol']:
                    raise ValueError('Wrong Yahoo ticker')
                source_date = pd.Timestamp(result['timestamp'][source_index], unit='s', tz='UTC').tz_convert(result['meta']['exchangeTimezoneName']).date().isoformat()
                if source_date != row.source_date:
                    raise ValueError('Wrong source session date')
                if source_date > row.date:
                    raise ValueError('Lookahead daily session')
                expected = {c: quote[c][source_index] for c in ['open', 'high', 'low', 'close', 'volume']}
                expected['adj_close'] = adj[source_index]
                for field, value in expected.items():
                    actual = prices.loc[row_index, field]
                    if pd.isna(actual) and row.price_policy.startswith('missing:'):
                        continue
                    if actual != value:
                        raise ValueError(f'{row.ticker}/{row.date} {field} differs from Yahoo source')
                    compared += 1
                if prices.loc[row_index, 'currency'] != result['meta']['currency']:
                    raise ValueError('Wrong source currency')
        else:
            data = payload['data']
            for row_index, row in group.iterrows():
                source = data['ohlc'][int(row.source_index)]
                end = pd.Timestamp(int(source['timestamp']), unit='s', tz='UTC') + pd.Timedelta(hours=1)
                if end != pd.Timestamp(row.target_timestamp) or end.isoformat() != row.bar_end_utc:
                    raise ValueError('Crypto price after target cutoff or wrong bar')
                if row.ticker.replace('-', '/') != data['pair']:
                    raise ValueError('Wrong crypto instrument')
                for field in ['open', 'high', 'low', 'close', 'volume']:
                    if prices.loc[row_index, field] != float(source[field]):
                        raise ValueError(f'{row.ticker}/{row.date} {field} differs from Bitstamp source')
                    compared += 1
                if not pd.isna(prices.loc[row_index, 'adj_close']):
                    raise ValueError('Unprovided crypto adjusted price was invented')
    dates = pd.to_datetime(prices.date)
    assert (dates.dt.dayofweek == 4).all()
    assert dates.max() <= pd.Timestamp(manifest['as_of'])
    assert not prices.duplicated(['ticker', 'date']).any()
    finite_closes = prices.close.dropna()
    assert (finite_closes > 0).all() and np.isfinite(finite_closes).all()
    report = dict(status='passed', rows=len(prices), tickers=int(prices.ticker.nunique()),
                  raw_numeric_fields_compared=compared,
                  missing_closes=int(prices.close.isna().sum()),
                  missing_crypto_adjusted_prices=int(prices.loc[prices.ticker.str.endswith('-USD'), 'adj_close'].isna().sum()),
                  source_ohlc_bounds_findings=len(manifest['source_ohlc_bounds_findings']),
                  scope='Deterministic source/CSV checks; not an independent market-price certification')
    (folder / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    print(json.dumps(check(parser.parse_args().folder), indent=2))
