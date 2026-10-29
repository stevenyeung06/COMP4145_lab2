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

    def test_zero_cost_parameters_reproduce_default_results(self):
        prices = pd.DataFrame({"Close": np.linspace(100.0, 130.0, len(self.index))}, index=self.index)

        default = compare_strategies(prices)
        zero_cost = compare_strategies(prices, commission_rate=0, slippage_rate=0)

        pd.testing.assert_frame_equal(default["summary"], zero_cost["summary"])
        pd.testing.assert_frame_equal(default["equity_curves"], zero_cost["equity_curves"])
        for strategy in default["results"]:
            pd.testing.assert_frame_equal(
                default["results"][strategy]["trades"],
                zero_cost["results"][strategy]["trades"],
            )

    def test_flat_buy_and_hold_applies_entry_and_end_of_data_costs(self):
        prices = pd.DataFrame({"Close": 100.0}, index=self.index)
        commission_rate = 0.001
        slippage_rate = 0.0005

        result = simulate_strategy(
            prices,
            "Buy and Hold",
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
        )
        expected_ending_equity = (
            10_000
            * (1 - slippage_rate)
            * (1 - commission_rate)
            / ((1 + slippage_rate) * (1 + commission_rate))
        )

        self.assertAlmostEqual(result["ending_equity"], expected_ending_equity)
        self.assertEqual(result["trades"].iloc[0]["Exit date"], self.index[-1])
        self.assertGreater(result["total_commissions"], 0)
        self.assertGreater(result["total_slippage"], 0)

    def test_no_trades_do_not_incur_costs(self):
        prices = pd.DataFrame({
            "Close": 100.0,
            "GoldenCross": False,
        }, index=self.index)

        result = simulate_strategy(
            prices,
            "Golden Cross",
            commission_rate=0.02,
            slippage_rate=0.03,
        )

        self.assertEqual(result["trade_count"], 0)
        self.assertEqual(result["total_commissions"], 0)
        self.assertEqual(result["total_slippage"], 0)
        self.assertEqual(result["ending_equity"], 10_000)

    def test_higher_costs_reduce_equity_without_changing_trade_dates(self):
        prices = pd.DataFrame({"Close": 100.0, "GoldenCross": False}, index=self.index)
        prices.loc[self.index[200], "GoldenCross"] = True
        prices.loc[self.index[202], "Close"] = 120.0
        prices.loc[self.index[203], "GoldenCross"] = True

        low_cost = simulate_strategy(prices, "Golden Cross")
        high_cost = simulate_strategy(
            prices,
            "Golden Cross",
            commission_rate=0.02,
            slippage_rate=0.03,
        )

        pd.testing.assert_frame_equal(
            low_cost["trades"][["Entry date", "Exit date"]],
            high_cost["trades"][["Entry date", "Exit date"]],
        )
        self.assertLess(high_cost["ending_equity"], low_cost["ending_equity"])
        expected_net_win_rate = (high_cost["trades"]["Return (%)"] > 0).mean() * 100
        self.assertAlmostEqual(high_cost["win_rate_pct"], expected_net_win_rate)

    def test_end_of_data_liquidation_charges_both_sides(self):
        prices = pd.DataFrame({"Close": 100.0, "GoldenCross": False}, index=self.index)
        prices.loc[self.index[-1], "GoldenCross"] = True

        result = simulate_strategy(
            prices,
            "Golden Cross",
            commission_rate=0.01,
            slippage_rate=0.02,
        )

        trade = result["trades"].iloc[0]
        self.assertEqual(trade["Entry date"], self.index[-1])
        self.assertEqual(trade["Exit date"], self.index[-1])
        self.assertAlmostEqual(
            result["total_commissions"],
            trade["Entry commission"] + trade["Exit commission"],
        )
        self.assertAlmostEqual(
            result["total_slippage"],
            trade["Entry slippage"] + trade["Exit slippage"],
        )

    def test_invalid_cost_rates_are_rejected(self):
        prices = pd.DataFrame({"Close": 100.0}, index=self.index)
        invalid_rates = [np.nan, np.inf, -0.01, 1.0]

        for rate in invalid_rates:
            with self.subTest(rate=rate):
                with self.assertRaisesRegex(ValueError, "commission_rate"):
                    simulate_strategy(prices, "Buy and Hold", commission_rate=rate)
                with self.assertRaisesRegex(ValueError, "slippage_rate"):
                    compare_strategies(prices, slippage_rate=rate)

    def test_insufficient_history_is_reported(self):
        short_prices = pd.DataFrame({"Close": 100.0}, index=self.index[:200])

        with self.assertRaisesRegex(ValueError, "Insufficient history"):
            compare_strategies(short_prices)


if __name__ == "__main__":
    unittest.main()