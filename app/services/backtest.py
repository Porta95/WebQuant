"""
backtest.py — Motor de backtesting vectorizado.
Calcula equity curve, métricas y stress tests sin loops lentos.
"""

import numpy as np
import pandas as pd
from typing import Optional
from .core import download_prices, add_indicators, compute_positions, trend_phase, phase_size, get_buffett, SLEEVE_MAP, CRYPTO_SPLIT, DEFAULT_TICKERS


STRESS_SCENARIOS = {
    "covid_2020":  {"name": "COVID Crash",       "start": "2020-02-19", "end": "2020-03-23"},
    "ftx_2022":    {"name": "FTX Collapse",       "start": "2022-11-01", "end": "2022-11-30"},
    "rates_2022":  {"name": "Rate Hike Cycle",    "start": "2022-01-01", "end": "2022-12-31"},
    "crypto_2018": {"name": "Crypto Bear 2018",   "start": "2018-01-01", "end": "2018-12-31"},
}


def run_backtest(
    tickers: Optional[list[str]] = None,
    start: str = "2020-01-01",
    initial_capital: float = 10_000,
    window: int = 50,
    rebalance_freq: str = "W",   # W=semanal, M=mensual
) -> dict:
    """
    Backtest completo de la estrategia rotacional.

    Returns:
        equity_curve   : lista de {date, value, benchmark}
        metrics        : CAGR, Sharpe, MaxDD, Sortino, WinRate
        weekly_returns : lista de floats
        drawdown_series: lista de floats
    """
    tickers = tickers or DEFAULT_TICKERS
    data = download_prices(tickers, start=start)
    data = add_indicators(data, tickers, window)
    positions = compute_positions(data, tickers, window)

    # Resamplear a frecuencia de rebalanceo
    rebal_dates = data.resample(rebalance_freq).last().index
    rebal_dates = rebal_dates[rebal_dates >= data.index[window + 5]]

    # SPY como benchmark
    spy = data["SPY"] if "SPY" in data.columns else data.iloc[:, 0]

    # Equity curves
    strat_val   = initial_capital
    bench_val   = initial_capital
    strat_curve = []
    bench_curve = []
    weekly_rets = []
    prev_date   = None

    for i, date in enumerate(rebal_dates):
        if date not in data.index:
            continue
        loc = data.index.get_loc(date)
        row = data.iloc[loc]

        # Calcular pesos en esta fecha
        weights = _weights_at(data, positions, tickers, loc, window)

        # Retorno hasta el próximo rebalanceo
        if i + 1 < len(rebal_dates):
            next_date = rebal_dates[i + 1]
        else:
            next_date = data.index[-1]

        if next_date not in data.index:
            continue

        # Retorno ponderado del portafolio
        period_ret = 0.0
        for t, w in weights.items():
            p0 = float(data.loc[date, t]) if t in data.columns else None
            p1 = float(data.loc[next_date, t]) if t in data.columns else None
            if p0 and p1 and p0 > 0:
                period_ret += w * (p1 / p0 - 1)

        # Benchmark SPY
        spy0 = float(spy.loc[date]) if date in spy.index else None
        spy1 = float(spy.loc[next_date]) if next_date in spy.index else None
        bench_ret = (spy1 / spy0 - 1) if spy0 and spy1 and spy0 > 0 else 0

        strat_val *= (1 + period_ret)
        bench_val *= (1 + bench_ret)
        weekly_rets.append(period_ret)

        strat_curve.append({"date": str(date.date()), "strategy": round(strat_val, 2), "benchmark": round(bench_val, 2)})

    if not strat_curve:
        return {"error": "Datos insuficientes para backtest"}

    # ── Métricas ──────────────────────────────────────────────────────────
    rets = np.array(weekly_rets)
    periods_per_year = 52 if rebalance_freq == "W" else 12

    total_ret   = strat_val / initial_capital - 1
    years       = len(rets) / periods_per_year
    cagr        = (1 + total_ret) ** (1 / max(years, 0.1)) - 1
    vol         = rets.std() * np.sqrt(periods_per_year)
    sharpe      = (cagr - 0.05) / vol if vol > 0 else 0  # rf = 5%
    neg_rets    = rets[rets < 0]
    sortino_vol = neg_rets.std() * np.sqrt(periods_per_year) if len(neg_rets) > 0 else 0
    sortino     = (cagr - 0.05) / sortino_vol if sortino_vol > 0 else 0
    win_rate    = float(np.sum(rets > 0) / len(rets)) if len(rets) > 0 else 0

    # Drawdown series
    values  = np.array([p["strategy"] for p in strat_curve])
    peak    = np.maximum.accumulate(values)
    dd_series = ((values - peak) / peak * 100).tolist()
    max_dd  = float(np.min(dd_series))

    # Benchmark CAGR
    bench_total = bench_val / initial_capital - 1
    bench_cagr  = (1 + bench_total) ** (1 / max(years, 0.1)) - 1

    metrics = {
        "cagr":           round(cagr * 100, 2),
        "cagr_bench":     round(bench_cagr * 100, 2),
        "sharpe":         round(sharpe, 2),
        "sortino":        round(sortino, 2),
        "max_drawdown":   round(max_dd, 2),
        "volatility":     round(vol * 100, 2),
        "win_rate":       round(win_rate * 100, 1),
        "total_return":   round(total_ret * 100, 2),
        "final_capital":  round(strat_val, 2),
        "years":          round(years, 1),
    }

    return {
        "equity_curve":    strat_curve,
        "metrics":         metrics,
        "weekly_returns":  [round(r * 100, 3) for r in rets.tolist()],
        "drawdown_series": [round(d, 2) for d in dd_series],
        "dates":           [p["date"] for p in strat_curve],
    }


