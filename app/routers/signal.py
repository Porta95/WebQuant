"""
signal.py — Señal dinámica basada en cartera del usuario.
"""

import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException

from ..services.core import compute_signal
from ..services.portfolio import load_portfolio_tickers
from ..services.telegram import send_signal_to_telegram, send_telegram
from ..models.schemas import TelegramRequest, TelegramResponse

router = APIRouter(prefix="/api/signal", tags=["signal"])

DATA_DIR = Path(__file__).parent.parent.parent / "data"


# =========================
# SIGNAL DINÁMICA
# =========================
@router.get("")
async def get_signal():
    """
    Señal calculada usando la cartera del usuario.
    """
    try:
        tickers = load_portfolio_tickers() or None
        return compute_signal(tickers)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal error: {e}")


# =========================
# HISTORICAL FILES
# =========================
def read_json(filename: str) -> dict:
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(503, "Datos no disponibles")
    return json.loads(path.read_text())


@router.get("/history")
async def get_history():
    return read_json("history.json")


@router.get("/performance")
async def get_performance():
    return read_json("performance.json")


# =========================
# TELEGRAM
# =========================
@router.post("/telegram", response_model=TelegramResponse)
async def send_to_telegram(body: TelegramRequest):
    token   = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise HTTPException(503, "Telegram no configurado")

    try:
        if body.message:
            result = send_telegram(body.message, token, chat_id)
        else:
            sig = await get_signal()
            result = send_signal_to_telegram(sig, token, chat_id)

        if result.get("ok"):
            return TelegramResponse(ok=True, message="Enviado")
        else:
            return TelegramResponse(ok=False, error=result.get("description"))

    except Exception as e:
        raise HTTPException(500, str(e))
