import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"

DEFAULT = {
    "assets": [
        {"ticker": "BTC-USD", "enabled": True},
        {"ticker": "ETH-USD", "enabled": True},
        {"ticker": "QQQ", "enabled": True},
        {"ticker": "SPY", "enabled": True},
        {"ticker": "GLD", "enabled": True},
    ]
}

def load_portfolio():
    if not PORTFOLIO_FILE.exists():
        return DEFAULT
    return json.loads(PORTFOLIO_FILE.read_text())

def save_portfolio(data: dict):
    PORTFOLIO_FILE.write_text(json.dumps(data, indent=2))
