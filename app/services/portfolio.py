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

def load_portfolio():
    try:
        if PORTFOLIO_FILE.exists():
            return json.loads(PORTFOLIO_FILE.read_text())
    except Exception:
        pass
    return DEFAULT_PORTFOLIO
