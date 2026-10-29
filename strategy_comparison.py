"""Deterministic strategy-comparison calculations for the dashboard."""

import numpy as np
import pandas as pd

STARTING_CAPITAL = 10_000.0
PROFIT_TARGET = 0.15
MAX_HOLDING_DAYS = 60


def calculate_wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Wilder RSI, seeded with the first period's simple averages."""
    prices = pd.to_numeric(close, errors="coerce")
    changes = prices.diff()
    gains = changes.clip(lower=0)
    losses = -changes.clip(upper=0)
    rsi = pd.Series(np.nan, index=prices.index, dtype=float)

    if period <= 0 or len(prices) <= period:
        return rsi

    average_gain = float(gains.iloc[1 : period + 1].mean())
    average_loss = float(losses.iloc[1 : period + 1].mean())

    def to_rsi(gain: float, loss: float) -> float:
        if gain == 0 and loss == 0:
            return 50.0
        if loss == 0:
            return 100.0
        if gain == 0:
            return 0.0
        relative_strength = gain / loss
        return 100.0 - 100.0 / (1.0 + relative_strength)

    rsi.iloc[period] = to_rsi(average_gain, average_loss)
    for position in range(period + 1, len(prices)):
        average_gain = ((period - 1) * average_gain + float(gains.iloc[position])) / period
        average_loss = ((period - 1) * average_loss + float(losses.iloc[position])) / period
        rsi.iloc[position] = to_rsi(average_gain, average_loss)

    return rsi


def _get_signal_series(prices: pd.DataFrame, strategy: str) -> pd.Series:
    if strategy == "Golden Cross":
        if "GoldenCross" in prices.columns:
            return prices["GoldenCross"].fillna(False).astype(bool)
        short_average = prices["Close"].rolling(window=50).mean()
        long_average = prices["Close"].rolling(window=200).mean()
        return ((short_average > long_average) & (short_average.shift(1) <= long_average.shift(1))).fillna(False)

    if strategy == "RSI":
        rsi = calculate_wilder_rsi(prices["Close"], period=14)
        return ((rsi > 30) & (rsi.shift(1) <= 30)).fillna(False)

    if strategy == "Buy and Hold":
        signal = pd.Series(False, index=prices.index)
        if len(signal):
            signal.iloc[200] = True
        return signal

    raise ValueError(f"Unknown strategy: {strategy}")


def _validate_cost_rate(rate: float, name: str) -> float:
    try:
        validated_rate = float(rate)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be a finite number in the range 0 <= rate < 1.") from None

    if not np.isfinite(validated_rate) or not 0 <= validated_rate < 1:
        raise ValueError(f"{name} must be a finite number in the range 0 <= rate < 1.")
    return validated_rate


