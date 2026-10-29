import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from trading_strategy import run_strategy
from strategy_comparison import compare_strategies


st.set_page_config(
    page_title="Crossing Point | Strategy Monitor",
    page_icon="CP",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');

    :root {
        --ink: #17231f;
        --muted: #718078;
        --line: #e2e8e2;
        --paper: #f6f8f4;
        --white: #ffffff;
        --green: #157a56;
        --red: #c34c43;
        --lime: #d3ef68;
    }
    html, body, [class*="css"] { font-family: 'Manrope', sans-serif; color: var(--ink); }
    .stApp { background: var(--paper); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { background: #edf2eb; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: var(--muted); }
    .brand { font-size: 12px; font-weight: 800; letter-spacing: 1.8px; text-transform: uppercase; color: var(--green); }
    .page-title { font-size: 34px; line-height: 1.15; font-weight: 800; margin: 8px 0 4px; }
    .page-subtitle { color: var(--muted); font-size: 14px; margin-bottom: 26px; }
    .metric { background: var(--white); border: 1px solid var(--line); border-radius: 6px; padding: 17px 18px; min-height: 96px; }
    .metric-label { color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { color: var(--ink); font-size: 26px; font-weight: 800; margin-top: 7px; }
    .section-label { font-family: 'DM Mono', monospace; color: var(--green); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin: 20px 0 8px; }
    .stRadio > div { gap: 8px; }
    .stRadio label { font-weight: 700; }
    [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 6px; }
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_strategy(ticker: str, period: str):
    return run_strategy(ticker=ticker, period=period)


def parse_tickers(ticker_text: str) -> list[str]:
    tickers = []
    seen = set()
    for ticker_value in ticker_text.split(","):
        normalized = ticker_value.strip().upper()
        if normalized and normalized not in seen:
            tickers.append(normalized)
            seen.add(normalized)
    return tickers


def format_money(value: float) -> str:
    return f"${value:,.2f}"


def metric(label: str, value: str) -> None:
    st.markdown(
        f'<div class="metric"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div></div>',
        unsafe_allow_html=True,
    )


with st.sidebar:
    st.markdown('<div class="brand">Crossing Point</div>', unsafe_allow_html=True)
    st.markdown("### Strategy monitor")
    ticker = st.text_input("Ticker", value="MSFT").strip().upper() or "MSFT"
    period = st.selectbox("History", ["1y", "2y", "5y", "10y"], index=2)
    st.caption("Golden Cross · 50-day / 200-day averages")
    st.markdown("---")
    page = st.radio(
        "Dashboard",
        ["Price chart", "Trade statistics", "Trade details", "Stock comparison", "Strategy comparison"],
        label_visibility="collapsed",
    )

if page == "Stock comparison":
    st.markdown('<div class="brand">Market strategy / comparison</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">Compare stocks</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">Compare Golden Cross results using the selected history period and the same trading rules.</div>',
        unsafe_allow_html=True,
    )

    with st.form("stock_comparison_form"):
        ticker_text = st.text_input(
            "Tickers (comma-separated)",
            value="MSFT, AAPL, AMZN",
            help="Enter between one and five unique ticker symbols.",
        )
        compare_submitted = st.form_submit_button("Compare", type="primary")

    if compare_submitted:
        comparison_tickers = parse_tickers(ticker_text)
        if not comparison_tickers:
            st.warning("Enter at least one ticker symbol to compare.")
        elif len(comparison_tickers) > 5:
            st.error("You can compare at most five unique tickers. Remove some symbols and try again.")
        else:
            comparison_rows = []
            for comparison_ticker in comparison_tickers:
                try:
                    comparison_prices, comparison_trades = load_strategy(comparison_ticker, period)
                except Exception as error:
                    comparison_rows.append({
                        "Ticker": comparison_ticker,
                        "Total trades": None,
                        "Win rate (%)": None,
                        "Average return per trade (%)": None,
                        "Average holding days": None,
                        "Status": f"Download failed: {error}",
                    })
                    continue

                if comparison_prices is None or comparison_prices.empty:
                    comparison_rows.append({
                        "Ticker": comparison_ticker,
                        "Total trades": None,
                        "Win rate (%)": None,
                        "Average return per trade (%)": None,
                        "Average holding days": None,
                        "Status": "No price data returned; check the ticker.",
                    })
                    continue

                if len(comparison_prices) <= 200:
                    comparison_rows.append({
                        "Ticker": comparison_ticker,
                        "Total trades": 0,
                        "Win rate (%)": None,
                        "Average return per trade (%)": None,
                        "Average holding days": None,
                        "Status": f"Insufficient history ({len(comparison_prices)} trading days; more than 200 required).",
                    })
                    continue

                if comparison_trades.empty:
                    comparison_rows.append({
                        "Ticker": comparison_ticker,
                        "Total trades": 0,
                        "Win rate (%)": None,
                        "Average return per trade (%)": None,
                        "Average holding days": None,
                        "Status": "No trades found for this period.",
                    })
                    continue

                trade_count = len(comparison_trades)
                wins = int((comparison_trades["ProfitPct"] > 0).sum())
                comparison_rows.append({
                    "Ticker": comparison_ticker,
                    "Total trades": trade_count,
                    "Win rate (%)": wins / trade_count * 100,
                    "Average return per trade (%)": float(comparison_trades["ProfitPct"].mean()),
                    "Average holding days": float(comparison_trades["HoldingDays"].mean()),
                    "Status": "OK",
                })

            comparison_table = pd.DataFrame(comparison_rows)
            ticker_issues = [
                f"{row['Ticker']}: {row['Status']}"
                for row in comparison_rows
                if row["Status"].startswith(("Download failed:", "No price data returned"))
            ]
            if ticker_issues:
                st.warning("\n\n".join(ticker_issues), title="Some tickers could not be compared")

            st.dataframe(
                comparison_table,
                hide_index=True,
                alt="Per-ticker Golden Cross trading performance comparison",
                column_config={
                    "Total trades": st.column_config.NumberColumn(format="%d"),
                    "Win rate (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Average return per trade (%)": st.column_config.NumberColumn(format="%+.2f%%"),
                    "Average holding days": st.column_config.NumberColumn(format="%.1f"),
                },
            )
            st.caption(f"History period: {period}. Returns are average returns per trade, not cumulative portfolio returns.")

    st.stop()

if page == "Strategy comparison":
    st.markdown('<div class="brand">Market strategy / comparison</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-title">Strategy comparison / {ticker}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">Compare three strategies over the same post-warmup evaluation window.</div>',
        unsafe_allow_html=True,
    )

    try:
        with st.spinner(f"Loading {ticker} market history..."):
            comparison_prices, _ = load_strategy(ticker, period)
    except Exception as error:
        st.error(f"Could not load market data for {ticker}: {error}")
        st.stop()

    if comparison_prices is None or comparison_prices.empty:
        st.warning(f"No price history was returned for {ticker}. Check the ticker and try again.")
        st.stop()
    if len(comparison_prices) <= 200:
        st.warning(
            f"Insufficient history for {ticker}: received {len(comparison_prices)} price rows; "
            "at least 201 are required to evaluate strategies after the 200-row warm-up."
        )
        st.stop()

    try:
        strategy_comparison = compare_strategies(comparison_prices)
    except (KeyError, ValueError, TypeError) as error:
        st.error(f"Could not compare strategies for {ticker}: {error}")
        st.stop()

    evaluation_start = strategy_comparison["evaluation_start"].strftime("%b %d, %Y")
    evaluation_end = strategy_comparison["evaluation_end"].strftime("%b %d, %Y")
    st.caption(f"Evaluation window: {evaluation_start} to {evaluation_end} · Starting capital: $10,000.00")

    st.dataframe(
        strategy_comparison["summary"],
        hide_index=True,
        alt=f"Strategy performance comparison for {ticker}",
        column_config={
            "Ending equity": st.column_config.NumberColumn(format="$%.2f"),
            "Total return (%)": st.column_config.NumberColumn(format="%+.2f%%"),
            "Trade count": st.column_config.NumberColumn(format="%d"),
            "Win rate (%)": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    no_trade_strategies = [
        strategy
        for strategy, result in strategy_comparison["results"].items()
        if strategy != "Buy and Hold" and result["trade_count"] == 0
    ]
    if no_trade_strategies:
        st.info(
            f"No entry signals occurred for {', '.join(no_trade_strategies)} during this window; "
            "their equity remains at the starting capital."
        )

    equity_figure = go.Figure()
    for strategy_name in ["Golden Cross", "RSI", "Buy and Hold"]:
        equity_figure.add_trace(go.Scatter(
            x=strategy_comparison["equity_curves"].index,
            y=strategy_comparison["equity_curves"][strategy_name],
            mode="lines",
            name=strategy_name,
            line={"width": 2},
        ))
    equity_figure.update_layout(
        title="Daily marked-to-market equity",
        height=440,
        margin={"l": 8, "r": 18, "t": 55, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        font={"family": "Manrope, sans-serif", "color": "#17231f"},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.12, "x": 0},
        xaxis={"showgrid": False, "title": "Evaluation date"},
        yaxis={"title": "Equity (USD)", "gridcolor": "#edf1ed", "tickprefix": "$"},
    )
    st.plotly_chart(
        equity_figure,
        alt=f"Daily equity curves for Golden Cross, RSI, and Buy and Hold on {ticker}",
    )

    st.markdown("### Strategy rules")
    st.markdown(
        "- **Golden Cross:** enter when the 50-day moving average crosses above the 200-day average. "
        "Exit at a 15% closing-price gain, or the last trading close within 60 calendar days.\n"
        "- **RSI:** enter when Wilder's 14-period RSI crosses upward through 30. "
        "Use the same 15% target and 60-calendar-day exit window.\n"
        "- **Buy and Hold:** buy at the first evaluation close and sell at the final evaluation close."
    )
    st.info(
        "Execution assumption: signals and exits are filled at the same day's closing price. "
        "Each strategy starts with $10,000, uses fractional shares, holds at most one long position, "
        "and pays zero transaction costs."
    )
    st.stop()

st.markdown('<div class="brand">Market strategy / 01</div>', unsafe_allow_html=True)
st.markdown(f'<div class="page-title">{ticker} strategy overview</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">Golden Cross signals with a 15% target and 60-day maximum hold.</div>',
    unsafe_allow_html=True,
)

try:
    with st.spinner(f"Loading {ticker} market history..."):
        prices, trades = load_strategy(ticker, period)
except Exception as error:
    st.error(f"Could not load market data for {ticker}: {error}")
    st.stop()

if prices.empty:
    st.warning("No price history was returned for this ticker and period.")
    st.stop()

total_trades = len(trades)
winning_trades = int((trades["ProfitPct"] > 0).sum()) if total_trades else 0
win_rate = winning_trades / total_trades * 100 if total_trades else 0
average_return = float(trades["ProfitPct"].mean()) if total_trades else 0
net_return = float(trades["ProfitPct"].sum()) if total_trades else 0
average_holding = float(trades["HoldingDays"].mean()) if total_trades else 0

if page == "Price chart":
    st.markdown('<div class="section-label">Price history and execution points</div>', unsafe_allow_html=True)
    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=prices.index, y=prices["Close"], mode="lines", name="Close",
        line={"color": "#17231f", "width": 1.8},
    ))
    figure.add_trace(go.Scatter(
        x=prices.index, y=prices["MA50"], mode="lines", name="50-day MA",
        line={"color": "#157a56", "width": 1.5},
    ))
    figure.add_trace(go.Scatter(
        x=prices.index, y=prices["MA200"], mode="lines", name="200-day MA",
        line={"color": "#d08b32", "width": 1.5},
    ))
    if total_trades:
        figure.add_trace(go.Scatter(
            x=trades["BuyDate"], y=trades["BuyPrice"], mode="markers", name="Buy",
            marker={"color": "#157a56", "size": 10, "symbol": "triangle-up", "line": {"color": "white", "width": 1}},
            customdata=trades[["ProfitPct"]],
            hovertemplate="Buy<br>%{x|%b %d, %Y}<br>$%{y:.2f}<extra></extra>",
        ))
        figure.add_trace(go.Scatter(
            x=trades["SellDate"], y=trades["SellPrice"], mode="markers", name="Sell",
            marker={"color": "#c34c43", "size": 10, "symbol": "triangle-down", "line": {"color": "white", "width": 1}},
            hovertemplate="Sell<br>%{x|%b %d, %Y}<br>$%{y:.2f}<extra></extra>",
        ))
    figure.update_layout(
        height=560, margin={"l": 8, "r": 18, "t": 20, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff",
        font={"family": "Manrope, sans-serif", "color": "#17231f"},
        hovermode="x unified", legend={"orientation": "h", "y": 1.08, "x": 0},
        xaxis={"showgrid": False, "rangeslider": {"visible": True}},
        yaxis={"title": "Price (USD)", "gridcolor": "#edf1ed", "tickprefix": "$"},
    )
    st.plotly_chart(figure, use_container_width=True)
    first_date = prices.index[0].strftime("%b %d, %Y")
    last_date = prices.index[-1].strftime("%b %d, %Y")
    st.caption(f"{first_date} to {last_date} · {len(prices):,} trading sessions · Buy and sell markers show simulated trade executions.")

elif page == "Trade statistics":
    st.markdown('<div class="section-label">All completed trades</div>', unsafe_allow_html=True)
    columns = st.columns(4)
    with columns[0]:
        metric("Total trades", f"{total_trades}")
    with columns[1]:
        metric("Win rate", f"{win_rate:.1f}%")
    with columns[2]:
        metric("Average trade return", f"{average_return:+.2f}%")
    with columns[3]:
        metric("Average holding", f"{average_holding:.0f} days")

    st.markdown('<div class="section-label">Performance breakdown</div>', unsafe_allow_html=True)
    left, right = st.columns([1.2, 1])
    with left:
        if total_trades:
            returns_figure = go.Figure(go.Bar(
                x=[f"Trade {index + 1}" for index in range(total_trades)],
                y=trades["ProfitPct"],
                marker_color=["#157a56" if value > 0 else "#c34c43" for value in trades["ProfitPct"]],
                text=[f"{value:+.1f}%" for value in trades["ProfitPct"]],
                textposition="outside",
            ))
            returns_figure.add_hline(y=0, line_color="#aab5ac", line_width=1)
            returns_figure.update_layout(
                title="Return by trade", height=340, margin={"l": 10, "r": 10, "t": 55, "b": 8},
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff",
                yaxis={"title": "Return (%)", "gridcolor": "#edf1ed"},
                xaxis={"showgrid": False}, showlegend=False,
            )
            st.plotly_chart(returns_figure, use_container_width=True)
        else:
            st.info("No trades were generated for this period.")
    with right:
        winning = int((trades["ProfitPct"] > 0).sum()) if total_trades else 0
        losing = total_trades - winning
        outcome_figure = go.Figure(go.Pie(
            labels=["Winning", "Losing"], values=[winning, losing], hole=0.68,
            marker_colors=["#157a56", "#c34c43"], textinfo="label+value",
        ))
        outcome_figure.update_layout(
            title="Trade outcomes", height=340, margin={"l": 10, "r": 10, "t": 55, "b": 8},
            paper_bgcolor="rgba(0,0,0,0)", legend={"orientation": "h", "y": -0.05},
        )
        st.plotly_chart(outcome_figure, use_container_width=True)
    st.caption(f"Positive trade-return sum: {net_return:+.2f}% · Target-hit exits: {int((trades['SellReason'] == 'Target reached').sum()) if total_trades else 0} · Time-limit exits: {int((trades['SellReason'] == 'Max holding period').sum()) if total_trades else 0}")

else:
    st.markdown('<div class="section-label">Trade ledger</div>', unsafe_allow_html=True)
    if trades.empty:
        st.info("No trades were generated for this period.")
    else:
        display_trades = trades.copy()
        display_trades.insert(0, "Trade", [f"#{number:02d}" for number in range(1, len(trades) + 1)])
        display_trades["BuyDate"] = pd.to_datetime(display_trades["BuyDate"]).dt.strftime("%b %d, %Y")
        display_trades["SellDate"] = pd.to_datetime(display_trades["SellDate"]).dt.strftime("%b %d, %Y")
        display_trades = display_trades.rename(columns={
            "BuyDate": "Buy date", "BuyPrice": "Buy price", "SellDate": "Sell date",
            "SellPrice": "Sell price", "HoldingDays": "Days held",
            "ProfitPct": "Return (%)", "SellReason": "Exit reason",
        })
        st.dataframe(
            display_trades,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Buy price": st.column_config.NumberColumn(format="$%.2f"),
                "Sell price": st.column_config.NumberColumn(format="$%.2f"),
                "Return (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Days held": st.column_config.NumberColumn(format="%d days"),
            },
        )
        csv = trades.to_csv(index=False).encode("utf-8")
        st.download_button("Download trade records", csv, f"{ticker.lower()}_trades.csv", "text/csv")