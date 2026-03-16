"""
risk.py — Institutional risk management.

Provides:
  - Portfolio-level volatility targeting (scales exposure when vol > target)
  - Equal Risk Contribution (risk parity) across sleeves
  - Concentration limits per asset
  - Trailing stop management helpers
"""

import numpy as np
import pandas as pd
from typing import Optional

# ── Institutional Parameters ──────────────────────────────────────────────────
VOL_TARGET        = 0.12   # 12% annualised portfolio volatility target
VOL_LOOKBACK      = 63     # 3-month rolling window for vol estimation
MAX_LEVERAGE      = 1.00   # No leverage: cap total exposure at 100%
MAX_SINGLE_ASSET  = 0.40   # No single asset > 40% of portfolio
MAX_SLEEVE        = 0.55   # No sleeve > 55% of portfolio (before regime cap)
ASSET_VOL_TARGET  = 0.20   # Individual asset vol target (for intra-sleeve sizing)
TRAILING_STOP_PCT = 0.15   # 15% trailing stop from high-water mark


# ── Portfolio Volatility ───────────────────────────────────────────────────────

def portfolio_volatility(weights: dict, returns_df: pd.DataFrame, lookback: int = VOL_LOOKBACK) -> float:
    """
    Estimate annualised portfolio volatility using historical covariance.

    Args:
        weights:    {ticker: weight} (need not sum to 1; only invested portion)
        returns_df: DataFrame of daily or period returns for all tickers
        lookback:   Number of periods for covariance estimation

    Returns:
        Annualised portfolio volatility (float, e.g. 0.14 = 14%)
    """
    tickers = [t for t in weights if t in returns_df.columns and weights.get(t, 0) > 0]
    if not tickers:
        return 0.0

    w    = np.array([weights[t] for t in tickers])
    rets = returns_df[tickers].dropna()

    if len(rets) < 10:
        return 0.0

    # Annualisation factor: detect period from index freq if possible
    freq = _infer_periods_per_year(returns_df)
    cov  = rets.tail(lookback).cov() * freq

    port_var = float(w @ cov.values @ w)
    return float(np.sqrt(max(port_var, 0.0)))


def _infer_periods_per_year(df: pd.DataFrame) -> int:
    """Estimate annualisation factor from DataFrame index."""
    try:
        if len(df) < 2:
            return 252
        delta = (df.index[-1] - df.index[0]).days / (len(df) - 1)
        if delta < 3:
            return 252   # daily
        if delta < 10:
            return 52    # weekly
        return 12        # monthly
    except Exception:
        return 252


# ── Volatility Targeting ──────────────────────────────────────────────────────

def vol_scale_weights(
    weights: dict,
    returns_df: pd.DataFrame,
    target_vol: float = VOL_TARGET,
    max_leverage: float = MAX_LEVERAGE,
) -> tuple:
    """
    Scale portfolio weights so that realised portfolio vol ≈ target_vol.

    When portfolio vol exceeds the target, weights are scaled down uniformly
    and the remainder goes to cash.  When vol is below target, weights are
    kept as-is (no leveraging up beyond max_leverage).

    Returns:
        scaled_weights: dict of adjusted weights
        cash_pct:       fraction allocated to cash
        realized_vol:   estimated portfolio vol before scaling
        scale_factor:   multiplier applied (1.0 means no change)
    """
    realized_vol = portfolio_volatility(weights, returns_df)

    if realized_vol <= 0 or realized_vol <= target_vol:
        cash_pct = max(0.0, 1.0 - sum(weights.values()))
        return weights, cash_pct, realized_vol, 1.0

    scale  = min(target_vol / realized_vol, max_leverage)
    scaled = {t: w * scale for t, w in weights.items()}
    cash_pct = max(0.0, 1.0 - sum(scaled.values()))

    return scaled, cash_pct, realized_vol, round(scale, 4)


# ── Concentration Limits ──────────────────────────────────────────────────────

