"""
generate_signal.py — Corre en GitHub Actions.
Descarga datos, calcula señal completa y guarda JSON en data/.
Railway solo lee esos archivos — sin depender de Yahoo Finance.
"""

import json
import os
import sys
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────
WINDOW   = 50
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Leer portfolio.json si existe, sino usar defaults
def load_portfolio_config():
    port_path = DATA_DIR / "portfolio.json"
    if port_path.exists():
        try:
            p = json.loads(port_path.read_text())
            crypto     = p.get("crypto", ["BTC-USD", "ETH-USD"])
            equities   = p.get("equities", ["SPY", "QQQ"])
            commodities = p.get("commodities", ["GLD"])
            tickers = crypto + equities + commodities
            sleeve_map = {}
            for t in crypto:      sleeve_map[t] = "crypto"
            for t in equities:    sleeve_map[t] = "equity"
            for t in commodities: sleeve_map[t] = "commodity"
            return tickers, sleeve_map, crypto
        except Exception as e:
            print(f"  [portfolio] error leyendo config: {e}")
    # defaults
    return (
        ["SPY", "QQQ", "BTC-USD", "ETH-USD", "GLD"],
        {"SPY": "equity", "QQQ": "equity", "BTC-USD": "crypto", "ETH-USD": "crypto", "GLD": "commodity"},
        ["BTC-USD", "ETH-USD"],
    )

TICKERS, SLEEVE_MAP, CRYPTO_TICKERS = load_portfolio_config()
CRYPTO_SPLIT = {t: 1/len(CRYPTO_TICKERS) for t in CRYPTO_TICKERS} if CRYPTO_TICKERS else {}

# ── Helpers ───────────────────────────────────────────────────────────────────
def download_prices(tickers, start="2018-01-01"):
    print(f"Descargando datos para {tickers}...")
    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        data = raw["Close"]
    else:
        data = raw
    data = data.dropna(how="all").ffill()
    print(f"  → {len(data)} filas descargadas hasta {data.index[-1].date()}")
    return data


def trend_phase(price, ma):
    if pd.isna(price) or pd.isna(ma):
        return "NO_DATA", 0.0, 0.0
    dist = (price - ma) / ma
    risk = abs(price - ma) / price if price != 0 else 0.0
    if price < ma:   return "BROKEN",   dist, risk
    elif dist < 0.03: return "EARLY",   dist, risk
    elif dist < 0.07: return "OK",      dist, risk
    else:             return "EXTENDED", dist, risk


def phase_size(ph):
    return {"EARLY": 1.0, "OK": 0.7, "EXTENDED": 0.4}.get(ph, 0.0)


def build_position(entry, exit_):
    pos = pd.Series(False, index=entry.index)
    in_pos = False
    for i in range(1, len(pos)):
        if not in_pos and entry.iloc[i]:   in_pos = True
        elif in_pos and exit_.iloc[i]:     in_pos = False
        pos.iloc[i] = in_pos
    return pos


def annual_vol(prices, window=90):
    r = prices.pct_change().dropna()
    return float(r.tail(window).std() * np.sqrt(252))


def get_buffett():
    try:
        wil = yf.download("^W5000", start="1990-01-01", auto_adjust=True, progress=False)["Close"]
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
        return {"value": round(val,1), "phase": ph, "mult": mt, "yoy": round(yoy,1) if yoy else None}
    except Exception as e:
        print(f"  [buffett] error: {e}")
        return {"value": None, "phase": "N/A", "mult": 1.0, "yoy": None}


