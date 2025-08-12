# handlers/funding_handler.py
###fonlama oranı binance 
from utils import binance_api
from datetime import datetime

async def funding_report(symbols):
    """
    Seçilen coinler için funding oranlarını API'den alır ve rapor üretir.
    """
    try:
        data = await binance_api.get_funding_rates(symbols)
        if not data:
            return "❌ Funding verisi alınamadı."

        report_lines = ["📊 **Funding Oranları**\n"]
        for item in data:
            sym = item.get("symbol", "???")
            rate = float(item.get("fundingRate", 0)) * 100
            time_ms = item.get("fundingTime")
            if time_ms:
                time_str = datetime.fromtimestamp(time_ms / 1000).strftime("%Y-%m-%d %H:%M")
            else:
                time_str = "-"
            color = "🟢" if rate > 0 else "🔴" if rate < 0 else "⚪"
            report_lines.append(f"{color} {sym}: {rate:.4f}% ({time_str})")

        return "\n".join(report_lines)

    except Exception as e:
        return f"❌ Funding raporu hatası: {e}"


async def handle_funding_data(data):
    """
    Stream veya periyodik polling ile gelen funding verilerini işler.
    """
    try:
        # WebSocket fundingRate event formatı
        if "s" in data and "r" in data:
            symbol = data["s"]
            rate = float(data["r"]) * 100
            time_str = datetime.fromtimestamp(data["T"] / 1000).strftime("%Y-%m-%d %H:%M")
            print(f"[WS] Funding Update: {symbol} → {rate:.4f}% @ {time_str}")
            return

        # REST veya polling formatı
        if "symbol" in data and "fundingRate" in data:
            symbol = data["symbol"]
            rate = float(data["fundingRate"]) * 100
            time_ms = data.get("fundingTime")
            time_str = datetime.fromtimestamp(time_ms / 1000).strftime("%Y-%m-%d %H:%M") if time_ms else "-"
            print(f"[API] Funding Update: {symbol} → {rate:.4f}% @ {time_str}")
            return

        print("⚠️ Tanınmayan funding data formatı:", data)

    except Exception as e:
        print(f"❌ handle_funding_data hata: {e}")
