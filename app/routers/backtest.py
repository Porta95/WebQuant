"""
backtest.py — Lee performance y permite análisis de candidatos.
"""

import json
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..models.schemas import AnalyzerRequest
from app.services.yahoo import download_prices

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

DATA_DIR = Path(__file__).parent.parent.parent / "data"

STRESS_SCENARIOS = {
    "covid_2020":  {"name": "COVID Crash",      "start": "2020-02-19", "end": "2020-03-23"},
    "ftx_2022":    {"name": "FTX Collapse",      "start": "2022-11-01", "end": "2022-11-30"},
    "rates_2022":  {"name": "Rate Hike Cycle",   "start": "2022-01-01", "end": "2022-12-31"},
    "crypto_2018": {"name": "Crypto Bear 2018",  "start": "2018-01-01", "end": "2018-12-31"},
}


@router.get("/performance")
async def get_performance():
    path = DATA_DIR / "performance.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Datos no disponibles. Corré el workflow primero.")
    return json.loads(path.read_text())


@router.get("/scenarios")
async def list_scenarios():
    return [{"key": k, "name": v["name"], "start": v["start"], "end": v["end"]}
            for k, v in STRESS_SCENARIOS.items()]


@router.get("/stress/{scenario_key}")
async def stress_test(scenario_key: str):
    sc = STRESS_SCENARIOS.get(scenario_key)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Escenario '{scenario_key}' no encontrado")

    path = DATA_DIR / "performance.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Datos no disponibles")

    perf  = json.loads(path.read_text())
    curve = perf.get("equity_curve", [])
    filtered = [p for p in curve if sc["start"] <= p["date"] <= sc["end"]]

    if len(filtered) < 2:
        return {"scenario": sc["name"], "period": f"{sc['start']} / {sc['end']}", "error": "Sin datos suficientes para este período"}

    strat_ret = filtered[-1]["strategy"] / filtered[0]["strategy"] - 1
    bench_ret = filtered[-1]["benchmark"] / filtered[0]["benchmark"] - 1

    return {
        "scenario":          sc["name"],
        "period":            f"{sc['start']} / {sc['end']}",
        "strategy_return":   round(strat_ret * 100, 2),
        "benchmark_return":  round(bench_ret * 100, 2),
        "outperformance":    round((strat_ret - bench_ret) * 100, 2),
        "equity_curve":      filtered,
    }

@router.post("/analyze")
async def analyze(body: AnalyzerRequest):
    ticker = body.ticker.strip().upper()
    current = body.current_tickers or ["SPY", "QQQ", "BTC-USD", "ETH-USD", "GLD"]
    all_t = list(set(current + [ticker]))

    try:
        data = download_prices(all_t, start="2020-01-01")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Yahoo error: {e}")

    if ticker not in data.columns:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' no encontrado")

    rets = data.pct_change().dropna()
    cr = rets[ticker]

    annual_ret = float(cr.mean() * 252)
    annual_vol = float(cr.std() * np.sqrt(252))
    sharpe = (annual_ret - 0.05) / annual_vol if annual_vol > 0 else 0

    peak = data[ticker].cummax()
    max_dd = float(((data[ticker] - peak) / peak).min())

    corrs = {t: round(float(rets[ticker].corr(rets[t])), 3)
             for t in current if t in rets.columns}
    avg_corr = float(np.mean(list(corrs.values()))) if corrs else 0

    port_before = rets[[t for t in current if t in rets.columns]].mean(axis=1)
    port_after = port_before * 0.95 + cr * 0.05

    def sharpe_s(s):
        return float((s.mean()*252 - 0.05) / (s.std()*np.sqrt(252))) if s.std() > 0 else 0

    sb = sharpe_s(port_before)
    sa = sharpe_s(port_after)

    score = 50
    score += min(sharpe * 12, 20)
    score -= avg_corr * 15
    score += 5 if max_dd > -0.20 else 0 if max_dd > -0.40 else -5 if max_dd > -0.60 else -12
    score += (sa - sb) * 100
    score = max(0, min(100, int(score)))

    verdict = "INCLUDE" if score >= 70 else "WATCH" if score >= 45 else "DISCARD"

    sleeve = (
        "crypto" if "USD" in ticker or any(c in ticker for c in ["BTC","ETH","SOL","BNB"])
        else "commodity" if any(c in ticker for c in ["GLD","SLV","IAU"])
        else "bonds" if any(c in ticker for c in ["TLT","IEF","BND"])
        else "equity"
    )

    return {
        "ticker": ticker,
        "verdict": verdict,
        "score": score,
        "metrics": {
            "sharpe": round(sharpe, 2),
            "max_dd": round(max_dd * 100, 2),
            "annual_vol": round(annual_vol * 100, 2),
            "annual_ret": round(annual_ret * 100, 2),
            "avg_corr": round(avg_corr, 3),
        },
        "correlations": corrs,
        "portfolio_impact": {
            "sharpe_before": round(sb, 2),
            "sharpe_after": round(sa, 2),
            "vol_before": round(float(port_before.std()*np.sqrt(252)*100), 2),
            "vol_after": round(float(port_after.std()*np.sqrt(252)*100), 2),
            "delta_sharpe": round(sa - sb, 3),
        },
        "suggested_sleeve": sleeve,
    }
