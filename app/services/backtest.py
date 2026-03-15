"""
backtest.py — Motor de backtesting vectorizado v3.

Mejoras v3:
- Costos de transacción: 10 bps por rotación (realista para ETFs)
- Circuit breaker: si drawdown > -15% desde el pico, reduce exposición al 50%
- _weights_at usa fases ATR-adaptativas y asignación multi-asset con momentum
- Nuevos escenarios de stress: crisis Argentina 2018, deuda 2020
- Importa y usa todas las funciones v3 de core.py
"""

import numpy as np
import pandas as pd
from typing import Optional
from .core import (
    download_prices, add_indicators, compute_positions,
    trend_phase_adaptive, phase_size, get_buffett,
    annual_volatility, vol_adjusted_size,
    compute_momentum, compute_value_score, allocate_sleeve, buffett_multiplier_continuous,
    SLEEVE_MAP, CRYPTO_SPLIT, DEFAULT_TICKERS,
)

# Costo de transacción por trade (bilateral: compra + venta = 2x este valor)
TRANSACTION_COST = 0.001   # 10 bps por lado (ETFs líquidos)

# Circuit breaker: drawdown máximo antes de reducir posiciones
DD_CIRCUIT_BREAKER = -0.15  # -15% desde el pico → reduce exposición al 50%

STRESS_SCENARIOS = {
    "covid_2020":      {"name": "COVID Crash",           "start": "2020-02-19", "end": "2020-03-23"},
    "ftx_2022":        {"name": "FTX Collapse",           "start": "2022-11-01", "end": "2022-11-30"},
    "rates_2022":      {"name": "Rate Hike Cycle",        "start": "2022-01-01", "end": "2022-12-31"},
    "crypto_2018":     {"name": "Crypto Bear 2018",       "start": "2018-01-01", "end": "2018-12-31"},
    "argentina_2018":  {"name": "Crisis Argentina 2018",  "start": "2018-01-01", "end": "2018-12-31"},
    "argentina_2020":  {"name": "Deuda Argentina 2020",   "start": "2020-01-01", "end": "2020-12-31"},
}


