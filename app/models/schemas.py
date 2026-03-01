"""
schemas.py — Modelos Pydantic para validación de requests y responses.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Signal ───────────────────────────────────────────────────────────────────
class PhaseInfo(BaseModel):
    phase: str
    dist:  float
    risk:  float


class BuffettInfo(BaseModel):
    value: Optional[float]
    phase: str
    mult:  float
    yoy:   Optional[float]


class SignalResponse(BaseModel):
    weights:      dict[str, float]
    phases:       dict[str, PhaseInfo]
    active:       dict[str, bool]
    dominant:     str
    buffett:      BuffettInfo
    volatilities: dict[str, float]
    signal_date:  str
    cash_pct:     float
    quality:      str
    tickers:      list[str]


# ── Backtest ─────────────────────────────────────────────────────────────────
class BacktestRequest(BaseModel):
    tickers:         Optional[list[str]] = None
    start:           str = "2020-01-01"
    initial_capital: float = Field(default=10_000, gt=0)
    window:          int   = Field(default=50, ge=10, le=200)
    rebalance_freq:  str   = "W"


class BacktestMetrics(BaseModel):
    cagr:          float
    cagr_bench:    float
    sharpe:        float
    sortino:       float
    max_drawdown:  float
    volatility:    float
    win_rate:      float
    total_return:  float
    final_capital: float
    years:         float


class EquityPoint(BaseModel):
    date:       str
    strategy:   float
    benchmark:  float


class BacktestResponse(BaseModel):
    equity_curve:    list[EquityPoint]
    metrics:         BacktestMetrics
    weekly_returns:  list[float]
    drawdown_series: list[float]
    dates:           list[str]


# ── Stress Test ───────────────────────────────────────────────────────────────
class StressTestResponse(BaseModel):
    scenario:           str
    period:             str
    strategy_return:    float
    benchmark_return:   float
    outperformance:     float
    equity_curve:       list[EquityPoint]


# ── Analyzer ─────────────────────────────────────────────────────────────────
class AnalyzerRequest(BaseModel):
    ticker:           str
    current_tickers:  Optional[list[str]] = None


class PortfolioImpact(BaseModel):
    sharpe_before:  float
    sharpe_after:   float
    vol_before:     float
    vol_after:      float
    delta_sharpe:   float


class CandidateMetrics(BaseModel):
    sharpe:     float
    max_dd:     float
    annual_vol: float
    annual_ret: float
    avg_corr:   float


class AnalyzerResponse(BaseModel):
    ticker:            str
    verdict:           str   # INCLUDE | WATCH | DISCARD
    score:             int
    metrics:           CandidateMetrics
    correlations:      dict[str, float]
    portfolio_impact:  PortfolioImpact
    suggested_sleeve:  str


# ── Portfolio Config ──────────────────────────────────────────────────────────
class AssetConfig(BaseModel):
    ticker:  str
    sleeve:  str
    enabled: bool = True
    notes:   Optional[str] = None


class PortfolioConfigRequest(BaseModel):
    assets:         list[AssetConfig]
    donchian_window: int   = 50
    ma_exit_window:  int   = 50
    max_position:    float = 0.55
    vol_target:      float = 0.20


# ── Telegram ─────────────────────────────────────────────────────────────────
class TelegramRequest(BaseModel):
    message: Optional[str] = None   # Si None, usa la señal actual


class TelegramResponse(BaseModel):
    ok:      bool
    message: Optional[str] = None
    error:   Optional[str] = None
