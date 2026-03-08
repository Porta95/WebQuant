"""
generate_signal.py — Corre en GitHub Actions.
Descarga datos, calcula señal completa y guarda JSON en data/.
Railway solo lee esos archivos — sin depender de Yahoo Finance en runtime.

Fixes v2:
- compute_recent_performance: elimina el hardcode ew *= 0.85, usa mult Buffett real.
- load_portfolio_config: más robusto, soporta tanto estructura nueva como legacy.
- build_position: vectorizado con NumPy (igual que core.py optimizado).
- Performance genera datos desde 2020 para tener más historial.
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
WINDOW   = 50
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def load_portfolio_config():
    """
    Lee portfolio.json y retorna (tickers, sleeve_map, crypto_tickers).
    Soporta la estructura del router: {crypto: [], equities: [], commodities: []}.
    Si el archivo no existe o está corrupto, usa defaults.
    """
    port_path = DATA_DIR / "portfolio.json"
    if port_path.exists():
        try:
            p = json.loads(port_path.read_text())

            # Estructura estándar del router/portfolio.py
            if all(k in p for k in ["crypto", "equities", "commodities"]):
                crypto      = [t.upper() for t in p.get("crypto", []) if t]
                equities    = [t.upper() for t in p.get("equities", []) if t]
                commodities = [t.upper() for t in p.get("commodities", []) if t]

                # Garantizar que haya al menos un equity como benchmark
                if "SPY" not in equities and "QQQ" not in equities:
                    equities = ["SPY"] + equities

                tickers    = equities + crypto + commodities
                sleeve_map = {}
                for t in crypto:      sleeve_map[t] = "crypto"
                for t in equities:    sleeve_map[t] = "equity"
                for t in commodities: sleeve_map[t] = "commodity"

                print(f"  [portfolio] cargado: {tickers}")
                return tickers, sleeve_map, crypto

        except Exception as e:
            print(f"  [portfolio] error leyendo config: {e}")

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
CRYPTO_SPLIT = (
    {t: 1 / len(CRYPTO_TICKERS) for t in CRYPTO_TICKERS}
    if CRYPTO_TICKERS else {}
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def download_prices(tickers, start="2018-01-01"):
    print(f"  Descargando {tickers} desde {start}...")
    raw  = yf.download(tickers, start=start, auto_adjust=True, progress=False)
    data = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    data = data.dropna(how="all").ffill()
    print(f"  → {len(data)} filas hasta {data.index[-1].date()}")
    return data


def trend_phase(price, ma):
    if pd.isna(price) or pd.isna(ma):
        return "NO_DATA", 0.0, 0.0
    dist = (price - ma) / ma if ma != 0 else 0.0
    risk = abs(price - ma) / price if price > 0 else 0.0
    if price < ma:    return "BROKEN",   dist, risk
    elif dist < 0.03: return "EARLY",    dist, risk
    elif dist < 0.07: return "OK",       dist, risk
    else:             return "EXTENDED", dist, risk


def phase_size(ph):
    return {"EARLY": 1.0, "OK": 0.7, "EXTENDED": 0.4}.get(ph, 0.0)


def build_position(entry, exit_):
    """Vectorizado con NumPy — igual que core.py optimizado."""
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
        return 0.20  # fallback razonable
    tail = r.tail(window) if len(r) >= window else r
    return float(tail.std() * np.sqrt(252))


def vol_adjusted_size(base, vol, target=0.20):
    if vol <= 0:
        return base
    return min(base * (target / vol), 1.5)


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
        ph  = "BARATO" if val < 90 else "JUSTO" if val < 120 else "CARO"
        mt  = 1.2 if val < 90 else 1.0 if val < 120 else 0.7
        return {"value": round(val, 1), "phase": ph, "mult": mt, "yoy": round(yoy, 1) if yoy else None}
    except Exception as e:
        print(f"  [buffett] error: {e}")
        return {"value": None, "phase": "N/A", "mult": 1.0, "yoy": None}


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

    positions = {}
    for t in TICKERS:
        if t not in data.columns:
            continue
        entry       = data[t] > data[f"{t}_HIGH{WINDOW}"].shift(1)
        exit_       = data[t] < data[f"{t}_MA{WINDOW}"]
        positions[t] = build_position(entry, exit_)

    latest = data.iloc[-1]
    phases, sizes, active, vols = {}, {}, {}, {}

    for t in TICKERS:
        if t not in data.columns:
            continue
        ph, dist, risk = trend_phase(float(latest[t]), float(latest[f"{t}_MA{WINDOW}"]))
        phases[t] = {
            "phase": ph,
            "dist":  round(dist * 100, 2),
            "risk":  round(risk * 100, 2),
            "price": round(float(latest[t]), 2),
        }
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

    return {
        "weights":      weights,
        "phases":       phases,
        "active":       active,
        "dominant":     dominant,
        "buffett":      buffett,
        "volatilities": vols,
        "signal_date":  str(data.index[-1].date()),
        "generated_at": datetime.utcnow().isoformat(),
        "cash_pct":     cash_pct,
        "quality":      quality,
        "tickers":      TICKERS,
    }


# ── Performance ───────────────────────────────────────────────────────────────

def compute_recent_performance():
    """
    Backtest desde 2020 con los tickers del portfolio actual.
    FIX: usa multiplicador Buffett real (calculado una sola vez).
    """
    print("  Calculando performance...")
    data = download_prices(TICKERS, start="2020-01-01")

    for t in TICKERS:
        if t in data.columns:
            data[f"{t}_MA{WINDOW}"]   = data[t].rolling(WINDOW, min_periods=20).mean()
            data[f"{t}_HIGH{WINDOW}"] = data[t].rolling(WINDOW, min_periods=20).max()

    positions = {}
    for t in TICKERS:
        if t not in data.columns:
            continue
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
    rebal_dates = data.resample("W").last().index
    rebal_dates = rebal_dates[rebal_dates >= data.index[WINDOW + 5]]

    spy_col = "SPY" if "SPY" in data.columns else data.columns[0]
    sv, bv  = 100.0, 100.0
    curve, weekly = [], []

    for i, date in enumerate(rebal_dates):
        if date not in data.index:
            continue
        loc = data.index.get_loc(date)
        row = data.iloc[loc]

        # Pesos con mult Buffett real
        w = compute_weights_at(row, positions, loc, TICKERS, SLEEVE_MAP, CRYPTO_SPLIT, vols, buffett_mult)

        nd = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else data.index[-1]
        if nd not in data.index:
            continue

        next_loc = data.index.get_loc(nd)

        # Retorno compuesto del período (vectorizado)
        pr = 0.0
        for t, wt in w.items():
            if wt == 0 or t not in daily_rets.columns:
                continue
            ticker_rets = daily_rets[t].iloc[loc + 1: next_loc + 1].values
            if len(ticker_rets) > 0:
                pr += wt * float(np.prod(1 + ticker_rets) - 1)

        spy_rets = daily_rets[spy_col].iloc[loc + 1: next_loc + 1].values
        br       = float(np.prod(1 + spy_rets) - 1) if len(spy_rets) > 0 else 0.0

        sv *= (1 + pr)
        bv *= (1 + br)
        weekly.append(round(pr * 100, 3))
        curve.append({
            "date":      str(date.date()),
            "strategy":  round(sv, 2),
            "benchmark": round(bv, 2),
        })

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
    peak      = np.maximum.accumulate(vals)
    dd        = ((vals - peak) / peak * 100).tolist()
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

🎯 *DOMINANTE: {signal['dominant']}*

📦 *ASIGNACIÓN:*
```
{alloc}
```
📈 *FASES:*
```
{phases_txt}
```
🌍 Buffett: `{buff_txt}`
_Quant Rotational v2_"""

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
