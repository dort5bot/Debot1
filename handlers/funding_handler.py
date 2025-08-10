# handlers/funding_handler.py
from utils import binance_api

async def handle_funding_data(data):
    # data may be the payload for fundingRate stream or REST item
    # normalize fields depending on source
    # This is a simple processor — extend as needed.
    try:
        # When coming from combined ws, it will be in data with keys like 's' or 'symbol'
        symbol = data.get("s") or data.get("symbol")
        rate = data.get("r") or data.get("fundingRate")
        time = data.get("T") or data.get("fundingTime")
        print(f"[FUNDING] {symbol} rate={rate} time={time}")
    except Exception as e:
        print("funding handler error", e)
