# handlers/ticker_handler.py
#sadece canlı akışı gözlemlemek için var, 
#anlamlı bir veri saklama veya işleme yapmaz
#gerçek uygulamada komut veya veri kaydı için genişletmek gerekir.

from utils import binance_api

async def handle_ticker_data(data):
    try:
        symbol = data.get("s") or data.get("symbol")
        last_price = data.get("c") or data.get("lastPrice")
        vol = data.get("v") or data.get("volume")
        print(f"[TICKER] {symbol} price={last_price} vol={vol}")
    except Exception as e:
        print("ticker handler error", e)
