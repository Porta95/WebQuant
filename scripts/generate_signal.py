"""
<<<<<<< HEAD
generate_signal.py — Corre en GitHub Actions.
Descarga datos, calcula señal completa y guarda JSON en data/.
Railway solo lee esos archivos — sin depender de Yahoo Finance en runtime.

Fixes v2:
- compute_recent_performance: elimina el hardcode ew *= 0.85, usa mult Buffett real.
- load_portfolio_config: más robusto, soporta tanto estructura nueva como legacy.
- build_position: vectorizado con NumPy (igual que core.py optimizado).
- Performance genera datos desde 2020 para tener más historial.
=======
generate_signal.py — Corre en GitHub Actions (script autocontenido).
Descarga datos, calcula señal completa v3.1 y guarda JSON en data/.
Railway solo lee esos archivos — sin depender de Yahoo Finance en runtime.

Mejoras v3:
- Fases adaptativas por ATR (no más 3%/7% fijos)
- Multi-asset por sleeve con momentum 12-1 meses
- Safe haven (IEF/BIL) cuando equities en BROKEN total
- Buffett multiplier continuo (interpolación lineal)
- Circuit breaker en performance: DD > -15% reduce exposición
- Quality score ponderado por peso real
- Dual timeframe: Donchian50 + MA20
- Nuevo sleeve "bonds" y "merval" (acciones argentinas)
- Costos de transacción en backtest (10 bps)

Mejoras v3.1:
- Sleeve "reits" (VNQ) con baja correlación a equity
- Salida anticipada: EXTENDED + momentum 1 mes < -4%
- Factor de valor (52-week range): activos baratos reciben sobrepeso
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
"""

