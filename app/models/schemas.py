"""
schemas.py — Pydantic models for request / response validation.

v3: Institutional metrics suite added.  Flat backward-compat aliases
    kept at the top level of BacktestMetrics so existing frontend
    consumers don't break.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any


# ── Signal ────────────────────────────────────────────────────────────────────

class PhaseInfo(BaseModel):
    phase: str
    dist:  float
    risk:  float
    price: Optional[float] = None


class BuffettInfo(BaseModel):
    value: Optional[float]
    phase: str
    mult:  float
    yoy:   Optional[float]


class RiskMeta(BaseModel):
    portfolio_vol: Optional[float] = None
    vol_scale:     Optional[float] = None


class SignalResponse(BaseModel):
    weights:      dict[str, float]
    phases:       dict[str, PhaseInfo]
    active:       dict[str, bool]
    dominant:     str
    regime:       Optional[str]        = None
    regime_max:   Optional[float]      = None
    vix:          Optional[float]      = None
    buffett:      BuffettInfo
    volatilities: dict[str, float]
    signal_date:  str
    cash_pct:     float
    quality:      str
    tickers:      list[str]
    risk:         Optional[RiskMeta]   = None


# ── Institutional Metrics (nested) ────────────────────────────────────────────

class PerformanceMetrics(BaseModel):
    cagr:          float
    total_return:  float
    volatility:    float
    final_capital: float
    years:         float
    cagr_bench:    Optional[float] = None


class RiskAdjustedMetrics(BaseModel):
    sharpe:      float
    sortino:     float
    calmar:      float
    ulcer_index: float


class DrawdownMetrics(BaseModel):
    max_drawdown:     float
    current_drawdown: float
    max_dd_duration:  int
    avg_dd_duration:  float
    recovery_factor:  float


class DistributionMetrics(BaseModel):
    skewness: float
    kurtosis: float
    var_95:   float
    cvar_95:  float
    var_99:   Optional[float] = None
    cvar_99:  Optional[float] = None


class AlphaMetrics(BaseModel):
    alpha:             float
    beta:              float
    information_ratio: float
    tracking_error:    float


class TradeStats(BaseModel):
    win_rate:       float
    profit_factor:  float
    expectancy:     float
    avg_win:        float
    avg_loss:       float
    win_loss_ratio: float
    n_periods:      int


class BenchmarkMetrics(BaseModel):
    cagr:         float
    volatility:   float
    max_drawdown: float
    sharpe:       float


class InstitutionalMetrics(BaseModel):
    # Nested sections
    performance:   Optional[PerformanceMetrics]   = None
    risk_adjusted: Optional[RiskAdjustedMetrics]  = None
    drawdown:      Optional[DrawdownMetrics]       = None
    distribution:  Optional[DistributionMetrics]  = None
    alpha:         Optional[AlphaMetrics]          = None
    trade_stats:   Optional[TradeStats]            = None
    benchmark:     Optional[BenchmarkMetrics]      = None

    # Flat aliases for backward compatibility
    cagr:          Optional[float] = None
    cagr_bench:    Optional[float] = None
    sharpe:        Optional[float] = None
    sortino:       Optional[float] = None
    calmar:        Optional[float] = None
    max_drawdown:  Optional[float] = None
    volatility:    Optional[float] = None
    win_rate:      Optional[float] = None
    total_return:  Optional[float] = None
    final_capital: Optional[float] = None
    years:         Optional[float] = None


# ── Backtest ──────────────────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    tickers:         Optional[list[str]] = None
    start:           str   = "2010-01-01"
    initial_capital: float = Field(default=10_000, gt=0)
    rebalance_freq:  str   = "W"
    include_costs:   bool  = True
    don_window:      int   = Field(default=100, ge=20, le=300)
    ma_window:       int   = Field(default=50,  ge=10, le=200)
    vol_target:      float = Field(default=0.12, gt=0, le=1.0)


class EquityPoint(BaseModel):
    date:          str
    strategy:      float
    benchmark:     float
    bench_60_40:   Optional[float] = None
    bench_ew:      Optional[float] = None
    regime:        Optional[str]   = None
    weights:       Optional[dict[str, float]] = None


class BacktestResponse(BaseModel):
    equity_curve:    list[EquityPoint]
    metrics:         InstitutionalMetrics
    weekly_returns:  list[float]
    drawdown_series: list[float]
    dates:           list[str]
    turnover_series: Optional[list[float]] = None
    config:          Optional[dict[str, Any]] = None


# ── Stress Test ───────────────────────────────────────────────────────────────

class StressTestResponse(BaseModel):
    scenario:          str
    period:            str
    strategy_return:   float
    benchmark_return:  float
    outperformance:    float
    scenario_max_dd:   Optional[float]     = None
    equity_curve:      list[EquityPoint]


# ── Walk-Forward ─────────────────────────────────────────────────────────────

class WalkForwardWindow(BaseModel):
    period:       str
    cagr:         float
    sharpe:       float
    sortino:      Optional[float] = None
    max_drawdown: float
    calmar:       Optional[float] = None


class WalkForwardSummary(BaseModel):
    avg_cagr:          float
    std_cagr:          float
    median_cagr:       float
    avg_sharpe:        float
    std_sharpe:        float
    pct_positive_cagr: float
    worst_dd:          float
    avg_dd:            float


class WalkForwardResponse(BaseModel):
    windows:   list[WalkForwardWindow]
    n_windows: int
    summary:   WalkForwardSummary


# ── Monte Carlo ───────────────────────────────────────────────────────────────

class MonteCarloDistribution(BaseModel):
    p5:  float
    p25: Optional[float] = None
    p50: float
    p75: Optional[float] = None
    p95: float


class MonteCarloResponse(BaseModel):
    n_simulations:       int
    n_periods_weeks:     int
    horizon_years:       float
    prob_positive_cagr:  float
    prob_dd_gt_30:       float
    cagr:                MonteCarloDistribution
    max_drawdown:        MonteCarloDistribution
    sharpe:              MonteCarloDistribution


# ── Analyzer ─────────────────────────────────────────────────────────────────

class AnalyzerRequest(BaseModel):
    ticker:          str
    current_tickers: Optional[list[str]] = None


class PortfolioImpact(BaseModel):
    sharpe_before: float
    sharpe_after:  float
    vol_before:    float
    vol_after:     float
    delta_sharpe:  float


class CandidateMetrics(BaseModel):
    sharpe:     float
    max_dd:     float
    annual_vol: float
    annual_ret: float
    avg_corr:   float


class AnalyzerResponse(BaseModel):
    ticker:            str
    verdict:           str    # INCLUDE | WATCH | DISCARD
    score:             int
    metrics:           CandidateMetrics
    correlations:      dict[str, float]
    portfolio_impact:  PortfolioImpact
    suggested_sleeve:  str


# ── Portfolio Config ──────────────────────────────────────────────────────────

class AssetConfig(BaseModel):
    ticker:  str
    sleeve:  Optional[str] = None
    enabled: bool = True
    notes:   Optional[str] = None


class PortfolioConfigRequest(BaseModel):
    assets:          list[AssetConfig]
    donchian_window: int   = 100
    ma_exit_window:  int   = 50
    max_position:    float = 0.40
    vol_target:      float = 0.12


# ── Telegram ─────────────────────────────────────────────────────────────────

class TelegramRequest(BaseModel):
    message: Optional[str] = None


class TelegramResponse(BaseModel):
    ok:      bool
    message: Optional[str] = None
    error:   Optional[str] = None
