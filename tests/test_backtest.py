"""
tests/test_backtest.py
Suite de tests para app/services/backtest.py

Ejecutar con:
    pytest tests/ -v
    pytest tests/ -v --cov=app/services --cov-report=term-missing
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock


# ─── Fixtures ────────────────────────────────────────────────────────────────

DEFAULT_TICKERS = ["SPY", "QQQ", "BTC-USD", "ETH-USD", "GLD"]


def make_prices(tickers=None, periods=300, trend="flat", seed=42):
    """Genera precios sintéticos controlados."""
    np.random.seed(seed)
    tickers = tickers or DEFAULT_TICKERS
    dates   = pd.date_range("2020-01-01", periods=periods, freq="B")
    bases   = {"SPY": 300, "QQQ": 250, "BTC-USD": 10000, "ETH-USD": 500, "GLD": 150}
    data    = {}
    for t in tickers:
        base = bases.get(t, 100)
        if trend == "up":
            prices = base * np.cumprod(1 + np.random.normal(0.002, 0.012, periods))
        elif trend == "down":
            prices = base * np.cumprod(1 + np.random.normal(-0.002, 0.012, periods))
        else:
            prices = base * np.cumprod(1 + np.random.normal(0.0, 0.012, periods))
        data[t] = prices
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def mock_bullish_prices():
    return make_prices(trend="up")


@pytest.fixture
def mock_bearish_prices():
    return make_prices(trend="down")


@pytest.fixture
def mock_flat_prices():
    return make_prices(trend="flat")


@pytest.fixture
def mock_buffett():
    return {"value": 100.0, "phase": "JUSTO", "mult": 1.0, "yoy": 5.0}


# ─── _max_drawdown ───────────────────────────────────────────────────────────

class TestMaxDrawdown:

    def test_no_drawdown_on_rising_prices(self):
        from app.services.backtest import _max_drawdown
        prices = pd.Series(np.linspace(100, 200, 100))
        dd = _max_drawdown(prices)
        assert abs(dd) < 1e-9

    def test_full_loss_returns_minus_one(self):
        from app.services.backtest import _max_drawdown
        prices = pd.Series([100, 50, 10, 1])
        dd = _max_drawdown(prices)
        assert dd < -0.98

    def test_known_drawdown(self):
        from app.services.backtest import _max_drawdown
        # Sube a 200 y cae a 100 → drawdown = -50%
        prices = pd.Series([100, 150, 200, 150, 100, 120])
        dd = _max_drawdown(prices)
        assert abs(dd - (-0.50)) < 0.001

    def test_returns_float(self):
        from app.services.backtest import _max_drawdown
        prices = pd.Series([100, 90, 80, 95])
        assert isinstance(_max_drawdown(prices), float)

    def test_always_non_positive(self):
        from app.services.backtest import _max_drawdown
        np.random.seed(0)
        prices = pd.Series(100 * np.cumprod(1 + np.random.normal(0, 0.02, 200)))
        assert _max_drawdown(prices) <= 0


# ─── _sharpe ─────────────────────────────────────────────────────────────────

class TestSharpe:

    def test_positive_returns_positive_sharpe(self):
        from app.services.backtest import _sharpe
        rets = pd.Series(np.ones(252) * 0.001)
        assert _sharpe(rets) > 0

    def test_negative_returns_negative_sharpe(self):
        from app.services.backtest import _sharpe
        rets = pd.Series(np.ones(252) * -0.001)
        assert _sharpe(rets) < 0

    def test_zero_std_returns_zero(self):
        from app.services.backtest import _sharpe
        rets = pd.Series([0.0] * 100)
        assert _sharpe(rets) == 0

    def test_higher_returns_higher_sharpe(self):
        from app.services.backtest import _sharpe
        np.random.seed(1)
        low_rets  = pd.Series(np.random.normal(0.0001, 0.01, 252))
        high_rets = pd.Series(np.random.normal(0.001,  0.01, 252))
        assert _sharpe(high_rets) > _sharpe(low_rets)


# ─── _suggest_sleeve ─────────────────────────────────────────────────────────

class TestSuggestSleeve:

    @pytest.mark.parametrize("ticker,expected", [
        ("BTC-USD", "crypto"),
        ("ETH-USD", "crypto"),
        ("SOL-USD", "crypto"),
        ("GLD",     "commodity"),
        ("SLV",     "commodity"),
        ("IAU",     "commodity"),
        ("TLT",     "bonds"),
        ("IEF",     "bonds"),
        ("BND",     "bonds"),
        ("AAPL",    "equity"),
        ("MSFT",    "equity"),
        ("SPY",     "equity"),
    ])
    def test_sleeve_classification(self, ticker, expected):
        from app.services.backtest import _suggest_sleeve
        assert _suggest_sleeve(ticker, {}) == expected


# ─── _score_candidate ────────────────────────────────────────────────────────

class TestScoreCandidate:

    def test_score_within_bounds(self):
        from app.services.backtest import _score_candidate
        score = _score_candidate(sharpe=1.0, avg_corr=0.3, max_dd=-0.15, delta_sharpe=0.02)
        assert 0 <= score <= 100

    def test_high_sharpe_increases_score(self):
        from app.services.backtest import _score_candidate
        low  = _score_candidate(sharpe=0.2, avg_corr=0.3, max_dd=-0.15, delta_sharpe=0.0)
        high = _score_candidate(sharpe=2.0, avg_corr=0.3, max_dd=-0.15, delta_sharpe=0.0)
        assert high > low

    def test_high_correlation_decreases_score(self):
        from app.services.backtest import _score_candidate
        low_corr  = _score_candidate(sharpe=1.0, avg_corr=0.1, max_dd=-0.15, delta_sharpe=0.0)
        high_corr = _score_candidate(sharpe=1.0, avg_corr=0.9, max_dd=-0.15, delta_sharpe=0.0)
        assert low_corr > high_corr

    def test_positive_delta_sharpe_increases_score(self):
        from app.services.backtest import _score_candidate
        neg = _score_candidate(sharpe=1.0, avg_corr=0.3, max_dd=-0.15, delta_sharpe=-0.1)
        pos = _score_candidate(sharpe=1.0, avg_corr=0.3, max_dd=-0.15, delta_sharpe=+0.1)
        assert pos > neg

    def test_deep_drawdown_penalizes(self):
        from app.services.backtest import _score_candidate
        mild = _score_candidate(sharpe=1.0, avg_corr=0.3, max_dd=-0.10, delta_sharpe=0.0)
        deep = _score_candidate(sharpe=1.0, avg_corr=0.3, max_dd=-0.80, delta_sharpe=0.0)
        assert mild >= deep


# ─── dd_penalty ──────────────────────────────────────────────────────────────

class TestDdPenalty:

    @pytest.mark.parametrize("dd,expected", [
        (-0.10, 5),
        (-0.25, 0),
        (-0.50, -5),
        (-0.70, -12),
    ])
    def test_penalty_tiers(self, dd, expected):
        from app.services.backtest import dd_penalty
        assert dd_penalty(dd) == expected


# ─── run_backtest ─────────────────────────────────────────────────────────────

class TestRunBacktest:

    @patch("app.services.backtest.download_prices")
    @patch("app.services.core.get_buffett")
    def test_returns_required_keys(self, mock_b, mock_dl):
        from app.services.backtest import run_backtest
        mock_dl.return_value = make_prices(trend="up")
        mock_b.return_value  = {"value": 100, "phase": "JUSTO", "mult": 1.0, "yoy": 5.0}
        result = run_backtest(start="2020-01-01")
        for key in ["equity_curve", "metrics", "weekly_returns", "drawdown_series", "dates"]:
            assert key in result

    @patch("app.services.backtest.download_prices")
    @patch("app.services.core.get_buffett")
    def test_metrics_keys_present(self, mock_b, mock_dl):
        from app.services.backtest import run_backtest
        mock_dl.return_value = make_prices(trend="up")
        mock_b.return_value  = {"value": 100, "phase": "JUSTO", "mult": 1.0, "yoy": 5.0}
        result = run_backtest()
        metrics = result["metrics"]
        for key in ["cagr", "sharpe", "sortino", "max_drawdown",
                    "volatility", "win_rate", "total_return", "final_capital"]:
            assert key in metrics

    @patch("app.services.backtest.download_prices")
    @patch("app.services.core.get_buffett")
    def test_equity_curve_starts_near_initial_capital(self, mock_b, mock_dl):
        from app.services.backtest import run_backtest
        mock_dl.return_value = make_prices(trend="flat")
        mock_b.return_value  = {"value": 100, "phase": "JUSTO", "mult": 1.0, "yoy": 5.0}
        result = run_backtest(initial_capital=10_000)
        first_val = result["equity_curve"][0]["strategy"]
        assert 8_000 <= first_val <= 12_000

    @patch("app.services.backtest.download_prices")
    @patch("app.services.core.get_buffett")
    def test_drawdown_always_non_positive(self, mock_b, mock_dl):
        from app.services.backtest import run_backtest
        mock_dl.return_value = make_prices(trend="up")
        mock_b.return_value  = {"value": 100, "phase": "JUSTO", "mult": 1.0, "yoy": 5.0}
        result = run_backtest()
        for dd in result["drawdown_series"]:
            assert dd <= 0.01  # pequeño margen por redondeo

    @patch("app.services.backtest.download_prices")
    @patch("app.services.core.get_buffett")
    def test_equity_curve_and_dates_same_length(self, mock_b, mock_dl):
        from app.services.backtest import run_backtest
        mock_dl.return_value = make_prices(trend="flat")
        mock_b.return_value  = {"value": 100, "phase": "JUSTO", "mult": 1.0, "yoy": 5.0}
        result = run_backtest()
        assert len(result["equity_curve"]) == len(result["dates"])

    @patch("app.services.backtest.download_prices")
    @patch("app.services.core.get_buffett")
    def test_bullish_market_positive_cagr(self, mock_b, mock_dl):
        from app.services.backtest import run_backtest
        mock_dl.return_value = make_prices(trend="up", periods=500)
        mock_b.return_value  = {"value": 80, "phase": "BARATO", "mult": 1.2, "yoy": -2.0}
        result = run_backtest()
        assert result["metrics"]["cagr"] > 0

    @patch("app.services.backtest.download_prices")
    @patch("app.services.core.get_buffett")
    def test_win_rate_between_0_and_100(self, mock_b, mock_dl):
        from app.services.backtest import run_backtest
        mock_dl.return_value = make_prices(trend="flat")
        mock_b.return_value  = {"value": 100, "phase": "JUSTO", "mult": 1.0, "yoy": 5.0}
        result = run_backtest()
        wr = result["metrics"]["win_rate"]
        assert 0 <= wr <= 100

    @patch("app.services.backtest.download_prices")
    def test_insufficient_data_returns_error(self, mock_dl):
        from app.services.backtest import run_backtest
        # Solo 10 filas → insuficiente para el backtest
        dates = pd.date_range("2020-01-01", periods=10, freq="B")
        mock_dl.return_value = pd.DataFrame(
            {t: np.ones(10) * 100 for t in DEFAULT_TICKERS}, index=dates
        )
        result = run_backtest()
        assert "error" in result


# ─── run_stress_test ──────────────────────────────────────────────────────────

class TestRunStressTest:

    def test_invalid_scenario_returns_error(self):
        from app.services.backtest import run_stress_test
        result = run_stress_test("nonexistent_scenario")
        assert "error" in result

    @patch("app.services.backtest.run_backtest")
    def test_returns_required_keys(self, mock_bt):
        from app.services.backtest import run_stress_test
        # Simular equity_curve que cubre el período COVID
        mock_bt.return_value = {
            "equity_curve": [
                {"date": "2020-02-19", "strategy": 10000, "benchmark": 10000},
                {"date": "2020-03-01", "strategy": 9500,  "benchmark": 9000},
                {"date": "2020-03-23", "strategy": 8500,  "benchmark": 7500},
            ]
        }
        result = run_stress_test("covid_2020")
        for key in ["scenario", "period", "strategy_return", "benchmark_return", "outperformance"]:
            assert key in result

    @patch("app.services.backtest.run_backtest")
    def test_outperformance_calculation(self, mock_bt):
        from app.services.backtest import run_stress_test
        mock_bt.return_value = {
            "equity_curve": [
                {"date": "2020-02-19", "strategy": 10000, "benchmark": 10000},
                {"date": "2020-03-23", "strategy": 9000,  "benchmark": 8000},
            ]
        }
        result = run_stress_test("covid_2020")
        # strategy: -10%, benchmark: -20%, outperformance: +10%
        assert abs(result["strategy_return"] - (-10.0)) < 0.1
        assert abs(result["benchmark_return"] - (-20.0)) < 0.1
        assert result["outperformance"] > 0

    @patch("app.services.backtest.run_backtest")
    def test_no_data_for_period_returns_error(self, mock_bt):
        from app.services.backtest import run_stress_test
        # El backtest retorna datos de otro período
        mock_bt.return_value = {
            "equity_curve": [
                {"date": "2023-01-01", "strategy": 10000, "benchmark": 10000},
            ]
        }
        result = run_stress_test("covid_2020")
        assert "error" in result

    @pytest.mark.parametrize("scenario_key", [
        "covid_2020", "ftx_2022", "rates_2022", "crypto_2018"
    ])
    def test_all_scenarios_defined(self, scenario_key):
        """Todos los escenarios deben estar en STRESS_SCENARIOS."""
        from app.services.backtest import STRESS_SCENARIOS
        assert scenario_key in STRESS_SCENARIOS

    @pytest.mark.parametrize("scenario_key", [
        "covid_2020", "ftx_2022", "rates_2022", "crypto_2018"
    ])
    def test_scenarios_have_required_fields(self, scenario_key):
        from app.services.backtest import STRESS_SCENARIOS
        sc = STRESS_SCENARIOS[scenario_key]
        assert "name" in sc
        assert "start" in sc
        assert "end" in sc


# ─── analyze_candidate ───────────────────────────────────────────────────────

class TestAnalyzeCandidate:

    @patch("app.services.backtest.download_prices")
    def test_unknown_ticker_returns_error(self, mock_dl):
        from app.services.backtest import analyze_candidate
        # Retornar datos sin el ticker buscado
        mock_dl.return_value = make_prices(["SPY", "QQQ"])
        result = analyze_candidate("FAKECOIN-USD")
        assert "error" in result

    @patch("app.services.backtest.download_prices")
    def test_returns_required_keys(self, mock_dl):
        from app.services.backtest import analyze_candidate
        mock_dl.return_value = make_prices(["SPY", "QQQ", "GLD"])
        result = analyze_candidate("GLD", current_tickers=["SPY", "QQQ"])
        for key in ["ticker", "verdict", "score", "metrics", "correlations",
                    "portfolio_impact", "suggested_sleeve"]:
            assert key in result

    @patch("app.services.backtest.download_prices")
    def test_verdict_valid_values(self, mock_dl):
        from app.services.backtest import analyze_candidate
        mock_dl.return_value = make_prices(["SPY", "QQQ", "GLD"])
        result = analyze_candidate("GLD", current_tickers=["SPY", "QQQ"])
        assert result["verdict"] in ("INCLUDE", "WATCH", "DISCARD")

    @patch("app.services.backtest.download_prices")
    def test_score_within_bounds(self, mock_dl):
        from app.services.backtest import analyze_candidate
        mock_dl.return_value = make_prices(["SPY", "QQQ", "GLD"])
        result = analyze_candidate("GLD", current_tickers=["SPY", "QQQ"])
        assert 0 <= result["score"] <= 100

    @patch("app.services.backtest.download_prices")
    def test_correlations_for_all_current_tickers(self, mock_dl):
        from app.services.backtest import analyze_candidate
        current = ["SPY", "QQQ"]
        mock_dl.return_value = make_prices(current + ["GLD"])
        result = analyze_candidate("GLD", current_tickers=current)
        for t in current:
            assert t in result["correlations"]

    @patch("app.services.backtest.download_prices")
    def test_correlation_values_between_minus1_and_1(self, mock_dl):
        from app.services.backtest import analyze_candidate
        mock_dl.return_value = make_prices(["SPY", "QQQ", "GLD"])
        result = analyze_candidate("GLD", current_tickers=["SPY", "QQQ"])
        for corr in result["correlations"].values():
            assert -1.0 <= corr <= 1.0

    @patch("app.services.backtest.download_prices")
    def test_download_error_returns_error(self, mock_dl):
        from app.services.backtest import analyze_candidate
        mock_dl.side_effect = RuntimeError("Network error")
        result = analyze_candidate("SOL-USD")
        assert "error" in result


# ─── _weights_at ─────────────────────────────────────────────────────────────

class TestWeightsAt:

    def test_weights_sum_lte_one(self):
        from app.services.backtest import _weights_at
        from app.services.core import add_indicators, compute_positions
        prices    = make_prices(trend="up", periods=200)
        tickers   = DEFAULT_TICKERS
        data      = add_indicators(prices.copy(), tickers, window=20)
        positions = compute_positions(data, tickers, window=20)
        weights   = _weights_at(data, positions, tickers, loc=150, window=20)
        assert sum(weights.values()) <= 1.001

    def test_no_negative_weights(self):
        from app.services.backtest import _weights_at
        from app.services.core import add_indicators, compute_positions
        prices    = make_prices(trend="up", periods=200)
        tickers   = DEFAULT_TICKERS
        data      = add_indicators(prices.copy(), tickers, window=20)
        positions = compute_positions(data, tickers, window=20)
        weights   = _weights_at(data, positions, tickers, loc=150, window=20)
        for t, w in weights.items():
            assert w >= 0

    def test_all_tickers_present_in_output(self):
        from app.services.backtest import _weights_at
        from app.services.core import add_indicators, compute_positions
        prices    = make_prices(trend="flat", periods=200)
        tickers   = DEFAULT_TICKERS
        data      = add_indicators(prices.copy(), tickers, window=20)
        positions = compute_positions(data, tickers, window=20)
        weights   = _weights_at(data, positions, tickers, loc=150, window=20)
        assert set(weights.keys()) == set(tickers)

    def test_bearish_market_all_zero_weights(self):
        from app.services.backtest import _weights_at
        from app.services.core import add_indicators, compute_positions
        prices    = make_prices(trend="down", periods=200)
        tickers   = DEFAULT_TICKERS
        data      = add_indicators(prices.copy(), tickers, window=20)
        positions = compute_positions(data, tickers, window=20)
        # En mercado bajista al final no debería haber posiciones
        weights = _weights_at(data, positions, tickers, loc=199, window=20)
        assert sum(weights.values()) < 0.01