import json
import os
import sys
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────
<<<<<<< HEAD
WINDOW   = 50
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def load_portfolio_config():
    """
    Lee portfolio.json y retorna (tickers, sleeve_map, crypto_tickers).
    Soporta la estructura del router: {crypto: [], equities: [], commodities: []}.
    Si el archivo no existe o está corrupto, usa defaults.
=======
WINDOW       = 50
DATA_DIR     = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

TRANSACTION_COST   = 0.001   # 10 bps por rotación
DD_CIRCUIT_BREAKER = -0.15   # -15% desde el pico activa el freno


def load_portfolio_config():
    """
    Lee portfolio.json y retorna (tickers, sleeve_map, crypto_tickers, bonds_tickers).
    Soporta los sleeves: equities, reits, crypto, commodities, bonds, merval.
    Si el archivo no existe o está corrupto, usa defaults con todos los sleeves.
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
    """
    port_path = DATA_DIR / "portfolio.json"
    if port_path.exists():
        try:
            p = json.loads(port_path.read_text())

<<<<<<< HEAD
            # Estructura estándar del router/portfolio.py
            if all(k in p for k in ["crypto", "equities", "commodities"]):
                crypto      = [t.upper() for t in p.get("crypto", []) if t]
                equities    = [t.upper() for t in p.get("equities", []) if t]
                commodities = [t.upper() for t in p.get("commodities", []) if t]

                # Garantizar que haya al menos un equity como benchmark
                if "SPY" not in equities and "QQQ" not in equities:
                    equities = ["SPY"] + equities

                tickers    = equities + crypto + commodities
=======
            if any(k in p for k in ["crypto", "equities", "commodities", "bonds", "merval", "reits"]):
                crypto      = [t.upper() for t in p.get("crypto", [])      if t]
                equities    = [t.upper() for t in p.get("equities", [])    if t]
                commodities = [t.upper() for t in p.get("commodities", []) if t]
                bonds       = [t.upper() for t in p.get("bonds", [])       if t]
                merval      = [t.upper() for t in p.get("merval", [])      if t]
                reits       = [t.upper() for t in p.get("reits", [])       if t]

                # Garantizar al menos un equity como benchmark
                if "SPY" not in equities and "QQQ" not in equities:
                    equities = ["SPY"] + equities

                tickers    = equities + reits + crypto + commodities + bonds + merval
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
                sleeve_map = {}
                for t in crypto:      sleeve_map[t] = "crypto"
                for t in equities:    sleeve_map[t] = "equity"
                for t in commodities: sleeve_map[t] = "commodity"
<<<<<<< HEAD

                print(f"  [portfolio] cargado: {tickers}")
                return tickers, sleeve_map, crypto
=======
                for t in bonds:       sleeve_map[t] = "bonds"
                for t in merval:      sleeve_map[t] = "merval"
                for t in reits:       sleeve_map[t] = "reits"

                print(f"  [portfolio] cargado: {tickers}")
                return tickers, sleeve_map, crypto, bonds
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)

        except Exception as e:
            print(f"  [portfolio] error leyendo config: {e}")

<<<<<<< HEAD
    # Defaults seguros
    print("  [portfolio] usando defaults")
    default_tickers    = ["SPY", "QQQ", "BTC-USD", "ETH-USD", "GLD"]
    default_sleeve_map = {
        "SPY": "equity", "QQQ": "equity",
        "BTC-USD": "crypto", "ETH-USD": "crypto",
        "GLD": "commodity",
    }
    return default_tickers, default_sleeve_map, ["BTC-USD", "ETH-USD"]


TICKERS, SLEEVE_MAP, CRYPTO_TICKERS = load_portfolio_config()
=======
    # Defaults seguros con todos los sleeves
    print("  [portfolio] usando defaults v3.1")
    default_tickers = [
        "SPY", "QQQ", "XLE", "XLV",
        "VNQ",
        "BTC-USD", "ETH-USD",
        "GLD",
        "IEF", "BIL",
        "GGAL.BA", "YPFD.BA",
    ]
    default_sleeve_map = {
        "SPY": "equity",  "QQQ": "equity",
        "XLE": "equity",  "XLV": "equity",
        "VNQ": "reits",
        "BTC-USD": "crypto", "ETH-USD": "crypto",
        "GLD": "commodity",
        "IEF": "bonds",   "BIL": "bonds",
        "GGAL.BA": "merval", "YPFD.BA": "merval",
    }
    return default_tickers, default_sleeve_map, ["BTC-USD", "ETH-USD"], ["IEF", "BIL"]


TICKERS, SLEEVE_MAP, CRYPTO_TICKERS, BOND_TICKERS = load_portfolio_config()
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
CRYPTO_SPLIT = (
    {t: 1 / len(CRYPTO_TICKERS) for t in CRYPTO_TICKERS}
    if CRYPTO_TICKERS else {}
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def download_prices(tickers, start="2018-01-01"):
<<<<<<< HEAD
    print(f"  Descargando {tickers} desde {start}...")
=======
    print(f"  Descargando {len(tickers)} tickers desde {start}...")
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
    raw  = yf.download(tickers, start=start, auto_adjust=True, progress=False)
    data = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    data = data.dropna(how="all").ffill()
    print(f"  → {len(data)} filas hasta {data.index[-1].date()}")
    return data


<<<<<<< HEAD
def trend_phase(price, ma):
    if pd.isna(price) or pd.isna(ma):
        return "NO_DATA", 0.0, 0.0
    dist = (price - ma) / ma if ma != 0 else 0.0
    risk = abs(price - ma) / price if price > 0 else 0.0
    if price < ma:    return "BROKEN",   dist, risk
    elif dist < 0.03: return "EARLY",    dist, risk
    elif dist < 0.07: return "OK",       dist, risk
    else:             return "EXTENDED", dist, risk
=======
def add_indicators(data, tickers):
    """Agrega MA50, HIGH50, MA20 y ATR20 para cada ticker."""
    for t in tickers:
        if t not in data.columns:
            continue
        data[f"{t}_MA{WINDOW}"]   = data[t].rolling(WINDOW, min_periods=20).mean()
        data[f"{t}_HIGH{WINDOW}"] = data[t].rolling(WINDOW, min_periods=20).max()
        data[f"{t}_MA20"]         = data[t].rolling(20, min_periods=10).mean()
        daily_abs_change          = data[t].diff().abs()
        data[f"{t}_ATR20"]        = daily_abs_change.rolling(20, min_periods=10).mean()
    return data


def trend_phase_adaptive(price, ma50, atr20=0.0):
    """Fases adaptativas por ATR. Fallback a umbrales fijos si ATR=0."""
    if pd.isna(price) or pd.isna(ma50):
        return "NO_DATA", 0.0, 0.0
    dist = (price - ma50) / ma50 if ma50 != 0 else 0.0
    risk = abs(price - ma50) / price if price > 0 else 0.0
    if price < ma50:
        return "BROKEN", dist, risk
    distance_price = price - ma50
    if atr20 > 0:
        if distance_price < 0.5 * atr20:   return "EARLY",    dist, risk
        elif distance_price < 1.5 * atr20: return "OK",       dist, risk
        else:                              return "EXTENDED", dist, risk
    else:
        if dist < 0.03:   return "EARLY",    dist, risk
        elif dist < 0.07: return "OK",       dist, risk
        else:             return "EXTENDED", dist, risk
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)


def phase_size(ph):
    return {"EARLY": 1.0, "OK": 0.7, "EXTENDED": 0.4}.get(ph, 0.0)


<<<<<<< HEAD
def build_position(entry, exit_):
    """Vectorizado con NumPy — igual que core.py optimizado."""
=======
def buffett_multiplier_continuous(ratio):
    """Interpolación lineal suave: ratio 80→1.30, ratio 180→0.40."""
    if ratio is None or pd.isna(ratio):
        return 1.0
    if ratio <= 80:    return 1.30
    elif ratio <= 180: return 1.30 - ((ratio - 80) / 100.0) * 0.90
    else:              return 0.40


def build_position(entry, exit_):
    """Vectorizado con NumPy."""
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
    ent   = entry.to_numpy(dtype=bool)
    ext   = exit_.to_numpy(dtype=bool)
    n     = len(ent)
    pos   = np.zeros(n, dtype=np.int8)
    state = np.int8(0)
    for i in range(1, n):
        if state == 0 and ent[i]:   state = 1
        elif state == 1 and ext[i]: state = 0
        pos[i] = state
    return pd.Series(pos.astype(bool), index=entry.index)


def annual_vol(prices, window=90):
    r = prices.pct_change().dropna()
    if len(r) == 0:
<<<<<<< HEAD
        return 0.20  # fallback razonable
=======
        return 0.20
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
    tail = r.tail(window) if len(r) >= window else r
    return float(tail.std() * np.sqrt(252))


def vol_adjusted_size(base, vol, target=0.20):
    if vol <= 0:
        return base
    return min(base * (target / vol), 1.5)


<<<<<<< HEAD
=======
def compute_momentum_12_1(data, ticker, slow=252, skip=21):
    """Momentum 12-1 meses: retorno de 12 meses excluyendo el último mes."""
    if ticker not in data.columns or len(data) < slow:
        return 0.0
    p_now = float(data[ticker].iloc[-skip])
    p_old = float(data[ticker].iloc[-slow])
    if p_old <= 0 or pd.isna(p_now) or pd.isna(p_old):
        return 0.0
    return p_now / p_old - 1


def compute_value_score(data, ticker, lookback=252):
    """
    Factor de valor: posición dentro del rango 52 semanas.
    1.0 = en mínimo (barato), 0.0 = en máximo (caro). 0.5 = neutral.
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


