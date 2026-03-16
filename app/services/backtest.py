"""
backtest.py — Institutional backtest engine v4.

v4 improvements over v3:
  - Default start "2003-01-01": includes GFC 2008 (critical stress test)
  - Default rebalance_freq "M": monthly reduces turnover drag vs weekly
  - Data downloaded once and shared across walk-forward and sensitivity
    windows (eliminates 5× redundant network calls in sensitivity analysis)
  - Cross-sectional momentum scores computed at each rebalance date
  - EWMA volatility used for asset-level vol estimation (more responsive)
  - 4th benchmark: SPY 10-month MA timing (institutional trend-following index)
  - avg_turnover reported in metrics output
  - Regime summary statistics added to output
  - run_walk_forward() and run_sensitivity_analysis() accept pre-downloaded
    data to avoid re-downloading; callers can pass data/vix from run_backtest()
  - Drawdown de-risking integrated into weight computation
"""

import numpy as np
import pandas as pd
from typing import Optional

from .core import (
    download_prices, download_vix, add_indicators, compute_positions,
    trend_phase, annual_volatility, ewma_volatility, get_buffett_historical,
    buffett_mult_at, compute_sleeve_weights, build_dynamic_sleeves,
    compute_momentum_scores,
    SLEEVES, DEFAULT_TICKERS, SLEEVE_MAP, CRYPTO_SPLIT,
    DONCHIAN_WINDOW, MA_EXIT_WINDOW, VOL_TARGET, PHASE_SIZE,
)
from .regime import compute_regime_series, regime_summary
from .metrics import compute_all_metrics

# ── Friction Costs ────────────────────────────────────────────────────────────
COMMISSION_RATE = 0.001    # 0.10% per transaction (institutional brokerage)
SLIPPAGE_RATE   = 0.0005   # 0.05% market impact / slippage estimate
TOTAL_FRICTION  = COMMISSION_RATE + SLIPPAGE_RATE   # 0.15% per dollar of turnover

# ── Stress Scenarios ─────────────────────────────────────────────────────────
STRESS_SCENARIOS: dict[str, dict] = {
    "dot_com_2000":  {"name": "Dot-Com Crash",          "start": "2000-03-01", "end": "2002-10-31"},
    "gfc_2008":      {"name": "Global Financial Crisis", "start": "2008-01-01", "end": "2009-03-31"},
    "covid_2020":    {"name": "COVID Crash",             "start": "2020-02-19", "end": "2020-04-30"},
    "rates_2022":    {"name": "Rate Hike Cycle 2022",    "start": "2022-01-01", "end": "2022-12-31"},
    "crypto_2018":   {"name": "Crypto Bear 2018",        "start": "2018-01-01", "end": "2018-12-31"},
    "ftx_2022":      {"name": "FTX Collapse",            "start": "2022-11-01", "end": "2022-11-30"},
}


# ── Core Backtest ─────────────────────────────────────────────────────────────