def run_stress_test(scenario_key: str, tickers: Optional[list[str]] = None) -> dict:
    """Corre el backtest en un período de stress específico."""
    sc = STRESS_SCENARIOS.get(scenario_key)
    if not sc:
        return {"error": f"Escenario '{scenario_key}' no encontrado"}

    tickers = tickers or DEFAULT_TICKERS
    result  = run_backtest(tickers, start=sc["start"])

    # Filtrar por ventana del escenario
    curve   = result.get("equity_curve", [])
    filtered = [p for p in curve if sc["start"] <= p["date"] <= sc["end"]]

    if not filtered:
        return {"error": "Sin datos para este escenario"}

    strat_ret = filtered[-1]["strategy"] / filtered[0]["strategy"] - 1
    bench_ret = filtered[-1]["benchmark"] / filtered[0]["benchmark"] - 1

    return {
        "scenario":       sc["name"],
        "period":         f"{sc['start']} / {sc['end']}",
        "strategy_return": round(strat_ret * 100, 2),
        "benchmark_return": round(bench_ret * 100, 2),
        "outperformance": round((strat_ret - bench_ret) * 100, 2),
        "equity_curve":   filtered,
    }


def analyze_candidate(ticker: str, current_tickers: Optional[list[str]] = None) -> dict:
    """
    Analiza si un activo candidato mejora la cartera.
    Calcula Sharpe, correlaciones, MaxDD y impacto marginal.
    """
    current_tickers = current_tickers or DEFAULT_TICKERS
    all_tickers = list(set(current_tickers + [ticker]))

    try:
        data = download_prices(all_tickers, start="2020-01-01")
    except Exception as e:
        return {"error": str(e)}

    if ticker not in data.columns:
        return {"error": f"Ticker '{ticker}' no encontrado"}

    rets = data.pct_change().dropna()

    # Métricas del candidato
    cand_rets  = rets[ticker]
    annual_ret = float(cand_rets.mean() * 252)
    annual_vol = float(cand_rets.std() * np.sqrt(252))
    sharpe     = (annual_ret - 0.05) / annual_vol if annual_vol > 0 else 0
    max_dd     = _max_drawdown(data[ticker])

    # Correlaciones con activos actuales
    correlations = {}
    for t in current_tickers:
        if t in rets.columns:
            correlations[t] = round(float(rets[ticker].corr(rets[t])), 3)

    # Correlación promedio con cartera
    avg_corr = np.mean(list(correlations.values())) if correlations else 0

    # Impacto en Sharpe si se incluye (simulación simple 5% de peso)
    port_rets_before = rets[current_tickers].mean(axis=1)
    port_rets_after  = port_rets_before * 0.95 + cand_rets * 0.05
    sharpe_before    = _sharpe(port_rets_before)
    sharpe_after     = _sharpe(port_rets_after)
    vol_before       = float(port_rets_before.std() * np.sqrt(252) * 100)
    vol_after        = float(port_rets_after.std() * np.sqrt(252) * 100)

    # Sleeve sugerido
    sleeve = _suggest_sleeve(ticker, correlations)

    # Veredicto
    score = _score_candidate(sharpe, avg_corr, max_dd, sharpe_after - sharpe_before)
    verdict = "INCLUDE" if score >= 70 else "WATCH" if score >= 45 else "DISCARD"

    return {
        "ticker":        ticker,
        "verdict":       verdict,
        "score":         score,
        "metrics": {
            "sharpe":     round(sharpe, 2),
            "max_dd":     round(max_dd * 100, 2),
            "annual_vol": round(annual_vol * 100, 2),
            "annual_ret": round(annual_ret * 100, 2),
            "avg_corr":   round(avg_corr, 3),
        },
        "correlations":  correlations,
        "portfolio_impact": {
            "sharpe_before": round(sharpe_before, 2),
            "sharpe_after":  round(sharpe_after, 2),
            "vol_before":    round(vol_before, 2),
            "vol_after":     round(vol_after, 2),
            "delta_sharpe":  round(sharpe_after - sharpe_before, 3),
        },
        "suggested_sleeve": sleeve,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────
def _weights_at(data, positions, tickers, loc, window):
    """Calcula pesos de la estrategia en un momento dado del histórico."""
    row = data.iloc[loc]
    weights = {t: 0.0 for t in tickers}
    sizes, active = {}, {}

    for t in tickers:
        if t not in data.columns:
            continue
        ph, _, _ = trend_phase(float(row[t]), float(row[f"{t}_MA{window}"]))
        sizes[t]  = phase_size(ph)
        active[t] = bool(positions[t].iloc[loc])

    crypto_assets    = [t for t in tickers if SLEEVE_MAP.get(t) == "crypto"]
    equity_assets    = [t for t in tickers if SLEEVE_MAP.get(t) == "equity"]
    commodity_assets = [t for t in tickers if SLEEVE_MAP.get(t) == "commodity"]

    def sleeve_s(assets):
        s = [sizes[a] for a in assets if active.get(a)]
        return max(s) if s else 0.0

    cs = sleeve_s(crypto_assets)
    es = sleeve_s(equity_assets)
    gs = sleeve_s(commodity_assets)
    total = cs + es + gs
    if total == 0:
        return weights

    cw = cs / total; ew = es / total; gw = gs / total
    # Buffett simplificado en backtest (sin llamada FRED en cada paso)
    ew *= 0.85  # Aproximación conservadora para velocidad

    t2 = cw + ew + gw
    cw /= t2; ew /= t2; gw /= t2

    for t in crypto_assets:
        if active.get(t):
            weights[t] = cw * CRYPTO_SPLIT.get(t, 0.5)

    eq_sorted = sorted(equity_assets, key=lambda t: 0 if t == "QQQ" else 1)
    for t in eq_sorted:
        if active.get(t):
            weights[t] = ew
            break

    for t in commodity_assets:
        if active.get(t):
            weights[t] = gw
            break

    total_w = sum(weights.values())
    if total_w > 0:
        weights = {t: w / total_w for t, w in weights.items()}
    return weights


def _max_drawdown(prices: pd.Series) -> float:
    peak = prices.cummax()
    dd   = (prices - peak) / peak
    return float(dd.min())


def _sharpe(rets: pd.Series, rf: float = 0.05 / 252) -> float:
    excess = rets - rf
    return float(excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0


def _suggest_sleeve(ticker: str, correlations: dict) -> str:
    t = ticker.upper()
    if "USD" in t or any(c in t for c in ["BTC", "ETH", "SOL", "BNB", "ADA"]):
        return "crypto"
    if any(c in t for c in ["GLD", "SLV", "IAU", "PDBC", "GSG"]):
        return "commodity"
    if any(c in t for c in ["TLT", "IEF", "BND", "AGG"]):
        return "bonds"
    return "equity"


def _score_candidate(sharpe: float, avg_corr: float, max_dd: float, delta_sharpe: float) -> int:
    score = 50
    score += min(sharpe * 12, 20)
    score -= avg_corr * 15
    score += max(dd_penalty(max_dd), -15)
    score += delta_sharpe * 100
    return max(0, min(100, int(score)))


def dd_penalty(max_dd: float) -> float:
    if max_dd > -0.20:  return 5
    if max_dd > -0.40:  return 0
    if max_dd > -0.60:  return -5
    return -12