def allocate_sleeve(assets, sleeve_weight, sizes, active, vols, momenta, splits=None, values=None):
    """
    Distribuye sleeve_weight entre TODOS los activos activos del sleeve.
    Score: phase_size × momentum_factor × value_factor × prior_split.
    - value_factor = 0.7 + 0.6 × value_score  (barato=1.3×, caro=0.7×, neutral=1.0×)
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


>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
def get_buffett():
    try:
        wil    = yf.download("^W5000", start="1990-01-01", auto_adjust=True, progress=False)["Close"]
        gdp_df = pd.read_csv(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GDP",
            parse_dates=[0], index_col=0,
        )
        gdp = gdp_df.iloc[:, 0].resample("D").ffill()
        df  = pd.concat([wil, gdp], axis=1).dropna()
        df.columns = ["WILL", "GDP"]
        b   = (df["WILL"] / df["GDP"]) * 100
        val = float(b.iloc[-1])
        yoy = float(b.iloc[-1] - b.iloc[-252]) if len(b) > 252 else None
<<<<<<< HEAD
        ph  = "BARATO" if val < 90 else "JUSTO" if val < 120 else "CARO"
        mt  = 1.2 if val < 90 else 1.0 if val < 120 else 0.7
        return {"value": round(val, 1), "phase": ph, "mult": mt, "yoy": round(yoy, 1) if yoy else None}
=======
        mult = buffett_multiplier_continuous(val)

        if val < 90:    ph = "BARATO"
        elif val < 120: ph = "JUSTO"
        elif val < 150: ph = "CARO"
        else:           ph = "MUY_CARO"

        return {"value": round(val, 1), "phase": ph, "mult": round(mult, 3),
                "yoy": round(yoy, 1) if yoy else None}
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
    except Exception as e:
        print(f"  [buffett] error: {e}")
        return {"value": None, "phase": "N/A", "mult": 1.0, "yoy": None}


<<<<<<< HEAD
def compute_weights_at(row, positions, loc, tickers, sleeve_map, crypto_split, vols, buffett_mult):
    """
    Calcula pesos en un momento dado del histórico.
    Usa el multiplicador Buffett real — sin hardcode.
    """
    sizes, active = {}, {}
    for t in tickers:
        if t not in row.index:
            continue
        ma_col = f"{t}_MA{WINDOW}"
        if ma_col not in row.index:
            continue
        ph, _, _  = trend_phase(float(row[t]), float(row[ma_col]))
        sizes[t]  = phase_size(ph)
        active[t] = bool(positions[t].iloc[loc])

    crypto_a    = [t for t in tickers if sleeve_map.get(t) == "crypto"]
    equity_a    = [t for t in tickers if sleeve_map.get(t) == "equity"]
    commodity_a = [t for t in tickers if sleeve_map.get(t) == "commodity"]

    def sleeve_s(assets):
        s = [sizes[a] for a in assets if active.get(a)]
        return max(s) if s else 0.0

    cs = sleeve_s(crypto_a)
    es = sleeve_s(equity_a)
    gs = sleeve_s(commodity_a)
    ts = cs + es + gs

    weights = {t: 0.0 for t in tickers}
    if ts == 0:
        return weights

    cw = cs / ts
    ew = es / ts * buffett_mult   # FIX: mult real, no hardcode 0.85
    gw = gs / ts
    t2 = cw + ew + gw
    if t2 > 0:
        cw /= t2; ew /= t2; gw /= t2

    for t in crypto_a:
        if active.get(t):
            split      = crypto_split.get(t, 1.0 / max(len(crypto_a), 1))
            weights[t] = round(vol_adjusted_size(cw * split, vols.get(t, 0.20)), 4)

    for t in sorted(equity_a, key=lambda x: 0 if x == "QQQ" else 1):
        if active.get(t):
            weights[t] = round(vol_adjusted_size(ew, vols.get(t, 0.15)), 4)
            break

    for t in commodity_a:
        if active.get(t):
            weights[t] = round(vol_adjusted_size(gw, vols.get(t, 0.10)), 4)
            break

    tw = sum(weights.values())
    if tw > 0:
        weights = {t: round(w / tw, 4) for t, w in weights.items()}
    return weights


# ── Signal ────────────────────────────────────────────────────────────────────

def compute_signal():
    data = download_prices(TICKERS)

    for t in TICKERS:
        if t in data.columns:
            data[f"{t}_MA{WINDOW}"]   = data[t].rolling(WINDOW, min_periods=20).mean()
            data[f"{t}_HIGH{WINDOW}"] = data[t].rolling(WINDOW, min_periods=20).max()

=======
# ── Signal ────────────────────────────────────────────────────────────────────

def compute_signal():
    """Calcula la señal rotacional v3 completa."""
    data = download_prices(TICKERS)
    data = add_indicators(data, TICKERS)

    # Dual timeframe + salida anticipada (EXTENDED + momentum 1 mes < -4%)
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
    positions = {}
    for t in TICKERS:
        if t not in data.columns:
            continue
<<<<<<< HEAD
        entry       = data[t] > data[f"{t}_HIGH{WINDOW}"].shift(1)
        exit_       = data[t] < data[f"{t}_MA{WINDOW}"]
        positions[t] = build_position(entry, exit_)

    latest = data.iloc[-1]
    phases, sizes, active, vols = {}, {}, {}, {}
=======
        ma20_col = f"{t}_MA20"
        if ma20_col in data.columns:
            entry = (
                (data[t] > data[f"{t}_HIGH{WINDOW}"].shift(1)) &
                (data[t] > data[ma20_col])
            )
        else:
            entry = data[t] > data[f"{t}_HIGH{WINDOW}"].shift(1)
        exit_normal   = data[t] < data[f"{t}_MA{WINDOW}"]
        mom_1m        = data[t].pct_change(21)
        extended_zone = data[t] > data[f"{t}_MA{WINDOW}"] * 1.07
        exit_early    = extended_zone & (mom_1m < -0.04)
        exit_         = exit_normal | exit_early
        positions[t]  = build_position(entry, exit_)

    latest = data.iloc[-1]
    phases, sizes, active, vols, momenta, values = {}, {}, {}, {}, {}, {}
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)

    for t in TICKERS:
        if t not in data.columns:
            continue
<<<<<<< HEAD
        ph, dist, risk = trend_phase(float(latest[t]), float(latest[f"{t}_MA{WINDOW}"]))
=======
        atr_col = f"{t}_ATR20"
        atr20   = float(latest[atr_col]) if atr_col in latest.index and not pd.isna(latest[atr_col]) else 0.0

        ph, dist, risk = trend_phase_adaptive(float(latest[t]), float(latest[f"{t}_MA{WINDOW}"]), atr20)
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
        phases[t] = {
            "phase": ph,
            "dist":  round(dist * 100, 2),
            "risk":  round(risk * 100, 2),
            "price": round(float(latest[t]), 2),
        }
<<<<<<< HEAD
        sizes[t]  = phase_size(ph)
        active[t] = bool(positions[t].iloc[-1])
        vols[t]   = round(annual_vol(data[t]), 4)

    crypto_a    = [t for t in TICKERS if SLEEVE_MAP.get(t) == "crypto"]
    equity_a    = [t for t in TICKERS if SLEEVE_MAP.get(t) == "equity"]
    commodity_a = [t for t in TICKERS if SLEEVE_MAP.get(t) == "commodity"]

    def sleeve_s(assets):
        s = [sizes[a] for a in assets if active.get(a)]
        return max(s) if s else 0.0

    cs = sleeve_s(crypto_a)
    es = sleeve_s(equity_a)
    gs = sleeve_s(commodity_a)
    total_s = cs + es + gs

    weights  = {t: 0.0 for t in TICKERS}
    dominant = "DEFENSIVO"
    buffett  = get_buffett()

    if total_s > 0:
        bm = buffett["mult"]
        cw = cs / total_s
        ew = es / total_s
        gw = gs / total_s
        ew *= bm
        t2 = cw + ew + gw
        if t2 > 0:
            cw /= t2; ew /= t2; gw /= t2

        for t in crypto_a:
            if active.get(t):
                split      = CRYPTO_SPLIT.get(t, 1.0 / max(len(crypto_a), 1))
                weights[t] = round(vol_adjusted_size(cw * split, vols[t]), 4)

        for t in sorted(equity_a, key=lambda x: 0 if x == "QQQ" else 1):
            if active.get(t):
                weights[t] = round(vol_adjusted_size(ew, vols[t]), 4)
                dominant = t
                break

        for t in commodity_a:
            if active.get(t):
                weights[t] = round(vol_adjusted_size(gw, vols[t]), 4)
                if dominant == "DEFENSIVO":
                    dominant = t

        tw = sum(weights.values())
        if tw > 0:
            weights = {t: round(w / tw, 4) for t, w in weights.items()}

        if cs > es and cs > gs and dominant == "DEFENSIVO":
            dominant = "CRYPTO"

    cash_pct = round(max(1.0 - sum(weights.values()), 0.0), 4)
    hq = sum(1 for t in TICKERS if active.get(t) and phases.get(t, {}).get("phase") in ("EARLY", "OK"))
    quality = "ALTA" if hq >= 3 else "MEDIA" if hq >= 2 else "BAJA"
=======
        sizes[t]   = phase_size(ph)
        active[t]  = bool(positions[t].iloc[-1])
        vols[t]    = round(annual_vol(data[t]), 4)
        momenta[t] = round(compute_momentum_12_1(data, t), 4)
        values[t]  = round(compute_value_score(data, t), 4)

    # Sleeves
    sleeves = {}
    for t in TICKERS:
        if t in data.columns:
            s = SLEEVE_MAP.get(t, "equity")
            sleeves.setdefault(s, []).append(t)

    trading_sleeves = [s for s in sleeves if s != "bonds"]

    def sleeve_strength(assets):
        s = [sizes[a] for a in assets if active.get(a)]
        return max(s) if s else 0.0

    sleeve_str = {s: sleeve_strength(sleeves[s]) for s in trading_sleeves}
    total_s    = sum(sleeve_str.values())

    buffett = get_buffett()
    bm      = buffett.get("mult", 1.0)

    weights  = {t: 0.0 for t in TICKERS}
    dominant = "DEFENSIVO"

    if total_s > 0:
        base_sw = {s: strength / total_s for s, strength in sleeve_str.items()}
        for s in ("equity", "merval"):
            if s in base_sw:
                base_sw[s] *= bm
        total_sw = sum(base_sw.values())
        if total_sw > 0:
            base_sw = {s: w / total_sw for s, w in base_sw.items()}

        for sleeve_name in trading_sleeves:
            sw = base_sw.get(sleeve_name, 0.0)
            if sw == 0:
                continue
            prior_splits = CRYPTO_SPLIT if sleeve_name == "crypto" else None
            alloc = allocate_sleeve(sleeves[sleeve_name], sw, sizes, active, vols, momenta,
                                    splits=prior_splits, values=values)
            weights.update(alloc)

    # Safe haven cuando equities en BROKEN
    equity_assets = sleeves.get("equity", [])
    bond_assets   = sleeves.get("bonds", [])
    equity_broken = all(not active.get(t) or sizes.get(t, 0) == 0 for t in equity_assets)
    if bond_assets and equity_broken:
        bond_budget = 1.0 / max(len(trading_sleeves), 1)
        bond_alloc  = allocate_sleeve(bond_assets, bond_budget, sizes, active, vols, momenta)
        if not bond_alloc and bond_assets:
            bond_alloc  = {bond_assets[0]: round(bond_budget, 4)}
            active[bond_assets[0]] = True
        weights.update(bond_alloc)

    total_w = sum(weights.values())
    if total_w > 0:
        weights = {t: round(w / total_w, 4) for t, w in weights.items()}

    if weights:
        top = max(weights.items(), key=lambda x: x[1])
        if top[1] > 0:
            dominant = top[0]

    cash_pct = round(max(1.0 - sum(weights.values()), 0.0), 4)

    # Quality score ponderado por peso real
    quality_score = sum(
        weights.get(t, 0) for t in TICKERS
        if active.get(t) and phases.get(t, {}).get("phase") in ("EARLY", "OK")
    )
    quality = "ALTA" if quality_score >= 0.5 else "MEDIA" if quality_score >= 0.25 else "BAJA"
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)

    return {
        "weights":      weights,
        "phases":       phases,
        "active":       active,
        "dominant":     dominant,
        "buffett":      buffett,
        "volatilities": vols,
<<<<<<< HEAD
=======
        "momenta":      momenta,
        "values":       values,
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
        "signal_date":  str(data.index[-1].date()),
        "generated_at": datetime.utcnow().isoformat(),
        "cash_pct":     cash_pct,
        "quality":      quality,
        "tickers":      TICKERS,
    }


# ── Performance ───────────────────────────────────────────────────────────────

def compute_recent_performance():
    """