def run_backtest(
    tickers: Optional[list[str]] = None,
    start: str = "2003-01-01",
    initial_capital: float = 10_000,
    rebalance_freq: str = "M",
    include_costs: bool = True,
    don_window: int = DONCHIAN_WINDOW,
    ma_window: int = MA_EXIT_WINDOW,
    vol_target: float = VOL_TARGET,
    pre_data: Optional[pd.DataFrame] = None,
    pre_vix: Optional[pd.Series] = None,
) -> dict:
    """
    Institutional backtest with historical Buffett, friction costs,
    regime filter (smoothed), portfolio vol targeting, cross-sectional
    momentum, drawdown de-risking, and full metrics suite.

    Args:
        tickers:         Asset universe (default: 9-asset institutional universe)
        start:           Backtest start date (YYYY-MM-DD). Default 2003 includes GFC.
        initial_capital: Starting portfolio value
        rebalance_freq:  'M' (monthly, default) or 'W' (weekly)
        include_costs:   Apply commission + slippage
        don_window:      Donchian entry window
        ma_window:       MA exit window
        vol_target:      Portfolio annual vol target
        pre_data:        Pre-downloaded price DataFrame (avoids re-download)
        pre_vix:         Pre-downloaded VIX Series (avoids re-download)

    Returns:
        equity_curve, metrics (full institutional), weekly_returns,
        drawdown_series, dates, regimes, turnover_series, regime_stats
    """
    tickers = tickers or DEFAULT_TICKERS
    dyn_sleeves = build_dynamic_sleeves(tickers)

    # ── Download (or reuse pre-downloaded data) ───────────────────────────────
    data       = pre_data if pre_data is not None else download_prices(tickers, start=start)
    vix_series = pre_vix  if pre_vix  is not None else download_vix(start=start)

    # Filter to requested start date when using pre-downloaded data
    if pre_data is not None and start:
        data = data[data.index >= pd.Timestamp(start)]
    if pre_vix is not None and start:
        vix_series = vix_series[vix_series.index >= pd.Timestamp(start)]

    # Align VIX to price calendar
    vix_al = vix_series.reindex(data.index).ffill().fillna(20.0)

    data      = add_indicators(data, tickers, don_window=don_window, ma_window=ma_window)
    positions = compute_positions(data, tickers, don_window=don_window, ma_window=ma_window)

    # Pre-compute historical Buffett series (single network call)
    buffett_hist = get_buffett_historical()

    # Pre-compute regime series (v4: with persistence smoothing)
    if "SPY" in data.columns:
        regime_df = compute_regime_series(data["SPY"], vix_al)
    else:
        regime_df = pd.DataFrame(
            {"regime": "NEUTRAL", "max_exposure": 0.70},
            index=data.index,
        )

    # ── Benchmarks ────────────────────────────────────────────────────────────
    spy = data["SPY"] if "SPY" in data.columns else data.iloc[:, 0]

    # 60/40 benchmark: 60% SPY + 40% TLT
    has_tlt = "TLT" in data.columns
    tlt     = data["TLT"] if has_tlt else None

    # Equal-weight benchmark
    ew_tickers = [t for t in ["SPY", "QQQ", "IWM", "TLT", "IEF", "GLD"] if t in data.columns]

    # 4th benchmark: SPY 10-month MA timing strategy (simple trend-following index)
    # Long SPY when SPY > 10M MA; else cash.  Standard institutional trend benchmark.
    spy_ma10m = spy.rolling(210, min_periods=100).mean()  # ≈ 10 months of trading days

    # ── Rebalance Dates ────────────────────────────────────────────────────────
    warmup      = max(don_window, 200) + 10
    rebal_dates = data.resample(rebalance_freq).last().index
    rebal_dates = rebal_dates[rebal_dates >= data.index[min(warmup, len(data) - 1)]]

    if len(rebal_dates) < 4:
        return {"error": "Insufficient data for backtest (check start date / warmup)"}

    # ── Simulation Loop ────────────────────────────────────────────────────────
    strat_val    = initial_capital
    bench_val    = initial_capital     # SPY
    bench60_val  = initial_capital     # 60/40
    bench_ew_val = initial_capital     # Equal weight
    bench_ma_val = initial_capital     # SPY 10M MA timing

    strat_curve: list[dict] = []
    strat_rets:  list[float] = []
    bench_rets:  list[float] = []
    turnover_series: list[float] = []
    equity_vals: list[float] = [initial_capital]

    prev_weights: dict[str, float] = {t: 0.0 for t in tickers}

    for i, date in enumerate(rebal_dates):
        if date not in data.index:
            continue
        loc = data.index.get_loc(date)
        row = data.iloc[loc]

        # Historical returns for vol targeting (trailing 126 bars ≈ 6 months)
        hist_start = max(0, loc - 126)
        hist_rets  = data[tickers].iloc[hist_start:loc].pct_change().dropna()

        # Cross-sectional momentum at this rebalance date (v4)
        mom_data = data.iloc[:loc + 1]
        momentum_scores = compute_momentum_scores(mom_data, tickers)

        # Regime and Buffett at this date
        regime_max  = float(regime_df["max_exposure"].iloc[loc])
        bm          = buffett_mult_at(buffett_hist, date)

        # Drawdown de-risking: pass equity curve up to this point
        equity_arr = np.array(equity_vals)

        # Per-asset state at this date
        asset_active: dict[str, bool]  = {}
        asset_sizes:  dict[str, float] = {}
        asset_vols:   dict[str, float] = {}

        for t in tickers:
            if t not in data.columns:
                continue
            ma_col      = f"{t}_MA{ma_window}"
            ph, _, _    = trend_phase(
                float(row[t]),
                float(row[ma_col]) if ma_col in row.index else float(row[t]),
            )
            asset_sizes[t]  = PHASE_SIZE.get(ph, 0.0)
            asset_active[t] = bool(positions[t].iloc[loc])
            # v4: EWMA vol for more responsive estimates
            asset_vols[t]   = ewma_volatility(data[t].iloc[max(0, loc - 90):loc])

        # Compute institutional weights (v4: with momentum + dd de-risking)
        weights, _cash_pct, _meta = compute_sleeve_weights(
            active=asset_active,
            sizes=asset_sizes,
            vols=asset_vols,
            buffett_mult=bm,
            regime_max=regime_max,
            returns_df=hist_rets,
            tickers=tickers,
            dynamic_sleeves=dyn_sleeves,
            momentum_scores=momentum_scores,
            equity_curve=equity_arr,
        )

        # ── Friction costs ─────────────────────────────────────────────────────
        friction = 0.0
        if include_costs:
            turnover = sum(
                abs(weights.get(t, 0.0) - prev_weights.get(t, 0.0))
                for t in tickers
            )
            friction = turnover * TOTAL_FRICTION
            turnover_series.append(round(turnover, 4))
        prev_weights = dict(weights)

        # ── Next rebalance ─────────────────────────────────────────────────────
        next_date = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else data.index[-1]
        if next_date not in data.index:
            continue

        # ── Strategy return ────────────────────────────────────────────────────
        period_ret = -friction
        for t, w in weights.items():
            if w <= 0 or t not in data.columns:
                continue
            p0 = float(data.loc[date, t])
            p1 = float(data.loc[next_date, t])
            if p0 > 0:
                period_ret += w * (p1 / p0 - 1.0)

        # ── SPY benchmark ──────────────────────────────────────────────────────
        s0 = float(spy.loc[date])
        s1 = float(spy.loc[next_date])
        bench_ret = (s1 / s0 - 1.0) if s0 > 0 else 0.0

        # ── 60/40 benchmark ────────────────────────────────────────────────────
        if has_tlt and tlt is not None:
            t0_tlt = float(tlt.loc[date])
            t1_tlt = float(tlt.loc[next_date])
            r_tlt  = (t1_tlt / t0_tlt - 1.0) if t0_tlt > 0 else 0.0
            bench60_ret = 0.60 * bench_ret + 0.40 * r_tlt
        else:
            bench60_ret = bench_ret

        # ── Equal-weight benchmark ─────────────────────────────────────────────
        ew_ret = 0.0
        for t in ew_tickers:
            p0 = float(data.loc[date, t])
            p1 = float(data.loc[next_date, t])
            if p0 > 0:
                ew_ret += (1.0 / len(ew_tickers)) * (p1 / p0 - 1.0)

        # ── SPY 10M MA timing benchmark ────────────────────────────────────────
        spy_ma_val = spy_ma10m.get(date, np.nan)
        if not pd.isna(spy_ma_val) and s0 > float(spy_ma_val):
            bench_ma_ret = bench_ret   # long SPY when above MA
        else:
            bench_ma_ret = 0.0         # cash when below MA

        # ── Accumulate ────────────────────────────────────────────────────────
        strat_val    *= (1.0 + period_ret)
        bench_val    *= (1.0 + bench_ret)
        bench60_val  *= (1.0 + bench60_ret)
        bench_ew_val *= (1.0 + ew_ret)
        bench_ma_val *= (1.0 + bench_ma_ret)

        equity_vals.append(strat_val)
        strat_rets.append(period_ret)
        bench_rets.append(bench_ret)

        strat_curve.append({
            "date":           str(date.date()),
            "strategy":       round(strat_val, 2),
            "benchmark":      round(bench_val, 2),
            "bench_60_40":    round(bench60_val, 2),
            "bench_ew":       round(bench_ew_val, 2),
            "bench_spy_ma":   round(bench_ma_val, 2),
            "regime":         str(regime_df["regime"].iloc[loc]),
            "weights":        {t: round(w, 3) for t, w in weights.items() if w > 0.001},
        })

    if not strat_curve:
        return {"error": "Insufficient data for backtest"}

    # ── Institutional Metrics ─────────────────────────────────────────────────
    periods_per_year = 52 if rebalance_freq == "W" else 12
    rets_arr  = np.array(strat_rets)
    bench_arr = np.array(bench_rets)

    metrics = compute_all_metrics(
        rets_arr, bench_arr, periods_per_year,
        initial_capital=initial_capital,
        turnover_series=turnover_series,
    )

    # Drawdown series
    values    = np.array([p["strategy"] for p in strat_curve])
    peak      = np.maximum.accumulate(values)
    dd_series = ((values - peak) / peak * 100).tolist()

    # Regime statistics
    reg_stats = regime_summary(regime_df)

    return {
        "equity_curve":    strat_curve,
        "metrics":         metrics,
        "weekly_returns":  [round(r * 100, 3) for r in rets_arr.tolist()],
        "drawdown_series": [round(d, 2) for d in dd_series],
        "dates":           [p["date"] for p in strat_curve],
        "turnover_series": turnover_series,
        "regime_stats":    reg_stats,
        "config": {
            "don_window":    don_window,
            "ma_window":     ma_window,
            "vol_target":    vol_target,
            "include_costs": include_costs,
            "rebalance":     rebalance_freq,
            "universe":      tickers,
            "start":         start,
        },
    }


