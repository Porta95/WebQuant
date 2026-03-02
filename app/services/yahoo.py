import time
import requests
import pandas as pd
import yfinance as yf

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0"
})

def download_prices(tickers, start="2020-01-01", tries=3):
    if isinstance(tickers, str):
        tickers = [tickers]

    tickers = [t.upper().strip() for t in tickers]

    for attempt in range(tries):
        try:
            frames = []

            for t in tickers:
                tk = yf.Ticker(t, session=SESSION)
                hist = tk.history(start=start, auto_adjust=True)

                if hist is None or hist.empty or "Close" not in hist:
                    continue

                frames.append(hist["Close"].rename(t))

            if not frames:
                raise ValueError("Yahoo sin datos")

            data = pd.concat(frames, axis=1)
            data = data.dropna(how="all").ffill()

            if data.empty:
                raise ValueError("Serie vacía")

            return data

        except Exception as e:
            if attempt == tries - 1:
                raise
            time.sleep(1)
