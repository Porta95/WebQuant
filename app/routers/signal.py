"""
signal.py — Router para señales rotacionales.
GET  /api/signal          → señal actual
POST /api/signal/telegram → envía señal a Telegram
"""

import os
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from ..services.core import compute_signal, DEFAULT_TICKERS
from ..services.telegram import send_signal_to_telegram, send_telegram
from ..models.schemas import SignalResponse, TelegramRequest, TelegramResponse

router = APIRouter(prefix="/api/signal", tags=["signal"])


@router.get("/", response_model=SignalResponse)
async def get_signal(
    tickers: Optional[str] = Query(
        default=None,
        description="Tickers separados por coma. Ej: SPY,QQQ,BTC-USD,ETH-USD,GLD"
    ),
    window: int = Query(default=50, ge=10, le=200, description="Ventana Donchian/MA"),
):
    """
    Calcula y retorna la señal rotacional actual.
    Descarga datos en tiempo real desde yfinance.
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",")] if tickers else DEFAULT_TICKERS

    try:
        result = compute_signal(tickers=ticker_list, window=window)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/telegram", response_model=TelegramResponse)
async def send_to_telegram(body: TelegramRequest):
    """
    Envía la señal actual a Telegram.
    Si se pasa `message`, envía ese texto directamente.
    """
    token   = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise HTTPException(
            status_code=503,
            detail="TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados en variables de entorno"
        )

    try:
        if body.message:
            result = send_telegram(body.message, token, chat_id)
        else:
            signal = compute_signal()
            result = send_signal_to_telegram(signal, token, chat_id)

        if result.get("ok"):
            return TelegramResponse(ok=True, message="Señal enviada correctamente")
        else:
            return TelegramResponse(ok=False, error=result.get("description", "Error desconocido"))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