# ── Stress Tests ─────────────────────────────────────────────────────────────

def run_stress_test(scenario_key: str, tickers: Optional[list[str]] = None) -> dict:
    """
    Run the strategy through a specific historical stress episode.

    Uses a 2-year warmup before the scenario start to ensure indicators
    and positions are properly initialised.
    """
    sc = STRESS_SCENARIOS.get(scenario_key)
    if not sc:
        return {"error": f"Scenario '{scenario_key}' not found. "
                         f"Available: {list(STRESS_SCENARIOS.keys())}"}

    tickers = tickers or DEFAULT_TICKERS

    warmup_start = pd.Timestamp(sc["start"]) - pd.DateOffset(years=2)
    result = run_backtest(tickers, start=str(warmup_start.date()))

    if "error" in result:
        return result

    curve    = result.get("equity_curve", [])
    filtered = [p for p in curve if sc["start"] <= p["date"] <= sc["end"]]

    if len(filtered) < 2:
        return {"error": f"No data found in scenario window {sc['start']} → {sc['end']}"}

    strat_ret = filtered[-1]["strategy"] / filtered[0]["strategy"] - 1.0
    bench_ret = filtered[-1]["benchmark"] / filtered[0]["benchmark"] - 1.0

    vals      = [p["strategy"] for p in filtered]
    peak_sc   = np.maximum.accumulate(vals)
    dd_sc     = ((np.array(vals) - peak_sc) / peak_sc).tolist()
    max_dd_sc = float(np.min(dd_sc))

    return {
        "scenario":         sc["name"],
        "period":           f"{sc['start']} / {sc['end']}",
        "strategy_return":  round(strat_ret * 100, 2),
        "benchmark_return": round(bench_ret * 100, 2),
        "outperformance":   round((strat_ret - bench_ret) * 100, 2),
        "scenario_max_dd":  round(max_dd_sc * 100, 2),
        "equity_curve":     filtered,
    }


