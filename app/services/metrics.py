"""
metrics.py — Institutional metrics engine.

Computes the full suite of performance, risk, and alpha metrics
required by institutional asset managers and hedge funds.
"""

import numpy as np
import pandas as pd
from scipy import stats


def compute_all_metrics(
    returns: np.ndarray,
    benchmark_returns: np.ndarray,
    periods_per_year: int = 52,
    rf_annual: float = 0.04,
    initial_capital: float = 10_000,
) -> dict:
    """
    Compute the full institutional metrics suite from a return series.

    Args:
        returns:           Strategy period returns (e.g. weekly floats)
        benchmark_returns: Benchmark returns at same frequency
        periods_per_year:  52 (weekly) or 12 (monthly)
        rf_annual:         Annual risk-free rate
        initial_capital:   Starting capital for final_capital calc

    Returns:
        Nested dict with performance / risk_adjusted / drawdown /
        distribution / alpha / trade_stats / benchmark sections.
    """
    rets  = np.array(returns, dtype=float)
    bench = np.array(benchmark_returns, dtype=float)
    n     = len(rets)

    if n < 4:
        return {"error": "Insufficient observations for metrics"}

    rf_period = rf_annual / periods_per_year  # per-period risk-free rate

    # ── Equity Curves ──────────────────────────────────────────────────────────
    equity       = np.cumprod(1 + rets)
    bench_equity = np.cumprod(1 + bench[:n])

    # ── Performance ───────────────────────────────────────────────────────────
    total_ret = float(equity[-1] - 1)
    years     = n / periods_per_year
    cagr      = float((1 + total_ret) ** (1 / max(years, 0.01)) - 1)
    vol       = float(rets.std() * np.sqrt(periods_per_year))
    final_cap = initial_capital * equity[-1]

    # ── Risk-Adjusted ─────────────────────────────────────────────────────────
    excess = rets - rf_period
    sharpe = float(excess.mean() / excess.std() * np.sqrt(periods_per_year)) if excess.std() > 0 else 0.0

    neg_mask    = rets < rf_period
    neg_rets    = rets[neg_mask]
    sortino_vol = float(neg_rets.std() * np.sqrt(periods_per_year)) if len(neg_rets) > 1 else 0.0
    sortino     = float((cagr - rf_annual) / sortino_vol) if sortino_vol > 0 else 0.0

    # ── Drawdown ──────────────────────────────────────────────────────────────
    peak       = np.maximum.accumulate(equity)
    dd_series  = (equity - peak) / peak
    max_dd     = float(dd_series.min())
    calmar     = float(cagr / abs(max_dd)) if max_dd != 0 else 0.0

    # Ulcer Index: RMS of drawdown
    ulcer = float(np.sqrt(np.mean(dd_series ** 2)) * 100)

    # Max drawdown duration (in periods)
    max_dd_duration = 0
    cur_dur = 0
    for v in dd_series:
        cur_dur = cur_dur + 1 if v < 0 else 0
        max_dd_duration = max(max_dd_duration, cur_dur)

    # Average drawdown duration
    durations = []
    cur_dur = 0
    for v in dd_series:
        if v < 0:
            cur_dur += 1
        else:
            if cur_dur > 0:
                durations.append(cur_dur)
            cur_dur = 0
    avg_dd_duration = float(np.mean(durations)) if durations else 0.0

    recovery_factor = float(abs(total_ret / max_dd)) if max_dd != 0 else 0.0
    current_dd      = float(dd_series[-1])

    # ── Distribution ──────────────────────────────────────────────────────────
    skewness = float(stats.skew(rets))
    kurtosis = float(stats.kurtosis(rets))   # excess kurtosis (normal = 0)

    # Parametric VaR & CVaR at 95% and 99% confidence
    var_95  = float(np.percentile(rets, 5))
    cvar_95 = float(rets[rets <= var_95].mean()) if np.any(rets <= var_95) else var_95
    var_99  = float(np.percentile(rets, 1))
    cvar_99 = float(rets[rets <= var_99].mean()) if np.any(rets <= var_99) else var_99

    # ── Alpha & Beta (OLS) ────────────────────────────────────────────────────
    min_len = min(len(rets), len(bench))
    r = rets[:min_len]
    b = bench[:min_len]

    if min_len > 4 and np.std(b) > 0:
        cov_m   = np.cov(r, b)
        beta    = float(cov_m[0, 1] / cov_m[1, 1])
        alpha_p = float(r.mean() - beta * b.mean())
        alpha_a = alpha_p * periods_per_year  # annualized Jensen's alpha
    else:
        beta, alpha_a = 0.0, 0.0

    # Tracking Error & Information Ratio
    active_rets    = r - b
    tracking_error = float(active_rets.std() * np.sqrt(periods_per_year))
    info_ratio     = float(active_rets.mean() * periods_per_year / tracking_error) if tracking_error > 0 else 0.0

    # ── Trade Statistics ──────────────────────────────────────────────────────
    wins   = rets[rets > 0]
    losses = rets[rets < 0]
    ties   = rets[rets == 0]

    win_rate    = float(len(wins) / n)
    avg_win     = float(wins.mean()) if len(wins) > 0 else 0.0
    avg_loss    = float(losses.mean()) if len(losses) > 0 else 0.0
    win_loss_r  = float(abs(avg_win / avg_loss)) if avg_loss != 0 else 0.0
    profit_fac  = float(abs(wins.sum() / losses.sum())) if losses.sum() != 0 else 99.99
    expectancy  = float(win_rate * avg_win + (1 - win_rate) * avg_loss) * periods_per_year

    # ── Benchmark Metrics ─────────────────────────────────────────────────────
    bench_total = float(bench_equity[-1] - 1)
    bench_cagr  = float((1 + bench_total) ** (1 / max(years, 0.01)) - 1)
    bench_vol   = float(bench.std() * np.sqrt(periods_per_year))
    bench_peak  = np.maximum.accumulate(bench_equity)
    bench_dd    = float(((bench_equity - bench_peak) / bench_peak).min())
    bench_sh    = float((bench_cagr - rf_annual) / bench_vol) if bench_vol > 0 else 0.0

    return {
        "performance": {
            "cagr":          round(cagr * 100, 2),
            "total_return":  round(total_ret * 100, 2),
            "volatility":    round(vol * 100, 2),
            "final_capital": round(final_cap, 2),
            "years":         round(years, 1),
            "cagr_bench":    round(bench_cagr * 100, 2),
        },
        "risk_adjusted": {
            "sharpe":     round(sharpe, 3),
            "sortino":    round(sortino, 3),
            "calmar":     round(calmar, 3),
            "ulcer_index": round(ulcer, 3),
        },
        "drawdown": {
            "max_drawdown":       round(max_dd * 100, 2),
            "current_drawdown":   round(current_dd * 100, 2),
            "max_dd_duration":    int(max_dd_duration),
            "avg_dd_duration":    round(avg_dd_duration, 1),
            "recovery_factor":    round(recovery_factor, 2),
        },
        "distribution": {
            "skewness":  round(skewness, 3),
            "kurtosis":  round(kurtosis, 3),
            "var_95":    round(var_95 * 100, 3),
            "cvar_95":   round(cvar_95 * 100, 3),
            "var_99":    round(var_99 * 100, 3),
            "cvar_99":   round(cvar_99 * 100, 3),
        },
        "alpha": {
            "alpha":             round(alpha_a * 100, 2),
            "beta":              round(beta, 3),
            "information_ratio": round(info_ratio, 3),
            "tracking_error":    round(tracking_error * 100, 2),
        },
        "trade_stats": {
            "win_rate":      round(win_rate * 100, 1),
            "profit_factor": round(min(profit_fac, 99.99), 2),
            "expectancy":    round(expectancy * 100, 2),
            "avg_win":       round(avg_win * 100, 3),
            "avg_loss":      round(avg_loss * 100, 3),
            "win_loss_ratio": round(win_loss_r, 2),
            "n_periods":     int(n),
        },
        "benchmark": {
            "cagr":         round(bench_cagr * 100, 2),
            "volatility":   round(bench_vol * 100, 2),
            "max_drawdown": round(bench_dd * 100, 2),
            "sharpe":       round(bench_sh, 3),
        },
        # Flat aliases for backward compatibility with existing API responses
        "cagr":          round(cagr * 100, 2),
        "cagr_bench":    round(bench_cagr * 100, 2),
        "sharpe":        round(sharpe, 3),
        "sortino":       round(sortino, 3),
        "calmar":        round(calmar, 3),
        "max_drawdown":  round(max_dd * 100, 2),
        "volatility":    round(vol * 100, 2),
        "win_rate":      round(win_rate * 100, 1),
        "total_return":  round(total_ret * 100, 2),
        "final_capital": round(final_cap, 2),
        "years":         round(years, 1),
    }