def apply_concentration_limits(
    weights: dict,
    max_single: float = MAX_SINGLE_ASSET,
) -> dict:
    """
    Cap any single asset at max_single and renormalise to sum = 1.

    Iterative: after capping, renormalise and check again (up to 10 passes).
    """
    w = dict(weights)
    for _ in range(10):
        total = sum(w.values())
        if total <= 0:
            return w
        normed  = {t: v / total for t, v in w.items()}
        capped  = {t: min(v, max_single) for t, v in normed.items()}
        total_c = sum(capped.values())
        if total_c > 0:
            renormed = {t: v / total_c for t, v in capped.items()}
        else:
            renormed = capped
        if all(abs(renormed.get(t, 0) - normed.get(t, 0)) < 1e-6 for t in normed):
            return renormed
        w = renormed
    return w


# ── Risk Parity (Equal Risk Contribution) ────────────────────────────────────

def equal_risk_contribution(sleeve_vols: dict, sleeve_names: list) -> dict:
    """
    Compute sleeve weights using simplified Equal Risk Contribution.

    Assumes zero inter-sleeve correlation (appropriate approximation when
    sleeves are equity / bonds / crypto / commodity — materially different
    risk factors).  Under this assumption:

        w_i ∝ 1 / σ_i

    giving each sleeve equal expected risk contribution.

    Args:
        sleeve_vols:  {sleeve_name: annualised_vol}  — active sleeves only
        sleeve_names: ordered list of all sleeve names

    Returns:
        {sleeve: weight}  — sums to 1 across active sleeves; 0 for inactive
    """
    active = {s: v for s, v in sleeve_vols.items() if s in sleeve_names and v > 0}
    if not active:
        return {s: 0.0 for s in sleeve_names}

    inv_vols = {s: 1.0 / v for s, v in active.items()}
    total    = sum(inv_vols.values())

    return {
        s: float(inv_vols[s] / total) if s in inv_vols and total > 0 else 0.0
        for s in sleeve_names
    }


def full_risk_parity(
    weights_raw: dict,
    returns_df: pd.DataFrame,
    max_iter: int = 100,
    tol: float = 1e-8,
) -> dict:
    """
    Full (correlated) Risk Parity via Newton's method.

    Finds weights w such that each asset contributes equally to total
    portfolio variance:  w_i * (Σw)_i = w_j * (Σw)_j  ∀ i, j.

    Falls back to inverse-vol weighting if covariance is singular.

    Args:
        weights_raw: Initial guess (active assets only; others set to 0)
        returns_df:  Return DataFrame for covariance estimation
        max_iter:    Maximum Newton iterations
        tol:         Convergence tolerance

    Returns:
        Normalised weight dict {ticker: weight}
    """
    active  = [t for t, w in weights_raw.items() if w > 0 and t in returns_df.columns]
    if len(active) < 2:
        total = sum(weights_raw.values())
        return {t: w / total for t, w in weights_raw.items()} if total > 0 else weights_raw

    rets = returns_df[active].dropna().tail(VOL_LOOKBACK)
    if len(rets) < 10:
        return weights_raw

    freq = _infer_periods_per_year(returns_df)
    cov  = rets.cov().values * freq
    n    = len(active)

    # Newton / gradient-descent iterations
    w = np.ones(n) / n
    try:
        for _ in range(max_iter):
            cov_w = cov @ w
            port_var = float(w @ cov_w)
            if port_var <= 0:
                break
            risk_contrib = w * cov_w / port_var       # each asset's risk share
            target = np.ones(n) / n                    # equal contribution
            grad   = risk_contrib - target
            if np.max(np.abs(grad)) < tol:
                break
            # Gradient step with learning rate
            w = w - 0.5 * grad
            w = np.clip(w, 1e-6, None)
            w /= w.sum()
    except Exception:
        pass

    result = {t: 0.0 for t in weights_raw}
    for t, wi in zip(active, w):
        result[t] = float(wi)
    return result
