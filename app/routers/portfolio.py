import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PORT_PATH = DATA_DIR / "portfolio.json"

DEFAULT = {
    "crypto": ["BTC-USD","ETH-USD"],
    "equities": ["SPY","QQQ"],
    "commodities": ["GLD"]
}

def load_port():
    if PORT_PATH.exists():
        return json.loads(PORT_PATH.read_text())
    return DEFAULT

def save_port(p):
    PORT_PATH.write_text(json.dumps(p, indent=2))

@router.get("")
async def get_portfolio():
    return load_port()

@router.post("")
async def set_portfolio(body: dict):
    save_port(body)
    return {"ok": True}
