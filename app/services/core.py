"""
core.py — Motor cuantitativo central.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import time
import requests
from datetime import datetime, timedelta
from typing import Optional

DEFAULT_TICKERS = ["SPY", "QQQ", "BTC-USD", "ETH-USD", "GLD"]

SLEEVE_MAP = {
    "SPY":     "equity",
    "QQQ":     "equity",
    "BTC-USD": "crypto",
    "ETH-USD": "crypto",
    "GLD":     "commodity",
}

CRYPTO_SPLIT = {
    "BTC-USD": 0.70,
    "ETH-USD": 0.30,
}


def download_prices(tickers: list[str], start: str = "2018-01-01", retries: int = 3) -> pd.DataFrame:
    end = datetime.today().strftime("%Y-%m-%d")
    
    for attempt in range(retries):
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            
            raw = yf.download(
                tickers,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                session=session,
            )

            if isinstance(raw.columns, pd.MultiIndex):
                data = raw["Close"]
            else:
                data = raw[["Close"]] if "Close" in raw else raw
                data.columns = tickers[:1]

            data = data.dropna(how="all").ffill()
            
            if len(data) > 100:
                return data
                
            print(f"[download] intento {attempt+1}: solo {len(data)} rows, reintentando...")
        except Exception as e:
            print(f"[download] intento {attempt+1} fallido: {e}")
        
        time.sleep(3)

    raise RuntimeError(f"No se pudieron descargar datos para: {tickers}")


def add_indicators(data: pd.DataFrame, tickers: list[str], window: int = 50) -> pd.DataFrame:
    for t in tickers:
        if t in data.columns:
            data[f"{t}_MA{window}"]   = data[t].rolling(window, min_periods=20).mean()
            data[f"{t}_HIGH{window}"] = data[t].rolling(window, min_periods=20).max()
    return data


def build_position(entry: pd.Series, exit_: pd.Series) -> pd.Series:
    pos = pd.Series(False, index=entry.index)
    in_pos = False
    for i in range(1, len(pos)):
        if not in_pos and entry.iloc[i]:
            in_pos = True
        elif in_pos and exit_.iloc[i]:
            in_pos = False
        pos.iloc[i] = in_pos
    return pos


def compute_positions(data: pd.DataFrame, tickers: list[str], window: int = 50) -> dict:
    positions = {}
    for t in tickers:
        if t not in data.columns:
            continue
        entry  = data[t] > data[f"{t}_HIGH{window}"].shift(1)
        exit_  = data[t] < data[f"{t}_MA{window}"]
        positions[t] = build_position(entry, exit_)
    return positions


def trend_phase(price: float, ma: float) -> tuple:
    if pd.isna(price) or pd.isna(ma):
        return "NO_DATA", 0.0, 0.0

    dist = (price - ma) / ma
    risk = abs(price - ma) / price if price != 0 else 0.0

    if price < ma:
        return "BROKEN", dist, risk
    elif dist < 0.03:
        return "EARLY", dist, risk
    elif dist < 0.07:
        return "OK", dist, risk
    else:
        return "EXTENDED", dist, risk


def phase_size(phase: str) -> float:
    return {"EARLY": 1.0, "OK": 0.7, "EXTENDED": 0.4}.get(phase, 0.0)


def get_buffett() -> dict:
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
        wil = yf.download("^W5000", start="1990-01-01", auto_adjust=True, progress=False, session=session)["Close"]

        gdp_df = pd.read_csv(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GDP",
            parse_dates=[0],
            index_col=0,
        )
        gdp = gdp_df.iloc[:, 0].resample("D").ffill()

        df = pd.concat([wil, gdp], axis=1).dropna()
        df.columns = ["WILL", "GDP"]
        buffett = (df["WILL"] / df["GDP"]) * 100

        val  = float(buffett.iloc[-1])
        yoy  = float(buffett.iloc[-1] - buffett.iloc[-252]) if len(buffett) > 252 else None

        if val < 90:
            phase, mult = "BARATO", 1.2
        elif val < 120:
            phase, mult = "JUSTO", 1.0
        else:
            phase, mult = "CARO", 0.7

        return {"value": round(val, 1), "phase": phase, "mult": mult, "yoy": round(yoy, 1) if yoy else None}

    except Exception as e:
        print(f"[buffett] error: {e}")
        return {"value": None, "phase": "N/A", "mult": 1.0, "yoy": None}


def annual_volatility(prices: pd.Series, window: int = 90) -> float:
    returns = prices.pct_change().dropna()
    if len(returns) < window:
        return float(returns.std() * np.sqrt(252))
    return float(returns.tail(window).std() * np.sqrt(252))


def vol_adjusted_size(base_size: float, annual_vol: float, target_vol: float = 0.20) -> float:
    if annual_vol <= 0:
        return base_size
    return min(base_size * (target_vol / annual_vol), 1.5)


def compute_signal(tickers: Optional[list] = None, window: int = 50) -> dict:
    tickers = tickers or DEFAULT_TICKERS
    data = download_prices(tickers)
    data = add_indicators(data, tickers, window)
    positions = compute_positions(data, tickers, window)

    latest = data.iloc[-1]
    phases, sizes, active, vols = {}, {}, {}, {}

    for t in tickers:
        if t not in data.columns:
            continue
        ph, dist, risk = trend_phase(float(latest[t]), float(latest[f"{t}_MA{window}"]))
        phases[t] = {"phase": ph, "dist": round(dist * 100, 2), "risk": round(risk * 100, 2)}
        sizes[t]  = phase_size(ph)
        active[t] = bool(positions[t].iloc[-1])
        vols[t]   = round(annual_volatility(data[t]), 4)

    crypto_assets    = [t for t in tickers if SLEEVE_MAP.get(t) == "crypto"]
    equity_assets    = [t for t in tickers if SLEEVE_MAP.get(t) == "equity"]
    commodity_assets = [t for t in tickers if SLEEVE_MAP.get(t) == "commodity"]

    def sleeve_strength(assets):
        s = [sizes[a] for a in assets if active.get(a)]
        return max(s) if s else 0.0

    crypto_s    = sleeve_strength(crypto_assets)
    equity_s    = sleeve_strength(equity_assets)
    commodity_s = sleeve_strength(commodity_assets)
    total_s     = crypto_s + equity_s + commodity_s

    weights  = {t: 0.0 for t in tickers}
    dominant = "DEFENSIVO"

    if total_s > 0:
        buffett = get_buffett()
        bm = buffett["mult"]

        cw = crypto_s    / total_s
        ew = equity_s    / total_s
        gw = commodity_s / total_s

        ew *= bm
        total2 = cw + ew + gw
        cw /= total2; ew /= total2; gw /= total2

        for t in crypto_assets:
            if active.get(t):
                split = CRYPTO_SPLIT.get(t, 1.0 / max(len(crypto_assets), 1))
                weights[t] = round(vol_adjusted_size(cw * split, vols[t]), 4)

        eq_sorted = sorted(equity_assets, key=lambda t: 0 if t == "QQQ" else 1)
        for t in eq_sorted:
            if active.get(t):
                weights[t] = round(vol_adjusted_size(ew, vols[t]), 4)
                dominant = t
                break

        for t in commodity_assets:
            if active.get(t):
                weights[t] = round(vol_adjusted_size(gw, vols[t]), 4)
                if dominant == "DEFENSIVO":
                    dominant = t

        total_w = sum(weights.values())
        if total_w > 0:
            weights = {t: round(w / total_w, 4) for t, w in weights.items()}

        if crypto_s > equity_s and crypto_s > commodity_s and dominant == "DEFENSIVO":
            dominant = "CRYPTO"
    else:
        buffett = get_buffett()

    cash_pct    = round(max(1.0 - sum(weights.values()), 0.0), 4)
    high_quality = sum(1 for t in tickers if active.get(t) and phases.get(t, {}).get("phase") in ("EARLY", "OK"))
    quality      = "ALTA" if high_quality >= 3 else "MEDIA" if high_quality >= 2 else "BAJA"

    return {
        "weights":      weights,
        "phases":       phases,
        "active":       active,
        "dominant":     dominant,
        "buffett":      buffett,
        "volatilities": vols,
        "signal_date":  str(data.index[-1].date()),
        "cash_pct":     cash_pct,
        "quality":      quality,
        "tickers":      tickers,
    }
