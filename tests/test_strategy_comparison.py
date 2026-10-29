import unittest

import numpy as np
import pandas as pd

from strategy_comparison import calculate_wilder_rsi, compare_strategies, simulate_strategy


class StrategyComparisonTests(unittest.TestCase):
    def setUp(self):
        self.index = pd.date_range("2020-01-01", periods=230, freq="D")

    def test_wilder_rsi_edge_cases_after_warmup(self):
        rising = pd.Series(np.arange(100.0, 330.0), index=self.index)
        falling = pd.Series(np.arange(330.0, 100.0, -1.0), index=self.index)
        flat = pd.Series(100.0, index=self.index)

        self.assertEqual(calculate_wilder_rsi(rising).iloc[14], 100)
        self.assertEqual(calculate_wilder_rsi(falling).iloc[14], 0)
        self.assertEqual(calculate_wilder_rsi(flat).iloc[14], 50)

    def test_wilder_rsi_uses_recursive_smoothing_after_seed(self):
        close = pd.Series([100.0] + [101.0 + offset for offset in range(14)] + [113.0], index=self.index[:16])
        rsi = calculate_wilder_rsi(close)
        average_gain = (13 * 1.0 + 0.0) / 14
        average_loss = (13 * 0.0 + 1.0) / 14
        expected_rsi = 100 - 100 / (1 + average_gain / average_loss)

        self.assertAlmostEqual(rsi.iloc[15], expected_rsi)

    def test_buy_and_hold_return_uses_evaluation_start_and_end_closes(self):
        close = pd.Series(np.arange(100.0, 330.0), index=self.index)
        result = simulate_strategy(pd.DataFrame({"Close": close}), "Buy and Hold")
        expected_return = (close.iloc[-1] / close.iloc[200] - 1) * 100

        self.assertAlmostEqual(result["total_return_pct"], expected_return)
        self.assertEqual(result["trade_count"], 1)
        self.assertEqual(result["evaluation_start"], self.index[200])
        self.assertEqual(result["evaluation_end"], self.index[-1])

    def test_no_trade_equity_stays_at_starting_capital(self):
        prices = pd.DataFrame({
            "Close": 100.0,
            "GoldenCross": False,
        }, index=self.index)
        result = simulate_strategy(prices, "Golden Cross")

        self.assertEqual(result["trade_count"], 0)
        self.assertEqual(result["ending_equity"], 10_000)
        self.assertTrue((result["equity_curve"] == 10_000).all())

    def test_trades_do_not_overlap_and_exit_day_cannot_reenter(self):
        prices = pd.DataFrame({"Close": 100.0, "GoldenCross": False}, index=self.index)
        prices.loc[self.index[200], "GoldenCross"] = True
        prices.loc[self.index[201], "Close"] = 116.0
        prices.loc[self.index[201], "GoldenCross"] = True
        prices.loc[self.index[202], "GoldenCross"] = True

        trades = simulate_strategy(prices, "Golden Cross")["trades"]

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades.iloc[0]["Exit date"], self.index[201])
        self.assertEqual(trades.iloc[1]["Entry date"], self.index[202])
        for trade_number in range(1, len(trades)):
            self.assertGreater(trades.iloc[trade_number]["Entry date"], trades.iloc[trade_number - 1]["Exit date"])

    def test_open_position_closes_at_end_of_data(self):
        prices = pd.DataFrame({"Close": 100.0, "GoldenCross": False}, index=self.index)
        prices.loc[self.index[229], "GoldenCross"] = True

        trades = simulate_strategy(prices, "Golden Cross")["trades"]

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades.iloc[0]["Exit date"], self.index[-1])
        self.assertEqual(trades.iloc[0]["Exit reason"], "End of data")

    def test_profit_target_exits_at_first_qualifying_close(self):
        index = pd.date_range("2020-01-01", periods=300, freq="D")
        prices = pd.DataFrame({"Close": 100.0, "GoldenCross": False}, index=index)
        prices.loc[index[200], "GoldenCross"] = True
        prices.loc[index[202], "Close"] = 114.0
        prices.loc[index[204], "Close"] = 116.0

        trades = simulate_strategy(prices, "Golden Cross")["trades"]

        self.assertEqual(trades.iloc[0]["Exit date"], index[204])
        self.assertEqual(trades.iloc[0]["Exit reason"], "Target reached")

    def test_maximum_holding_exits_at_last_close_in_calendar_window(self):
        index = pd.date_range("2020-01-01", periods=300, freq="D")
        prices = pd.DataFrame({"Close": 100.0, "GoldenCross": False}, index=index)
        prices.loc[index[200], "GoldenCross"] = True

        trades = simulate_strategy(prices, "Golden Cross")["trades"]

        self.assertEqual(trades.iloc[0]["Exit date"], index[260])
        self.assertEqual(trades.iloc[0]["Holding days"], 60)
        self.assertEqual(trades.iloc[0]["Exit reason"], "Max holding period")

    def test_all_strategies_share_evaluation_dates(self):
        prices = pd.DataFrame({"Close": 100.0}, index=self.index)
        comparison = compare_strategies(prices)

        self.assertEqual(comparison["evaluation_start"], self.index[200])
        self.assertEqual(comparison["evaluation_end"], self.index[-1])
        self.assertEqual(list(comparison["equity_curves"].columns), ["Golden Cross", "RSI", "Buy and Hold"])

    def test_insufficient_history_is_reported(self):
        short_prices = pd.DataFrame({"Close": 100.0}, index=self.index[:200])

        with self.assertRaisesRegex(ValueError, "Insufficient history"):
            compare_strategies(short_prices)


if __name__ == "__main__":
    unittest.main()