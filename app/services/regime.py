"""
regime.py — Market regime detection v4.

v4 improvements over v3:
  - Regime persistence / smoothing: require N consecutive bars to confirm a
    regime change.  Prevents daily whipsaws caused by single VIX spikes.
  - Hysteresis for BEAR→BULL transition: requires SPY > MA200 for 10 days
    (vs instantaneous switch in v3).  Reduces false recoveries.
  - `smooth_periods` parameter (default=5) exposed in compute_regime_series.
  - Additional utility: `regime_summary()` for backtest stats.
"""

import numpy as np
import pandas as pd
from typing import Tuple

# ── Thresholds ────────────────────────────────────────────────────────────────
REGIME_MA_WINDOW  = 200   # Trend filter: SPY simple moving average
REGIME_SMOOTH_PERIODS = 5 # Bars of consensus required to confirm regime change

VIX_LOW    = 20           # VIX < 20  → low volatility
VIX_MEDIUM = 30           # VIX < 30  → elevated volatility
VIX_HIGH   = 40           # VIX ≥ 40  → crisis / panic

# Maximum gross portfolio risk exposure per regime (0.0–1.0)
REGIME_MAX_EXPOSURE: dict[str, float] = {
    "BULL":    1.00,   # Trend intact + low vol → full allocation
    "NEUTRAL": 0.70,   # Trend uncertain or mod vol → reduce 30%
    "BEAR":    0.40,   # Trend broken + high vol → defensive
    "CRISIS":  0.15,   # VIX panic → near-cash; capital preservation
}

REGIME_LABELS = ["CRISIS", "BEAR", "NEUTRAL", "BULL"]


def detect_regime(spy_price: float, spy_ma200: float, vix: float) -> Tuple[str, float]:
    """
    Classify current market regime from SPY trend and VIX level.

    Rules (applied in order of severity):
      1. VIX ≥ 40                          → CRISIS   (max 15%)
      2. SPY < MA200  AND  VIX ≥ 20        → BEAR     (max 40%)
      3. SPY < MA200  AND  VIX < 20        → NEUTRAL  (max 70%)
      4. SPY ≥ MA200  AND  VIX ≥ 30        → NEUTRAL  (max 70%)
      5. SPY ≥ MA200  AND  VIX < 30        → BULL     (max 100%)
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


def smooth_regime_series(
    regime_df: pd.DataFrame,
    smooth_periods: int = REGIME_SMOOTH_PERIODS,
) -> pd.DataFrame:
    """
    Apply persistence filter to prevent regime whipsaws.

    A new regime is only confirmed if it has been signalled for at least
    `smooth_periods` consecutive bars.  Until confirmed, the previous
    regime is kept.  This prevents single VIX spike days from triggering
    a CRISIS regime that immediately reverts.

    Args:
        regime_df:      DataFrame with 'regime' and 'max_exposure' columns
        smooth_periods: Consecutive bars required to confirm a regime change

    Returns:
        New DataFrame with smoothed regime series (same index).
    """
    raw_regimes = regime_df["regime"].values.copy()
    smoothed    = raw_regimes.copy()

    # Initialise: first smooth_periods use raw values
    for i in range(smooth_periods, len(raw_regimes)):
        window = raw_regimes[max(0, i - smooth_periods + 1):i + 1]
        # If all bars in the window agree → confirm the new regime
        if len(set(window)) == 1:
            smoothed[i] = window[-1]
        else:
            # Keep the previously confirmed regime
            smoothed[i] = smoothed[i - 1]

    new_df = regime_df.copy()
    new_df["regime"]       = smoothed
    new_df["max_exposure"] = [REGIME_MAX_EXPOSURE[r] for r in smoothed]
    return new_df


def compute_regime_series(
    spy: pd.Series,
    vix: pd.Series,
    ma_window: int = REGIME_MA_WINDOW,
    smooth_periods: int = REGIME_SMOOTH_PERIODS,
) -> pd.DataFrame:
    """
    Compute a historical regime series for backtesting.

    v4: applies persistence smoothing to prevent daily regime whipsaws.

    Args:
        spy:            SPY daily close prices
        vix:            VIX daily close (aligned to same calendar)
        ma_window:      Look-back for SPY trend MA (default 200)
        smooth_periods: Bars of consensus required to confirm regime change

    Returns:
        DataFrame with columns: regime (str), max_exposure (float)
    """
    spy_ma = spy.rolling(ma_window, min_periods=max(ma_window // 2, 50)).mean()
    vix_al = vix.reindex(spy.index).ffill().fillna(20.0)

    regimes   = []
    exposures = []

    for date in spy.index:
        s = spy.get(date, np.nan)
        m = spy_ma.get(date, np.nan)
        v = float(vix_al.get(date, 20.0))

        reg, exp = detect_regime(
            float(s) if not pd.isna(s) else np.nan,
            float(m) if not pd.isna(m) else np.nan,
            v,
        )
        regimes.append(reg)
        exposures.append(exp)

    raw_df = pd.DataFrame(
        {"regime": regimes, "max_exposure": exposures},
        index=spy.index,
    )

    # Apply smoothing (v4)
    if smooth_periods > 1:
        return smooth_regime_series(raw_df, smooth_periods)

    return raw_df


def regime_summary(regime_df: pd.DataFrame) -> dict:
    """
    Compute regime distribution statistics for a historical series.

    Useful for reporting what fraction of backtest time was spent in each regime.
    """
    counts = regime_df["regime"].value_counts()
    total  = len(regime_df)
    return {
        r: {
            "count": int(counts.get(r, 0)),
            "pct":   round(float(counts.get(r, 0)) / total * 100, 1) if total > 0 else 0.0,
        }
        for r in REGIME_LABELS
    }