# ── Walk-Forward Validation ────────────────────────────────────────────────────

def run_walk_forward(
    tickers: Optional[list[str]] = None,
    start: str = "2003-01-01",
    train_years: int = 3,
    test_years: int = 1,
    pre_data: Optional[pd.DataFrame] = None,
    pre_vix: Optional[pd.Series] = None,
) -> dict:
    """
    Walk-forward validation: expanding train window, fixed test window.

    v4: accepts pre_data/pre_vix to avoid redundant downloads when called
    after run_backtest().

    Evaluates whether strategy performance holds out-of-sample across
    multiple non-overlapping test periods.
    """
    tickers = tickers or DEFAULT_TICKERS

    # Download data once if not provided
    if pre_data is None:
        pre_data = download_prices(tickers, start=start)
    if pre_vix is None:
        pre_vix = download_vix(start=start)

    data = pre_data[pre_data.index >= pd.Timestamp(start)]
    total_years = (data.index[-1] - data.index[0]).days / 365.25

    if total_years < train_years + test_years:
        return {"error": f"Insufficient history ({total_years:.1f}y) for walk-forward "
                         f"({train_years}y train + {test_years}y test)"}

    start_dt = data.index[0]
    end_dt   = data.index[-1]

    test_start = start_dt + pd.DateOffset(years=train_years)
    windows = []
    while test_start + pd.DateOffset(years=test_years) <= end_dt:
        test_end = test_start + pd.DateOffset(years=test_years)
        windows.append({
            "train_start": start_dt,
            "train_end":   test_start,
            "test_start":  test_start,
            "test_end":    test_end,
        })
        test_start += pd.DateOffset(years=test_years)

    results = []
    for w in windows:
        # Pass pre-downloaded data to avoid redundant downloads
        result = run_backtest(
            tickers=tickers,
            start=str(w["train_start"].date()),
            pre_data=pre_data,
            pre_vix=pre_vix,
        )
        if "error" in result:
            continue

        curve = result.get("equity_curve", [])
        test_curve = [
            p for p in curve
            if str(w["test_start"].date()) <= p["date"] <= str(w["test_end"].date())
        ]
        if len(test_curve) < 4:
            continue

        rets_test  = []
        bench_test = []
        for j in range(1, len(test_curve)):
            prev = test_curve[j - 1]
            curr = test_curve[j]
            rets_test.append(curr["strategy"] / prev["strategy"] - 1.0)
            bench_test.append(curr["benchmark"] / prev["benchmark"] - 1.0)

        if not rets_test:
            continue

        test_m = compute_all_metrics(
            np.array(rets_test), np.array(bench_test), periods_per_year=12
        )
        results.append({
            "period":       f"{w['test_start'].date()} → {w['test_end'].date()}",
            "cagr":         test_m.get("cagr", 0),
            "sharpe":       test_m.get("sharpe", 0),
            "sortino":      test_m.get("sortino", 0),
            "max_drawdown": test_m.get("max_drawdown", 0),
            "calmar":       test_m.get("calmar", 0),
            "sterling":     test_m.get("sterling", 0),
        })

    if not results:
        return {"error": "No valid test windows produced results"}

    cagrs   = [r["cagr"] for r in results]
    sharpes = [r["sharpe"] for r in results]
    dds     = [r["max_drawdown"] for r in results]

    return {
        "windows":   results,
        "n_windows": len(results),
        "summary": {
            "avg_cagr":          round(float(np.mean(cagrs)), 2),
            "std_cagr":          round(float(np.std(cagrs)), 2),
            "median_cagr":       round(float(np.median(cagrs)), 2),
            "avg_sharpe":        round(float(np.mean(sharpes)), 2),
            "std_sharpe":        round(float(np.std(sharpes)), 2),
            "pct_positive_cagr": round(float(np.mean([c > 0 for c in cagrs])) * 100, 1),
            "worst_dd":          round(float(np.min(dds)), 2),
            "avg_dd":            round(float(np.mean(dds)), 2),
        },
    }


