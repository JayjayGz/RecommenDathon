import unittest
import pandas as pd
from extend_weekly_history import weekly_means


class WeeklyMeanTests(unittest.TestCase):
    def rows(self, dates, values):
        return pd.DataFrame([dict(ticker='TEST', date=date, open=value, high=value+2,
                                  low=value-2, close=value+1, adj_close=value/2,
                                  volume=value*10, currency='CAD')
                             for date, value in zip(dates, values)])

    def test_arithmetic_mean_and_volume_mean(self):
        rows, coverage = weekly_means(self.rows(['2016-01-04','2016-01-08'],[10,20]), '2016-01-01','2016-01-15')
        self.assertEqual(rows.iloc[0].open,15)
        self.assertEqual(rows.iloc[0].high,17)
        self.assertEqual(rows.iloc[0].low,13)
        self.assertEqual(rows.iloc[0].close,16)
        self.assertEqual(rows.iloc[0].adj_close,7.5)
        self.assertEqual(rows.iloc[0].volume,150)
        self.assertEqual(str(rows.iloc[0].date.date()),'2016-01-08')
        self.assertEqual(coverage.iloc[0].daily_rows,2)

    def test_friday_boundary_and_no_unobserved_week_fill(self):
        rows, coverage = weekly_means(self.rows(['2016-01-08','2016-01-09','2016-01-29'],[10,20,30]), '2016-01-01','2016-01-31')
        self.assertEqual(list(rows.date.dt.strftime('%Y-%m-%d')),['2016-01-08','2016-01-15','2016-01-29'])
        self.assertEqual(coverage.iloc[0].empty_weeks,1)

    def test_start_cutoff_and_post_inception_history(self):
        rows, _ = weekly_means(self.rows(['2015-12-31','2016-01-01','2016-01-02'],[10,20,30]), '2016-01-01','2016-01-03')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows.iloc[0].open,20)
        rows, coverage = weekly_means(self.rows(['2018-02-01'],[20]), '2016-01-01','2018-02-03')
        self.assertEqual(len(rows),1)
        self.assertTrue(coverage.iloc[0].history_starts_after_requested_start)

    def test_duplicate_invalid_price_and_missing_value_rejected(self):
        good=self.rows(['2016-01-04'],[10])
        for bad in [pd.concat([good,good]),good.assign(close=-1),good.assign(volume=float('nan')),
                    good.assign(high=1),good.assign(currency=None)]:
            with self.assertRaises(ValueError):
                weekly_means(bad,'2016-01-01','2016-01-08')


if __name__ == '__main__':
    unittest.main()