<<<<<<< HEAD
    Backtest desde 2020 con los tickers del portfolio actual.
    FIX: usa multiplicador Buffett real (calculado una sola vez).
    """
    print("  Calculando performance...")
    data = download_prices(TICKERS, start="2020-01-01")

    for t in TICKERS:
        if t in data.columns:
            data[f"{t}_MA{WINDOW}"]   = data[t].rolling(WINDOW, min_periods=20).mean()
            data[f"{t}_HIGH{WINDOW}"] = data[t].rolling(WINDOW, min_periods=20).max()
=======
    Backtest desde 2020 con todas las mejoras v3:
    - Fases ATR-adaptativas
    - Multi-asset por sleeve con momentum
    - Safe haven bonds
    - Costos de transacción (10 bps)
    - Circuit breaker (-15% DD)
    """
    print("  Calculando performance v3...")
    data = download_prices(TICKERS, start="2020-01-01")
    data = add_indicators(data, TICKERS)
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)

    positions = {}
    for t in TICKERS:
        if t not in data.columns:
            continue
<<<<<<< HEAD
        entry       = data[t] > data[f"{t}_HIGH{WINDOW}"].shift(1)
        exit_       = data[t] < data[f"{t}_MA{WINDOW}"]
        positions[t] = build_position(entry, exit_)

    # Calcular vols por ticker (una sola vez)
    vols = {t: annual_vol(data[t]) for t in TICKERS if t in data.columns}

    # Obtener mult Buffett una sola vez para todo el backtest
    buffett      = get_buffett()
    buffett_mult = buffett.get("mult", 1.0)

    # Pre-calcular retornos diarios
    daily_rets  = data.pct_change().fillna(0)