def run_backtest(
    tickers: Optional[list[str]] = None,
    start: str = "2020-01-01",
    initial_capital: float = 10_000,
    window: int = 50,
    rebalance_freq: str = "W",   # W=semanal, M=mensual
    transaction_cost: float = TRANSACTION_COST,
    use_circuit_breaker: bool = True,
) -> dict:
    """
    Backtest completo de la estrategia rotacional v3.

    Novedades:
    - Costos de transacción deducidos en cada rebalanceo según rotación real
    - Circuit breaker: reduce exposición al 50% si drawdown > DD_CIRCUIT_BREAKER
    - Usa fases ATR-adaptativas y asignación multi-asset con momentum

    Returns:
        equity_curve   : lista de {date, strategy, benchmark}
        metrics        : CAGR, Sharpe, MaxDD, Sortino, WinRate, etc.
        weekly_returns : lista de floats (retornos por período)
        drawdown_series: lista de floats
    """
    tickers = tickers or DEFAULT_TICKERS
    data    = download_prices(tickers, start=start)
    data    = add_indicators(data, tickers, window)
    positions = compute_positions(data, tickers, window)

    # Métricas pre-calculadas (una sola vez, no en cada rebalanceo)
    vols    = {t: annual_volatility(data[t])   for t in tickers if t in data.columns}
    momenta = {t: compute_momentum(data, t)    for t in tickers if t in data.columns}
    values  = {t: compute_value_score(data, t) for t in tickers if t in data.columns}

    # Resamplear a frecuencia de rebalanceo
    rebal_dates = data.resample(rebalance_freq).last().index
    rebal_dates = rebal_dates[rebal_dates >= data.index[window + 5]]

    # SPY como benchmark
    spy = data["SPY"] if "SPY" in data.columns else data.iloc[:, 0]

    # Estado inicial
    strat_val   = initial_capital
    bench_val   = initial_capital
    peak_val    = initial_capital   # para circuit breaker
    strat_curve = []
    weekly_rets = []
    prev_weights: dict[str, float] = {t: 0.0 for t in tickers}
    circuit_breaker_active = False

    # Obtener multiplicador Buffett una sola vez para el backtest
    try:
        buffett      = get_buffett()
        buffett_mult = buffett.get("mult", 1.0)
    except Exception:
        buffett_mult = 1.0

    for i, date in enumerate(rebal_dates):
        if date not in data.index:
            continue
        loc = data.index.get_loc(date)
        row = data.iloc[loc]

        # Calcular pesos en esta fecha (con factor de valor)
        weights = _weights_at(data, positions, tickers, loc, window, vols, momenta, buffett_mult, values)

        # ── Circuit breaker ─────────────────────────────────────────────────
        current_dd = (strat_val - peak_val) / peak_val if peak_val > 0 else 0.0
        if use_circuit_breaker and current_dd < DD_CIRCUIT_BREAKER:
            if not circuit_breaker_active:
                print(f"[circuit_breaker] activado en {date}: DD={current_dd:.1%}")
                circuit_breaker_active = True
            weights = {t: w * 0.5 for t, w in weights.items()}
        elif circuit_breaker_active and current_dd > -0.05:
            # Desactivar cuando recupera hasta -5%
            circuit_breaker_active = False

        # ── Costos de transacción ────────────────────────────────────────────
        total_rotation = sum(
            abs(weights.get(t, 0.0) - prev_weights.get(t, 0.0))
            for t in set(list(weights.keys()) + list(prev_weights.keys()))
        )
        transaction_drag = total_rotation * transaction_cost

        # Siguiente fecha de rebalanceo
        next_date = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else data.index[-1]
        if next_date not in data.index:
            continue

        # ── Retorno ponderado del período ────────────────────────────────────
        period_ret = 0.0
        for t, w in weights.items():
            if w == 0 or t not in data.columns:
                continue
            p0 = float(data.loc[date, t])
            p1 = float(data.loc[next_date, t])
            if p0 > 0:
                period_ret += w * (p1 / p0 - 1)

        period_ret -= transaction_drag   # deducir fricción

        # Benchmark SPY
        spy0      = float(spy.loc[date])      if date      in spy.index else None
        spy1      = float(spy.loc[next_date]) if next_date in spy.index else None
        bench_ret = (spy1 / spy0 - 1) if spy0 and spy1 and spy0 > 0 else 0.0

        strat_val *= (1 + period_ret)
        bench_val *= (1 + bench_ret)
        peak_val   = max(peak_val, strat_val)

        weekly_rets.append(period_ret)
        strat_curve.append({
            "date":      str(date.date()),
            "strategy":  round(strat_val, 2),
            "benchmark": round(bench_val, 2),
        })
        prev_weights = dict(weights)

    if not strat_curve:
        return {"error": "Datos insuficientes para backtest"}

    # ── Métricas ──────────────────────────────────────────────────────────────
    rets             = np.array(weekly_rets)
    periods_per_year = 52 if rebalance_freq == "W" else 12

    total_ret   = strat_val / initial_capital - 1
    years       = len(rets) / periods_per_year
    cagr        = (1 + total_ret) ** (1 / max(years, 0.1)) - 1
    vol         = rets.std() * np.sqrt(periods_per_year)
    sharpe      = (cagr - 0.05) / vol if vol > 0 else 0
    neg_rets    = rets[rets < 0]
    sortino_vol = neg_rets.std() * np.sqrt(periods_per_year) if len(neg_rets) > 0 else 0
    sortino     = (cagr - 0.05) / sortino_vol if sortino_vol > 0 else 0
    win_rate    = float(np.sum(rets > 0) / len(rets)) if len(rets) > 0 else 0

    # Drawdown series
    vals      = np.array([p["strategy"] for p in strat_curve])
    peak      = np.maximum.accumulate(vals)
    dd_series = ((vals - peak) / peak * 100).tolist()
    max_dd    = float(np.min(dd_series))

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

    curve    = result.get("equity_curve", [])
    filtered = [p for p in curve if sc["start"] <= p["date"] <= sc["end"]]

    if not filtered:
        return {"error": "Sin datos para este escenario"}

    strat_ret = filtered[-1]["strategy"]   / filtered[0]["strategy"]   - 1
    bench_ret = filtered[-1]["benchmark"] / filtered[0]["benchmark"] - 1

    return {
        "scenario":          sc["name"],
        "period":            f"{sc['start']} / {sc['end']}",
        "strategy_return":   round(strat_ret * 100, 2),
        "benchmark_return":  round(bench_ret * 100, 2),
        "outperformance":    round((strat_ret - bench_ret) * 100, 2),
        "equity_curve":      filtered,
    }