def simulate_strategy(
    prices: pd.DataFrame,
    strategy: str,
    starting_capital: float = STARTING_CAPITAL,
    profit_target: float = PROFIT_TARGET,
    max_holding_days: int = MAX_HOLDING_DAYS,
    commission_rate: float = 0.0,
    slippage_rate: float = 0.0,
) -> dict:
    """Simulate one strategy over the shared post-warmup evaluation window."""
    commission_rate = _validate_cost_rate(commission_rate, "commission_rate")
    slippage_rate = _validate_cost_rate(slippage_rate, "slippage_rate")

    if len(prices) <= 200:
        raise ValueError("At least 201 price rows are required for evaluation.")

    signals = _get_signal_series(prices, strategy)
    evaluation_prices = prices.iloc[200:].copy()
    evaluation_signals = signals.reindex(evaluation_prices.index, fill_value=False)
    if evaluation_prices["Close"].isna().any():
        raise ValueError("Evaluation prices contain missing closing values.")

    dates = evaluation_prices.index
    cash = float(starting_capital)
    shares = 0.0
    entry_date = None
    entry_price = None
    entry_execution_price = None
    entry_cash = 0.0
    entry_commission = 0.0
    entry_slippage = 0.0
    scheduled_exit_position = None
    scheduled_exit_reason = None
    trade_rows = []
    equity_values = []
    just_exited = False
    total_commissions = 0.0
    total_slippage = 0.0

    for position, (date, row) in enumerate(evaluation_prices.iterrows()):
        close_price = float(row["Close"])
        just_exited = False

        if shares > 0:
            hit_target = strategy != "Buy and Hold" and close_price >= entry_price * (1 + profit_target)
            reached_exit_window = position >= scheduled_exit_position
            is_final_row = position == len(evaluation_prices) - 1

            if hit_target:
                exit_reason = "Target reached"
            elif reached_exit_window:
                exit_reason = scheduled_exit_reason
            elif is_final_row:
                exit_reason = "End of data"
            else:
                exit_reason = None

            if exit_reason is not None:
                exit_execution_price = close_price * (1 - slippage_rate)
                exit_commission = shares * exit_execution_price * commission_rate
                exit_slippage = shares * (close_price - exit_execution_price)
                sale_proceeds = shares * exit_execution_price - exit_commission
                cash += sale_proceeds
                total_commissions += exit_commission
                total_slippage += exit_slippage
                net_return = (sale_proceeds / entry_cash - 1) * 100
                trade_rows.append({
                    "Entry date": entry_date,
                    "Entry price": entry_price,
                    "Entry execution price": entry_execution_price,
                    "Exit date": date,
                    "Exit price": close_price,
                    "Exit execution price": exit_execution_price,
                    "Holding days": (date - entry_date).days,
                    "Return (%)": net_return,
                    "Gross return (%)": (close_price / entry_price - 1) * 100,
                    "Entry commission": entry_commission,
                    "Exit commission": exit_commission,
                    "Entry slippage": entry_slippage,
                    "Exit slippage": exit_slippage,
                    "Exit reason": exit_reason,
                })
                shares = 0.0
                entry_date = None
                entry_price = None
                entry_execution_price = None
                entry_cash = 0.0
                entry_commission = 0.0
                entry_slippage = 0.0
                scheduled_exit_position = None
                scheduled_exit_reason = None
                just_exited = True

        if shares == 0 and not just_exited and bool(evaluation_signals.loc[date]):
            entry_cash = cash
            entry_execution_price = close_price * (1 + slippage_rate)
            shares = entry_cash / (entry_execution_price * (1 + commission_rate))
            entry_commission = shares * entry_execution_price * commission_rate
            entry_slippage = shares * (entry_execution_price - close_price)
            total_commissions += entry_commission
            total_slippage += entry_slippage
            cash = 0.0
            entry_date = date
            entry_price = close_price

            if strategy == "Buy and Hold":
                scheduled_exit_position = len(evaluation_prices) - 1
                scheduled_exit_reason = "End of data"
            else:
                deadline = date + pd.Timedelta(days=max_holding_days)
                last_position = int(dates.searchsorted(deadline, side="right") - 1)
                scheduled_exit_position = max(position, last_position)
                if dates[-1] < deadline:
                    scheduled_exit_reason = "End of data"
                else:
                    scheduled_exit_reason = "Max holding period"

        equity_values.append(cash + shares * close_price)

    if shares > 0:
        final_date = evaluation_prices.index[-1]
        final_price = float(evaluation_prices["Close"].iloc[-1])
        exit_execution_price = final_price * (1 - slippage_rate)
        exit_commission = shares * exit_execution_price * commission_rate
        exit_slippage = shares * (final_price - exit_execution_price)
        sale_proceeds = shares * exit_execution_price - exit_commission
        cash += sale_proceeds
        total_commissions += exit_commission
        total_slippage += exit_slippage
        trade_rows.append({
            "Entry date": entry_date,
            "Entry price": entry_price,
            "Entry execution price": entry_execution_price,
            "Exit date": final_date,
            "Exit price": final_price,
            "Exit execution price": exit_execution_price,
            "Holding days": (final_date - entry_date).days,
            "Return (%)": (sale_proceeds / entry_cash - 1) * 100,
            "Gross return (%)": (final_price / entry_price - 1) * 100,
            "Entry commission": entry_commission,
            "Exit commission": exit_commission,
            "Entry slippage": entry_slippage,
            "Exit slippage": exit_slippage,
            "Exit reason": "End of data",
        })
        equity_values[-1] = cash

    equity_curve = pd.Series(equity_values, index=evaluation_prices.index, name=strategy)
    trades = pd.DataFrame(trade_rows)
    if trades.empty:
        trades = pd.DataFrame(columns=[
            "Entry date", "Entry price", "Entry execution price", "Exit date",
            "Exit price", "Exit execution price", "Holding days", "Return (%)",
            "Gross return (%)", "Entry commission", "Exit commission",
            "Entry slippage", "Exit slippage", "Exit reason",
        ])

    ending_equity = float(equity_curve.iloc[-1])
    total_return = (ending_equity / starting_capital - 1) * 100
    trade_count = len(trades)
    win_rate = float((trades["Return (%)"] > 0).mean() * 100) if trade_count else np.nan

    return {
        "strategy": strategy,
        "equity_curve": equity_curve,
        "trades": trades,
        "ending_equity": ending_equity,
        "total_return_pct": total_return,
        "trade_count": trade_count,
        "win_rate_pct": win_rate,
        "total_commissions": total_commissions,
        "total_slippage": total_slippage,
        "evaluation_start": evaluation_prices.index[0],
        "evaluation_end": evaluation_prices.index[-1],
    }


def compare_strategies(
    prices: pd.DataFrame,
    commission_rate: float = 0.0,
    slippage_rate: float = 0.0,
) -> dict:
    """Run all supported strategies against the same full-history input."""
    commission_rate = _validate_cost_rate(commission_rate, "commission_rate")
    slippage_rate = _validate_cost_rate(slippage_rate, "slippage_rate")

    if prices.empty:
        raise ValueError("No price history was returned.")
    if len(prices) <= 200:
        raise ValueError("Insufficient history: more than 200 price rows are required.")

    strategies = ["Golden Cross", "RSI", "Buy and Hold"]
    results = [
        simulate_strategy(
            prices,
            strategy,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
        )
        for strategy in strategies
    ]
    summary = pd.DataFrame([
        {
            "Strategy": result["strategy"],
            "Ending equity": result["ending_equity"],
            "Total return (%)": result["total_return_pct"],
            "Trade count": result["trade_count"],
            "Win rate (%)": result["win_rate_pct"],
        }
        for result in results
    ])
    equity_curves = pd.concat([result["equity_curve"] for result in results], axis=1)
    return {
        "summary": summary,
        "equity_curves": equity_curves,
        "results": {result["strategy"]: result for result in results},
        "evaluation_start": results[0]["evaluation_start"],
        "evaluation_end": results[0]["evaluation_end"],
    }