=======
        ma20_col = f"{t}_MA20"
        if ma20_col in data.columns:
            entry = (
                (data[t] > data[f"{t}_HIGH{WINDOW}"].shift(1)) &
                (data[t] > data[ma20_col])
            )
        else:
            entry = data[t] > data[f"{t}_HIGH{WINDOW}"].shift(1)
        exit_        = data[t] < data[f"{t}_MA{WINDOW}"]
        positions[t] = build_position(entry, exit_)

    # Calcular vols y momenta (una sola vez)
    vols    = {t: annual_vol(data[t]) for t in TICKERS if t in data.columns}
    momenta = {t: compute_momentum_12_1(data, t) for t in TICKERS if t in data.columns}

    buffett      = get_buffett()
    buffett_mult = buffett.get("mult", 1.0)

>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
    rebal_dates = data.resample("W").last().index
    rebal_dates = rebal_dates[rebal_dates >= data.index[WINDOW + 5]]

    spy_col = "SPY" if "SPY" in data.columns else data.columns[0]
    sv, bv  = 100.0, 100.0
<<<<<<< HEAD
    curve, weekly = [], []
=======
    peak_v  = 100.0
    curve, weekly = [], []
    prev_weights: dict = {t: 0.0 for t in TICKERS}
    circuit_active = False

    # Clasificar sleeves
    sleeves = {}
    for t in TICKERS:
        if t in data.columns:
            s = SLEEVE_MAP.get(t, "equity")
            sleeves.setdefault(s, []).append(t)
    trading_sleeves = [s for s in sleeves if s != "bonds"]

    daily_rets = data.pct_change().fillna(0)
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)

    for i, date in enumerate(rebal_dates):
        if date not in data.index:
            continue
        loc = data.index.get_loc(date)
        row = data.iloc[loc]

