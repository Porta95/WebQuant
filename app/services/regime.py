"""
regime.py — Market regime detection.

Classifies the macro environment as BULL / NEUTRAL / BEAR / CRISIS
using SPY trend (MA200) and VIX level.  Each regime maps to a maximum
allowed portfolio risk exposure, acting as a top-level circuit-breaker.
"""

import numpy as np
import pandas as pd
from typing import Tuple

# ── Thresholds ────────────────────────────────────────────────────────────────
REGIME_MA_WINDOW = 200   # Trend filter: SPY simple moving average

VIX_LOW    = 20          # VIX < 20  → low volatility (complacency)
VIX_MEDIUM = 30          # VIX < 30  → elevated volatility
VIX_HIGH   = 40          # VIX ≥ 40  → crisis / panic

# Maximum gross portfolio risk exposure per regime (0.0–1.0)
REGIME_MAX_EXPOSURE: dict[str, float] = {
    "BULL":    1.00,   # Trend intact + low vol → full allocation
    "NEUTRAL": 0.70,   # Trend uncertain or mod vol → reduce 30%
    "BEAR":    0.40,   # Trend broken + high vol → defensive
    "CRISIS":  0.15,   # VIX panic → near-cash; capital preservation
}

# Regime labels in priority order for display
REGIME_LABELS = ["CRISIS", "BEAR", "NEUTRAL", "BULL"]


def detect_regime(spy_price: float, spy_ma200: float, vix: float) -> Tuple[str, float]:
    """
    Classify current market regime.

    Rules (applied in order of severity):
      1. VIX ≥ 40                          → CRISIS   (max 15%)
      2. SPY < MA200  AND  VIX ≥ 20        → BEAR     (max 40%)
      3. SPY < MA200  AND  VIX < 20        → NEUTRAL  (max 70%)
      4. SPY ≥ MA200  AND  VIX ≥ 30        → NEUTRAL  (max 70%)
      5. SPY ≥ MA200  AND  VIX < 30        → BULL     (max 100%)

    Args:
        spy_price:  Current SPY close price
        spy_ma200:  SPY 200-day simple moving average
        vix:        VIX index close (use 20.0 if unavailable)

    Returns:
        regime:      Regime label string
        max_exposure: Corresponding maximum portfolio exposure (0–1)
    """
    if pd.isna(vix) or vix <= 0:
        vix = 20.0

    if vix >= VIX_HIGH:
        regime = "CRISIS"
    elif pd.isna(spy_price) or pd.isna(spy_ma200):
        regime = "NEUTRAL"
    elif spy_price < spy_ma200:
        regime = "BEAR" if vix >= VIX_LOW else "NEUTRAL"
    else:
        regime = "NEUTRAL" if vix >= VIX_MEDIUM else "BULL"

    return regime, REGIME_MAX_EXPOSURE[regime]


def compute_regime_series(spy: pd.Series, vix: pd.Series, ma_window: int = REGIME_MA_WINDOW) -> pd.DataFrame:
    """
    Compute a daily historical regime series for backtesting.

    Args:
        spy:       SPY daily close prices
        vix:       VIX daily close prices (aligned to same calendar)
        ma_window: Look-back for SPY trend MA (default 200)

    Returns:
        DataFrame indexed like `spy` with columns:
            regime       (str)
            max_exposure (float)
    """
    spy_ma  = spy.rolling(ma_window, min_periods=max(ma_window // 2, 50)).mean()
    vix_al  = vix.reindex(spy.index).ffill().fillna(20.0)

    regimes  = []
    exposures = []

    for date in spy.index:
        s = spy.get(date, np.nan)
        m = spy_ma.get(date, np.nan)
        v = float(vix_al.get(date, 20.0))

        reg, exp = detect_regime(float(s) if not pd.isna(s) else np.nan,
                                  float(m) if not pd.isna(m) else np.nan,
                                  v)
        regimes.append(reg)
        exposures.append(exp)

    return pd.DataFrame(
        {"regime": regimes, "max_exposure": exposures},
        index=spy.index,
    )
