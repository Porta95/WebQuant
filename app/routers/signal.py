"""
signal.py — Lee señal desde data/signal.json (generado por GitHub Actions).
"""

import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..services.telegram import send_signal_to_telegram, send_telegram
from ..models.schemas import TelegramRequest, TelegramResponse
from ..routers.portfolio import load_port
from app.core import compute_signal
from ..services.portfolio import load_portfolio

router = APIRouter(prefix="/api/signal", tags=["signal"])

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def read_json(filename: str) -> dict:
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Datos no disponibles aún. Corré el workflow de GitHub Actions primero.")
    return json.loads(path.read_text())


@router.get("")
async def get_signal():
    """Retorna señal calculada usando cartera del usuario."""
    port = load_port()

    tickers = (
        port.get("crypto", []) +
        port.get("equities", []) +
        port.get("commodities", [])
    )

    if not tickers:
        raise HTTPException(400, "Portfolio vacío")

    return compute_signal(tickers)

@router.get("/compute")
async def compute_live_signal():
    """
    Señal dinámica basada en la cartera del usuario.
    """
    try:
        portfolio = load_portfolio()
        tickers = [a["ticker"] for a in portfolio.get("assets", []) if a.get("enabled")]

        if not tickers:
            tickers = None  # usa DEFAULT_TICKERS

        signal = compute_signal(tickers)
        return signal

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal compute error: {e}")


@router.get("/history")
async def get_history():
    """Retorna historial de señales semanales."""
    return read_json("history.json")


@router.get("/performance")
async def get_performance():
    """Retorna equity curve y métricas de performance."""
    return read_json("performance.json")


@router.post("/telegram", response_model=TelegramResponse)
async def send_to_telegram(body: TelegramRequest):
    """Envía la señal actual a Telegram."""
    token   = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise HTTPException(status_code=503, detail="TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados")

    try:
        if body.message:
            result = send_telegram(body.message, token, chat_id)
        else:
            signal = read_json("signal.json")
            result = send_signal_to_telegram(signal, token, chat_id)

        if result.get("ok"):
            return TelegramResponse(ok=True, message="Señal enviada correctamente")
        else:
            return TelegramResponse(ok=False, error=result.get("description", "Error desconocido"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from app.core import compute_signal
from pathlib import Path
import json

PORTFOLIO_FILE = DATA_DIR / "portfolio.json"


def read_portfolio_tickers():
    if not PORTFOLIO_FILE.exists():
        return ["SPY", "QQQ", "BTC-USD", "ETH-USD", "GLD"]

    p = json.loads(PORTFOLIO_FILE.read_text())
    return list(set(
        p.get("crypto", []) +
        p.get("equities", []) +
        p.get("commodities", [])
    ))


@router.get("/compute")
async def compute_dynamic_signal():
    tickers = read_portfolio_tickers()
    sig = compute_signal(tickers)
    return sig
