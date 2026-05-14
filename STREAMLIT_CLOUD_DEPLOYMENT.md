# Streamlit Cloud Deployment Checklist

## Files to upload to GitHub

Upload:

- app.py
- requirements.txt
- README.md
- config.json
- .gitignore
- .streamlit/config.toml
- .streamlit/secrets.toml.example
- runtime.txt
- STREAMLIT_CLOUD_DEPLOYMENT.md

Do not upload:

- .env
- .venv/
- .streamlit/secrets.toml

## Streamlit Cloud settings

Main file path:

```text
app.py
```

This fixed package has `app.py` at the repository root. If you use an older package where `app.py` is inside `sp500_risk_dashboard_project/`, the main file path must instead be:

```text
sp500_risk_dashboard_project/app.py
```

Secrets:

```toml
FRED_API_KEY = "your_fred_api_key_here"
```

## After deployment

Open the app URL and check:

- The dashboard loads
- Market data loads
- No package installation errors appear
- FRED data appears once the secret has been added
- Daily and weekly report tabs render correctly

## Troubleshooting

If FRED data does not load:

1. Check the FRED API key is correct.
2. Make sure the secret is named exactly `FRED_API_KEY`.
3. Reboot the Streamlit app after saving secrets.

If market data does not load:

1. Reboot the app.
2. Check whether Yahoo/yfinance is temporarily rate-limiting requests.
3. Try again later or swap to a more reliable paid market-data API.
