"""
generate_signal.py — GitHub Actions entrypoint.

Runs the full institutional pipeline, saves results to data/, and
sends the daily signal to Telegram.

Output files:
  data/signal.json      — current signal (weights, phases, regime, Buffett)
  data/performance.json — recent backtest metrics + equity curve
  data/history.json     — rolling 52-week signal history
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Path setup so we can import app.services ──────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import requests
from app.services.core import compute_signal, DEFAULT_TICKERS, SLEEVES
from app.services.backtest import run_backtest

DATA_DIR = REPO_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


# ── Portfolio config ───────────────────────────────────────────────────────────

def load_portfolio_tickers() -> list[str]:
    """
    Load user portfolio from data/portfolio.json if it exists and is valid.
    Falls back to the full institutional universe.
    """
    port_path = DATA_DIR / "portfolio.json"
    if port_path.exists():
        try:
            p = json.loads(port_path.read_text())
            # Support both legacy format {crypto,equities,commodities} and
            # new format {assets: [{ticker, sleeve, enabled}]}
            if "assets" in p:
                tickers = [a["ticker"] for a in p["assets"] if a.get("enabled", True)]
            else:
                tickers = (
                    p.get("crypto", [])
                    + p.get("equities", [])
                    + p.get("commodities", [])
                )
            if tickers:
                print(f"  [portfolio] loaded {len(tickers)} tickers from portfolio.json")
                return tickers
        except Exception as e:
            print(f"  [portfolio] error reading config: {e}")

    print(f"  [portfolio] using default {len(DEFAULT_TICKERS)}-asset universe")
    return DEFAULT_TICKERS


# ── Telegram ──────────────────────────────────────────────────────────────────

def format_signal_message(signal: dict) -> str:
    """Format the institutional signal as a Telegram Markdown message."""
    w       = signal.get("weights", {})
    ph      = signal.get("phases", {})
    bf      = signal.get("buffett", {})
    quality = signal.get("quality", "—")
    regime  = signal.get("regime", "—")
    vix     = signal.get("vix", "—")
    cash    = signal.get("cash_pct", 0.0)
    date    = signal.get("signal_date", "—")
    dominant = signal.get("dominant", "—")

    qe = {"ALTA": "🟢", "MEDIA": "🟡", "BAJA": "🔴"}.get(quality, "⚪")
    re = {"BULL": "🐂", "NEUTRAL": "⚖️", "BEAR": "🐻", "CRISIS": "🚨"}.get(regime, "❓")
    pe = {"EARLY": "🌱", "OK": "✅", "EXTENDED": "⚠️", "BROKEN": "❌", "NO_DATA": "❓"}

    alloc_lines = "\n".join(
        f"  {t:10s} {p:5.0%}"
        for t, p in sorted(w.items(), key=lambda x: -x[1])
        if p > 0.001
    )
    if cash > 0.01:
        alloc_lines += f"\n  {'CASH':10s} {cash:5.0%}"

    phase_lines = "\n".join(
        f"  {pe.get(v.get('phase',''),'⚪')} {t:10s} {v.get('phase',''):9s} ({v.get('dist',0):+.1f}%)"
        for t, v in ph.items()
    )

    bf_str = (
        f"{bf['value']:.0f}% → {bf['phase']} (×{bf['mult']})"
        if bf.get("value") else "N/A"
    )

    msg = f"""📊 *QUANT ROTATIONAL v3 — SEÑAL DIARIA*
📅 `{date}`
{qe} Calidad: *{quality}*  |  {re} Régimen: *{regime}*  |  VIX: `{vix}`

🎯 *DOMINANTE: {dominant}*

📦 *ASIGNACIÓN:*
```
{alloc_lines}
```
📈 *FASES:*
```
{phase_lines}
```
🌍 Buffett: `{bf_str}`
_Quant Rotational v3 · Institutional Engine_"""

    return msg.strip()


def send_telegram(signal: dict) -> None:
    token   = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("  [telegram] env vars not set, skipping")
        return

    try:
        msg = format_signal_message(signal)
        r   = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
        ok = r.json().get("ok", False)
        print(f"  [telegram] {'OK' if ok else 'FAILED: ' + r.text[:120]}")
    except Exception as e:
        print(f"  [telegram] error: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print(f"Quant Rotational v3  |  {datetime.utcnow().isoformat()} UTC")
    print("=" * 55)

    tickers = load_portfolio_tickers()

    # ── 1. Current signal ─────────────────────────────────────────────────────
    print("\n1. Computing institutional signal…")
    signal = compute_signal(tickers)
    signal["generated_at"] = datetime.utcnow().isoformat()

    print(f"   Dominant : {signal['dominant']}")
    print(f"   Regime   : {signal['regime']} (max_exposure={signal['regime_max']:.0%})")
    print(f"   VIX      : {signal['vix']}")
    print(f"   Quality  : {signal['quality']}")
    print(f"   Cash     : {signal['cash_pct']:.1%}")
    print(f"   Weights  : {signal['weights']}")

    sig_path = DATA_DIR / "signal.json"
    sig_path.write_text(json.dumps(signal, indent=2, default=str))
    print(f"   ✅ Saved → {sig_path}")

    # ── 2. Backtest / performance ─────────────────────────────────────────────
    print("\n2. Running institutional backtest (2010-present)…")
    try:
        perf = run_backtest(
            tickers=tickers,
            start="2010-01-01",
            initial_capital=10_000,
            rebalance_freq="W",
            include_costs=True,
        )
        if "metrics" in perf:
            m = perf["metrics"]
            print(f"   CAGR     : {m.get('cagr', m.get('performance', {}).get('cagr','?'))}%")
            print(f"   Sharpe   : {m.get('sharpe', m.get('risk_adjusted', {}).get('sharpe','?'))}")
            print(f"   Max DD   : {m.get('max_drawdown', m.get('drawdown', {}).get('max_drawdown','?'))}%")

        perf["generated_at"] = datetime.utcnow().isoformat()
        perf_path = DATA_DIR / "performance.json"
        perf_path.write_text(json.dumps(perf, indent=2, default=str))
        print(f"   ✅ Saved → {perf_path}")
    except Exception as e:
        print(f"   ⚠️  Backtest error: {e}")

    # ── 3. Signal history (rolling 52 weeks) ─────────────────────────────────
    print("\n3. Updating signal history…")
    history_path = DATA_DIR / "history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else []

    entry = {
        "date":       signal["signal_date"],
        "dominant":   signal["dominant"],
        "regime":     signal.get("regime", "UNKNOWN"),
        "vix":        signal.get("vix"),
        "weights":    signal["weights"],
        "quality":    signal["quality"],
        "cash_pct":   signal.get("cash_pct", 0),
        "buffett":    signal["buffett"],
    }
    history = [h for h in history if h.get("date") != signal["signal_date"]]
    history.append(entry)
    history = sorted(history, key=lambda x: x["date"], reverse=True)[:52]
    history_path.write_text(json.dumps(history, indent=2, default=str))
    print(f"   ✅ History: {len(history)} entries saved")

    # ── 4. Telegram ───────────────────────────────────────────────────────────
    print("\n4. Sending to Telegram…")
    send_telegram(signal)

    print("\n✅ Pipeline complete.")
