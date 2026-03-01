"""
main.py — Entry point de la API FastAPI.

Arrancar en desarrollo:
    uvicorn app.main:app --reload --port 8000

Estructura de endpoints:
    GET  /                          → health check
    GET  /api/signal                → señal actual
    POST /api/signal/telegram       → enviar señal a Telegram
    POST /api/backtest              → backtest completo
    GET  /api/backtest/scenarios    → escenarios disponibles
    GET  /api/backtest/stress/{key} → stress test
    POST /api/backtest/analyze      → analizador de activos
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import signal, backtest

app = FastAPI(
    title="Quant Rotational API",
    description="Motor cuantitativo rotacional con señales, backtest y análisis de activos.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# En producción reemplazar "*" por el dominio de Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(signal.router)
app.include_router(backtest.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/", tags=["health"])
async def root():
    return {
        "status": "ok",
        "service": "Quant Rotational API v2",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health():
    return {"status": "healthy"}
