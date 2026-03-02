import time
import requests
import pandas as pd

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0"
})

def _fetch_chart(ticker, start_ts):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "period1": start_ts,
        "period2": int(time.time()),
        "interval": "1d",
        "events": "div,splits"
    }

    r = SESSION.get(url, params=params, timeout=10)
    r.raise_for_status()
    j = r.json()

    result = j["chart"]["result"][0]
    ts = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]

    df = pd.DataFrame({"Close": closes}, index=pd.to_datetime(ts, unit="s"))
    return df.dropna()

def download_prices(tickers, start="2020-01-01"):
    if isinstance(tickers, str):
        tickers = [tickers]

    start_ts = int(pd.Timestamp(start).timestamp())

    frames = []
    for t in tickers:
        t = t.upper().strip()
        try:
            df = _fetch_chart(t, start_ts)
            frames.append(df["Close"].rename(t))
        except Exception:
            continue

    if not frames:
        raise ValueError("Yahoo sin datos")

    data = pd.concat(frames, axis=1).ffill()
    return data
