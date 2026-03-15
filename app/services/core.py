"""
core.py — Motor cuantitativo central v3.1

Mejoras v3:
- Umbrales de fase adaptativos por ATR (no más 3%/7% fijos para todos los activos)
- Multi-asset por sleeve: todos los activos activos reciben peso proporcional
- Momentum relativo 12-1 meses como factor de ponderación dentro de cada sleeve
- Safe haven inteligente (IEF/BIL cuando equities en BEAR total)
- Buffett multiplier continuo con interpolación lineal suave (no más 3 buckets)
- Quality score ponderado por peso real de cada posición
- Dual timeframe: Donchian50 + MA20 reduce whipsaws en la entrada
- Nuevos sleeves: "bonds" (safe haven) y "merval" (acciones argentinas)

Mejoras v3.1:
- REITs (VNQ, XLRE) como sleeve independiente de baja correlación
- Salida anticipada: si posición está en EXTENDED y momentum 1 mes < -4%, salir antes
- Factor de valor (52-week range position): activos más baratos reciben más peso

Fix Buffett cash:
- El multiplicador Buffett ya no se cancela por normalización cuando solo hay un sleeve activo.
  Si total_sw <= 1.0, el resto queda como cash. Solo se normaliza si total_sw > 1.0
  (mercado barato con Buffett > 1.0 podría superar 100%).
"""

import time
import numpy as np
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime
from typing import Optional

DEFAULT_TICKERS = [
    "SPY", "QQQ", "XLE", "XLV",        # equities USA
    "VNQ",                              # REITs
    "BTC-USD", "ETH-USD",               # crypto
    "GLD",                              # commodity
    "IEF", "BIL",                       # bonds / safe haven
    "GGAL.BA", "YPFD.BA",               # merval Argentina
]

SLEEVE_MAP = {
    # ETFs equity USA
    "SPY": "equity",  "QQQ": "equity",  "IVV": "equity",
    # Sectores USA
    "XLE": "equity",  "XLK": "equity",  "XLV": "equity",
    "XLP": "equity",  "XLF": "equity",  "XLI": "equity",
    # Internacional
    "EEM": "equity",  "EWJ": "equity",  "VEA": "equity",
    # Acciones USA individuales
    "TSM": "equity",  "V": "equity",    "MSFT": "equity",
    "AAPL": "equity", "NVDA": "equity",
    # REITs — sleeve propio para aprovechar baja correlación con equities
    "VNQ":   "reits", "XLRE": "reits", "IYR": "reits",
    # Merval / Argentina (Yahoo Finance: sufijo .BA = BYMA en ARS)
    "GGAL.BA":  "merval", "BMA.BA":   "merval", "YPFD.BA":  "merval",
    "TXAR.BA":  "merval", "ALUA.BA":  "merval", "PAMP.BA":  "merval",
    "TECO2.BA": "merval", "CEPU.BA":  "merval", "LOMA.BA":  "merval",
    "CRES.BA":  "merval", "SUPV.BA":  "merval", "MORI.BA":  "merval",
    # Crypto
    "BTC-USD": "crypto", "ETH-USD": "crypto", "SOL-USD": "crypto",
    # Commodities
    "GLD": "commodity", "SLV": "commodity", "IAU": "commodity",
    # Bonds / Safe Haven
    "IEF": "bonds", "TLT": "bonds", "BIL": "bonds", "SHY": "bonds",
}

CRYPTO_SPLIT = {
    "BTC-USD": 0.70,
    "ETH-USD": 0.30,
}

# ─── Caché en memoria para get_buffett (TTL = 6 horas) ───────────────────────
_buffett_cache: dict = {"data": None, "ts": 0.0}
_BUFFETT_TTL = 6 * 3600


# ─────────────────────────────────────────────────────────────────────────────
#  DESCARGA DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