def analyze_candidate(ticker: str, current_tickers: Optional[list[str]] = None) -> dict:
    """
    Analiza si un activo candidato mejora la cartera.
    Calcula Sharpe, correlaciones, MaxDD e impacto marginal.
    """
    current_tickers = current_tickers or DEFAULT_TICKERS
    all_tickers     = list(set(current_tickers + [ticker]))

    try:
        data = download_prices(all_tickers, start="2020-01-01")
    except Exception as e:
        return {"error": str(e)}

    if ticker not in data.columns:
        return {"error": f"Ticker '{ticker}' no encontrado"}

    rets = data.pct_change().dropna()

    cand_rets  = rets[ticker]
    annual_ret = float(cand_rets.mean() * 252)
    annual_vol = float(cand_rets.std() * np.sqrt(252))
    sharpe     = (annual_ret - 0.05) / annual_vol if annual_vol > 0 else 0
    max_dd     = _max_drawdown(data[ticker])

    correlations = {}
    for t in current_tickers:
        if t in rets.columns:
            correlations[t] = round(float(rets[ticker].corr(rets[t])), 3)

    avg_corr = np.mean(list(correlations.values())) if correlations else 0

    valid_curr = [t for t in current_tickers if t in rets.columns]
    port_rets_before = rets[valid_curr].mean(axis=1)
    port_rets_after  = port_rets_before * 0.95 + cand_rets * 0.05
    sharpe_before    = _sharpe(port_rets_before)
    sharpe_after     = _sharpe(port_rets_after)
    vol_before       = float(port_rets_before.std() * np.sqrt(252) * 100)
    vol_after        = float(port_rets_after.std()  * np.sqrt(252) * 100)

    sleeve  = _suggest_sleeve(ticker, correlations)
    score   = _score_candidate(sharpe, avg_corr, max_dd, sharpe_after - sharpe_before)
    verdict = "INCLUDE" if score >= 70 else "WATCH" if score >= 45 else "DISCARD"

    return {
        "ticker":  ticker,
        "verdict": verdict,
        "score":   score,
        "metrics": {
            "sharpe":     round(sharpe, 2),
            "max_dd":     round(max_dd * 100, 2),
            "annual_vol": round(annual_vol * 100, 2),
            "annual_ret": round(annual_ret * 100, 2),
            "avg_corr":   round(avg_corr, 3),
        },
        "correlations": correlations,
        "portfolio_impact": {
            "sharpe_before": round(sharpe_before, 2),
            "sharpe_after":  round(sharpe_after, 2),
            "vol_before":    round(vol_before, 2),
            "vol_after":     round(vol_after, 2),
            "delta_sharpe":  round(sharpe_after - sharpe_before, 3),
        },
        "suggested_sleeve": sleeve,
    }


# ── Helpers internos ──────────────────────────────────────────────────────────

