"""Fetch missing daily histories; cache exact Yahoo Chart responses for audit.

Existing local daily histories are retained per ticker, without splicing prices
from two adjustment snapshots within a ticker. No weekly averages are inputs.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import quote, urlencode

import pandas as pd


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(weekly: Path, local_daily: Path, output: Path, all_symbols: bool = False) -> dict:
    symbols = set(pd.read_csv(weekly, usecols=['ticker']).ticker)
    supplied = set(pd.read_csv(local_daily, usecols=['ticker']).ticker)
    missing = sorted(symbols if all_symbols else symbols - supplied)
    output.mkdir(parents=True, exist_ok=True)
    params = urlencode(dict(period1=1451606400, period2=1794787200,
                            interval='1d', events='history', includeAdjustedClose='true'))

    def fetch(ticker: str) -> dict:
        filename = quote(ticker, safe='') + '.json'
        path = output / filename
        url = 'https://query2.finance.yahoo.com/v8/finance/chart/' + quote(ticker, safe='') + '?' + params
        record = dict(ticker=ticker, url=url, path=str(path.resolve()))
        try:
            if not path.exists():
                temporary = path.with_suffix('.json.part')
                run = subprocess.run(['curl.exe', '--silent', '--show-error', '--fail',
                                      '--location', '--max-time', '35', '-A', 'Mozilla/5.0',
                                      url, '-o', str(temporary)], capture_output=True, text=True)
                if run.returncode:
                    raise RuntimeError(run.stderr.strip())
                payload = json.loads(temporary.read_bytes())
                if payload['chart'].get('error') or not payload['chart'].get('result'):
                    raise ValueError('No successful Chart result')
                temporary.replace(path)
            data = json.loads(path.read_bytes())['chart']['result'][0]
            if data['meta']['symbol'] != ticker:
                raise ValueError('Returned symbol differs from requested symbol')
            record.update(status='complete', sha256=sha256(path),
                          retrieved_at_utc=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                          currency=data['meta'].get('currency'),
                          timezone=data['meta'].get('exchangeTimezoneName'),
                          observations=len(data.get('timestamp', [])))
        except Exception as error:
            record.update(status='failed', error=str(error))
        return record

    records = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch, ticker): ticker for ticker in missing}
        for future in as_completed(futures):
            result = future.result()
            records.append(result)
            print(f"{len(records)}/{len(missing)} {result['ticker']}: {result['status']}", flush=True)
    manifest = dict(provider='Yahoo Finance Chart API; daily interval; unmodified JSON responses',
                    policy='Yahoo for all tickers' if all_symbols else 'Yahoo only for tickers absent from local daily history',
                    requested_start='2016-01-01', end_exclusive='2026-11-16',
                    weekly={'path': str(weekly.resolve()), 'sha256': sha256(weekly)},
                    local_daily={'path': str(local_daily.resolve()), 'sha256': sha256(local_daily)},
                    sources=sorted(records, key=lambda row: row['ticker']))
    (output / 'download_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    failed = [r['ticker'] for r in records if r['status'] != 'complete']
    print(json.dumps(dict(total=len(records), failed=failed)))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--weekly', type=Path, required=True)
    parser.add_argument('--local-daily', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--all-symbols', action='store_true')
    args = parser.parse_args()
    result = download(args.weekly, args.local_daily, args.output, args.all_symbols)
    raise SystemExit(any(r['status'] != 'complete' for r in result['sources']))
