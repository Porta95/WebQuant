"""
routers/portfolio.py — Gestión de cartera persistida en GitHub.

En lugar de escribir en el filesystem de Railway (efímero),
lee y escribe data/portfolio.json directamente en el repo de GitHub
via la GitHub Contents API. Esto garantiza persistencia entre deploys y restarts.

Variables de entorno requeridas en Railway:
  GITHUB_TOKEN  = ghp_...   (Personal Access Token con permisos repo)
  GITHUB_REPO   = Porta95/WebQuant
"""

import os
import json
import base64
import requests
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_API   = "https://api.github.com"
FILE_PATH    = "data/portfolio.json"

DEFAULT_PORTFOLIO = {
<<<<<<< HEAD
    "crypto":      ["BTC-USD", "ETH-USD"],
    "equities":    ["SPY", "QQQ"],
    "commodities": ["GLD"],
=======
    "equities":    ["SPY", "QQQ", "XLE", "XLK", "XLV"],
    "reits":       ["VNQ"],
    "crypto":      ["BTC-USD", "ETH-USD"],
    "commodities": ["GLD", "SLV"],
    "bonds":       ["IEF", "BIL"],
    "merval":      ["GGAL.BA", "BMA.BA", "YPFD.BA", "ALUA.BA", "PAMP.BA"],
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
}


def _headers() -> dict:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(
            status_code=503,
            detail="GITHUB_TOKEN no configurado en Railway. Agregalo en Variables."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _repo() -> str:
    repo = os.getenv("GITHUB_REPO", "Porta95/WebQuant")
    return repo


def _get_file() -> tuple[dict, str]:
    """
    Obtiene el contenido actual de portfolio.json desde GitHub.
    Retorna (contenido_parseado, sha_del_archivo).
    El sha es necesario para poder hacer el PUT (update).
    """
    url = f"{GITHUB_API}/repos/{_repo()}/contents/{FILE_PATH}"
    r   = requests.get(url, headers=_headers(), timeout=10)

    if r.status_code == 404:
        # El archivo no existe todavía → retornar defaults con sha vacío
        return DEFAULT_PORTFOLIO.copy(), ""

    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Error leyendo portfolio desde GitHub: {r.status_code} {r.text[:200]}"
        )

    data    = r.json()
    sha     = data["sha"]
    content = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    return content, sha


def _put_file(content: dict, sha: str, message: str = "portfolio: actualizar cartera") -> dict:
    """
    Escribe portfolio.json en GitHub via Contents API.
    Si sha está vacío, crea el archivo. Si tiene sha, lo actualiza.
    """
    url     = f"{GITHUB_API}/repos/{_repo()}/contents/{FILE_PATH}"
    encoded = base64.b64encode(
        json.dumps(content, indent=2).encode("utf-8")
    ).decode("utf-8")

    body = {
        "message": message,
        "content": encoded,
        "branch":  "main",
    }
    if sha:
        body["sha"] = sha  # requerido para actualizar archivo existente

    r = requests.put(url, headers=_headers(), json=body, timeout=15)

    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Error guardando portfolio en GitHub: {r.status_code} {r.text[:200]}"
        )

    return r.json()


def _clean_portfolio(p: dict) -> dict:
<<<<<<< HEAD
    """Normaliza y valida la estructura del portfolio."""
    cleaned = {
        "crypto":      [t.upper().strip() for t in p.get("crypto", [])      if t],
        "equities":    [t.upper().strip() for t in p.get("equities", [])    if t],
        "commodities": [t.upper().strip() for t in p.get("commodities", []) if t],
=======
    """Normaliza y valida la estructura del portfolio (soporta todos los sleeves v3)."""
    cleaned = {
        "equities":    [t.upper().strip() for t in p.get("equities", [])    if t],
        "reits":       [t.upper().strip() for t in p.get("reits", [])       if t],
        "crypto":      [t.upper().strip() for t in p.get("crypto", [])      if t],
        "commodities": [t.upper().strip() for t in p.get("commodities", []) if t],
        "bonds":       [t.upper().strip() for t in p.get("bonds", [])       if t],
        "merval":      [t.upper().strip() for t in p.get("merval", [])      if t],
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
    }

    # Garantizar al menos SPY como equity para el benchmark del backtest
    if not cleaned["equities"]:
        cleaned["equities"] = ["SPY"]

    return cleaned


# ── Rutas ─────────────────────────────────────────────────────────────────────

@router.get("")
async def get_portfolio():
    """Retorna la cartera actual desde GitHub."""
    try:
        content, _ = _get_file()
        return content
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def set_portfolio(body: dict):
    """
    Guarda la cartera en GitHub (data/portfolio.json).
    Persiste entre deploys y restarts de Railway.
    """
    try:
        cleaned = _clean_portfolio(body)

        # Obtener sha actual para el update
        _, sha = _get_file()

        _put_file(
            content = cleaned,
            sha     = sha,
            message = f"portfolio: actualizar cartera via dashboard",
        )

        return cleaned

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def portfolio_status():
    """
    Verifica que la integración con GitHub esté funcionando.
    Útil para debuggear desde /docs.
    """
    token = os.getenv("GITHUB_TOKEN")
    repo  = _repo()

    if not token:
        return {
            "ok":    False,
            "error": "GITHUB_TOKEN no configurado",
            "fix":   "Agregar GITHUB_TOKEN en Railway → Variables"
        }

    try:
        content, sha = _get_file()
<<<<<<< HEAD
=======
        all_tickers = (
            content.get("equities", []) +
            content.get("reits", []) +
            content.get("crypto", []) +
            content.get("commodities", []) +
            content.get("bonds", []) +
            content.get("merval", [])
        )
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
        return {
            "ok":      True,
            "repo":    repo,
            "file":    FILE_PATH,
            "sha":     sha[:8] if sha else "nuevo",
<<<<<<< HEAD
            "tickers": (
                content.get("crypto", []) +
                content.get("equities", []) +
                content.get("commodities", [])
            ),
=======
            "tickers": all_tickers,
            "sleeves": {
                "equities":    content.get("equities", []),
                "crypto":      content.get("crypto", []),
                "commodities": content.get("commodities", []),
                "bonds":       content.get("bonds", []),
                "merval":      content.get("merval", []),
            },
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
        }
    except HTTPException as e:
        return {"ok": False, "error": e.detail}
