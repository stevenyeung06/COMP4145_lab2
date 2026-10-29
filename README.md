# COMP4145_lab2

## Golden Cross Trading Strategy

A Python project that downloads historical stock prices with `yfinance`, calculates 50-day and 200-day moving averages, and evaluates a Golden Cross strategy with a 15% profit target and a 60-calendar-day maximum holding period.

The Streamlit dashboard includes:

- **Price chart:** closing price, moving averages, and simulated buy/sell points.
- **Trade statistics:** overall trade counts, win rate, returns, and holding time.
- **Trade details:** individual trade records with CSV export.
- **Stock comparison:** compare Golden Cross performance across tickers.
- **Strategy comparison:** compare Golden Cross, RSI, and Buy and Hold over a shared evaluation window, including a configurable commission and slippage simulation with gross-versus-net results.

Strategy comparison applies costs to every entry and exit, while signals and exit decisions continue to use reference closing prices. Set commission and slippage to 0% to see the zero-cost baseline.

## Run locally

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Launch the dashboard:

```bash
streamlit run app.py
```

The default ticker is `MSFT`; the sidebar lets you choose another ticker and history period. The standalone strategy can also be run in the terminal with `python trading_strategy.py`.
