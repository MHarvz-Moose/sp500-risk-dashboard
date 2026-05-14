"""
S&P 500 Risk Dashboard

Run locally:
    streamlit run app.py

Run on Streamlit Community Cloud:
    1. Upload this project to GitHub
    2. Deploy app.py on Streamlit Community Cloud
    3. Add FRED_API_KEY in App settings > Secrets

Free-data prototype:
- Market/ETF data via yfinance
- Macro/rates/credit via FRED
- Daily and weekly Markdown reports
- Traffic-light composite risk score

Important:
- yfinance is suitable for prototyping, not institutional production.
- Forward EPS / earnings revision data is not included because reliable data is usually paid.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf
from dotenv import load_dotenv

try:
    from fredapi import Fred
except Exception:
    Fred = None

load_dotenv()


def get_secret(name: str, default: str | None = None) -> str | None:
    """Read secrets from Streamlit Cloud first, then local environment variables.

    Streamlit Cloud:
        App dashboard > Settings > Secrets

        FRED_API_KEY = "your_key_here"

    Local fallback:
        Add FRED_API_KEY to a .env file.
    """
    try:
        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:
        pass

    return os.getenv(name, default)


MARKET_TICKERS = {
    "S&P 500": "^GSPC",
    "SPY ETF": "SPY",
    "Equal-weight S&P 500": "RSP",
    "Nasdaq 100": "QQQ",
    "Russell 2000": "IWM",
    "VIX": "^VIX",
    "High Yield ETF": "HYG",
    "Investment Grade ETF": "LQD",
    "Tech Sector": "XLK",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Utilities": "XLU",
    "Financials": "XLF",
    "Industrials": "XLI",
    "Energy": "XLE",
}

FRED_SERIES = {
    "10Y Treasury Yield": "DGS10",
    "2Y Treasury Yield": "DGS2",
    "10Y Real Yield": "DFII10",
    "10Y Breakeven Inflation": "T10YIE",
    "High Yield Spread": "BAMLH0A0HYM2",
    "Investment Grade Spread": "BAMLC0A0CM",
    "Financial Conditions Index": "NFCI",
    "Initial Jobless Claims": "ICSA",
}


@dataclass
class Signal:
    name: str
    status: str
    score: int
    detail: str
    latest_value: Optional[float] = None


@st.cache_data(ttl=60 * 60)
def load_market_data(period: str = "18mo") -> pd.DataFrame:
    tickers = list(MARKET_TICKERS.values())
    raw = yf.download(
        tickers,
        period=period,
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )

    closes = pd.DataFrame()

    for name, ticker in MARKET_TICKERS.items():
        try:
            closes[name] = raw[ticker]["Close"]
        except Exception:
            closes[name] = np.nan

    closes = closes.dropna(how="all").sort_index()
    return closes


@st.cache_data(ttl=60 * 60 * 4)
def load_fred_data(start_date: str) -> pd.DataFrame:
    api_key = get_secret("FRED_API_KEY")

    if not api_key or Fred is None:
        return pd.DataFrame()

    fred = Fred(api_key=api_key)
    out = pd.DataFrame()

    for name, code in FRED_SERIES.items():
        try:
            series = fred.get_series(code, observation_start=start_date)
            out[name] = series
        except Exception:
            out[name] = np.nan

    out.index = pd.to_datetime(out.index)
    return out.sort_index().ffill()


def pct_change(series: pd.Series, days: int) -> float:
    s = series.dropna()
    if len(s) <= days:
        return np.nan
    return float((s.iloc[-1] / s.iloc[-days - 1] - 1.0) * 100)


def status_from_score(score: int) -> str:
    if score <= 0:
        return "Green"
    if score == 1:
        return "Amber"
    return "Red"


def evaluate_signals(mkt: pd.DataFrame, fred: pd.DataFrame) -> List[Signal]:
    signals: List[Signal] = []

    spx = mkt["S&P 500"].dropna()
    rsp = mkt["Equal-weight S&P 500"].dropna()
    qqq = mkt["Nasdaq 100"].dropna()
    iwm = mkt["Russell 2000"].dropna()
    vix = mkt["VIX"].dropna()

    # 1. S&P 500 trend
    ma50 = spx.rolling(50).mean().iloc[-1]
    ma200 = spx.rolling(200).mean().iloc[-1]
    spx_latest = spx.iloc[-1]

    if spx_latest < ma200:
        score = 2
        detail = "S&P 500 is below its 200-day moving average."
    elif spx_latest < ma50:
        score = 1
        detail = "S&P 500 is below its 50-day moving average but above its 200-day moving average."
    else:
        score = 0
        detail = "S&P 500 is above its 50-day and 200-day moving averages."

    signals.append(Signal("S&P 500 trend", status_from_score(score), score, detail, float(spx_latest)))

    # 2. Breadth proxy
    rel_rsp_spx = (rsp / spx).dropna()
    rel_1m = pct_change(rel_rsp_spx, 21)
    rel_3m = pct_change(rel_rsp_spx, 63)

    if rel_1m < -3 and rel_3m < -5:
        score = 2
        detail = f"Equal-weight S&P is underperforming over 1m ({rel_1m:.1f}%) and 3m ({rel_3m:.1f}%)."
    elif rel_1m < -2 or rel_3m < -3:
        score = 1
        detail = f"Breadth is soft: equal-weight relative performance is {rel_1m:.1f}% over 1m and {rel_3m:.1f}% over 3m."
    else:
        score = 0
        detail = f"Breadth proxy is stable: equal-weight relative performance is {rel_1m:.1f}% over 1m and {rel_3m:.1f}% over 3m."

    signals.append(Signal("Market breadth proxy", status_from_score(score), score, detail, rel_1m))

    # 3. Small caps
    rel_iwm_spx = (iwm / spx).dropna()
    smallcap_1m = pct_change(rel_iwm_spx, 21)

    if smallcap_1m < -5:
        score = 2
        detail = f"Russell 2000 is sharply underperforming S&P 500 over 1m ({smallcap_1m:.1f}%)."
    elif smallcap_1m < -3:
        score = 1
        detail = f"Small caps are underperforming S&P 500 over 1m ({smallcap_1m:.1f}%)."
    else:
        score = 0
        detail = f"Small caps are not showing major stress vs S&P 500 over 1m ({smallcap_1m:.1f}%)."

    signals.append(Signal("Small-cap risk appetite", status_from_score(score), score, detail, smallcap_1m))

    # 4. Volatility
    vix_latest = float(vix.iloc[-1])
    vix_1m = pct_change(vix, 21)

    if vix_latest > 25 or vix_1m > 50:
        score = 2
        detail = f"VIX stress is elevated: latest {vix_latest:.1f}, 1m change {vix_1m:.1f}%."
    elif vix_latest > 20 or vix_1m > 25:
        score = 1
        detail = f"VIX is rising/moderately elevated: latest {vix_latest:.1f}, 1m change {vix_1m:.1f}%."
    else:
        score = 0
        detail = f"VIX is contained: latest {vix_latest:.1f}, 1m change {vix_1m:.1f}%."

    signals.append(Signal("Volatility", status_from_score(score), score, detail, vix_latest))

    # 5. Credit stress
    hyg = mkt["High Yield ETF"].dropna()
    lqd = mkt["Investment Grade ETF"].dropna()
    rel_hyg_lqd = (hyg / lqd).dropna()
    credit_proxy_1m = pct_change(rel_hyg_lqd, 21)

    hy_spread_score = 0
    hy_spread_detail = ""

    if not fred.empty and "High Yield Spread" in fred:
        hy = fred["High Yield Spread"].dropna()
        if len(hy) > 30:
            hy_change_1m = float(hy.iloc[-1] - hy.iloc[-22]) if len(hy) > 22 else np.nan
            hy_spread_detail = f" HY spread latest {hy.iloc[-1]:.2f}%, 1m change {hy_change_1m:.2f}pp."
            if hy_change_1m > 0.75 or hy.iloc[-1] > 5.5:
                hy_spread_score = 2
            elif hy_change_1m > 0.35 or hy.iloc[-1] > 4.5:
                hy_spread_score = 1

    if credit_proxy_1m < -3 or hy_spread_score == 2:
        score = 2
        detail = f"Credit conditions are deteriorating: HYG/LQD 1m relative move {credit_proxy_1m:.1f}%." + hy_spread_detail
    elif credit_proxy_1m < -1.5 or hy_spread_score == 1:
        score = 1
        detail = f"Credit conditions are mildly weaker: HYG/LQD 1m relative move {credit_proxy_1m:.1f}%." + hy_spread_detail
    else:
        score = 0
        detail = f"Credit proxy is stable: HYG/LQD 1m relative move {credit_proxy_1m:.1f}%." + hy_spread_detail

    signals.append(Signal("Credit stress", status_from_score(score), score, detail, credit_proxy_1m))

    # 6. Rates / real yields
    if not fred.empty and "10Y Treasury Yield" in fred:
        ten = fred["10Y Treasury Yield"].dropna()
        real = fred.get("10Y Real Yield", pd.Series(dtype=float)).dropna()
        ten_latest = float(ten.iloc[-1])
        ten_1m_change = float(ten.iloc[-1] - ten.iloc[-22]) if len(ten) > 22 else np.nan
        real_latest = float(real.iloc[-1]) if len(real) else np.nan

        if ten_1m_change > 0.40 or real_latest > 2.5:
            score = 2
            detail = f"Rate pressure is high: 10Y yield {ten_latest:.2f}%, 1m change {ten_1m_change:.2f}pp, real yield {real_latest:.2f}%."
        elif ten_1m_change > 0.20 or real_latest > 2.2:
            score = 1
            detail = f"Rate pressure is rising: 10Y yield {ten_latest:.2f}%, 1m change {ten_1m_change:.2f}pp, real yield {real_latest:.2f}%."
        else:
            score = 0
            detail = f"Rates are not flashing major warning: 10Y yield {ten_latest:.2f}%, 1m change {ten_1m_change:.2f}pp, real yield {real_latest:.2f}%."

        signals.append(Signal("Rates / real yields", status_from_score(score), score, detail, ten_latest))
    else:
        signals.append(Signal("Rates / real yields", "Amber", 1, "FRED data unavailable. Add FRED_API_KEY to enable this signal.", None))

    # 7. Inflation expectations
    if not fred.empty and "10Y Breakeven Inflation" in fred:
        bei = fred["10Y Breakeven Inflation"].dropna()
        bei_latest = float(bei.iloc[-1])
        bei_1m_change = float(bei.iloc[-1] - bei.iloc[-22]) if len(bei) > 22 else np.nan

        if bei_1m_change > 0.25 or bei_latest > 2.7:
            score = 2
            detail = f"Inflation expectations are pressuring valuations: 10Y breakeven {bei_latest:.2f}%, 1m change {bei_1m_change:.2f}pp."
        elif bei_1m_change > 0.15 or bei_latest > 2.5:
            score = 1
            detail = f"Inflation expectations are moderately elevated: 10Y breakeven {bei_latest:.2f}%, 1m change {bei_1m_change:.2f}pp."
        else:
            score = 0
            detail = f"Inflation expectations look contained: 10Y breakeven {bei_latest:.2f}%, 1m change {bei_1m_change:.2f}pp."

        signals.append(Signal("Inflation expectations", status_from_score(score), score, detail, bei_latest))
    else:
        signals.append(Signal("Inflation expectations", "Amber", 1, "FRED breakeven inflation data unavailable.", None))

    # 8. Defensive rotation
    defensive = (mkt["Utilities"] + mkt["Consumer Staples"]) / 2
    cyc_growth = (mkt["Tech Sector"] + mkt["Consumer Discretionary"] + mkt["Industrials"] + mkt["Financials"]) / 4
    rel_def = (defensive / cyc_growth).dropna()
    def_1m = pct_change(rel_def, 21)

    if def_1m > 5:
        score = 2
        detail = f"Defensive sectors are strongly outperforming cyclicals/growth over 1m ({def_1m:.1f}%)."
    elif def_1m > 3:
        score = 1
        detail = f"Defensive sectors are starting to outperform over 1m ({def_1m:.1f}%)."
    else:
        score = 0
        detail = f"No strong defensive rotation: defensive relative move over 1m is {def_1m:.1f}%."

    signals.append(Signal("Defensive rotation", status_from_score(score), score, detail, def_1m))

    # 9. AI / mega-cap leadership proxy
    rel_qqq_spx = (qqq / spx).dropna()
    qqq_1m = pct_change(rel_qqq_spx, 21)
    qqq_3m = pct_change(rel_qqq_spx, 63)

    if qqq_1m < -4 and qqq_3m < -6:
        score = 2
        detail = f"Mega-cap growth/AI proxy is breaking down: QQQ vs S&P {qqq_1m:.1f}% over 1m and {qqq_3m:.1f}% over 3m."
    elif qqq_1m < -2.5:
        score = 1
        detail = f"Mega-cap growth/AI leadership is weakening: QQQ vs S&P {qqq_1m:.1f}% over 1m."
    else:
        score = 0
        detail = f"Mega-cap growth/AI leadership is intact: QQQ vs S&P {qqq_1m:.1f}% over 1m."

    signals.append(Signal("AI / mega-cap leadership", status_from_score(score), score, detail, qqq_1m))

    return signals


def aggregate_score(signals: List[Signal]) -> Tuple[int, str, str]:
    total = sum(s.score for s in signals)
    max_score = len(signals) * 2
    pct = total / max_score if max_score else 0

    if pct >= 0.55:
        label = "High"
        interpretation = "Multiple risk channels are flashing at once. Near-term S&P 500 drawdown risk is elevated."
    elif pct >= 0.30:
        label = "Moderate"
        interpretation = "Some risk channels are deteriorating. The market is vulnerable if earnings, rates, credit, or mega-cap leadership weaken further."
    else:
        label = "Low"
        interpretation = "The dashboard is not showing broad stress. Keep watching earnings revisions, breadth, rates, and credit."

    return total, label, interpretation


def generate_daily_report(signals: List[Signal]) -> str:
    total, label, interpretation = aggregate_score(signals)
    red = [s for s in signals if s.status == "Red"]
    amber = [s for s in signals if s.status == "Amber"]
    green = [s for s in signals if s.status == "Green"]

    lines = [
        f"# Daily S&P 500 Risk Report — {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"**Overall risk level: {label}**",
        f"Composite score: **{total} / {len(signals) * 2}**",
        "",
        interpretation,
        "",
    ]

    if red:
        lines.append("## Red flags")
        for s in red:
            lines.append(f"- **{s.name}:** {s.detail}")
        lines.append("")

    if amber:
        lines.append("## Watch closely")
        for s in amber:
            lines.append(f"- **{s.name}:** {s.detail}")
        lines.append("")

    lines.append("## Stable signals")
    for s in green:
        lines.append(f"- **{s.name}:** {s.detail}")

    lines.extend([
        "",
        "## Interpretation",
        "A higher score is not a trading signal by itself. It means the conditions that often precede S&P 500 pullbacks are becoming more visible. The highest-conviction warning usually comes when earnings revisions, rates, credit spreads, breadth, and mega-cap leadership weaken together.",
    ])

    return "\n".join(lines)


def generate_weekly_report(signals: List[Signal], mkt: pd.DataFrame) -> str:
    total, label, interpretation = aggregate_score(signals)
    spx = mkt["S&P 500"].dropna()

    week = pct_change(spx, 5)
    month = pct_change(spx, 21)
    quarter = pct_change(spx, 63)

    lines = [
        f"# Weekly S&P 500 Risk Report — week ending {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"**Overall risk level: {label}** | Composite score: **{total} / {len(signals) * 2}**",
        "",
        f"S&P 500 performance: **{week:.1f}% 1w**, **{month:.1f}% 1m**, **{quarter:.1f}% 3m**.",
        "",
        "## Executive summary",
        interpretation,
        "",
        "## Signal review",
    ]

    for s in signals:
        lines.extend([
            f"### {s.name} — {s.status}",
            s.detail,
            "",
        ])

    lines.extend([
        "## What would change the risk view next week?",
        "- Risk rises if more signals move from Amber to Red, especially credit spreads, rates, breadth, and AI/mega-cap leadership.",
        "- Risk falls if the S&P 500 remains above trend, equal-weight breadth improves, credit spreads tighten, and yields stop rising.",
        "- The biggest future upgrade is paid forward-EPS and earnings-revision data.",
    ])

    return "\n".join(lines)


def signal_colour(status: str) -> str:
    return {
        "Green": "#D7F7DF",
        "Amber": "#FFF2CC",
        "Red": "#F8D7DA",
    }.get(status, "#FFFFFF")


def main() -> None:
    st.set_page_config(page_title="S&P 500 Risk Dashboard", layout="wide")
    st.title("S&P 500 Risk Dashboard")
    st.caption("Prototype risk monitor for S&P 500 drawdown risk over the next 1–3 months.")

    start_date = (datetime.now() - timedelta(days=450)).strftime("%Y-%m-%d")

    with st.spinner("Loading market and macro data..."):
        market_data = load_market_data("18mo")
        fred_data = load_fred_data(start_date)

    if market_data.empty:
        st.error("Market data could not be loaded. Check your internet connection and yfinance availability.")
        return

    signals = evaluate_signals(market_data, fred_data)
    total, risk_label, interpretation = aggregate_score(signals)

    col1, col2, col3 = st.columns(3)
    col1.metric("Overall risk", risk_label)
    col2.metric("Composite score", f"{total} / {len(signals) * 2}")
    col3.metric("Latest S&P 500", f"{market_data['S&P 500'].dropna().iloc[-1]:,.0f}")

    st.info(interpretation)

    st.subheader("Risk signals")
    signal_df = pd.DataFrame([s.__dict__ for s in signals])
    display_df = signal_df[["name", "status", "score", "detail"]].copy()
    st.dataframe(
        display_df.style.applymap(lambda v: f"background-color: {signal_colour(v)}" if v in ["Green", "Amber", "Red"] else ""),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Charts")

    c1, c2 = st.columns(2)
    with c1:
        spx = market_data["S&P 500"].dropna()
        chart_df = pd.DataFrame({
            "S&P 500": spx,
            "50-day MA": spx.rolling(50).mean(),
            "200-day MA": spx.rolling(200).mean(),
        })
        st.plotly_chart(px.line(chart_df, title="S&P 500 trend"), use_container_width=True)

    with c2:
        breadth = (market_data["Equal-weight S&P 500"] / market_data["S&P 500"]).dropna()
        st.plotly_chart(px.line(breadth, title="Breadth proxy: RSP / S&P 500"), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(px.line(market_data["VIX"].dropna(), title="VIX"), use_container_width=True)

    with c4:
        credit_proxy = (market_data["High Yield ETF"] / market_data["Investment Grade ETF"]).dropna()
        st.plotly_chart(px.line(credit_proxy, title="Credit proxy: HYG / LQD"), use_container_width=True)

    c5, c6 = st.columns(2)
    with c5:
        ai_leadership = (market_data["Nasdaq 100"] / market_data["S&P 500"]).dropna()
        st.plotly_chart(px.line(ai_leadership, title="AI / mega-cap leadership proxy: QQQ / S&P 500"), use_container_width=True)

    with c6:
        defensive = (market_data["Utilities"] + market_data["Consumer Staples"]) / 2
        cyc_growth = (
            market_data["Tech Sector"]
            + market_data["Consumer Discretionary"]
            + market_data["Industrials"]
            + market_data["Financials"]
        ) / 4
        defensive_rotation = (defensive / cyc_growth).dropna()
        st.plotly_chart(px.line(defensive_rotation, title="Defensive rotation proxy"), use_container_width=True)

    if not fred_data.empty:
        st.subheader("FRED macro/rates/credit data")
        default_cols = [c for c in ["10Y Treasury Yield", "10Y Real Yield", "High Yield Spread"] if c in fred_data.columns]
        selected = st.multiselect("Select FRED series", list(fred_data.columns), default=default_cols)
        if selected:
            st.plotly_chart(px.line(fred_data[selected], title="Selected FRED series"), use_container_width=True)
    else:
        st.warning("FRED data is not enabled. On Streamlit Cloud, add FRED_API_KEY under App settings > Secrets. Locally, add it to your .env file.")

    st.subheader("Reports")
    daily_report = generate_daily_report(signals)
    weekly_report = generate_weekly_report(signals, market_data)

    tab1, tab2 = st.tabs(["Daily summary", "Weekly in-depth"])
    with tab1:
        st.markdown(daily_report)
        st.download_button("Download daily report", daily_report, file_name="daily_sp500_risk_report.md")

    with tab2:
        st.markdown(weekly_report)
        st.download_button("Download weekly report", weekly_report, file_name="weekly_sp500_risk_report.md")


if __name__ == "__main__":
    main()
