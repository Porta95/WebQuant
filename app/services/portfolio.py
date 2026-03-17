"""
services/portfolio.py — Portfolio loader unificado.

Orden de prioridad para leer la cartera:
  1. GitHub API  (si GITHUB_TOKEN está configurado en Railway)
  2. Filesystem local  (data/portfolio.json — usado en GitHub Actions y dev)
  3. DEFAULT_TICKERS   (fallback)

Esto garantiza que Railway siempre tenga la versión actualizada
aunque el usuario haya modificado la cartera sin hacer un nuevo deploy.
"""

import json
import os
import base64
from pathlib import Path

import requests as _requests

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"

GITHUB_API  = "https://api.github.com"
FILE_PATH   = "data/portfolio.json"

DEFAULT_TICKERS = ["SPY", "QQQ", "BTC-USD", "ETH-USD", "GLD", "IEF", "BIL"]


# ── helpers ────────────────────────────────────────────────────────────────────

def _tickers_from_dict(p: dict) -> list[str]:
    """Extract tickers from either portfolio format."""
    # New format: {assets: [{ticker, enabled}]}
    if "assets" in p and isinstance(p["assets"], list):
        return [a["ticker"] for a in p["assets"] if a.get("enabled", True)]

    # Sleeve format: {equities:[], reits:[], crypto:[], commodities:[], bonds:[], merval:[]}
    return (
        p.get("equities",    [])
        + p.get("reits",       [])
        + p.get("crypto",      [])
        + p.get("commodities", [])
        + p.get("bonds",       [])
        + p.get("merval",      [])
    )


def _load_from_github() -> list[str]:
    """
    Fetch portfolio.json from GitHub Contents API.
    Returns [] on any failure so caller can fall through to local file.
    """
    token = os.getenv("GITHUB_TOKEN")
    repo  = os.getenv("GITHUB_REPO", "Porta95/WebQuant")
    if not token:
        return []
    try:
        url = f"{GITHUB_API}/repos/{repo}/contents/{FILE_PATH}"
        r = _requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=8,
        )
        if not r.ok:
            return []
        raw  = json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
        tickers = _tickers_from_dict(raw)
        if tickers:
            print(f"[portfolio] loaded {len(tickers)} tickers from GitHub")
            return tickers
    except Exception as e:
        print(f"[portfolio] GitHub fetch failed: {e}")
    return []


def _load_from_file() -> list[str]:
    """Read portfolio.json from local filesystem."""
    try:
        if PORTFOLIO_FILE.exists():
            p = json.loads(PORTFOLIO_FILE.read_text())
            tickers = _tickers_from_dict(p)
            if tickers:
                print(f"[portfolio] loaded {len(tickers)} tickers from local file")
                return tickers
    except Exception as e:
        print(f"[portfolio] local file read failed: {e}")
    return []


# ── public API ────────────────────────────────────────────────────────────────

def load_portfolio_tickers() -> list[str]:
    """
    Load enabled tickers with GitHub API → local file → default fallback.
    """
    tickers = _load_from_github() or _load_from_file()
    if tickers:
        return tickers
    print(f"[portfolio] using default {len(DEFAULT_TICKERS)}-asset universe")
    return DEFAULT_TICKERS


def load_portfolio() -> dict:
    """Legacy: returns {assets:[...]} format for backward compat."""
    tickers = load_portfolio_tickers()
    return {"assets": [{"ticker": t, "enabled": True} for t in tickers]}


def save_portfolio(portfolio: dict):
    """Save to local file (used only in dev / GitHub Actions context)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cleaned = {
        "assets": [
            {"ticker": a["ticker"].upper(), "enabled": bool(a.get("enabled", True))}
            for a in portfolio.get("assets", [])
        ]
    }
    PORTFOLIO_FILE.write_text(json.dumps(cleaned, indent=2))
    return cleaned
