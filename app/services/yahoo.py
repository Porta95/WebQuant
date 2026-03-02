import time
import requests
import pandas as pd
import yfinance as yf

# --- CONFIG CLOUD ---
yf.set_tz_cache_location("/tmp")  # Railway/Docker safe

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

# --- DOWNLOAD ROBUSTO ---
def download_prices(tickers, start="2020-01-01", tries=3):
    if isinstance(tickers, str):
        tickers = [tickers]

    tickers = [t.upper().strip() for t in tickers]

    for attempt in range(tries):
        try:
            raw = yf.download(
                tickers,
                start=start,
                auto_adjust=True,
                progress=False,
                threads=False,
                group_by="ticker",
                ignore_tz=True,
                session=SESSION,
            )

            if raw is None or len(raw) == 0:
                raise ValueError("Yahoo vacío")

            # --- Multi ticker ---
            if isinstance(raw.columns, pd.MultiIndex):
                frames = []
                for t in tickers:
                    if (t, "Close") in raw.columns:
                        frames.append(raw[(t, "Close")].rename(t))
                if not frames:
                    raise ValueError("Sin Close en Yahoo")
                data = pd.concat(frames, axis=1)

            # --- Single ticker ---
            else:
                if "Close" not in raw:
                    raise ValueError("Sin Close")
                data = raw["Close"].to_frame(name=tickers[0])

            data = data.dropna(how="all").ffill()

            if data.empty:
                raise ValueError("Serie vacía")

            return data

        except Exception as e:
            if attempt == tries - 1:
                raise
            time.sleep(1.2)
