"""
telegram.py — Servicio de notificaciones a Telegram.
Formatea y envía la señal diaria.
"""

import requests
from typing import Optional


def format_signal_message(signal: dict) -> str:
    """Formatea la señal rotacional para Telegram con emojis."""
    w  = signal.get("weights", {})
    ph = signal.get("phases", {})
    bf = signal.get("buffett", {})
    quality = signal.get("quality", "—")
    dominant = signal.get("dominant", "—")
    date = signal.get("signal_date", "—")
    cash = signal.get("cash_pct", 0)

    quality_emoji = {"ALTA": "🟢", "MEDIA": "🟡", "BAJA": "🔴"}.get(quality, "⚪")
    phase_emoji   = {"EARLY": "🌱", "OK": "✅", "EXTENDED": "⚠️", "BROKEN": "❌", "NO_DATA": "❓"}

    def phase_line(ticker: str) -> str:
        info = ph.get(ticker, {})
        p    = info.get("phase", "—")
        dist = info.get("dist", 0)
        sign = "+" if dist >= 0 else ""
        return f"{phase_emoji.get(p,'⚪')} {ticker:10s} {p:9s} ({sign}{dist:.1f}% vs MA50)"

    alloc_lines = []
    for ticker, pct in sorted(w.items(), key=lambda x: -x[1]):
        bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
        alloc_lines.append(f"  {ticker:10s} {pct:5.0%}  {bar}")
    if cash > 0.01:
        alloc_lines.append(f"  {'CASH':10s} {cash:5.0%}")

    buffett_val   = bf.get("value")
    buffett_phase = bf.get("phase", "N/A")
    buffett_mult  = bf.get("mult", 1.0)
    buff_str      = f"{buffett_val:.0f}% → {buffett_phase} (×{buffett_mult})" if buffett_val else "N/A"

    msg = f"""
📊 *QUANT ROTATIONAL — SEÑAL DIARIA*
📅 Fecha: `{date}`
{quality_emoji} Calidad: *{quality}*

━━━━━━━━━━━━━━━━━━━━━
🎯 *ACTIVO DOMINANTE: {dominant}*
━━━━━━━━━━━━━━━━━━━━━

📦 *ASIGNACIÓN RECOMENDADA:*
```
{''.join(f'{l}\n' for l in alloc_lines)}```

📈 *FASES DE MERCADO:*
```
{''.join(f'{phase_line(t)}\n' for t in ph)}```

🌍 *INDICADOR BUFFETT:*
`{buff_str}`

{'⚠️ Equity reducida por valuación alta.' if buffett_mult < 1.0 else '✅ Equity sin restricciones.'}
━━━━━━━━━━━━━━━━━━━━━
_Generado automáticamente · Quant Rotational v2_
""".strip()

    return msg


def send_telegram(
    message: str,
    token: str,
    chat_id: str,
    parse_mode: str = "Markdown",
) -> dict:
    """Envía un mensaje a Telegram. Retorna la respuesta de la API."""
    if not token or not chat_id:
        return {"ok": False, "error": "TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados"}

    try:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(
            url,
            json={
                "chat_id":    chat_id,
                "text":       message,
                "parse_mode": parse_mode,
            },
            timeout=10,
        )
        return resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_signal_to_telegram(signal: dict, token: str, chat_id: str) -> dict:
    """Helper de alto nivel: formatea y envía la señal."""
    msg = format_signal_message(signal)
    return send_telegram(msg, token, chat_id)
