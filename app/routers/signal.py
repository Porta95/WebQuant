"""
signal.py — Lee señal desde data/signal.json (generado por GitHub Actions).
"""

import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..services.telegram import send_signal_to_telegram, send_telegram
from ..models.schemas import TelegramRequest, TelegramResponse

router = APIRouter(prefix="/api/signal", tags=["signal"])

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def read_json(filename: str) -> dict:
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Datos no disponibles aún. Corré el workflow de GitHub Actions primero.")
    return json.loads(path.read_text())


@router.get("")
async def get_signal():
    """Retorna la señal rotacional más reciente."""
    return read_json("signal.json")


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