def download_prices(tickers: list[str], start: str = "2018-01-01", retries: int = 3) -> pd.DataFrame:
    end = datetime.today().strftime("%Y-%m-%d")

    for attempt in range(retries):
        try:
            raw = yf.download(
                tickers,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
            )

            if isinstance(raw.columns, pd.MultiIndex):
                data = raw["Close"]
            else:
                data = raw[["Close"]] if "Close" in raw else raw
                data.columns = tickers[:1]

            data = data.dropna(how="all").ffill()

            if len(data) > 100:
                return data

            print(f"[download] intento {attempt+1}: solo {len(data)} rows, reintentando...")
        except Exception as e:
            print(f"[download] intento {attempt+1} fallido: {e}")

        time.sleep(3)

    raise RuntimeError(f"No se pudieron descargar datos para: {tickers}")


# ─────────────────────────────────────────────────────────────────────────────
#  INDICADORES TÉCNICOS
# ─────────────────────────────────────────────────────────────────────────────

def add_indicators(data: pd.DataFrame, tickers: list[str], window: int = 50) -> pd.DataFrame:
    """
    Agrega para cada ticker:
    - MA{window}: media móvil lenta (50 por defecto)
    - HIGH{window}: máximo de Donchian para entrada
    - MA20: media móvil rápida (filtro dual timeframe)
    - ATR20: Average True Range aproximado usando cambios de cierre
    """
    for t in tickers:
        if t not in data.columns:
            continue
        data[f"{t}_MA{window}"]   = data[t].rolling(window, min_periods=20).mean()
        data[f"{t}_HIGH{window}"] = data[t].rolling(window, min_periods=20).max()
        data[f"{t}_MA20"]         = data[t].rolling(20, min_periods=10).mean()
        daily_abs_change          = data[t].diff().abs()
        data[f"{t}_ATR20"]        = daily_abs_change.rolling(20, min_periods=10).mean()
    return data


# ─────────────────────────────────────────────────────────────────────────────
#  CONSTRUCCIÓN DE POSICIONES
# ─────────────────────────────────────────────────────────────────────────────

def build_position(entry: pd.Series, exit_: pd.Series) -> pd.Series:
    """
    Construye la serie de posición (True/False) de forma eficiente con NumPy.
    - Entra cuando entry=True y no hay posición abierta.
    - Sale cuando exit_=True y hay posición abierta.
    """
    ent   = entry.to_numpy(dtype=bool)
    ext   = exit_.to_numpy(dtype=bool)
    n     = len(ent)
    pos   = np.zeros(n, dtype=np.int8)
    state = np.int8(0)

    for i in range(1, n):
        if state == 0 and ent[i]:
            state = 1
        elif state == 1 and ext[i]:
            state = 0
        pos[i] = state

    return pd.Series(pos.astype(bool), index=entry.index)


def compute_positions(data: pd.DataFrame, tickers: list[str], window: int = 50) -> dict:
    """
    Dual timeframe + salida anticipada para reducir drawdown en EXTENDED:

    Entrada:
      - Breakout Donchian50 (precio > máximo anterior de 50 períodos)
      - Y precio sobre MA20 (confirma tendencia rápida alcista)

    Salida normal:
      - Precio bajo MA50 (tendencia lenta rota)

    Salida anticipada (mejora #3):
      - Si posición está en zona EXTENDED (precio > MA50 * 1.07)
        Y momentum de 1 mes < -4%, salir antes de que rompa la MA50.
    """
    positions = {}
    for t in tickers:
        if t not in data.columns:
            continue

        ma20_col = f"{t}_MA20"
        if ma20_col in data.columns:
            entry = (
                (data[t] > data[f"{t}_HIGH{window}"].shift(1)) &
                (data[t] > data[ma20_col])
            )
        else:
            entry = data[t] > data[f"{t}_HIGH{window}"].shift(1)

        exit_normal   = data[t] < data[f"{t}_MA{window}"]
        mom_1m        = data[t].pct_change(21)
        extended_zone = data[t] > data[f"{t}_MA{window}"] * 1.07
        exit_early    = extended_zone & (mom_1m < -0.04)
        exit_         = exit_normal | exit_early

        positions[t] = build_position(entry, exit_)
    return positions


