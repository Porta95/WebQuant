from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from routers import signal, backtest, debug, portfolio

app = FastAPI(
    title="Quant Rotational API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signal.router)
app.include_router(backtest.router)
app.include_router(debug.router)
app.include_router(portfolio.router)

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