<<<<<<< HEAD
        # Pesos con mult Buffett real
        w = compute_weights_at(row, positions, loc, TICKERS, SLEEVE_MAP, CRYPTO_SPLIT, vols, buffett_mult)
=======
        # Calcular fases y posiciones en esta fecha
        loc_sizes  = {}
        loc_active = {}
        for t in TICKERS:
            if t not in data.columns:
                continue
            ma_col  = f"{t}_MA{WINDOW}"
            atr_col = f"{t}_ATR20"
            if ma_col not in row.index:
                continue
            atr20 = float(row[atr_col]) if atr_col in row.index and not pd.isna(row[atr_col]) else 0.0
            ph, _, _     = trend_phase_adaptive(float(row[t]), float(row[ma_col]), atr20)
            loc_sizes[t]  = phase_size(ph)
            loc_active[t] = bool(positions[t].iloc[loc])

        sleeve_str_loc = {}
        for s in trading_sleeves:
            s_assets = sleeves.get(s, [])
            sv_list  = [loc_sizes[a] for a in s_assets if loc_active.get(a)]
            sleeve_str_loc[s] = max(sv_list) if sv_list else 0.0

        total_s = sum(sleeve_str_loc.values())

        w = {t: 0.0 for t in TICKERS}
        if total_s > 0:
            base_sw = {s: strength / total_s for s, strength in sleeve_str_loc.items()}
            for s in ("equity", "merval"):
                if s in base_sw:
                    base_sw[s] *= buffett_mult
            total_sw = sum(base_sw.values())
            if total_sw > 0:
                base_sw = {s: wt / total_sw for s, wt in base_sw.items()}

            for sleeve_name in trading_sleeves:
                sw = base_sw.get(sleeve_name, 0.0)
                if sw == 0:
                    continue
                prior_splits = CRYPTO_SPLIT if sleeve_name == "crypto" else None
                alloc = allocate_sleeve(sleeves[sleeve_name], sw, loc_sizes, loc_active,
                                        vols, momenta, splits=prior_splits)
                w.update(alloc)

        # Safe haven
        eq_assets   = sleeves.get("equity", [])
        bond_assets = sleeves.get("bonds", [])
        eq_broken   = all(not loc_active.get(t) or loc_sizes.get(t, 0) == 0 for t in eq_assets)
        if bond_assets and eq_broken:
            bond_budget = 1.0 / max(len(trading_sleeves), 1)
            bond_alloc  = allocate_sleeve(bond_assets, bond_budget, loc_sizes, loc_active,
                                          vols, momenta)
            if not bond_alloc and bond_assets:
                bond_alloc = {bond_assets[0]: round(bond_budget, 4)}
                loc_active[bond_assets[0]] = True
            w.update(bond_alloc)

        tw = sum(w.values())
        if tw > 0:
            w = {t: wt / tw for t, wt in w.items()}

        # Circuit breaker
        current_dd = (sv - peak_v) / peak_v if peak_v > 0 else 0.0
        if current_dd < DD_CIRCUIT_BREAKER:
            if not circuit_active:
                print(f"    [circuit_breaker] activado {date}: DD={current_dd:.1%}")
                circuit_active = True
            w = {t: wt * 0.5 for t, wt in w.items()}
        elif circuit_active and current_dd > -0.05:
            circuit_active = False

        # Costos de transacción
        total_rotation   = sum(abs(w.get(t, 0) - prev_weights.get(t, 0)) for t in set(list(w) + list(prev_weights)))
        transaction_drag = total_rotation * TRANSACTION_COST
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)

        nd = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else data.index[-1]
        if nd not in data.index:
            continue
