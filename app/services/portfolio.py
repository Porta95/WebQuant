import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"

DEFAULT_PORTFOLIO = {
    "assets": [
        {"ticker": "BTC-USD", "enabled": True},
        {"ticker": "ETH-USD", "enabled": True},
        {"ticker": "QQQ", "enabled": True},
        {"ticker": "SPY", "enabled": True},
        {"ticker": "GLD", "enabled": True},
    ]
}


# =========================
# LOAD
# =========================
def load_portfolio():
    try:
        if PORTFOLIO_FILE.exists():
            data = json.loads(PORTFOLIO_FILE.read_text())

            # validación mínima
            if "assets" in data and isinstance(data["assets"], list):
                return data
    except Exception:
        pass

    return DEFAULT_PORTFOLIO


# =========================
# SAVE
# =========================
def save_portfolio(portfolio: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # normalizar estructura
    cleaned = {
        "assets": [
            {
                "ticker": a["ticker"].upper(),
                "enabled": bool(a.get("enabled", True)),
            }
            for a in portfolio.get("assets", [])
        ]
    }

    PORTFOLIO_FILE.write_text(json.dumps(cleaned, indent=2))
    return cleaned
