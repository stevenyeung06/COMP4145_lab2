# COMP4145_lab2

## Golden Cross Trading Strategy

A Python project that downloads historical stock prices with `yfinance`, calculates 50-day and 200-day moving averages, and evaluates a Golden Cross strategy with a 15% profit target and a 60-calendar-day maximum holding period.

The Streamlit dashboard presents the results in three views:

- **Price chart:** closing price, moving averages, and simulated buy/sell points.
- **Trade statistics:** overall trade counts, win rate, returns, and holding time.
- **Trade details:** individual trade records with CSV export.

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
