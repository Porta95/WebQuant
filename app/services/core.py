"""
core.py — Institutional quantitative engine v3.

Key improvements over v2:
  - Extended universe: equity (SPY/QQQ/IWM) + bonds (TLT/IEF) +
    commodity (GLD/XLE) + crypto (BTC/ETH)
  - Donchian 100 breakout entry  (vs 50 — fewer false signals)
  - Dual exit: MA50 cross  OR  15% trailing stop from high-water
  - Phase sizing: EARLY=1.0 / OK=0.85 / EXTENDED=0.60 (tighter EXTENDED)
  - Risk parity (ERC) across sleeves instead of proportional max()
  - All equity assets sized with inverse-vol weighting (not just one)
  - Portfolio-level vol targeting (target 12% annual)
  - Market regime filter via SPY MA200 + VIX
  - Historical Buffett multiplier (no hardcoded value in backtest)
  - Quality metric wired into signal output (informational)
"""

import time
import requests
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from .regime import detect_regime, REGIME_MAX_EXPOSURE
from .risk import (
    vol_scale_weights,
    apply_concentration_limits,
    equal_risk_contribution,
    MAX_SLEEVE,
    ASSET_VOL_TARGET,
    TRAILING_STOP_PCT,
)

# ── Universe ──────────────────────────────────────────────────────────────────
SLEEVES: dict[str, list[str]] = {
    "equity":    ["SPY", "QQQ", "IWM"],
    "bonds":     ["TLT", "IEF"],
    "commodity": ["GLD", "XLE"],
    "crypto":    ["BTC-USD", "ETH-USD"],
}

DEFAULT_TICKERS: list[str] = [t for assets in SLEEVES.values() for t in assets]

# Reverse map: ticker → sleeve name (predefined only)
SLEEVE_MAP: dict[str, str] = {t: s for s, assets in SLEEVES.items() for t in assets}

# Fixed split within crypto sleeve (BTC dominant)
CRYPTO_SPLIT: dict[str, float] = {"BTC-USD": 0.65, "ETH-USD": 0.35}


def detect_sleeve(ticker: str) -> str:
    """
    Infer the sleeve for any ticker (predefined or custom).

    Matches by ticker name patterns so that custom assets added by
    the user (e.g. XLV, VNQ, BIL, GGAL.BA) are routed to the correct
    sleeve instead of being silently ignored.
    """
    if ticker in SLEEVE_MAP:
        return SLEEVE_MAP[ticker]

    t = ticker.upper()
    # Crypto: ends in -USD for most cases, or known coin prefixes
    if t.endswith("-USD") or any(x in t for x in ["BTC", "ETH", "SOL", "BNB", "ADA", "XRP"]):
        return "crypto"
    # Bonds / cash-like: known bond ETFs + BIL (T-Bills)
    if any(x in t for x in ["TLT", "IEF", "IEI", "BND", "AGG", "SHY", "BIL", "SHV", "GOVT", "VGSH"]):
        return "bonds"
    # Commodity / real assets / energy
    if any(x in t for x in ["GLD", "SLV", "IAU", "PDBC", "GSG", "XLE", "XOM", "USO", "VNQ", "IYR", "REIT"]):
        return "commodity"
    # Default: equity (covers ETFs like XLV, VNQ, ARKK, individual stocks, foreign ADRs, .BA etc.)
    return "equity"


def build_dynamic_sleeves(tickers: list[str]) -> dict[str, list[str]]:
    """
    Build a full sleeve map for any ticker universe, including custom tickers.

    Returns a dict {sleeve: [tickers]} covering all requested tickers,
    assigning unknown ones to their closest sleeve via detect_sleeve().
    """
    result: dict[str, list[str]] = {"equity": [], "bonds": [], "commodity": [], "crypto": []}
    for t in tickers:
        sleeve = detect_sleeve(t)
        if sleeve not in result:
            result[sleeve] = []
        if t not in result[sleeve]:
            result[sleeve].append(t)
    return result