# ── Monte Carlo Bootstrap ─────────────────────────────────────────────────────

def run_monte_carlo(
    weekly_returns: list[float],
    n_simulations: int = 2000,
    n_periods: int = 260,    # 5 years of weekly data
    rf_annual: float = 0.04,
) -> dict:
    """
    Block Bootstrap Monte Carlo simulation.

    Resamples historical return blocks (block size 4 weeks) to preserve
    serial correlation structure, then estimates distribution of 5-year
    CAGR, max drawdown, and Sharpe across n_simulations paths.
    """
    rets = np.array(weekly_returns, dtype=float)
    n    = len(rets)

    if n < 52:
        return {"error": "Insufficient return history for Monte Carlo (min 52 weeks)"}

    block_size = 4    # 4-week blocks to preserve short-term autocorrelation
    n_blocks   = n_periods // block_size + 1

    sim_cagrs   = []
    sim_maxdds  = []
    sim_sharpes = []
    sim_sterlings = []

    rng = np.random.default_rng(42)

    for _ in range(n_simulations):
        starts   = rng.integers(0, n - block_size, size=n_blocks)
        sampled  = np.concatenate([rets[s:s + block_size] for s in starts])[:n_periods]

        equity   = np.cumprod(1 + sampled)
        total_r  = float(equity[-1] - 1)
        years    = n_periods / 52.0
        cagr     = float((1 + total_r) ** (1 / years) - 1)
        vol      = float(sampled.std() * np.sqrt(52))
        sharpe   = float((cagr - rf_annual) / vol) if vol > 0 else 0.0

        peak     = np.maximum.accumulate(equity)
        dd_ser   = (equity - peak) / peak
        max_dd   = float(dd_ser.min())

        # Sterling: use avg annual max dd approximation
        ann_size = 52
        ann_dds  = [abs(float(dd_ser[j:j+ann_size].min())) for j in range(0, n_periods-ann_size, ann_size//2)]
        avg_ann_dd = float(np.mean(ann_dds)) if ann_dds else abs(max_dd)
        sterling = float(cagr / avg_ann_dd) if avg_ann_dd > 0 else 0.0

        sim_cagrs.append(cagr * 100)
        sim_maxdds.append(max_dd * 100)
        sim_sharpes.append(sharpe)
        sim_sterlings.append(sterling)

    def pct(arr, q):
        return round(float(np.percentile(arr, q)), 2)

    return {
        "n_simulations":        n_simulations,
        "n_periods_weeks":      n_periods,
        "horizon_years":        round(n_periods / 52.0, 1),
        "prob_positive_cagr":   round(float(np.mean([c > 0 for c in sim_cagrs])) * 100, 1),
        "prob_dd_gt_20":        round(float(np.mean([d < -20 for d in sim_maxdds])) * 100, 1),
        "prob_dd_gt_30":        round(float(np.mean([d < -30 for d in sim_maxdds])) * 100, 1),
        "cagr": {
            "p5":  pct(sim_cagrs, 5),  "p25": pct(sim_cagrs, 25),
            "p50": pct(sim_cagrs, 50), "p75": pct(sim_cagrs, 75),
            "p95": pct(sim_cagrs, 95),
        },
        "max_drawdown": {
            "p5":  pct(sim_maxdds, 5),
            "p50": pct(sim_maxdds, 50),
            "p95": pct(sim_maxdds, 95),
        },
        "sharpe": {
            "p5":  pct(sim_sharpes, 5),
            "p50": pct(sim_sharpes, 50),
            "p95": pct(sim_sharpes, 95),
        },
        "sterling": {
            "p5":  pct(sim_sterlings, 5),
            "p50": pct(sim_sterlings, 50),
            "p95": pct(sim_sterlings, 95),
        },
    }


# ── Parameter Sensitivity ─────────────────────────────────────────────────────

def run_sensitivity_analysis(
    tickers: Optional[list[str]] = None,
    start: str = "2003-01-01",
    pre_data: Optional[pd.DataFrame] = None,
    pre_vix: Optional[pd.Series] = None,
) -> dict:
    """
    Test strategy robustness across a range of Donchian window values.

    v4: accepts pre-downloaded data so all 5 runs share a single download.
    """
    tickers = tickers or DEFAULT_TICKERS

    # Download once and share across all parameter runs
    if pre_data is None:
        pre_data = download_prices(tickers, start=start)
    if pre_vix is None:
        pre_vix = download_vix(start=start)

    results = {}

    for don_w in [50, 75, 100, 150, 200]:
        try:
            res = run_backtest(
                tickers=tickers,
                start=start,
                don_window=don_w,
                pre_data=pre_data,
                pre_vix=pre_vix,
            )
            if "metrics" in res:
                m = res["metrics"]
                results[str(don_w)] = {
                    "donchian_window": don_w,
                    "cagr":           m.get("cagr", 0),
                    "sharpe":         m.get("sharpe", 0),
                    "sortino":        m.get("sortino", 0),
                    "calmar":         m.get("calmar", 0),
                    "sterling":       m.get("sterling", 0),
                    "max_drawdown":   m.get("max_drawdown", 0),
                    "volatility":     m.get("volatility", 0),
                }
        except Exception as e:
            results[str(don_w)] = {"error": str(e)}

    # Robustness score: coefficient of variation of Sharpe across params
    sharpes = [v.get("sharpe", 0) for v in results.values() if "sharpe" in v]
    robustness_score = None
    if len(sharpes) >= 3:
        cv = float(np.std(sharpes) / np.mean(sharpes)) if np.mean(sharpes) != 0 else 999
        robustness_score = round(max(0, 100 - cv * 100), 1)

    return {
        "parameter":        "donchian_window",
        "results":          results,
        "robustness_score": robustness_score,
        "interpretation":   (
            "Score > 70: parameter-robust strategy. "
            "Score < 40: performance concentrated in specific window — overfitting risk."
        ),
    }


# ── Candidate Asset Analysis ──────────────────────────────────────────────────

def analyze_candidate(ticker: str, current_tickers: Optional[list[str]] = None) -> dict:
    """
    Evaluate whether adding a new asset improves the portfolio.

    Computes standalone metrics, correlation with existing assets, and
    marginal Sharpe impact when added at 5% weight.
    """
    current_tickers = current_tickers or DEFAULT_TICKERS
    all_tickers     = list(set(current_tickers + [ticker]))

    try:
        data = download_prices(all_tickers, start="2003-01-01")
    except Exception as e:
        return {"error": str(e)}

    if ticker not in data.columns:
        return {"error": f"Ticker '{ticker}' not found in downloaded data"}

    rets = data.pct_change().dropna()
    cr   = rets[ticker]

    ann_ret = float(cr.mean() * 252)
    ann_vol = float(cr.std() * np.sqrt(252))
    sharpe  = float((ann_ret - 0.04) / ann_vol) if ann_vol > 0 else 0.0
    peak    = data[ticker].cummax()
    max_dd  = float(((data[ticker] - peak) / peak).min())

    corrs    = {t: round(float(rets[ticker].corr(rets[t])), 3)
                for t in current_tickers if t in rets.columns}
    avg_corr = float(np.mean(list(corrs.values()))) if corrs else 0.0

    current_cols  = [t for t in current_tickers if t in rets.columns]
    port_before   = rets[current_cols].mean(axis=1)
    port_after    = port_before * 0.95 + cr * 0.05

    def _sharpe(s: pd.Series) -> float:
        ann  = float(s.mean() * 252)
        vol  = float(s.std() * np.sqrt(252))
        return float((ann - 0.04) / vol) if vol > 0 else 0.0

    sharpe_before = _sharpe(port_before)
    sharpe_after  = _sharpe(port_after)

    t = ticker.upper()
    sleeve = (
        "crypto"    if "USD" in t or any(c in t for c in ["BTC","ETH","SOL","BNB","ADA"])
        else "commodity" if any(c in t for c in ["GLD","SLV","IAU","PDBC","XLE","USO"])
        else "bonds"     if any(c in t for c in ["TLT","IEF","BND","AGG","SHY","GOVT"])
        else "equity"
    )

    score = 50
    score += min(sharpe * 12, 20)
    score -= avg_corr * 15
    score += (5 if max_dd > -0.20 else 0 if max_dd > -0.40 else -5 if max_dd > -0.60 else -12)
    score += (sharpe_after - sharpe_before) * 100
    score  = max(0, min(100, int(score)))
    verdict = "INCLUDE" if score >= 70 else "WATCH" if score >= 45 else "DISCARD"

    return {
        "ticker":  ticker,
        "verdict": verdict,
        "score":   score,
        "metrics": {
            "sharpe":     round(sharpe, 2),
            "max_dd":     round(max_dd * 100, 2),
            "annual_vol": round(ann_vol * 100, 2),
            "annual_ret": round(ann_ret * 100, 2),
            "avg_corr":   round(avg_corr, 3),
        },
        "correlations": corrs,
        "portfolio_impact": {
            "sharpe_before": round(sharpe_before, 2),
            "sharpe_after":  round(sharpe_after, 2),
            "vol_before":    round(float(port_before.std() * np.sqrt(252) * 100), 2),
            "vol_after":     round(float(port_after.std() * np.sqrt(252) * 100), 2),
            "delta_sharpe":  round(sharpe_after - sharpe_before, 3),
        },
        "suggested_sleeve": sleeve,
    }
