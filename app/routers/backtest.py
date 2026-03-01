"""
backtest.py — Router de backtesting y análisis de candidatos.

POST /api/backtest              → backtest completo
GET  /api/backtest/stress/{key} → stress test histórico
POST /api/backtest/analyze      → analizar activo candidato
GET  /api/backtest/scenarios    → lista de escenarios disponibles
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from ..services.backtest import run_backtest, run_stress_test, analyze_candidate, STRESS_SCENARIOS
from ..models.schemas import (
    BacktestRequest, BacktestResponse,
    StressTestResponse, AnalyzerRequest, AnalyzerResponse,
)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/", response_model=BacktestResponse)
async def backtest(body: BacktestRequest):
    """
    Corre el backtest completo de la estrategia rotacional.
    Retorna equity curve, métricas y distribución de retornos.
    """
    try:
        result = run_backtest(
            tickers=body.tickers,
            start=body.start,
            initial_capital=body.initial_capital,
            window=body.window,
            rebalance_freq=body.rebalance_freq,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios")
async def list_scenarios():
    """Lista los escenarios de stress disponibles."""
    return [
        {"key": k, "name": v["name"], "start": v["start"], "end": v["end"]}
        for k, v in STRESS_SCENARIOS.items()
    ]


@router.get("/stress/{scenario_key}", response_model=StressTestResponse)
async def stress_test(
    scenario_key: str,
    tickers: Optional[str] = Query(default=None),
):
    """Corre un stress test en un período histórico específico."""
    ticker_list = [t.strip().upper() for t in tickers.split(",")] if tickers else None

    try:
        result = run_stress_test(scenario_key, tickers=ticker_list)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=AnalyzerResponse)
async def analyze(body: AnalyzerRequest):
    """
    Analiza un activo candidato para incluir en la cartera.
    Calcula Sharpe, correlaciones, MaxDD e impacto en el portafolio.
    """
    ticker = body.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker requerido")

    try:
        result = analyze_candidate(ticker, current_tickers=body.current_tickers)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