# ── Signal Parameters ─────────────────────────────────────────────────────────
DONCHIAN_WINDOW  = 100    # Entry: price must break 100-day high (vs 50 prev)
MA_EXIT_WINDOW   = 50     # Exit trigger 1: price crosses below MA50
TRAILING_STOP    = TRAILING_STOP_PCT   # Exit trigger 2: 15% from high-water
VOL_WINDOW       = 63     # 3-month window for asset-level volatility
VOL_TARGET       = 0.12   # Portfolio annual volatility target (12%)


# ── Data Download ─────────────────────────────────────────────────────────────

def download_prices(
    tickers: list[str],
    start: str = "2004-01-01",
    retries: int = 3,
) -> pd.DataFrame:
    """Download adjusted close prices via yfinance with retry logic."""
    end     = datetime.today().strftime("%Y-%m-%d")
    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )

    for attempt in range(retries):
        try:
            raw = yf.download(
                tickers,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                session=session,
            )

            # Handle MultiIndex columns from yfinance
            if isinstance(raw.columns, pd.MultiIndex):
                data = raw["Close"]
                # yfinance sometimes returns (metric, ticker) — flatten
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(-1)
            else:
                data = raw[["Close"]] if "Close" in raw.columns else raw
                if "Close" in data.columns and len(tickers) == 1:
                    data = data.rename(columns={"Close": tickers[0]})

            # Keep only requested tickers that exist
            available = [t for t in tickers if t in data.columns]
            data = data[available].dropna(how="all").ffill()

            if len(data) > 100:
                return data

            print(f"[download] attempt {attempt+1}: only {len(data)} rows, retrying…")

        except Exception as e:
            print(f"[download] attempt {attempt+1} failed: {e}")

        time.sleep(3)

    raise RuntimeError(f"Failed to download data for: {tickers}")


def download_vix(start: str = "2004-01-01") -> pd.Series:
    """Download VIX (^VIX) for regime detection. Returns empty Series on failure."""
    try:
        session = requests.Session()
        session.headers["User-Agent"] = "Mozilla/5.0"
        raw = yf.download("^VIX", start=start, auto_adjust=True,
                          progress=False, session=session)
        close = raw["Close"] if "Close" in raw.columns else raw.iloc[:, 0]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close.dropna()
    except Exception as e:
        print(f"[vix] download failed: {e}")
        return pd.Series(dtype=float)


# ── Indicators ────────────────────────────────────────────────────────────────