def _weights_at(
    data: pd.DataFrame,
    positions: dict,
    tickers: list,
    loc: int,
    window: int,
    vols: Optional[dict] = None,
    momenta: Optional[dict] = None,
    buffett_mult: float = 1.0,
    values: Optional[dict] = None,
) -> dict:
    """
    Calcula pesos de la estrategia en un momento dado del histórico.

    v3.1: usa fases ATR-adaptativas, multi-asset, momentum y factor de valor.
    """
    row     = data.iloc[loc]
    weights = {t: 0.0 for t in tickers}
    sizes   = {}
    active  = {}

    if vols is None:
        vols = {}
    if momenta is None:
        momenta = {}
    if values is None:
        values = {}

    for t in tickers:
        if t not in data.columns:
            continue
        ma_col  = f"{t}_MA{window}"
        atr_col = f"{t}_ATR20"
        if ma_col not in row.index:
            continue

        atr20 = float(row[atr_col]) if atr_col in row.index and not pd.isna(row[atr_col]) else 0.0
        ph, _, _   = trend_phase_adaptive(float(row[t]), float(row[ma_col]), atr20)
        sizes[t]   = phase_size(ph)
        active[t]  = bool(positions[t].iloc[loc])

    # Clasificar en sleeves
    effective_sleeve = {t: SLEEVE_MAP.get(t, "equity") for t in tickers if t in data.columns}
    sleeves: dict[str, list] = {}
    for t, s in effective_sleeve.items():
        sleeves.setdefault(s, []).append(t)

    trading_sleeves = [s for s in sleeves if s != "bonds"]

    def sleeve_strength(assets):
        s = [sizes[a] for a in assets if active.get(a)]
        return max(s) if s else 0.0

    sleeve_str = {s: sleeve_strength(sleeves[s]) for s in trading_sleeves}
    total_s    = sum(sleeve_str.values())

    if total_s == 0:
        # Safe haven fallback
        bond_assets = sleeves.get("bonds", [])
        equity_assets = sleeves.get("equity", [])
        equity_broken = all(not active.get(t) or sizes.get(t, 0) == 0 for t in equity_assets)
        if bond_assets and equity_broken:
            bond_budget = 1.0 / max(len(trading_sleeves), 1) if trading_sleeves else 0.3
            bond_alloc  = allocate_sleeve(bond_assets, bond_budget, sizes, active,
                                          vols or {}, momenta or {})
            if not bond_alloc and bond_assets:
                bond_alloc = {bond_assets[0]: round(bond_budget, 4)}
                active[bond_assets[0]] = True
            weights.update(bond_alloc)
        tw = sum(weights.values())
        if tw > 0:
            weights = {t: w / tw for t, w in weights.items()}
        return weights

    base_sw = {s: strength / total_s for s, strength in sleeve_str.items()}
    for s in ("equity", "merval"):
        if s in base_sw:
            base_sw[s] *= buffett_mult

    # FIX: solo normalizar si > 1.0 (evitar sobreapalancamiento).
    # Si total_sw < 1.0 (Buffett reduce), dejar el resto como cash.
    total_sw = sum(base_sw.values())
    if total_sw > 1.0:
        base_sw = {s: w / total_sw for s, w in base_sw.items()}

    for sleeve_name in trading_sleeves:
        sw = base_sw.get(sleeve_name, 0.0)
        if sw == 0:
            continue
        prior_splits = CRYPTO_SPLIT if sleeve_name == "crypto" else None
        alloc = allocate_sleeve(
            sleeves[sleeve_name], sw, sizes, active,
            vols or {}, momenta or {}, splits=prior_splits, values=values or {},
        )
        weights.update(alloc)

    # Safe haven redirect
    equity_assets = sleeves.get("equity", [])
    bond_assets   = sleeves.get("bonds", [])
    equity_broken = all(not active.get(t) or sizes.get(t, 0) == 0 for t in equity_assets)
    if bond_assets and equity_broken:
        bond_budget = 1.0 / max(len(trading_sleeves), 1)
        bond_alloc  = allocate_sleeve(bond_assets, bond_budget, sizes, active,
                                      vols or {}, momenta or {})
        if not bond_alloc and bond_assets:
            bond_alloc = {bond_assets[0]: round(bond_budget, 4)}
            active[bond_assets[0]] = True
        weights.update(bond_alloc)

    # NO normalizar a 100% — la diferencia con 1.0 es cash (efecto Buffett real)
    total_w = sum(weights.values())
    if total_w > 1.0:
        weights = {t: round(w / total_w, 4) for t, w in weights.items()}
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
    if any(c in t for c in ["GLD", "SLV", "IAU", "PDBC", "GSG", "USO"]):
        return "commodity"
    if any(c in t for c in ["TLT", "IEF", "BND", "AGG", "BIL", "SHY"]):
        return "bonds"
    if t.endswith(".BA"):
        return "merval"
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