# ─────────────────────────────────────────────────────────────────────────────
#  CLASIFICACIÓN DE FASE ADAPTATIVA (ATR)
# ─────────────────────────────────────────────────────────────────────────────

def trend_phase_adaptive(price: float, ma50: float, atr20: float) -> tuple:
    """
    Clasifica la fase de tendencia usando bandas de ATR adaptativas.
    Si ATR no disponible, usa umbrales fijos de fallback (3% / 7%).
    """
    if pd.isna(price) or pd.isna(ma50):
        return "NO_DATA", 0.0, 0.0

    dist = (price - ma50) / ma50 if ma50 != 0 else 0.0
    risk = abs(price - ma50) / price if price > 0 else 0.0

    if price < ma50:
        return "BROKEN", dist, risk

    distance_price = price - ma50

    if atr20 > 0:
        if distance_price < 0.5 * atr20:
            return "EARLY", dist, risk
        elif distance_price < 1.5 * atr20:
            return "OK", dist, risk
        else:
            return "EXTENDED", dist, risk
    else:
        if dist < 0.03:   return "EARLY",    dist, risk
        elif dist < 0.07: return "OK",        dist, risk
        else:             return "EXTENDED",  dist, risk


def trend_phase(price: float, ma: float) -> tuple:
    """Backward compatible — delega a trend_phase_adaptive sin ATR."""
    return trend_phase_adaptive(price, ma, 0.0)


def phase_size(phase: str) -> float:
    return {"EARLY": 1.0, "OK": 0.7, "EXTENDED": 0.4}.get(phase, 0.0)


# ─────────────────────────────────────────────────────────────────────────────
#  INDICADOR BUFFETT — MULTIPLICADOR CONTINUO
# ─────────────────────────────────────────────────────────────────────────────

def buffett_multiplier_continuous(ratio: float) -> float:
    """
    Escala continua con interpolación lineal.
      ratio ≤ 80  → 1.30  (mercado muy barato, máxima exposición)
      ratio = 130 → 0.85  (punto medio)
      ratio ≥ 180 → 0.40  (mercado extremadamente caro)
    """
    if ratio is None or pd.isna(ratio):
        return 1.0
    if ratio <= 80:
        return 1.30
    elif ratio <= 180:
        return 1.30 - ((ratio - 80) / 100.0) * 0.90
    else:
        return 0.40


def get_buffett(force_refresh: bool = False) -> dict:
    """
    Indicador Buffett = Wilshire 5000 / GDP × 100.
    Resultado cacheado en memoria 6 horas.
    Multiplicador calculado con escala continua (v3).
    """
    now = time.time()
    if not force_refresh and _buffett_cache["data"] and (now - _buffett_cache["ts"]) < _BUFFETT_TTL:
        return _buffett_cache["data"]

    try:
        wil = yf.download(
            "^W5000", start="1990-01-01", auto_adjust=True, progress=False
        )["Close"]

        gdp_df = pd.read_csv(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GDP",
            parse_dates=[0],
            index_col=0,
        )
        gdp     = gdp_df.iloc[:, 0].resample("D").ffill()
        df      = pd.concat([wil, gdp], axis=1).dropna()
        df.columns = ["WILL", "GDP"]
        buffett = (df["WILL"] / df["GDP"]) * 100

        val  = float(buffett.iloc[-1])
        yoy  = float(buffett.iloc[-1] - buffett.iloc[-252]) if len(buffett) > 252 else None
        mult = buffett_multiplier_continuous(val)

        if val < 90:    phase = "BARATO"
        elif val < 120: phase = "JUSTO"
        elif val < 150: phase = "CARO"
        else:           phase = "MUY_CARO"

        result = {
            "value": round(val, 1),
            "phase": phase,
            "mult":  round(mult, 3),
            "yoy":   round(yoy, 1) if yoy else None,
        }
        _buffett_cache["data"] = result
        _buffett_cache["ts"]   = now
        return result

    except Exception as e:
        print(f"[buffett] error: {e}")
        return {"value": None, "phase": "N/A", "mult": 1.0, "yoy": None}


