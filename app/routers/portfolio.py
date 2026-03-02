import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PORT_PATH = DATA_DIR / "portfolio.json"

DEFAULT = {
    "crypto": ["BTC-USD", "ETH-USD"],
    "equities": ["SPY", "QQQ"],
    "commodities": ["GLD"]
}


# =========================
# LOAD
# =========================
def load_port():
    try:
        if PORT_PATH.exists():
            data = json.loads(PORT_PATH.read_text())

            # validar estructura
            if all(k in data for k in ["crypto", "equities", "commodities"]):
                return data
    except Exception:
        pass

    return DEFAULT


# =========================
# SAVE
# =========================
def save_port(p: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    clean = {
        "crypto": [t.upper() for t in p.get("crypto", [])],
        "equities": [t.upper() for t in p.get("equities", [])],
        "commodities": [t.upper() for t in p.get("commodities", [])],
    }

    PORT_PATH.write_text(json.dumps(clean, indent=2))
    return clean


# =========================
# ROUTES
# =========================
@router.get("")
async def get_portfolio():
    return load_port()


@router.post("")
async def set_portfolio(body: dict):
    try:
        return save_port(body)
    except Exception as e:
        raise HTTPException(500, str(e))
