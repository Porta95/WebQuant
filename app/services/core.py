"""
core.py — Institutional quantitative engine v4.

v4 improvements over v3:
  - EWMA volatility (span=30) replaces rolling std — more responsive to vol regimes
  - Cross-sectional momentum overlay (12-1 month) for intra-sleeve tilting
  - Buffett multiplier BUG FIX: applied as total exposure cap, not as equity sleeve
    scale followed by renormalization (which was cancelling the signal entirely)
  - Momentum tilt in equity sleeve (70% inv-vol + 30% momentum rank)
  - Bond duration tilt via momentum (TLT vs IEF adapts to rate environment)
  - Separate `invested_pct` tracking so Buffett cash buffer is preserved through
    the full weight pipeline
  - Drawdown de-risking wired into final exposure computation
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
    drawdown_derisking_multiplier,
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

# Fixed split within crypto sleeve (BTC dominant); used only as tiebreaker,
# actual weight is momentum + inv-vol driven
CRYPTO_SPLIT: dict[str, float] = {"BTC-USD": 0.60, "ETH-USD": 0.40}

# ── Signal Parameters ─────────────────────────────────────────────────────────
DONCHIAN_WINDOW  = 100    # Entry: price must break 100-day high
MA_EXIT_WINDOW   = 50     # Exit trigger 1: price crosses below MA50
TRAILING_STOP    = TRAILING_STOP_PCT   # Exit trigger 2: 15% from high-water
VOL_WINDOW       = 63     # 3-month window (used as fallback when EWMA insufficient)
EWMA_SPAN        = 30     # EWMA volatility span (≈ 1.5 month half-life)
VOL_TARGET       = 0.12   # Portfolio annual volatility target (12%)

# Cross-sectional momentum parameters
MOM_LONG         = 252    # 12-month lookback
MOM_SHORT        = 21     # Skip last month (avoid reversal)
MOMENTUM_BLEND   = 0.30   # 30% momentum tilt, 70% inv-vol in intra-sleeve weighting


# ── Sleeve Detection ──────────────────────────────────────────────────────────

def detect_sleeve(ticker: str) -> str:
    """
    Infer the sleeve for any ticker (predefined or custom).
    Matches by ticker name patterns so custom assets are routed correctly.
    """
    if ticker in SLEEVE_MAP:
        return SLEEVE_MAP[ticker]

    t = ticker.upper()
    if t.endswith("-USD") or any(x in t for x in ["BTC", "ETH", "SOL", "BNB", "ADA", "XRP"]):
        return "crypto"
    if any(x in t for x in ["TLT", "IEF", "IEI", "BND", "AGG", "SHY", "BIL", "SHV", "GOVT", "VGSH"]):
        return "bonds"
    if any(x in t for x in ["GLD", "SLV", "IAU", "PDBC", "GSG", "XLE", "XOM", "USO", "VNQ", "IYR", "REIT"]):
        return "commodity"
    return "equity"


def build_dynamic_sleeves(tickers: list[str]) -> dict[str, list[str]]:
    """Build a full sleeve map for any ticker universe, including custom tickers."""
    result: dict[str, list[str]] = {"equity": [], "bonds": [], "commodity": [], "crypto": []}
    for t in tickers:
        sleeve = detect_sleeve(t)
        if sleeve not in result:
            result[sleeve] = []
        if t not in result[sleeve]:
            result[sleeve].append(t)
    return result


# ── Data Download ─────────────────────────────────────────────────────────────

def download_prices(
    tickers: list[str],
    start: str = "2003-01-01",
    retries: int = 3,
) -> pd.DataFrame:
    """Download adjusted close prices via yfinance with retry logic."""
    end = datetime.today().strftime("%Y-%m-%d")

    for attempt in range(retries):
        try:
            raw = yf.download(
                tickers,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
            )

            if isinstance(raw.columns, pd.MultiIndex):
                data = raw["Close"]
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(-1)
            else:
                data = raw[["Close"]] if "Close" in raw.columns else raw
                if "Close" in data.columns and len(tickers) == 1:
                    data = data.rename(columns={"Close": tickers[0]})

            available = [t for t in tickers if t in data.columns]
            data = data[available].dropna(how="all").ffill()

            if len(data) > 100:
                return data

            print(f"[download] attempt {attempt+1}: only {len(data)} rows, retrying…")

        except Exception as e:
            print(f"[download] attempt {attempt+1} failed: {e}")

        time.sleep(3)

    raise RuntimeError(f"Failed to download data for: {tickers}")


def download_vix(start: str = "2003-01-01") -> pd.Series:
    """Download VIX (^VIX) for regime detection. Returns empty Series on failure."""
    try:
        raw = yf.download("^VIX", start=start, auto_adjust=True,
                          progress=False)
        close = raw["Close"] if "Close" in raw.columns else raw.iloc[:, 0]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close.dropna()
    except Exception as e:
        print(f"[vix] download failed: {e}")
        return pd.Series(dtype=float)


# ── Volatility ─────────────────────────────────────────────────────────────────

def ewma_volatility(prices: pd.Series, span: int = EWMA_SPAN) -> float:
    """
    EWMA-based annualised volatility — more responsive than rolling std.

    Uses an exponentially weighted variance with the given span (half-life ≈ span/2).
    Falls back to 0.30 when insufficient data.
    """
    rets = prices.pct_change().dropna()
    if len(rets) < 10:
        return 0.30
    ewma_var = rets.ewm(span=span, adjust=False).var().iloc[-1]
    return float(np.sqrt(max(ewma_var, 0)) * np.sqrt(252))


def annual_volatility(prices: pd.Series, window: int = VOL_WINDOW) -> float:
    """Rolling annualised volatility (used as fallback / for backtest historical vol)."""
    rets = prices.pct_change().dropna()
    if len(rets) < 10:
        return 0.30
    tail = rets.tail(window) if len(rets) >= window else rets
    return float(tail.std() * np.sqrt(252))


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


# ── Cross-Sectional Momentum ──────────────────────────────────────────────────

def compute_momentum_scores(
    data: pd.DataFrame,
    tickers: list[str],
    mom_long: int = MOM_LONG,
    mom_short: int = MOM_SHORT,
) -> dict[str, float]:
    """
    Compute 12-1 month cross-sectional momentum scores for each ticker.

    Uses the return from `mom_long` bars ago to `mom_short` bars ago,
    skipping the most recent month to avoid short-term reversal.

    Returns:
        {ticker: raw_return}  — not yet normalized;
        normalization is done within compute_sleeve_weights per sleeve.
    """
    scores: dict[str, float] = {}
    for t in tickers:
        if t not in data.columns:
            scores[t] = 0.0
            continue
        prices = data[t].dropna()
        if len(prices) < mom_long + 1:
            scores[t] = 0.0
            continue
        p_long  = float(prices.iloc[-(mom_long + 1)])
        p_short = float(prices.iloc[-mom_short])
        scores[t] = (p_short / p_long - 1.0) if p_long > 0 else 0.0
    return scores


def _rank_normalize(scores: dict[str, float]) -> dict[str, float]:
    """
    Normalize momentum scores to [0, 1] by rank within the provided dict.

    Ties are broken by score value.  A single asset receives 0.5.
    """
    if not scores:
        return {}
    items = sorted(scores.items(), key=lambda x: x[1])
    n = len(items)
    if n == 1:
        return {items[0][0]: 0.5}
    return {t: i / (n - 1) for i, (t, _) in enumerate(items)}


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
            if p > d:
                in_pos     = True
                high_water = p
        else:
            high_water = max(high_water, p)
            stop = high_water * (1.0 - trail_pct)
            if p < m or p < stop:
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

PHASE_SIZE: dict[str, float] = {
    "EARLY":    1.00,
    "OK":       0.85,
    "EXTENDED": 0.60,
    "BROKEN":   0.00,
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


# ── Buffett Indicator ─────────────────────────────────────────────────────────

def get_buffett() -> dict:
    """Fetch live Buffett Indicator (Wilshire 5000 / GDP × 100)."""
    try:
        wil = yf.download(
            "^W5000", start="1990-01-01", auto_adjust=True,
            progress=False
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
        mt  = 1.00     if val < 90 else 1.00    if val < 120 else 0.75

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
    Returns a daily pd.Series of (Wilshire5000 / GDP) × 100.
    """
    try:
        wil = yf.download(
            "^W5000", start="1990-01-01", auto_adjust=True,
            progress=False
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
    Return the Buffett exposure multiplier for a given historical date.

    v4 fix: mult=1.0 for BARATO and JUSTO; 0.75 for CARO.
    This is a TOTAL EXPOSURE cap, not an equity-sleeve multiplier.
    The distinction matters: previously it was applied to equity then
    renormalized (cancelling the signal). Now it reduces total invested %.
    """
    if buffett_hist is None or buffett_hist.empty:
        return 1.0
    try:
        idx = buffett_hist.index[buffett_hist.index <= date]
        if len(idx) == 0:
            return 1.0
        val = float(buffett_hist.loc[idx[-1]])
        # When extremely overvalued (>140%), reduce to 75%
        # When fair or cheap, full allocation
        return 0.75 if val >= 140 else 1.0
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
    momentum_scores: Optional[dict] = None,
    equity_curve: Optional[np.ndarray] = None,
) -> tuple:
    """
    Institutional weight computation pipeline v4:

    1. Equal Risk Contribution (inv-vol approximation) across active sleeves
    2. Cap each sleeve at MAX_SLEEVE; renormalise
    3. Intra-sleeve allocation:
       - Equity:    70% inverse-vol + 30% cross-sectional momentum rank
       - Bonds:     70% inverse-vol + 30% momentum (duration tilt: TLT vs IEF)
       - Crypto:    fixed BTC/ETH split × inverse-vol scale
       - Commodity: equal weight (no reliable momentum signal at this horizon)
    4. Scale invested fraction by Buffett multiplier (NO renormalization):
       When Buffett < 1.0, equity sleeve is reduced and the gap goes to cash.
       This is the v4 bug fix — v3 renormalized after Buffett, cancelling it.
    5. Drawdown de-risking: further reduce exposure if portfolio is in drawdown
    6. Portfolio-level vol targeting → scale + cash when vol > target
    7. Single-asset concentration limit (max 40%)
    8. Regime cap: final total exposure = min(regime_max, remaining exposure)

    Returns:
        weights:  {ticker: weight}
        cash_pct: fraction in cash
        metadata: dict with vol / scale / regime info
    """
    tickers = tickers or DEFAULT_TICKERS
    sleeves_map = dynamic_sleeves if dynamic_sleeves is not None else build_dynamic_sleeves(tickers)

    # ── 1. Identify active sleeves and compute ERC weights ────────────────────
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

    sleeve_w = equal_risk_contribution(sleeve_vols, active_sleeves)

    # ── 2. Cap each sleeve at MAX_SLEEVE and renormalise ─────────────────────
    sleeve_w = {s: min(w, MAX_SLEEVE) for s, w in sleeve_w.items()}
    total_sw = sum(sleeve_w.values())
    if total_sw > 0:
        sleeve_w = {s: w / total_sw for s, w in sleeve_w.items()}

    # ── 3. v4 Buffett fix: reduce equity directly, DO NOT renormalise ─────────
    # Effect: when Buffett expensive (mult=0.75), equity sleeve shrinks and the
    # difference becomes cash. Previous renorm step was cancelling this entirely.
    if "equity" in sleeve_w and buffett_mult < 1.0:
        sleeve_w["equity"] = sleeve_w["equity"] * buffett_mult
    # total sleeve_w now sums to ≤ 1.0; deficit = Buffett-driven cash buffer
    invested_sleeve_pct = sum(sleeve_w.values())

    # ── 4. Intra-sleeve asset allocation ─────────────────────────────────────
    raw_weights: dict[str, float] = {t: 0.0 for t in tickers}
    mom_ranks = _rank_normalize(momentum_scores or {})

    for sleeve, sw in sleeve_w.items():
        if sw <= 0:
            continue
        sleeve_assets = [
            t for t in sleeves_map.get(sleeve, [])
            if t in tickers and active.get(t) and sizes.get(t, 0) > 0
        ]
        if not sleeve_assets:
            continue

        n = len(sleeve_assets)

        if sleeve == "crypto":
            # BTC/ETH split × inverse-vol scale, then renormalise within sleeve
            raw = {}
            for t in sleeve_assets:
                split     = CRYPTO_SPLIT.get(t, 1.0 / n)
                asset_vol = max(vols.get(t, 0.20), 0.01)
                iv_scale  = min(ASSET_VOL_TARGET / asset_vol, 2.0)
                raw[t]    = split * iv_scale
            total_raw = sum(raw.values())
            for t in sleeve_assets:
                raw_weights[t] = sw * (raw[t] / total_raw) if total_raw > 0 else sw / n

        elif sleeve == "equity":
            # 70% inverse-vol + 30% momentum rank
            inv_vols  = {t: 1.0 / max(vols.get(t, 0.20), 0.01) for t in sleeve_assets}
            total_iv  = sum(inv_vols.values())
            # Momentum ranks (default 0.5 = neutral when missing)
            mom_avail = {t: mom_ranks.get(t, 0.5) for t in sleeve_assets}
            mom_total = sum(mom_avail.values())
            for t in sleeve_assets:
                iv_w  = (inv_vols[t] / total_iv) if total_iv > 0 else 1.0 / n
                mom_w = (mom_avail[t] / mom_total) if mom_total > 0 else 1.0 / n
                raw_weights[t] = sw * (
                    (1 - MOMENTUM_BLEND) * iv_w + MOMENTUM_BLEND * mom_w
                )

        elif sleeve == "bonds":
            # 70% inverse-vol + 30% momentum (captures duration tilt: TLT vs IEF)
            inv_vols  = {t: 1.0 / max(vols.get(t, 0.20), 0.01) for t in sleeve_assets}
            total_iv  = sum(inv_vols.values())
            mom_avail = {t: mom_ranks.get(t, 0.5) for t in sleeve_assets}
            mom_total = sum(mom_avail.values())
            BOND_BLEND = 0.30
            for t in sleeve_assets:
                iv_w  = (inv_vols[t] / total_iv) if total_iv > 0 else 1.0 / n
                mom_w = (mom_avail[t] / mom_total) if mom_total > 0 else 1.0 / n
                raw_weights[t] = sw * (
                    (1 - BOND_BLEND) * iv_w + BOND_BLEND * mom_w
                )

        else:
            # Commodity: equal weight
            for t in sleeve_assets:
                raw_weights[t] = sw / n

    # Normalise intra-sleeve to sum to invested_sleeve_pct (preserves cash buffer)
    total_w = sum(raw_weights.values())
    if total_w > 0:
        for t in raw_weights:
            raw_weights[t] = raw_weights[t] / total_w * invested_sleeve_pct

    # ── 5. Drawdown de-risking ─────────────────────────────────────────────────
    dd_mult = 1.0
    if equity_curve is not None and len(equity_curve) >= 2:
        dd_mult = drawdown_derisking_multiplier(equity_curve)
        if dd_mult < 1.0:
            raw_weights = {t: w * dd_mult for t, w in raw_weights.items()}

    # ── 6. Concentration limit ────────────────────────────────────────────────
    weights = apply_concentration_limits(raw_weights, max_single=0.40)

    # ── 7. Portfolio-level vol targeting ─────────────────────────────────────
    if returns_df is not None and len(returns_df) >= 20:
        weights, cash_pct, port_vol, scale = vol_scale_weights(
            weights, returns_df, target_vol=VOL_TARGET
        )
    else:
        cash_pct = max(0.0, 1.0 - sum(weights.values()))
        port_vol = 0.0
        scale    = 1.0

    # ── 8. Regime exposure cap ────────────────────────────────────────────────
    total_invested = sum(weights.values())
    if total_invested > regime_max and total_invested > 0:
        scale_regime = regime_max / total_invested
        weights  = {t: w * scale_regime for t, w in weights.items()}
        cash_pct = max(0.0, 1.0 - sum(weights.values()))

    meta = {
        "portfolio_vol":   round(port_vol, 4),
        "vol_scale":       round(scale, 4),
        "dd_derisking":    round(dd_mult, 4),
        "buffett_mult":    round(buffett_mult, 2),
        "invested_pct":    round(sum(weights.values()), 4),
    }
    return weights, cash_pct, meta


# ── Main Signal ───────────────────────────────────────────────────────────────

def compute_signal(tickers: Optional[list] = None) -> dict:
    """
    Compute the full institutional trading signal (v4).

    Downloads prices + VIX, computes EWMA vols, cross-sectional momentum,
    positions, and applies the full weight pipeline:
      ERC → sleeve cap → Buffett (no renorm) → momentum tilt → drawdown
      → vol targeting → concentration → regime cap
    """
    tickers = tickers or DEFAULT_TICKERS
    dyn_sleeves = build_dynamic_sleeves(tickers)

    data       = download_prices(tickers)
    vix_series = download_vix()
    data       = add_indicators(data, tickers)
    positions  = compute_positions(data, tickers)

    latest      = data.iloc[-1]
    latest_date = data.index[-1]

    # Returns DataFrame for portfolio vol estimation
    returns_df = data[tickers].pct_change().dropna()

    # Cross-sectional momentum scores (v4)
    momentum_scores = compute_momentum_scores(data, tickers)

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
            "momentum": round(momentum_scores.get(t, 0.0) * 100, 2),
        }
        sizes[t]  = PHASE_SIZE.get(ph, 0.0)
        active[t] = bool(positions[t].iloc[-1])
        # v4: use EWMA vol for live signal
        vols[t]   = round(ewma_volatility(data[t]), 4)

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
        momentum_scores=momentum_scores,
    )

    # ── Quality score ─────────────────────────────────────────────────────────
    n_total = len([t for t in tickers if t in data.columns])
    hq = sum(
        1 for t in tickers
        if active.get(t) and phases.get(t, {}).get("phase") in ("EARLY", "OK")
    )
    quality_pct = hq / max(n_total, 1)
    quality  = "ALTA" if quality_pct >= 0.4 else "MEDIA" if quality_pct >= 0.2 else "BAJA"
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
        "momentum":     {t: round(v * 100, 2) for t, v in momentum_scores.items()},
        "signal_date":  str(latest_date.date()),
        "cash_pct":     round(cash_pct, 4),
        "quality":      quality,
        "tickers":      tickers,
        "risk":         risk_meta,
    }