<<<<<<< HEAD

        next_loc = data.index.get_loc(nd)

        # Retorno compuesto del período (vectorizado)
=======
        next_loc = data.index.get_loc(nd)

        # Retorno del período
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
        pr = 0.0
        for t, wt in w.items():
            if wt == 0 or t not in daily_rets.columns:
                continue
            ticker_rets = daily_rets[t].iloc[loc + 1: next_loc + 1].values
            if len(ticker_rets) > 0:
                pr += wt * float(np.prod(1 + ticker_rets) - 1)
<<<<<<< HEAD
=======
        pr -= transaction_drag
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)

        spy_rets = daily_rets[spy_col].iloc[loc + 1: next_loc + 1].values
        br       = float(np.prod(1 + spy_rets) - 1) if len(spy_rets) > 0 else 0.0

        sv *= (1 + pr)
        bv *= (1 + br)
<<<<<<< HEAD
=======
        peak_v = max(peak_v, sv)

>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
        weekly.append(round(pr * 100, 3))
        curve.append({
            "date":      str(date.date()),
            "strategy":  round(sv, 2),
            "benchmark": round(bv, 2),
        })
<<<<<<< HEAD
=======
        prev_weights = dict(w)
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)

    if not curve:
        return {"error": "Datos insuficientes"}

    rets      = np.array(weekly) / 100
    total_ret = sv / 100 - 1
    years     = len(rets) / 52
    cagr      = (1 + total_ret) ** (1 / max(years, 0.1)) - 1
    vol       = rets.std() * np.sqrt(52)
    sharpe    = (cagr - 0.05) / vol if vol > 0 else 0
    neg       = rets[rets < 0]
    sortino_v = neg.std() * np.sqrt(52) if len(neg) > 0 else 0
    sortino   = (cagr - 0.05) / sortino_v if sortino_v > 0 else 0
    win_rate  = float(np.sum(rets > 0) / len(rets)) if len(rets) > 0 else 0
    vals      = np.array([p["strategy"] for p in curve])
<<<<<<< HEAD
    peak      = np.maximum.accumulate(vals)
    dd        = ((vals - peak) / peak * 100).tolist()
=======
    peak_arr  = np.maximum.accumulate(vals)
    dd        = ((vals - peak_arr) / peak_arr * 100).tolist()
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
    max_dd    = float(np.min(dd)) if dd else 0
    b_total   = bv / 100 - 1
    b_cagr    = (1 + b_total) ** (1 / max(years, 0.1)) - 1

    return {
        "equity_curve":    curve,
        "weekly_returns":  weekly,
        "drawdown_series": [round(d, 2) for d in dd],
        "metrics": {
            "cagr":         round(cagr * 100, 2),
            "cagr_bench":   round(b_cagr * 100, 2),
            "sharpe":       round(sharpe, 2),
            "sortino":      round(sortino, 2),
            "max_drawdown": round(max_dd, 2),
            "volatility":   round(vol * 100, 2),
            "win_rate":     round(win_rate * 100, 1),
            "total_return": round(total_ret * 100, 2),
            "final_value":  round(sv, 2),
            "years":        round(years, 1),
        },
        "tickers":      TICKERS,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(signal):
    token   = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("  [telegram] vars no configuradas, saltando...")
        return

<<<<<<< HEAD
    w  = signal["weights"]
    ph = signal["phases"]
    bf = signal["buffett"]
    q  = signal["quality"]
    qe = {"ALTA": "🟢", "MEDIA": "🟡", "BAJA": "🔴"}.get(q, "⚪")
    pe = {"EARLY": "🌱", "OK": "✅", "EXTENDED": "⚠️", "BROKEN": "❌"}

    alloc = "\n".join(
        f"  {t:12s} {p:.0%}"
        for t, p in sorted(w.items(), key=lambda x: -x[1]) if p > 0
    )
    phases_txt = "\n".join(
        f"  {pe.get(v['phase'], '⚪')} {t:12s} {v['phase']} ({v['dist']:+.1f}%)"
        for t, v in ph.items()
    )
    buff_txt = f"{bf['value']:.0f}% → {bf['phase']} (×{bf['mult']})" if bf.get("value") else "N/A"

    msg = f"""📊 *QUANT ROTATIONAL — SEÑAL DIARIA*
📅 `{signal['signal_date']}`
{qe} Calidad: *{q}*
=======
    w   = signal["weights"]
    ph  = signal["phases"]
    bf  = signal["buffett"]
    q   = signal["quality"]
    mom = signal.get("momenta", {})
    qe  = {"ALTA": "🟢", "MEDIA": "🟡", "BAJA": "🔴"}.get(q, "⚪")
    pe  = {"EARLY": "🌱", "OK": "✅", "EXTENDED": "⚠️", "BROKEN": "❌", "NO_DATA": "⚪"}

    alloc = "\n".join(
        f"  {t:12s} {p:.0%}  (mom: {mom.get(t, 0):+.0%})"
        for t, p in sorted(w.items(), key=lambda x: -x[1]) if p > 0
    )
    phases_txt = "\n".join(
        f"  {pe.get(v['phase'], '⚪')} {t:12s} {v['phase']:8s} ({v['dist']:+.1f}%)"
        for t, v in ph.items()
    )
    buff_val = bf.get("value")
    buff_txt = f"{buff_val:.0f}% → {bf['phase']} (×{bf['mult']:.2f})" if buff_val else "N/A"
    cash_txt = f"{signal['cash_pct']:.0%}"

    msg = f"""📊 *QUANT ROTATIONAL v3 — SEÑAL DIARIA*
📅 `{signal['signal_date']}`
{qe} Calidad: *{q}* | 💵 Cash: `{cash_txt}`
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)

