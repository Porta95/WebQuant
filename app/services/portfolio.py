import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"

DEFAULT_TICKERS = ["BTC-USD", "ETH-USD", "QQQ", "SPY", "GLD"]

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
# LOAD (legacy {assets} format)
# =========================
def load_portfolio():
    try:
        if PORTFOLIO_FILE.exists():
            data = json.loads(PORTFOLIO_FILE.read_text())
            if "assets" in data and isinstance(data["assets"], list):
                return data
    except Exception:
        pass
    return DEFAULT_PORTFOLIO


# =========================
# UNIFIED TICKER LOADER
# Supports both storage formats:
#   new:    {assets: [{ticker, enabled}]}
#   legacy: {crypto: [...], equities: [...], commodities: [...]}
# =========================
def load_portfolio_tickers() -> list[str]:
    """
    Read enabled tickers from portfolio.json regardless of which format it uses.
    Falls back to DEFAULT_TICKERS if the file is missing or cannot be parsed.
    """
    try:
        if PORTFOLIO_FILE.exists():
            p = json.loads(PORTFOLIO_FILE.read_text())

            # New format: {assets: [{ticker, enabled}, ...]}
            if "assets" in p and isinstance(p["assets"], list):
                tickers = [a["ticker"] for a in p["assets"] if a.get("enabled", True)]
                if tickers:
                    return tickers

            # Router format: all 6 sleeves (equities/reits/crypto/commodities/bonds/merval)
            tickers = (
                p.get("equities", [])
                + p.get("reits", [])
                + p.get("crypto", [])
                + p.get("commodities", [])
                + p.get("bonds", [])
                + p.get("merval", [])
            )
            if tickers:
                return tickers

    except Exception:
        pass

    return DEFAULT_TICKERS


# =========================
# SAVE
# =========================
def save_portfolio(portfolio: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

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
