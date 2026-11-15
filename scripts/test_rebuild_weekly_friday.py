"""Regression checks for real closes, Friday boundaries, DST and missing data."""
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from rebuild_weekly_friday import crypto_at_1600, friday_last, verified_manifest


def daily(ticker, date, close):
    return dict(ticker=ticker, date=date, open=close-1, high=close+2,
                low=close-2, close=close, adj_close=close/2, volume=100, currency='USD')


def hourly(timestamp, close):
    return dict(ticker='BTC-USD', bar_start_utc=timestamp, open=close-1,
                high=close+1, low=close-2, close=close, volume=10, currency='USD')


class FridayHistoryTests(unittest.TestCase):
    def test_correction_close_not_average_and_saturday_next_week(self):
        rows = pd.DataFrame([daily('ABC', '2026-11-09', 100), daily('ABC', '2026-11-12', 120),
                             daily('ABC', '2026-11-13', 130), daily('ABC', '2026-11-14', 999)])
        result = friday_last(rows, '2026-11-01', '2026-11-15')
        self.assertEqual(result.close.tolist(), [130])
        self.assertEqual(result.adj_close.tolist(), [65])
        self.assertNotEqual(result.close.iloc[0], (100+120+130)/3)
        self.assertEqual(result.source_date.iloc[0], '2026-11-13')

    def test_prior_session_and_empty_week_not_filled(self):
        rows = pd.DataFrame([daily('ABC', '2026-11-05', 101), daily('ABC', '2026-11-19', 102)])
        result = friday_last(rows, '2026-11-01', '2026-11-20')
        self.assertEqual(result.date.dt.strftime('%Y-%m-%d').tolist(), ['2026-11-06', '2026-11-20'])
        self.assertEqual(result.close.tolist(), [101,102])

    def test_vendor_bounds_defect_preserved_explicitly_not_repaired(self):
        rows = pd.DataFrame([daily('FX', '2026-11-13', 100)])
        rows.loc[0, 'high'] = 99
        with self.assertRaisesRegex(ValueError, 'High is below'):
            friday_last(rows, '2026-11-13', '2026-11-15')
        result = friday_last(rows, '2026-11-13', '2026-11-15', validate_ohlc=False)
        self.assertEqual(result.high.iloc[0], 99)
        self.assertEqual(result.close.iloc[0], 100)

    def test_invalid_last_row_rejected_not_replaced_by_prior_close(self):
        rows = pd.DataFrame([daily('ABC', '2026-11-12', 120), daily('ABC', '2026-11-13', 130)])
        rows.loc[1, 'close'] = np.nan
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            friday_last(rows, '2026-11-01', '2026-11-15')

    def test_crypto_winter_1600_is_2100_utc_and_no_later_bar(self):
        rows = pd.DataFrame([hourly('2026-11-13T20:00:00Z', 130),
                             hourly('2026-11-13T21:00:00Z', 999)])
        result = crypto_at_1600(rows, '2026-11-13', '2026-11-15')
        self.assertEqual(result.close.tolist(), [130])
        self.assertEqual(result.bar_end_utc.iloc[0], '2026-11-13T21:00:00+00:00')
        self.assertTrue(pd.isna(result.adj_close.iloc[0]))

    def test_crypto_summer_dst_1600_is_2000_utc(self):
        rows = pd.DataFrame([hourly('2026-07-03T19:00:00Z', 200),
                             hourly('2026-07-03T20:00:00Z', 999)])
        result = crypto_at_1600(rows, '2026-07-03', '2026-07-04')
        self.assertEqual(result.close.tolist(), [200])
        self.assertEqual(result.bar_end_utc.iloc[0], '2026-07-03T20:00:00+00:00')

    def test_crypto_missing_weeks_not_filled_and_source_zero_volume_preserved(self):
        rows = pd.DataFrame([hourly('2026-11-06T20:00:00Z', 100),
                             hourly('2026-11-13T20:00:00Z', 999)])
        rows.loc[1, 'volume'] = 0
        result = crypto_at_1600(rows, '2026-11-06', '2026-11-20')
        self.assertEqual(result.date.dt.strftime('%Y-%m-%d').tolist(), ['2026-11-06','2026-11-13'])
        self.assertEqual(result.close.tolist(), [100,999])
        self.assertEqual(result.volume.tolist(), [10,0])

    def test_modified_source_rejected(self):
        import json
        payload = json.dumps({'sources':[dict(ticker='ABC', status='complete', path='source.json', sha256='expected')]})
        with patch.object(Path, 'read_text', return_value=payload), patch('rebuild_weekly_friday.sha256', return_value='changed'):
            with self.assertRaisesRegex(ValueError, 'Changed source'):
                verified_manifest(Path('manifest.json'))
        with patch.object(Path, 'read_text', return_value=payload), patch('rebuild_weekly_friday.sha256', return_value='expected'):
            self.assertEqual(verified_manifest(Path('manifest.json'))['sources'][0]['ticker'], 'ABC')


if __name__ == '__main__':
    unittest.main()
