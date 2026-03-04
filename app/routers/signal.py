"""
signal.py — Lee señal desde GitHub raw (siempre datos frescos).
"""
import os
import json
import requests
from fastapi import APIRouter, HTTPException
from ..services.telegram import send_signal_to_telegram, send_telegram
from ..models.schemas import TelegramRequest, TelegramResponse

router = APIRouter(prefix="/api/signal", tags=["signal"])

GITHUB_RAW = "https://raw.githubusercontent.com/Porta95/WebQuant/main/data"

def fetch_json(filename: str) -> dict:
    url = f"{GITHUB_RAW}/{filename}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error obteniendo datos: {e}")

@router.get("")
async def get_signal():
    return fetch_json("signal.json")

@router.get("/history")
async def get_history():
    return fetch_json("history.json")

@router.get("/performance")
async def get_performance():
    return fetch_json("performance.json")

@router.post("/telegram", response_model=TelegramResponse)
async def send_to_telegram(body: TelegramRequest):
    token   = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise HTTPException(status_code=503, detail="TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados")
    try:
        if body.message:
            result = send_telegram(body.message, token, chat_id)
        else:
            signal = fetch_json("signal.json")
            result = send_signal_to_telegram(signal, token, chat_id)
        if result.get("ok"):
            return TelegramResponse(ok=True, message="Señal enviada correctamente")
        else:
            return TelegramResponse(ok=False, error=result.get("description", "Error desconocido"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