🎯 *DOMINANTE: {signal['dominant']}*

📦 *ASIGNACIÓN:*
```
<<<<<<< HEAD
{alloc}
```
📈 *FASES:*
=======
{alloc if alloc else "  100% CASH / SAFE HAVEN"}
```
📈 *FASES (ATR-adaptativas):*
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
```
{phases_txt}
```
🌍 Buffett: `{buff_txt}`
<<<<<<< HEAD
_Quant Rotational v2_"""
=======
_Quant Rotational v3 — Multi-asset · Momentum · Safe Haven_"""
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
        print(f"  [telegram] {r.status_code} — {'OK' if r.json().get('ok') else r.text[:100]}")
    except Exception as e:
        print(f"  [telegram] error: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
<<<<<<< HEAD
    print("=" * 55)
    print(f"Generando señal: {datetime.utcnow().isoformat()}")
    print(f"Tickers activos: {TICKERS}")
    print("=" * 55)

    print("\n1. Calculando señal rotacional...")
    signal = compute_signal()
    print(f"   Dominante: {signal['dominant']}")
    print(f"   Calidad:   {signal['quality']}")
    print(f"   Pesos:     {signal['weights']}")
    (DATA_DIR / "signal.json").write_text(json.dumps(signal, indent=2, default=str))
    print(f"   ✅ signal.json guardado")

    print("\n2. Calculando performance...")
    try:
        perf = compute_recent_performance()
        if "error" not in perf:
            print(f"   CAGR: {perf['metrics']['cagr']}% | Sharpe: {perf['metrics']['sharpe']}")
            (DATA_DIR / "performance.json").write_text(json.dumps(perf, indent=2, default=str))
            print(f"   ✅ performance.json guardado")
=======
    print("=" * 60)
    print(f"Generando señal v3: {datetime.utcnow().isoformat()}")
    print(f"Tickers activos: {TICKERS}")
    print("=" * 60)

    print("\n1. Calculando señal rotacional v3...")
    signal = compute_signal()
    print(f"   Dominante: {signal['dominant']}")
    print(f"   Calidad:   {signal['quality']}")
    print(f"   Cash:      {signal['cash_pct']:.0%}")
    print(f"   Buffett:   {signal['buffett']}")
    print(f"   Pesos:     {signal['weights']}")
    print(f"   Momenta:   {signal['momenta']}")
    (DATA_DIR / "signal.json").write_text(json.dumps(signal, indent=2, default=str))
    print("   ✅ signal.json guardado")

    print("\n2. Calculando performance v3...")
    try:
        perf = compute_recent_performance()
        if "error" not in perf:
            m = perf["metrics"]
            print(f"   CAGR: {m['cagr']}% | Bench: {m['cagr_bench']}% | Sharpe: {m['sharpe']} | MaxDD: {m['max_drawdown']}%")
            (DATA_DIR / "performance.json").write_text(json.dumps(perf, indent=2, default=str))
            print("   ✅ performance.json guardado")
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
        else:
            print(f"   ⚠️  {perf['error']}")
    except Exception as e:
        print(f"   ⚠️  Error en performance: {e}")

    print("\n3. Actualizando historial...")
    history_path = DATA_DIR / "history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else []
    entry = {
        "date":     signal["signal_date"],
        "dominant": signal["dominant"],
        "weights":  signal["weights"],
        "quality":  signal["quality"],
        "buffett":  signal["buffett"],
<<<<<<< HEAD
=======
        "momenta":  signal.get("momenta", {}),
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
        "tickers":  signal["tickers"],
    }
    history = [h for h in history if h.get("date") != signal["signal_date"]]
    history.append(entry)
    history = sorted(history, key=lambda x: x["date"], reverse=True)[:52]
    history_path.write_text(json.dumps(history, indent=2, default=str))
    print(f"   ✅ history.json: {len(history)} entradas")

    print("\n4. Enviando a Telegram...")
    send_telegram(signal)

    print("\n✅ Todo listo!")
