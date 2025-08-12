# handlers/funding_handler.py
###fonlama oranı binance 
import asyncio
from utils import binance_api

async def funding_report(symbols=None):
    """
    Funding rate raporu üretir.
    symbols: list[str] veya None
    """
    all_symbols = await binance_api.get_all_symbols()

    # Sadece USDT perpetual'lar
    futures_symbols = [s for s in all_symbols if s.endswith("USDT")]

    if symbols:
        # Kullanıcının yazdığı coinleri USDT ile tamamla
        req_symbols = []
        for sym in symbols:
            s = sym.upper()
            if not s.endswith("USDT"):
                s += "USDT"
            if s in futures_symbols:
                req_symbols.append(s)
        futures_symbols = req_symbols

    if not futures_symbols:
        return "❌ Geçerli bir sembol bulunamadı."

    results = []

    async def fetch_funding(sym):
        try:
            data = await binance_api.get_funding_rate(symbol=sym, limit=1)
            if data and isinstance(data, list) and len(data) > 0:
                rate = float(data[0]["fundingRate"]) * 100
                return (sym, rate)
        except:
            return None

    tasks = [fetch_funding(s) for s in futures_symbols]
    fetched = await asyncio.gather(*tasks)

    for item in fetched:
        if item:
            results.append(item)

    if not results:
        return "❌ Veri alınamadı."

    # Rate'e göre sırala (mutlak değeri en yüksek olanlar başta)
    results.sort(key=lambda x: abs(x[1]), reverse=True)

    if not symbols:
        # Sadece top 10 göster
        results = results[:10]

    # Ortalama funding
    avg_rate = sum(r[1] for r in results) / len(results)

    # Formatla
    lines = []
    for sym, rate in results:
        arrow = "🔼" if rate > 0 else "🔻"
        lines.append(f"{sym}: {rate:.3f}% {arrow}")

    yorum = "Short yönlü baskı artıyor" if avg_rate < 0 else "Long yönlü baskı artıyor"

    return f"📊 Funding Rate Raporu\n" + "\n".join(lines) + \
           f"\n\nGenel Ortalama: {avg_rate:.3f}% {'🔻' if avg_rate < 0 else '🔼'}\nYorum: {yorum}"
    
