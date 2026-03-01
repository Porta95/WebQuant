import yfinance as yf
import requests
from datetime import datetime

print("Test 1: requests directo a Yahoo...")
try:
    r = requests.get(
        "https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=5d",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10
    )
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

print("\nTest 2: yfinance con fecha explícita...")
try:
    data = yf.download("SPY", start="2024-01-01", end="2024-12-31", progress=False)
    print(f"Rows: {len(data)}")
    print(data.tail(3))
except Exception as e:
    print(f"Error: {e}")