def add_indicators(
    data: pd.DataFrame,
    tickers: list[str],
    don_window: int = DONCHIAN_WINDOW,
    ma_window:  int = MA_EXIT_WINDOW,
) -> pd.DataFrame:
    """
    Add per-ticker technical indicators in-place.

    Columns added for each ticker:
      {t}_DONCHIAN{don_window}  — rolling high for breakout entry
      {t}_MA{ma_window}         — moving average for exit filter
      {t}_MA200                 — long-term trend filter
    """
    min_p = max(don_window // 3, 20)
    for t in tickers:
        if t not in data.columns:
            continue
        data[f"{t}_DONCHIAN{don_window}"] = (
            data[t].rolling(don_window, min_periods=min_p).max()
        )
        data[f"{t}_MA{ma_window}"] = (
            data[t].rolling(ma_window, min_periods=min_p).mean()
        )
        data[f"{t}_MA200"] = (
            data[t].rolling(200, min_periods=100).mean()
        )
    return data


# ── Position Builder ──────────────────────────────────────────────────────────

def build_position_with_trailing_stop(
    data: pd.DataFrame,
    ticker: str,
    don_window: int = DONCHIAN_WINDOW,
    ma_window:  int = MA_EXIT_WINDOW,
    trail_pct:  float = TRAILING_STOP,
) -> pd.Series:
    """
    Long-only binary position signal with dual-exit filter.

    Entry:   price[t] > Donchian_high[t-1]     (breakout, no look-ahead)
    Exit 1:  price[t] < MA(ma_window)[t]        (trend broken)
    Exit 2:  price[t] < peak_since_entry * (1 - trail_pct)  (trailing stop)

    Returns:
        Boolean Series aligned to data.index (True = long, False = flat)
    """
    don_col = f"{ticker}_DONCHIAN{don_window}"
    ma_col  = f"{ticker}_MA{ma_window}"

    price    = data[ticker]
    donchian = data[don_col]
    ma       = data[ma_col]

    pos        = pd.Series(False, index=price.index)
    in_pos     = False
    high_water = 0.0

    for i in range(1, len(pos)):
        p = float(price.iloc[i])
        d = float(donchian.iloc[i - 1])   # previous bar → no look-ahead
        m = float(ma.iloc[i])

        if pd.isna(p) or pd.isna(d) or pd.isna(m):
            pos.iloc[i] = in_pos
            continue

        if not in_pos:
            if p > d:                       # Donchian breakout
                in_pos     = True
                high_water = p
        else:
            high_water = max(high_water, p)
            stop = high_water * (1.0 - trail_pct)
            if p < m or p < stop:           # MA break OR trailing stop
                in_pos     = False
                high_water = 0.0

        pos.iloc[i] = in_pos

    return pos


def compute_positions(
    data: pd.DataFrame,
    tickers: list[str],
    don_window: int = DONCHIAN_WINDOW,
    ma_window:  int = MA_EXIT_WINDOW,
) -> dict:
    """Return {ticker: position_series} for all available tickers."""
    return {
        t: build_position_with_trailing_stop(data, t, don_window, ma_window)
        for t in tickers
        if t in data.columns
        and f"{t}_DONCHIAN{don_window}" in data.columns
    }


# ── Phase Classification ──────────────────────────────────────────────────────

# Sizing multipliers: how much of sleeve allocation to apply per phase
PHASE_SIZE: dict[str, float] = {
    "EARLY":    1.00,   # Just broke out — full allocation
    "OK":       0.85,   # Extended but not extreme
    "EXTENDED": 0.60,   # Very extended — reduce vs v2's 0.40
    "BROKEN":   0.00,   # Below MA — no position
    "NO_DATA":  0.00,
}


def trend_phase(price: float, ma: float) -> tuple:
    """
    Classify asset trend phase relative to MA.

    Returns:
        phase: BROKEN / EARLY / OK / EXTENDED / NO_DATA
        dist:  (price - ma) / ma  (fractional distance)
        risk:  abs(price - ma) / price
    """
    if pd.isna(price) or pd.isna(ma) or ma == 0:
        return "NO_DATA", 0.0, 0.0

    dist = (price - ma) / ma
    risk = abs(price - ma) / price if price != 0 else 0.0

    if price < ma:
        phase = "BROKEN"
    elif dist < 0.03:
        phase = "EARLY"
    elif dist < 0.07:
        phase = "OK"
    else:
        phase = "EXTENDED"

    return phase, dist, risk


# ── Volatility ────────────────────────────────────────────────────────────────

def annual_volatility(prices: pd.Series, window: int = VOL_WINDOW) -> float:
    """Annualised realised volatility from recent price history."""
    rets = prices.pct_change().dropna()
    if len(rets) < 10:
        return 0.30      # conservative fallback
    tail = rets.tail(window) if len(rets) >= window else rets
    return float(tail.std() * np.sqrt(252))


# ── Buffett Indicator ─────────────────────────────────────────────────────────

def get_buffett() -> dict:
    """Fetch live Buffett Indicator (Wilshire 5000 / GDP × 100)."""
    try:
        session = requests.Session()
        session.headers["User-Agent"] = "Mozilla/5.0"

        wil = yf.download(
            "^W5000", start="1990-01-01", auto_adjust=True,
            progress=False, session=session
        )["Close"]
        if isinstance(wil, pd.DataFrame):
            wil = wil.iloc[:, 0]

        gdp_df = pd.read_csv(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GDP",
            parse_dates=[0], index_col=0,
        )
        gdp = gdp_df.iloc[:, 0].resample("D").ffill()

        df          = pd.concat([wil, gdp], axis=1).dropna()
        df.columns  = ["WILL", "GDP"]
        buffett     = (df["WILL"] / df["GDP"]) * 100

        val = float(buffett.iloc[-1])
        yoy = float(buffett.iloc[-1] - buffett.iloc[-252]) if len(buffett) > 252 else None
        ph  = "BARATO" if val < 90 else "JUSTO" if val < 120 else "CARO"
        mt  = 1.20     if val < 90 else 1.00    if val < 120 else 0.70

        return {
            "value": round(val, 1),
            "phase": ph,
            "mult":  mt,
            "yoy":   round(yoy, 1) if yoy is not None else None,
        }

    except Exception as e:
        print(f"[buffett] error: {e}")
        return {"value": None, "phase": "N/A", "mult": 1.0, "yoy": None}


def get_buffett_historical() -> pd.Series:
    """
    Compute full historical Buffett series for backtesting.

    Returns a daily pd.Series of (Wilshire5000 / GDP) × 100 from ~1995.
    Returns empty Series on failure — callers must handle the fallback.
    """
    try:
        session = requests.Session()
        session.headers["User-Agent"] = "Mozilla/5.0"

        wil = yf.download(
            "^W5000", start="1990-01-01", auto_adjust=True,
            progress=False, session=session
        )["Close"]
        if isinstance(wil, pd.DataFrame):
            wil = wil.iloc[:, 0]

        gdp_df = pd.read_csv(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GDP",
            parse_dates=[0], index_col=0,
        )
        gdp = gdp_df.iloc[:, 0].resample("D").ffill()

        df         = pd.concat([wil, gdp], axis=1).dropna()
        df.columns = ["WILL", "GDP"]
        return (df["WILL"] / df["GDP"]) * 100

    except Exception as e:
        print(f"[buffett_hist] error: {e}")
        return pd.Series(dtype=float)


def buffett_mult_at(buffett_hist: pd.Series, date) -> float:
    """
    Return the Buffett multiplier for a given historical date.

    Uses the most recent available observation ≤ date to avoid look-ahead.
    Falls back to 1.0 (neutral) if history is unavailable.
    """
    if buffett_hist is None or buffett_hist.empty:
        return 1.0
    try:
        idx = buffett_hist.index[buffett_hist.index <= date]
        if len(idx) == 0:
            return 1.0
        val = float(buffett_hist.loc[idx[-1]])
        return 1.20 if val < 90 else 1.00 if val < 120 else 0.70
    except Exception:
        return 1.0


# ── Weight Computation ────────────────────────────────────────────────────────

def compute_sleeve_weights(
    active: dict,
    sizes: dict,
    vols: dict,
    buffett_mult: float,
    regime_max: float,
    returns_df: Optional[pd.DataFrame] = None,
    tickers: Optional[list] = None,
    dynamic_sleeves: Optional[dict] = None,
) -> tuple:
    """
    Institutional weight computation pipeline:

    1. Equal Risk Contribution (risk parity) across active sleeves
    2. Buffett multiplier scales equity sleeve
    3. Cap each sleeve at MAX_SLEEVE and renormalise
    4. Intra-sleeve asset allocation:
       - Equity: inverse-vol weighting across ALL active equity assets
       - Crypto:  fixed BTC/ETH split × inverse-vol scale
       - Bonds:   equal weight
       - Commodity: equal weight
    5. Portfolio-level vol targeting → scale down + cash when vol > target
    6. Single-asset concentration limit (max 40%)
    7. Regime cap: reduce total exposure to regime_max if needed

    Returns:
        weights:  {ticker: weight}
        cash_pct: fraction in cash
        metadata: dict with vol / scale / regime info
    """
    tickers = tickers or DEFAULT_TICKERS
    # Use dynamic sleeves if provided (handles custom tickers), else build from universe
    sleeves_map = dynamic_sleeves if dynamic_sleeves is not None else build_dynamic_sleeves(tickers)

    # ── Identify active sleeves ────────────────────────────────────────────────
    sleeve_vols: dict[str, float] = {}
    for sleeve, assets in sleeves_map.items():
        active_vols = [
            vols.get(t, 0.20)
            for t in assets
            if t in tickers and active.get(t) and sizes.get(t, 0) > 0
        ]
        if active_vols:
            sleeve_vols[sleeve] = float(np.mean(active_vols))

    active_sleeves = list(sleeve_vols.keys())
    if not active_sleeves:
        return {t: 0.0 for t in tickers}, 1.0, {"regime": "DEFENSIVO", "portfolio_vol": 0.0}

    # ── Risk parity across sleeves ─────────────────────────────────────────────
    sleeve_w = equal_risk_contribution(sleeve_vols, active_sleeves)

    # ── Buffett adjustment on equity sleeve ───────────────────────────────────
    if "equity" in sleeve_w:
        sleeve_w["equity"] = sleeve_w.get("equity", 0.0) * buffett_mult

    # Renormalise
    total_sw = sum(sleeve_w.values())
    if total_sw > 0:
        sleeve_w = {s: w / total_sw for s, w in sleeve_w.items()}

    # ── Cap each sleeve ────────────────────────────────────────────────────────
    sleeve_w = {s: min(w, MAX_SLEEVE) for s, w in sleeve_w.items()}
    total_sw = sum(sleeve_w.values())
    if total_sw > 0:
        sleeve_w = {s: w / total_sw for s, w in sleeve_w.items()}

    # ── Intra-sleeve asset allocation ─────────────────────────────────────────
    raw_weights: dict[str, float] = {t: 0.0 for t in tickers}

    for sleeve, sw in sleeve_w.items():
        sleeve_assets = [
            t for t in sleeves_map.get(sleeve, [])
            if t in tickers and active.get(t) and sizes.get(t, 0) > 0
        ]
        if not sleeve_assets:
            continue

        if sleeve == "crypto":
            # Fixed BTC/ETH split + inverse-vol scaling within sleeve
            for t in sleeve_assets:
                split     = CRYPTO_SPLIT.get(t, 1.0 / len(sleeve_assets))
                asset_vol = max(vols.get(t, 0.20), 0.01)
                iv_scale  = min(ASSET_VOL_TARGET / asset_vol, 2.0)
                raw_weights[t] = sw * split * iv_scale

        elif sleeve == "equity":
            # All active equity assets — inverse-vol weighted (no single asset bias)
            inv_vols = {t: 1.0 / max(vols.get(t, 0.20), 0.01) for t in sleeve_assets}
            total_iv = sum(inv_vols.values())
            for t in sleeve_assets:
                raw_weights[t] = sw * (inv_vols[t] / total_iv) if total_iv > 0 else 0.0

        else:
            # Bonds / Commodity: equal weight among active assets
            n = len(sleeve_assets)
            for t in sleeve_assets:
                raw_weights[t] = sw / n

    # Normalise to invested fraction
    total_w = sum(raw_weights.values())
    if total_w > 0:
        raw_weights = {t: w / total_w for t, w in raw_weights.items()}

    # ── Concentration limit ────────────────────────────────────────────────────
    weights = apply_concentration_limits(raw_weights, max_single=0.40)

    # ── Portfolio-level vol targeting ─────────────────────────────────────────
    if returns_df is not None and len(returns_df) >= 20:
        weights, cash_pct, port_vol, scale = vol_scale_weights(
            weights, returns_df, target_vol=VOL_TARGET
        )
    else:
        cash_pct = max(0.0, 1.0 - sum(weights.values()))
        port_vol = 0.0
        scale    = 1.0

    # ── Regime exposure cap ────────────────────────────────────────────────────
    total_invested = sum(weights.values())
    if total_invested > regime_max and total_invested > 0:
        scale_regime = regime_max / total_invested
        weights  = {t: w * scale_regime for t, w in weights.items()}
        cash_pct = max(0.0, 1.0 - sum(weights.values()))

    meta = {"portfolio_vol": round(port_vol, 4), "vol_scale": round(scale, 4)}
    return weights, cash_pct, meta


# ── Main Signal ───────────────────────────────────────────────────────────────

def compute_signal(tickers: Optional[list] = None) -> dict:
    """
    Compute the full institutional trading signal.

    Downloads prices + VIX, computes indicators and positions, applies
    the full weight pipeline (risk parity → Buffett → vol targeting →
    regime cap), and returns a comprehensive signal dict.
    """
    tickers = tickers or DEFAULT_TICKERS

    # Build sleeve map for this specific universe (handles custom tickers)
    dyn_sleeves = build_dynamic_sleeves(tickers)

    data       = download_prices(tickers)
    vix_series = download_vix()
    data       = add_indicators(data, tickers)
    positions  = compute_positions(data, tickers)

    latest      = data.iloc[-1]
    latest_date = data.index[-1]

    # Returns DataFrame for portfolio vol estimation
    returns_df = data[tickers].pct_change().dropna()

    # ── Per-asset metrics ─────────────────────────────────────────────────────
    phases: dict = {}
    sizes:  dict = {}
    active: dict = {}
    vols:   dict = {}

    for t in tickers:
        if t not in data.columns:
            continue
        ma_col      = f"{t}_MA{MA_EXIT_WINDOW}"
        ph, dist, risk = trend_phase(
            float(latest[t]),
            float(latest[ma_col]) if ma_col in latest.index else float(latest[t]),
        )
        phases[t] = {
            "phase": ph,
            "dist":  round(dist * 100, 2),
            "risk":  round(risk * 100, 2),
            "price": round(float(latest[t]), 2),
        }
        sizes[t]  = PHASE_SIZE.get(ph, 0.0)
        active[t] = bool(positions[t].iloc[-1])
        vols[t]   = round(annual_volatility(data[t]), 4)

    # ── Regime detection ──────────────────────────────────────────────────────
    spy_price = float(latest["SPY"]) if "SPY" in data.columns else 0.0
    spy_ma200 = float(latest.get("SPY_MA200", spy_price))
    vix_val   = float(vix_series.iloc[-1]) if len(vix_series) > 0 else 20.0

    regime, regime_max = detect_regime(spy_price, spy_ma200, vix_val)

    # ── Buffett (live) ────────────────────────────────────────────────────────
    buffett = get_buffett()
    bm      = buffett["mult"]

    # ── Weights ───────────────────────────────────────────────────────────────
    weights, cash_pct, risk_meta = compute_sleeve_weights(
        active=active,
        sizes=sizes,
        vols=vols,
        buffett_mult=bm,
        regime_max=regime_max,
        returns_df=returns_df,
        tickers=tickers,
        dynamic_sleeves=dyn_sleeves,
    )

    # ── Quality score ─────────────────────────────────────────────────────────
    hq = sum(
        1 for t in tickers
        if active.get(t) and phases.get(t, {}).get("phase") in ("EARLY", "OK")
    )
    quality  = "ALTA" if hq >= 3 else "MEDIA" if hq >= 2 else "BAJA"
    dominant = (
        max(weights, key=lambda t: weights.get(t, 0))
        if any(w > 0 for w in weights.values())
        else "DEFENSIVO"
    )

    return {
        "weights":      {t: round(w, 4) for t, w in weights.items()},
        "phases":       phases,
        "active":       active,
        "dominant":     dominant,
        "regime":       regime,
        "regime_max":   regime_max,
        "vix":          round(vix_val, 1),
        "buffett":      buffett,
        "volatilities": vols,
        "signal_date":  str(latest_date.date()),
        "cash_pct":     round(cash_pct, 4),
        "quality":      quality,
        "tickers":      tickers,
        "risk":         risk_meta,
    }
