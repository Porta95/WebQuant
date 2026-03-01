import requests
import yfinance as yf
from fastapi import APIRouter

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/network")
async def test_network():
    results = {}
    try:
        r = requests.get("https://www.google.com", timeout=5)
        results["google"] = r.status_code
    except Exception as e:
        results["google"] = str(e)
    try:
        data = yf.download("SPY", period="5d", progress=False)
        results["yfinance_spy"] = f"OK - {len(data)} rows"
    except Exception as e:
        results["yfinance_spy"] = str(e)
    return results