# ─────────────────────────────────────────────────────────────────────────────
#  MOMENTUM Y FACTOR DE VALOR
# ─────────────────────────────────────────────────────────────────────────────

def compute_momentum(data: pd.DataFrame, ticker: str, slow: int = 252, skip: int = 21) -> float:
    """Momentum 12-1: retorno de los últimos 12 meses excluyendo el último mes."""
    if ticker not in data.columns or len(data) < slow:
        return 0.0
    p_now = float(data[ticker].iloc[-skip])
    p_old = float(data[ticker].iloc[-slow])
    if p_old <= 0 or pd.isna(p_now) or pd.isna(p_old):
        return 0.0
    return p_now / p_old - 1


def compute_value_score(data: pd.DataFrame, ticker: str, lookback: int = 252) -> float:
    """
    Factor de valor basado en la posición dentro del rango de 52 semanas.
    1.0 = activo en mínimo (barato), 0.0 = en máximo (caro). 0.5 = neutral.
    """
    if ticker not in data.columns or len(data) < lookback:
        return 0.5
    prices  = data[ticker].tail(lookback)
    high_52 = float(prices.max())
    low_52  = float(prices.min())
    current = float(data[ticker].iloc[-1])
    if high_52 <= low_52 or pd.isna(current):
        return 0.5
    position = (current - low_52) / (high_52 - low_52)
    return round(1.0 - position, 4)


# ─────────────────────────────────────────────────────────────────────────────
#  VOLATILIDAD
# ─────────────────────────────────────────────────────────────────────────────

def annual_volatility(prices: pd.Series, window: int = 90) -> float:
    """Volatilidad anualizada usando sqrt(252). Retorna 0.0 para series vacías."""
    returns = prices.pct_change().dropna()
    if len(returns) == 0:
        return 0.0
    tail = returns.tail(window) if len(returns) >= window else returns
    return float(tail.std() * np.sqrt(252))


def vol_adjusted_size(base_size: float, annual_vol: float, target_vol: float = 0.20) -> float:
    """Ajusta el tamaño de posición por volatilidad relativa al objetivo. Cap en 1.5x."""
    if annual_vol <= 0:
        return base_size
    return min(base_size * (target_vol / annual_vol), 1.5)


# ─────────────────────────────────────────────────────────────────────────────
#  ALLOCACIÓN MULTI-ASSET POR SLEEVE
# ─────────────────────────────────────────────────────────────────────────────

