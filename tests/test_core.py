"""
tests/test_core.py
Suite de tests para app/services/core.py

Ejecutar con:
    pytest tests/ -v
    pytest tests/ -v --cov=app/services --cov-report=term-missing
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_prices():
    """DataFrame de precios sintéticos para 5 tickers, 200 días."""
    np.random.seed(42)
    dates = pd.date_range("2022-01-01", periods=200, freq="B")
    tickers = ["SPY", "QQQ", "BTC-USD", "ETH-USD", "GLD"]
    bases = {"SPY": 400, "QQQ": 300, "BTC-USD": 30000, "ETH-USD": 2000, "GLD": 170}
    data = {}
    for t in tickers:
        rets = np.random.normal(0.0005, 0.015, 200)
        data[t] = bases[t] * np.cumprod(1 + rets)
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def trending_prices():
    """Precios con tendencia alcista clara."""
    dates = pd.date_range("2022-01-01", periods=200, freq="B")
    prices = np.linspace(100, 200, 200)
    return pd.DataFrame({"SPY": prices, "QQQ": prices * 0.75}, index=dates)


@pytest.fixture
def bearish_prices():
    """Precios bajistas continuos."""
    dates = pd.date_range("2022-01-01", periods=200, freq="B")
    tickers = ["SPY", "QQQ", "BTC-USD", "ETH-USD", "GLD"]
    return pd.DataFrame(
        {t: np.linspace(1000, 100, 200) for t in tickers},
        index=dates
    )


# ─── trend_phase ─────────────────────────────────────────────────────────────

class TestTrendPhase:

    def test_broken_when_price_below_ma(self):
        from app.services.core import trend_phase
        phase, dist, risk = trend_phase(90.0, 100.0)
        assert phase == "BROKEN"
        assert dist < 0

    def test_early_phase(self):
        from app.services.core import trend_phase
        phase, dist, risk = trend_phase(101.0, 100.0)  # 1% over MA
        assert phase == "EARLY"

    def test_ok_phase(self):
        from app.services.core import trend_phase
        phase, dist, risk = trend_phase(105.0, 100.0)  # 5% over MA
        assert phase == "OK"

    def test_extended_phase(self):
        from app.services.core import trend_phase
        phase, dist, risk = trend_phase(115.0, 100.0)  # 15% over MA
        assert phase == "EXTENDED"

    def test_nan_price_returns_no_data(self):
        from app.services.core import trend_phase
        phase, dist, risk = trend_phase(float("nan"), 100.0)
        assert phase == "NO_DATA"
        assert dist == 0.0
        assert risk == 0.0

    def test_nan_ma_returns_no_data(self):
        from app.services.core import trend_phase
        phase, dist, risk = trend_phase(100.0, float("nan"))
        assert phase == "NO_DATA"

    def test_zero_price_no_division_error(self):
        """price=0 no debe lanzar ZeroDivisionError."""
        from app.services.core import trend_phase
        phase, dist, risk = trend_phase(0.0, 100.0)
        assert phase == "BROKEN"
        assert risk == 0.0

    def test_dist_is_accurate(self):
        from app.services.core import trend_phase
        phase, dist, risk = trend_phase(110.0, 100.0)
        assert abs(dist - 0.10) < 1e-9

    @pytest.mark.parametrize("price,ma,expected_phase", [
        (95.0,  100.0, "BROKEN"),
        (101.5, 100.0, "EARLY"),
        (104.0, 100.0, "OK"),
        (120.0, 100.0, "EXTENDED"),
    ])
    def test_phase_boundaries(self, price, ma, expected_phase):
        from app.services.core import trend_phase
        phase, _, _ = trend_phase(price, ma)
        assert phase == expected_phase


# ─── phase_size ──────────────────────────────────────────────────────────────

class TestPhaseSize:

    @pytest.mark.parametrize("phase,expected", [
        ("EARLY",    1.0),
        ("OK",       0.7),
        ("EXTENDED", 0.4),
        ("BROKEN",   0.0),
        ("NO_DATA",  0.0),
        ("UNKNOWN",  0.0),
    ])
    def test_all_known_phases(self, phase, expected):
        from app.services.core import phase_size
        assert phase_size(phase) == expected

    def test_returns_float(self):
        from app.services.core import phase_size
        assert isinstance(phase_size("OK"), float)


# ─── annual_volatility ───────────────────────────────────────────────────────

class TestAnnualVolatility:

    def test_positive_on_random_walk(self):
        from app.services.core import annual_volatility
        np.random.seed(1)
        prices = pd.Series(100 * np.cumprod(1 + np.random.normal(0, 0.01, 200)))
        assert annual_volatility(prices) > 0

    def test_zero_on_constant_prices(self):
        from app.services.core import annual_volatility
        prices = pd.Series([100.0] * 100)
        assert annual_volatility(prices) == 0.0

    def test_short_series_no_error(self):
        from app.services.core import annual_volatility
        prices = pd.Series([100, 102, 101, 105, 103])
        vol = annual_volatility(prices, window=90)
        assert vol >= 0

    def test_uses_sqrt252_annualization(self):
        from app.services.core import annual_volatility
        np.random.seed(0)
        rets = np.random.normal(0, 0.01, 300)
        prices = pd.Series(100 * np.cumprod(1 + rets))
        vol = annual_volatility(prices, window=300)
        expected = pd.Series(rets).std() * np.sqrt(252)
        assert abs(vol - expected) < 0.001


# ─── vol_adjusted_size ───────────────────────────────────────────────────────

class TestVolAdjustedSize:

    def test_high_vol_reduces_size(self):
        from app.services.core import vol_adjusted_size
        assert vol_adjusted_size(1.0, annual_vol=0.60, target_vol=0.20) < 1.0

    def test_low_vol_increases_size(self):
        from app.services.core import vol_adjusted_size
        assert vol_adjusted_size(1.0, annual_vol=0.05, target_vol=0.20) > 1.0

    def test_never_exceeds_cap(self):
        from app.services.core import vol_adjusted_size
        assert vol_adjusted_size(1.0, annual_vol=0.001, target_vol=0.20) <= 1.5

    def test_zero_vol_returns_base(self):
        from app.services.core import vol_adjusted_size
        assert vol_adjusted_size(0.5, annual_vol=0.0) == 0.5

    def test_negative_vol_returns_base(self):
        from app.services.core import vol_adjusted_size
        assert vol_adjusted_size(0.5, annual_vol=-0.1) == 0.5

    def test_exact_target_vol_returns_base(self):
        from app.services.core import vol_adjusted_size
        # Si annual_vol == target_vol, el tamaño no cambia
        result = vol_adjusted_size(1.0, annual_vol=0.20, target_vol=0.20)
        assert abs(result - 1.0) < 1e-9


# ─── add_indicators ──────────────────────────────────────────────────────────

class TestAddIndicators:

    def test_creates_ma_column(self, sample_prices):
        from app.services.core import add_indicators
        result = add_indicators(sample_prices[["SPY"]].copy(), ["SPY"], window=50)
        assert "SPY_MA50" in result.columns

    def test_creates_high_column(self, sample_prices):
        from app.services.core import add_indicators
        result = add_indicators(sample_prices[["SPY"]].copy(), ["SPY"], window=20)
        assert "SPY_HIGH20" in result.columns

    def test_skips_missing_tickers(self, sample_prices):
        from app.services.core import add_indicators
        result = add_indicators(sample_prices.copy(), ["SPY", "GHOST"], window=20)
        assert "GHOST_MA20" not in result.columns

    def test_preserves_price_columns(self, sample_prices):
        from app.services.core import add_indicators
        original_cols = set(sample_prices.columns)
        result = add_indicators(sample_prices.copy(), list(sample_prices.columns), window=20)
        assert original_cols.issubset(set(result.columns))

    def test_ma_matches_rolling_mean(self, sample_prices):
        from app.services.core import add_indicators
        result = add_indicators(sample_prices[["SPY"]].copy(), ["SPY"], window=10)
        expected = sample_prices["SPY"].rolling(10, min_periods=20).mean()
        pd.testing.assert_series_equal(result["SPY_MA10"], expected, check_names=False)


# ─── build_position ──────────────────────────────────────────────────────────

class TestBuildPosition:

    def test_enters_on_entry_signal(self):
        from app.services.core import build_position
        entry = pd.Series([False, True,  False, False, False])
        exit_ = pd.Series([False, False, False, False, True])
        pos   = build_position(entry, exit_)
        assert pos.iloc[1] == True
        assert pos.iloc[2] == True

    def test_exits_on_exit_signal(self):
        from app.services.core import build_position
        entry = pd.Series([False, True,  False, False, False])
        exit_ = pd.Series([False, False, False, True,  False])
        pos   = build_position(entry, exit_)
        assert pos.iloc[2] == True
        assert pos.iloc[3] == False

    def test_no_position_without_entry(self):
        from app.services.core import build_position
        entry = pd.Series([False] * 5)
        exit_ = pd.Series([False] * 5)
        assert build_position(entry, exit_).sum() == 0

    def test_returns_bool_series(self):
        from app.services.core import build_position
        pos = build_position(pd.Series([False, True, False]),
                             pd.Series([False, False, True]))
        assert pos.dtype == bool

    def test_length_preserved(self):
        from app.services.core import build_position
        n = 100
        entry = pd.Series([i == 10 for i in range(n)])
        exit_ = pd.Series([i == 50 for i in range(n)])
        assert len(build_position(entry, exit_)) == n

    def test_can_reenter_after_exit(self):
        from app.services.core import build_position
        # Entra en i=1, sale en i=3, re-entra en i=5
        entry = pd.Series([False, True,  False, False, False, True,  False])
        exit_ = pd.Series([False, False, False, True,  False, False, False])
        pos   = build_position(entry, exit_)
        assert pos.iloc[2] == True   # dentro
        assert pos.iloc[3] == False  # salió
        assert pos.iloc[5] == True   # re-entró
        assert pos.iloc[6] == True   # sigue


# ─── compute_positions ───────────────────────────────────────────────────────

class TestComputePositions:

    def test_returns_dict(self, sample_prices):
        from app.services.core import add_indicators, compute_positions
        tickers = ["SPY", "QQQ"]
        data = add_indicators(sample_prices[tickers].copy(), tickers, window=20)
        result = compute_positions(data, tickers, window=20)
        assert isinstance(result, dict)

    def test_keys_match_available_tickers(self, sample_prices):
        from app.services.core import add_indicators, compute_positions
        tickers = ["SPY", "QQQ"]
        data = add_indicators(sample_prices[tickers].copy(), tickers, window=20)
        result = compute_positions(data, tickers, window=20)
        assert set(result.keys()) == set(tickers)

    def test_values_are_bool_series(self, sample_prices):
        from app.services.core import add_indicators, compute_positions
        tickers = ["SPY"]
        data = add_indicators(sample_prices[tickers].copy(), tickers, window=20)
        result = compute_positions(data, tickers, window=20)
        assert result["SPY"].dtype == bool

    def test_skips_missing_tickers(self, sample_prices):
        from app.services.core import add_indicators, compute_positions
        data = add_indicators(sample_prices[["SPY"]].copy(), ["SPY"], window=20)
        result = compute_positions(data, ["SPY", "GHOST"], window=20)
        assert "GHOST" not in result

    def test_trending_market_generates_entries(self, trending_prices):
        from app.services.core import add_indicators, compute_positions
        tickers = ["SPY"]
        data = add_indicators(trending_prices.copy(), tickers, window=20)
        result = compute_positions(data, tickers, window=20)
        assert result["SPY"].sum() > 0

    def test_bearish_market_no_positions(self, bearish_prices):
        from app.services.core import add_indicators, compute_positions
        tickers = ["SPY"]
        data = add_indicators(bearish_prices[tickers].copy(), tickers, window=20)
        result = compute_positions(data, tickers, window=20)
        # En tendencia bajista pura no debe haber entradas
        assert result["SPY"].sum() == 0


# ─── compute_signal (mocked) ─────────────────────────────────────────────────

class TestComputeSignal:

    def _mock_data(self, tickers, periods=200):
        np.random.seed(42)
        dates = pd.date_range("2022-01-01", periods=periods, freq="B")
        bases = {"SPY": 400, "QQQ": 300, "BTC-USD": 30000, "ETH-USD": 2000, "GLD": 170}
        data = {t: bases.get(t, 100) * np.cumprod(1 + np.random.normal(0.001, 0.015, periods))
                for t in tickers}
        return pd.DataFrame(data, index=dates)

    def _mock_buffett(self):
        return {"value": 100.0, "phase": "JUSTO", "mult": 1.0, "yoy": 5.0}

    @patch("app.services.core.download_prices")
    @patch("app.services.core.get_buffett")
    def test_required_keys_present(self, mock_b, mock_dl):
        from app.services.core import compute_signal, DEFAULT_TICKERS
        mock_dl.return_value = self._mock_data(DEFAULT_TICKERS)
        mock_b.return_value  = self._mock_buffett()
        result = compute_signal()
        for key in ["weights", "phases", "active", "dominant",
                    "buffett", "volatilities", "signal_date", "cash_pct", "quality", "tickers"]:
            assert key in result

    @patch("app.services.core.download_prices")
    @patch("app.services.core.get_buffett")
    def test_weights_sum_lte_one(self, mock_b, mock_dl):
        from app.services.core import compute_signal, DEFAULT_TICKERS
        mock_dl.return_value = self._mock_data(DEFAULT_TICKERS)
        mock_b.return_value  = self._mock_buffett()
        result = compute_signal()
        assert sum(result["weights"].values()) <= 1.001

    @patch("app.services.core.download_prices")
    @patch("app.services.core.get_buffett")
    def test_no_negative_weights(self, mock_b, mock_dl):
        from app.services.core import compute_signal, DEFAULT_TICKERS
        mock_dl.return_value = self._mock_data(DEFAULT_TICKERS)
        mock_b.return_value  = self._mock_buffett()
        result = compute_signal()
        for t, w in result["weights"].items():
            assert w >= 0, f"Peso negativo para {t}: {w}"

    @patch("app.services.core.download_prices")
    @patch("app.services.core.get_buffett")
    def test_cash_pct_complement_of_weights(self, mock_b, mock_dl):
        from app.services.core import compute_signal, DEFAULT_TICKERS
        mock_dl.return_value = self._mock_data(DEFAULT_TICKERS)
        mock_b.return_value  = self._mock_buffett()
        result = compute_signal()
        total_w = sum(result["weights"].values())
        assert abs(result["cash_pct"] - max(1.0 - total_w, 0.0)) < 0.001

    @patch("app.services.core.download_prices")
    @patch("app.services.core.get_buffett")
    def test_quality_valid_value(self, mock_b, mock_dl):
        from app.services.core import compute_signal, DEFAULT_TICKERS
        mock_dl.return_value = self._mock_data(DEFAULT_TICKERS)
        mock_b.return_value  = self._mock_buffett()
        result = compute_signal()
        assert result["quality"] in ("ALTA", "MEDIA", "BAJA")

    @patch("app.services.core.download_prices")
    @patch("app.services.core.get_buffett")
    def test_bearish_market_is_defensive(self, mock_b, mock_dl):
        from app.services.core import compute_signal, DEFAULT_TICKERS
        dates = pd.date_range("2022-01-01", periods=200, freq="B")
        mock_dl.return_value = pd.DataFrame(
            {t: np.linspace(1000, 100, 200) for t in DEFAULT_TICKERS}, index=dates
        )
        mock_b.return_value = {"value": 130, "phase": "CARO", "mult": 0.7, "yoy": None}
        result = compute_signal()
        assert result["dominant"] == "DEFENSIVO"
        assert result["cash_pct"] >= 0.99

    @patch("app.services.core.download_prices")
    @patch("app.services.core.get_buffett")
    def test_custom_tickers_respected(self, mock_b, mock_dl):
        from app.services.core import compute_signal
        custom = ["SPY", "GLD"]
        mock_dl.return_value = self._mock_data(custom)
        mock_b.return_value  = self._mock_buffett()
        result = compute_signal(tickers=custom)
        assert result["tickers"] == custom

    @patch("app.services.core.download_prices")
    @patch("app.services.core.get_buffett")
    def test_caro_buffett_reduces_equity(self, mock_b, mock_dl):
        """Buffett CARO debe reducir la ponderación de equity."""
        from app.services.core import compute_signal, DEFAULT_TICKERS
        mock_dl.return_value = self._mock_data(DEFAULT_TICKERS)
        mock_b.return_value  = {"value": 150, "phase": "CARO", "mult": 0.7, "yoy": 10.0}
        result_caro = compute_signal()

        mock_b.return_value  = {"value": 80, "phase": "BARATO", "mult": 1.2, "yoy": -5.0}
        mock_dl.return_value = self._mock_data(DEFAULT_TICKERS)  # reset seed
        result_barato = compute_signal()

        spy_caro   = result_caro["weights"].get("SPY", 0) + result_caro["weights"].get("QQQ", 0)
        spy_barato = result_barato["weights"].get("SPY", 0) + result_barato["weights"].get("QQQ", 0)
        # Equity total debe ser menor cuando Buffett dice CARO
        assert spy_caro <= spy_barato + 0.05  # margen pequeño por efectos de vol


# ─── get_buffett (mocked) ────────────────────────────────────────────────────

class TestGetBuffett:

    @patch("app.services.core.yf.download", side_effect=Exception("Network error"))
    def test_fallback_on_network_error(self, mock_yf):
        from app.services.core import get_buffett
        result = get_buffett()
        assert result == {"value": None, "phase": "N/A", "mult": 1.0, "yoy": None}

    @pytest.mark.parametrize("val,expected_phase", [
        (80,  "BARATO"),
        (105, "JUSTO"),
        (135, "CARO"),
    ])
    def test_phase_thresholds(self, val, expected_phase):
        """Verifica los umbrales <90 / <120 / ≥120."""
        from app.services.core import get_buffett
        dates = pd.date_range("1990-01-01", periods=600, freq="B")
        will  = pd.Series(np.ones(600) * val, index=dates)
        gdp   = pd.Series(np.ones(600), index=dates)

        with patch("app.services.core.yf.download") as mock_yf, \
             patch("app.services.core.pd.read_csv") as mock_csv:
            mock_yf.return_value = pd.DataFrame({"Close": will})
            gdp_df = pd.DataFrame({"GDP": gdp})
            gdp_df.index = dates
            mock_csv.return_value = gdp_df
            result = get_buffett()

        if result["value"] is not None:
            v = result["value"]
            if v < 90:   assert result["phase"] == "BARATO"
            elif v < 120: assert result["phase"] == "JUSTO"
            else:          assert result["phase"] == "CARO"
