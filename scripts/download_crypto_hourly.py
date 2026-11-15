"""Cache official Bitstamp USD hourly candles, without fabricating gaps."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode


PAIRS = {'BTC-USD': 'btcusd', 'ETH-USD': 'ethusd', 'BCH-USD': 'bchusd',
         'LTC-USD': 'ltcusd', 'XRP-USD': 'xrpusd'}


def download(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    start = int(datetime(2016, 1, 1, tzinfo=timezone.utc).timestamp())
    cutoff = int(datetime(2026, 11, 14, tzinfo=timezone.utc).timestamp())
    tasks = [(ticker, pair, begin, min(begin + 1000 * 3600, cutoff) - 1)
             for ticker, pair in PAIRS.items() for begin in range(start, cutoff, 1000 * 3600)]

    def fetch(task: tuple) -> dict:
        ticker, pair, begin, end = task
        path = output / f'{ticker}_{begin}_{end}.json'
        # Bitstamp uses end when both start/end are supplied. End + limit
        # specifies this exact, nonoverlapping 1000-hour (or shorter) block.
        limit = (end - begin + 1) // 3600
        url = f'https://www.bitstamp.net/api/v2/ohlc/{pair}/?' + urlencode(
            dict(step=3600, limit=limit, end=end, exclude_current_candle='true'))
        record = dict(ticker=ticker, pair=pair, requested_start=begin, requested_end=end,
                      url=url, path=str(path.resolve()))
        try:
            if not path.exists():
                temporary = path.with_suffix('.json.part')
                for attempt in range(2):
                    run = subprocess.run(['curl.exe', '--silent', '--show-error', '--fail',
                                          '--location', '--max-time', '30', url, '-o', str(temporary)],
                                         capture_output=True, text=True)
                    if run.returncode == 0:
                        break
                    if attempt == 0:
                        time.sleep(1)
                if run.returncode:
                    raise RuntimeError(run.stderr.strip())
                data = json.loads(temporary.read_bytes())
                if data.get('data', {}).get('pair') != pair[:-3].upper() + '/USD':
                    raise ValueError('Missing or mismatched source pair')
                temporary.replace(path)
            data = json.loads(path.read_bytes())
            rows = data['data']['ohlc']
            if any(not begin <= int(r['timestamp']) <= end for r in rows):
                raise ValueError('Source returned observations outside requested interval')
            record.update(status='complete', rows=len(rows),
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                          retrieved_at_utc=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())
        except Exception as error:
            record.update(status='failed', error=str(error))
        return record

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch, task) for task in tasks]):
            result = future.result()
            results.append(result)
            if len(results) % 25 == 0 or result['status'] != 'complete':
                print(f"{len(results)}/{len(tasks)}; {result['ticker']}: {result['status']} "
                      + result.get('error', ''), flush=True)
    manifest = dict(provider='Bitstamp official public OHLC API', interval_seconds=3600,
                    currency='USD', sources=sorted(results, key=lambda r: (r['ticker'], r['requested_start'])))
    (output / 'download_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(total=len(results), failed=sum(r['status'] != 'complete' for r in results))))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    result = download(parser.parse_args().output)
    raise SystemExit(any(r['status'] != 'complete' for r in result['sources']))
