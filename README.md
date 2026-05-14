# S&P 500 Risk Dashboard

## Easiest setup: Streamlit Community Cloud

This is the recommended setup if you do not want to use Terminal.

### 1. Create free accounts

Create accounts for:

- GitHub
- Streamlit Community Cloud
- FRED API

### 2. Create a GitHub repository

Create a new GitHub repository called something like:

```text
sp500-risk-dashboard
```

Upload these files/folders from this project:

```text
app.py
requirements.txt
runtime.txt
README.md
config.json
.streamlit/config.toml
.streamlit/secrets.toml.example
.gitignore
STREAMLIT_CLOUD_DEPLOYMENT.md
```

Do **not** upload a real `.env` file or a real `.streamlit/secrets.toml` file.

### 3. Deploy on Streamlit Cloud

In Streamlit Community Cloud:

1. Click **Create app**
2. Choose your GitHub repository
3. Set the main file path to:

```text
app.py
```

4. Deploy the app

### 4. Add your FRED API key as a secret

In the Streamlit app dashboard, go to:

```text
Settings > Secrets
```

Add:

```toml
FRED_API_KEY = "your_fred_api_key_here"
```

Save, then reboot/redeploy the app.

The dashboard will still load without a FRED key, but macro signals such as rates, real yields, inflation expectations and credit spreads will be incomplete.


A local Streamlit dashboard for monitoring 1–3 month S&P 500 drawdown risk.

## What it tracks

- S&P 500 trend vs 50-day and 200-day moving averages
- Market breadth proxy: equal-weight S&P 500 vs cap-weight S&P 500
- Small-cap risk appetite: Russell 2000 vs S&P 500
- Volatility: VIX
- Credit stress: HYG/LQD plus optional FRED high-yield spread
- Rates and real yields via FRED
- Inflation expectations via FRED breakevens
- Defensive sector rotation
- AI / mega-cap leadership proxy: Nasdaq 100 vs S&P 500

## Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your `.env` file:

```bash
cp .env.example .env
```

Then edit `.env` and add your FRED API key.

Run the app:

```bash
streamlit run app.py
```

## Data sources

This first version uses:

- `yfinance` for market and ETF prices
- FRED for Treasury yields, real yields, breakevens, credit spreads, financial conditions and jobless claims

## Limitations

This is a prototype. It does **not** yet include:

- Paid earnings-revision data
- Paid S&P 500 forward EPS / forward P/E feeds
- Automated email delivery
- Persistent historical signal logging
- Portfolio-specific risk analytics

## Recommended next upgrades

1. Add a daily CSV log of signal scores.
2. Add scheduled report generation using cron, Windows Task Scheduler, or GitHub Actions.
3. Add email delivery.
4. Add paid forward EPS / earnings-revision data.
5. Add a backtest to see how the composite score behaved before historical drawdowns.

## Not financial advice

This dashboard is a risk-monitoring tool, not a trading system or investment recommendation.