# ── Signal ────────────────────────────────────────────────────────────────────
def compute_signal():
    data = download_prices(TICKERS)

    for t in TICKERS:
        if t in data.columns:
            data[f"{t}_MA{WINDOW}"]   = data[t].rolling(WINDOW, min_periods=20).mean()
            data[f"{t}_HIGH{WINDOW}"] = data[t].rolling(WINDOW, min_periods=20).max()

    positions = {}
    for t in TICKERS:
        if t not in data.columns: continue
        entry = data[t] > data[f"{t}_HIGH{WINDOW}"].shift(1)
        exit_ = data[t] < data[f"{t}_MA{WINDOW}"]
        positions[t] = build_position(entry, exit_)

    latest = data.iloc[-1]
    phases, sizes, active, vols = {}, {}, {}, {}

    for t in TICKERS:
        if t not in data.columns: continue
        ph, dist, risk = trend_phase(float(latest[t]), float(latest[f"{t}_MA{WINDOW}"]))
        phases[t] = {"phase": ph, "dist": round(dist*100,2), "risk": round(risk*100,2), "price": round(float(latest[t]),2)}
        sizes[t]  = phase_size(ph)
        active[t] = bool(positions[t].iloc[-1])
        vols[t]   = round(annual_vol(data[t]), 4)

    crypto_a    = [t for t in TICKERS if SLEEVE_MAP.get(t) == "crypto"]
    equity_a    = [t for t in TICKERS if SLEEVE_MAP.get(t) == "equity"]
    commodity_a = [t for t in TICKERS if SLEEVE_MAP.get(t) == "commodity"]

    def sleeve_s(assets):
        s = [sizes[a] for a in assets if active.get(a)]
        return max(s) if s else 0.0

    cs = sleeve_s(crypto_a); es = sleeve_s(equity_a); gs = sleeve_s(commodity_a)
    total_s = cs + es + gs

    weights  = {t: 0.0 for t in TICKERS}
    dominant = "DEFENSIVO"
    buffett  = get_buffett()

    if total_s > 0:
        bm = buffett["mult"]
        cw = cs/total_s; ew = es/total_s; gw = gs/total_s
        ew *= bm
        t2 = cw+ew+gw; cw/=t2; ew/=t2; gw/=t2

        for t in crypto_a:
            if active.get(t):
                split = CRYPTO_SPLIT.get(t, 0.5)
                base  = cw * split
                adj   = min(base * (0.20 / max(vols[t], 0.01)), 1.5)
                weights[t] = round(adj, 4)

        for t in sorted(equity_a, key=lambda x: 0 if x=="QQQ" else 1):
            if active.get(t):
                adj = min(ew * (0.20 / max(vols[t], 0.01)), 1.5)
                weights[t] = round(adj, 4)
                dominant = t
                break

        for t in commodity_a:
            if active.get(t):
                adj = min(gw * (0.20 / max(vols[t], 0.01)), 1.5)
                weights[t] = round(adj, 4)
                if dominant == "DEFENSIVO": dominant = t

        tw = sum(weights.values())
        if tw > 0:
            weights = {t: round(w/tw, 4) for t,w in weights.items()}

    cash_pct = round(max(1.0 - sum(weights.values()), 0.0), 4)
    hq = sum(1 for t in TICKERS if active.get(t) and phases.get(t,{}).get("phase") in ("EARLY","OK"))
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


