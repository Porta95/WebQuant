"""
backtest.py (router) — Performance data, stress tests, walk-forward,
Monte Carlo, sensitivity analysis, and candidate asset evaluation.

Pre-computed data (GitHub Actions) is served from data/*.json.
On-demand endpoints compute results live when called interactively.
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

from ..models.schemas import AnalyzerRequest
from ..services.backtest import (
    run_stress_test,
    run_walk_forward,
    run_monte_carlo,
    run_sensitivity_analysis,
    analyze_candidate,
    STRESS_SCENARIOS,
)

router   = APIRouter(prefix="/api/backtest", tags=["backtest"])
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _read_json(filename: str) -> dict:
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Data not available ({filename}). Run the GitHub Actions workflow first.",
        )
    return json.loads(path.read_text())


@router.get("/performance")
async def get_performance():
    """Return pre-computed backtest metrics and equity curve."""
    return _read_json("performance.json")


@router.get("/scenarios")
async def list_scenarios():
    """List available stress test scenarios."""
    return [
        {"key": k, "name": v["name"], "start": v["start"], "end": v["end"]}
        for k, v in STRESS_SCENARIOS.items()
    ]


@router.get("/stress/{scenario_key}")
async def stress_test(scenario_key: str):
    """
    Run strategy through a historical stress episode with proper 2-year warmup.
    Fixes warm-up bias present in v2 (which started backtest at scenario start).
    """
    result = run_stress_test(scenario_key)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/walk-forward")
async def walk_forward(
    start:       str = "2007-01-01",
    train_years: int = 3,
    test_years:  int = 1,
):
    """
    Walk-forward validation: expanding train window, rolling 1-year test.
    Returns per-window out-of-sample statistics and consistency summary.
    """
    result = run_walk_forward(start=start, train_years=train_years, test_years=test_years)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/monte-carlo")
async def monte_carlo(n_simulations: int = 2000, horizon_years: int = 5):
    """
    Bootstrap Monte Carlo using pre-computed historical weekly returns.
    Returns percentile distributions for CAGR, max drawdown, and Sharpe.
    """
    perf_data      = _read_json("performance.json")
    weekly_returns = perf_data.get("weekly_returns", [])
    if not weekly_returns:
        raise HTTPException(status_code=503, detail="No weekly returns in performance.json")

    result = run_monte_carlo(
        weekly_returns=[r / 100 for r in weekly_returns],
        n_simulations=n_simulations,
        n_periods=horizon_years * 52,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/sensitivity")
async def sensitivity_analysis(start: str = "2010-01-01"):
    """
    Test Sharpe robustness across Donchian windows [50, 75, 100, 150, 200].
    A robust strategy shows flat performance; a peak indicates overfitting.
    """
    return run_sensitivity_analysis(start=start)


@router.post("/analyze")
async def analyze(body: AnalyzerRequest):
    """
    Evaluate whether a candidate ticker improves the portfolio.
    Returns standalone metrics, correlations, and marginal Sharpe impact.
    """
    result = analyze_candidate(
        ticker=body.ticker.strip().upper(),
        current_tickers=body.current_tickers,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