def allocate_sleeve(
    assets: list,
    sleeve_weight: float,
    sizes: dict,
    active: dict,
    vols: dict,
    momenta: dict,
    splits: Optional[dict] = None,
    values: Optional[dict] = None,
) -> dict:
    """
    Distribuye sleeve_weight entre TODOS los activos activos del sleeve.
    Score: phase_size × momentum_factor × value_factor × prior_split
    """
    active_assets = [t for t in assets if active.get(t) and sizes.get(t, 0) > 0]
    if not active_assets:
        return {}

    raw_scores = {}
    for t in active_assets:
        mom          = momenta.get(t, 0.0)
        mom_factor   = max(1.0 + mom, 0.2)
        val_score    = values.get(t, 0.5) if values else 0.5
        value_factor = 0.7 + 0.6 * val_score
        prior        = splits.get(t, 1.0) if splits else 1.0
        raw_scores[t] = sizes[t] * mom_factor * value_factor * prior

    total_score = sum(raw_scores.values())
    if total_score == 0:
        return {}

    result = {}
    for t, score in raw_scores.items():
        prop_weight = (score / total_score) * sleeve_weight
        result[t]   = round(vol_adjusted_size(prop_weight, vols.get(t, 0.20)), 4)

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  SEÑAL PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def compute_signal(tickers: Optional[list] = None, window: int = 50) -> dict:
    """
    Calcula la señal rotacional con todas las mejoras v3.1.
    """
    tickers   = tickers or DEFAULT_TICKERS
    data      = download_prices(tickers)
    data      = add_indicators(data, tickers, window)
    positions = compute_positions(data, tickers, window)

    latest = data.iloc[-1]
    phases, sizes, active, vols, momenta, values = {}, {}, {}, {}, {}, {}

    for t in tickers:
        if t not in data.columns:
            continue

        atr_col = f"{t}_ATR20"
        atr20   = float(latest[atr_col]) if atr_col in latest.index and not pd.isna(latest[atr_col]) else 0.0

        ph, dist, risk = trend_phase_adaptive(
            float(latest[t]), float(latest[f"{t}_MA{window}"]), atr20
        )
        phases[t]   = {
            "phase": ph,
            "dist":  round(dist * 100, 2),
            "risk":  round(risk * 100, 2),
            "price": round(float(latest[t]), 2),
        }
        sizes[t]    = phase_size(ph)
        active[t]   = bool(positions[t].iloc[-1])
        vols[t]     = round(annual_volatility(data[t]), 4)
        momenta[t]  = round(compute_momentum(data, t), 4)
        values[t]   = round(compute_value_score(data, t), 4)

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

    buffett = get_buffett()
    bm      = buffett.get("mult", 1.0)

    weights  = {t: 0.0 for t in tickers}
    dominant = "DEFENSIVO"

    if total_s > 0:
        base_sw = {s: strength / total_s for s, strength in sleeve_str.items()}

        # Buffett reduce equity/merval; no afecta crypto ni commodities
        for s in ("equity", "merval"):
            if s in base_sw:
                base_sw[s] *= bm

        total_sw = sum(base_sw.values())
        # FIX: solo normalizar si total_sw > 1.0 (evitar sobreapalancamiento).
        # Si total_sw < 1.0 (Buffett reduce), dejar el resto como cash.
        if total_sw > 1.0:
            base_sw = {s: w / total_sw for s, w in base_sw.items()}

        for sleeve_name in trading_sleeves:
            sw = base_sw.get(sleeve_name, 0.0)
            if sw == 0:
                continue
            prior_splits = CRYPTO_SPLIT if sleeve_name == "crypto" else None
            alloc = allocate_sleeve(
                sleeves[sleeve_name], sw, sizes, active, vols, momenta,
                splits=prior_splits, values=values,
            )
            weights.update(alloc)

    # Safe haven: cuando equities están todas en BROKEN, redirigir a bonds
    equity_assets = sleeves.get("equity", [])
    bond_assets   = sleeves.get("bonds", [])
    equity_broken = all(not active.get(t) or sizes.get(t, 0) == 0 for t in equity_assets)

    if bond_assets and equity_broken:
        bond_budget = 1.0 / max(len(trading_sleeves), 1)
        bond_alloc  = allocate_sleeve(bond_assets, bond_budget, sizes, active, vols, momenta)
        if not bond_alloc:
            first_bond         = bond_assets[0]
            bond_alloc         = {first_bond: round(bond_budget, 4)}
            active[first_bond] = True
        weights.update(bond_alloc)

    # NO normalizar a 100% — la diferencia con 1.0 es cash (efecto Buffett real)
    total_w = sum(weights.values())
    if total_w > 1.0:
        weights = {t: round(w / total_w, 4) for t, w in weights.items()}

    if weights:
        top = max(weights.items(), key=lambda x: x[1])
        if top[1] > 0:
            dominant = top[0]

    cash_pct = round(max(1.0 - sum(weights.values()), 0.0), 4)

    quality_score = sum(
        weights.get(t, 0) for t in tickers
        if active.get(t) and phases.get(t, {}).get("phase") in ("EARLY", "OK")
    )
    quality = "ALTA" if quality_score >= 0.5 else "MEDIA" if quality_score >= 0.25 else "BAJA"

    return {
        "weights":      weights,
        "phases":       phases,
        "active":       active,
        "dominant":     dominant,
        "buffett":      buffett,
        "volatilities": vols,
        "momenta":      momenta,
        "values":       values,
        "signal_date":  str(data.index[-1].date()),
        "cash_pct":     cash_pct,
        "quality":      quality,
        "tickers":      tickers,
    }