# ── Backtest semanal (últimas 52 semanas para el gráfico) ─────────────────────
def compute_recent_performance():
    print("Calculando performance reciente...")
    data = download_prices(TICKERS, start="2022-01-01")

    for t in TICKERS:
        if t in data.columns:
            data[f"{t}_MA{WINDOW}"]   = data[t].rolling(WINDOW, min_periods=20).mean()
            data[f"{t}_HIGH{WINDOW}"] = data[t].rolling(WINDOW, min_periods=20).max()

    positions = {}
    for t in TICKERS:
        if t not in data.columns: continue
        entry = data[t] > data[f"{t}_HIGH{WINDOW}"].shift(1)
        exit_ = data[t] < data[f"{t}_MA{WINDOW}"]
        positions[t] = build_position(entry, exit_)

    rebal_dates = data.resample("W").last().index
    rebal_dates = rebal_dates[rebal_dates >= data.index[WINDOW + 5]]

    spy     = data["SPY"] if "SPY" in data.columns else data.iloc[:,0]
    sv, bv  = 100.0, 100.0
    curve   = []
    weekly  = []

    for i, date in enumerate(rebal_dates):
        if date not in data.index: continue
        loc = data.index.get_loc(date)
        row = data.iloc[loc]

        # Calcular pesos
        w = {}
        sizes_t, active_t = {}, {}
        for t in TICKERS:
            if t not in data.columns: continue
            ph,_,_ = trend_phase(float(row[t]), float(row[f"{t}_MA{WINDOW}"]))
            sizes_t[t]  = phase_size(ph)
            active_t[t] = bool(positions[t].iloc[loc])

        cs = max([sizes_t[t] for t in ["BTC-USD","ETH-USD"] if active_t.get(t)], default=0)
        es = max([sizes_t[t] for t in ["SPY","QQQ"] if active_t.get(t)], default=0)
        gs = sizes_t.get("GLD",0) if active_t.get("GLD") else 0
        ts = cs+es+gs

        if ts > 0:
            cw=cs/ts; ew=es/ts*0.85; gw=gs/ts
            t2=cw+ew+gw; cw/=t2; ew/=t2; gw/=t2
            for t in ["BTC-USD","ETH-USD"]:
                if active_t.get(t): w[t] = cw * CRYPTO_SPLIT.get(t,0.5)
            for t in ["QQQ","SPY"]:
                if active_t.get(t): w[t] = ew; break
            if active_t.get("GLD"): w["GLD"] = gw
            tw = sum(w.values())
            if tw > 0: w = {k:v/tw for k,v in w.items()}

        if i+1 < len(rebal_dates):
            nd = rebal_dates[i+1]
        else:
            nd = data.index[-1]

        if nd not in data.index: continue

        pr = 0.0
        for t,wt in w.items():
            p0 = float(data.loc[date,t]) if t in data.columns else None
            p1 = float(data.loc[nd,t])   if t in data.columns else None
            if p0 and p1 and p0 > 0: pr += wt*(p1/p0-1)

        s0 = float(spy.loc[date]) if date in spy.index else None
        s1 = float(spy.loc[nd])   if nd in spy.index else None
        br = (s1/s0-1) if s0 and s1 and s0>0 else 0

        sv *= (1+pr); bv *= (1+br)
        weekly.append(round(pr*100, 3))
        curve.append({
            "date":       str(date.date()),
            "strategy":   round(sv, 2),
            "benchmark":  round(bv, 2),
        })

    rets = np.array(weekly) / 100
    total_ret   = sv/100 - 1
    years       = len(rets)/52
    cagr        = (1+total_ret)**(1/max(years,0.1)) - 1
    vol         = rets.std() * np.sqrt(52)
    sharpe      = (cagr-0.05)/vol if vol > 0 else 0
    neg         = rets[rets<0]
    sortino_v   = neg.std()*np.sqrt(52) if len(neg)>0 else 0
    sortino     = (cagr-0.05)/sortino_v if sortino_v>0 else 0
    win_rate    = float(np.sum(rets>0)/len(rets)) if len(rets)>0 else 0
    vals        = np.array([p["strategy"] for p in curve])
    peak        = np.maximum.accumulate(vals)
    dd          = ((vals-peak)/peak*100).tolist()
    max_dd      = float(np.min(dd)) if dd else 0

    b_total = bv/100-1
    b_cagr  = (1+b_total)**(1/max(years,0.1))-1

    return {
        "equity_curve":    curve,
        "weekly_returns":  weekly,
        "drawdown_series": [round(d,2) for d in dd],
        "metrics": {
            "cagr":         round(cagr*100,2),
            "cagr_bench":   round(b_cagr*100,2),
            "sharpe":       round(sharpe,2),
            "sortino":      round(sortino,2),
            "max_drawdown": round(max_dd,2),
            "volatility":   round(vol*100,2),
            "win_rate":     round(win_rate*100,1),
            "total_return": round(total_ret*100,2),
            "final_value":  round(sv,2),
            "years":        round(years,1),
        },
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
    qe = {"ALTA":"🟢","MEDIA":"🟡","BAJA":"🔴"}.get(q,"⚪")
    pe = {"EARLY":"🌱","OK":"✅","EXTENDED":"⚠️","BROKEN":"❌"}

    alloc = "\n".join(
        f"  {t:10s} {p:.0%}" for t,p in sorted(w.items(), key=lambda x:-x[1]) if p > 0
    )
    phases_txt = "\n".join(
        f"  {pe.get(v['phase'],'⚪')} {t:10s} {v['phase']} ({v['dist']:+.1f}%)"
        for t,v in ph.items()
    )
    buff_txt = f"{bf['value']:.0f}% → {bf['phase']} (×{bf['mult']})" if bf["value"] else "N/A"

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
        print(f"  [telegram] {r.status_code} - {'OK' if r.json().get('ok') else r.text[:100]}")
    except Exception as e:
        print(f"  [telegram] error: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print(f"Generando señal: {datetime.utcnow().isoformat()}")
    print("=" * 50)

    # Señal
    print("\n1. Calculando señal rotacional...")
    signal = compute_signal()
    print(f"   Dominante: {signal['dominant']}")
    print(f"   Calidad:   {signal['quality']}")
    print(f"   Pesos:     {signal['weights']}")

    signal_path = DATA_DIR / "signal.json"
    signal_path.write_text(json.dumps(signal, indent=2, default=str))
    print(f"   ✅ Guardado en {signal_path}")

    # Performance
    print("\n2. Calculando performance...")
    try:
        perf = compute_recent_performance()
        print(f"   CAGR: {perf['metrics']['cagr']}% | Sharpe: {perf['metrics']['sharpe']}")
        perf_path = DATA_DIR / "performance.json"
        perf_path.write_text(json.dumps(perf, indent=2, default=str))
        print(f"   ✅ Guardado en {perf_path}")
    except Exception as e:
        print(f"   ⚠️  Error en performance: {e}")

    # Historial de señales (append)
    history_path = DATA_DIR / "history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else []
    entry = {
        "date":     signal["signal_date"],
        "dominant": signal["dominant"],
        "weights":  signal["weights"],
        "quality":  signal["quality"],
        "buffett":  signal["buffett"],
    }
    # Evitar duplicados del mismo día
    history = [h for h in history if h.get("date") != signal["signal_date"]]
    history.append(entry)
    history = sorted(history, key=lambda x: x["date"], reverse=True)[:52]  # últimas 52 semanas
    history_path.write_text(json.dumps(history, indent=2, default=str))
    print(f"   ✅ Historial: {len(history)} entradas")

    # Telegram
    print("\n3. Enviando a Telegram...")
    send_telegram(signal)

    print("\n✅ Todo listo!")
