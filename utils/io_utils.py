# utils/io_utils.py
import asyncio
import math
import time
from typing import Dict, List, Optional, Tuple, Any

from utils import binance_api

# --- Config ---
IO_DEFAULT_INTERVALS = ["15m", "1h", "4h", "12h", "1d"]
IO_TOP_SYMBOLS = int(os.getenv("IO_TOP_SYMBOLS", "60")) if "os" in globals() else 60  # 24h quoteVolume'a göre seçilecek
IO_QUOTE = os.getenv("IO_QUOTE", "USDT") if "os" in globals() else "USDT"
IO_SHOW_TOP_FLOWS = int(os.getenv("IO_SHOW_TOP_FLOWS", "25")) if "os" in globals() else 25
IO_TAKER_PERIOD_FOR_FLOW = os.getenv("IO_TAKER_PERIOD_FOR_FLOW", "15m") if "os" in globals() else "15m"
IO_ORDERBOOK_LIMIT = int(os.getenv("IO_ORDERBOOK_LIMIT", "100")) if "os" in globals() else 100  # opsiyonel kullanım

# --- Helpers ---

async def _get_futures_symbols_usdt() -> List[str]:
    """USDT-M perpetual sembollerini getirir."""
    try:
        data = await binance_api._get("/fapi/v1/exchangeInfo", base=binance_api.FAPI_BASE)
        out = []
        for s in data.get("symbols", []):
            if s.get("status") == "TRADING" and s.get("contractType") in ("PERPETUAL", "CURRENT_QUARTER", "NEXT_QUARTER"):
                if s.get("quoteAsset") == IO_QUOTE:
                    out.append(s.get("symbol"))
        return sorted(list(set(out)))
    except Exception:
        return []

async def _get_top_spot_by_quote_volume(limit: int = IO_TOP_SYMBOLS) -> List[str]:
    """Spot 24h verisinden en yüksek quoteVolume olan USDT pariteleri (USDT-M futures ile kesişimi tercih edilir)."""
    fut = asyncio.create_task(_get_futures_symbols_usdt())
    tick = await binance_api.get_24h_ticker()
    futures_syms = await fut
    items = []
    for t in tick or []:
        sym = t.get("symbol")
        if not sym or not sym.endswith(IO_QUOTE):
            continue
        try:
            qv = float(t.get("quoteVolume", 0.0))
        except Exception:
            qv = 0.0
        items.append((sym, qv))
    items.sort(key=lambda x: x[1], reverse=True)
    syms = [s for s, _ in items[: limit * 2]]  # geniş seç, sonra kesiştir
    # Futures'ta da olanları öne al
    ordered = [s for s in syms if s in futures_syms]
    # Eğer yetersizse geri kalan spotları ekle
    if len(ordered) < limit:
        fill = [s for s in syms if s not in ordered]
        ordered.extend(fill[: max(0, limit - len(ordered))])
    return ordered[:limit]

async def _get_taker_long_short_ratio(symbol: str, period: str, limit: int = 48) -> List[Dict[str, Any]]:
    """
    Binance Futures: /futures/data/takerlongshortRatio
    Dönüş: [{ "buyVol": "123", "sellVol": "100", "timestamp": 1710000000000, ...}, ...]
    """
    params = {"symbol": symbol, "period": period, "limit": limit}
    try:
        data = await binance_api._get("/futures/data/takerlongshortRatio", params=params, base=binance_api.FAPI_BASE)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []

def _last_two(items: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not items:
        return None, None
    if len(items) == 1:
        return items[-1], None
    return items[-1], items[-2]

def _as_float(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0

def _ratio(buy: float, sell: float) -> float:
    tot = buy + sell
    return (buy / tot) * 100.0 if tot > 0 else 0.0

def _arrow(buy_ratio: float) -> str:
    return "🔼" if buy_ratio >= 50.0 else "🔻"

def _format_pct(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}"

def _momentum_factor(cur_total: float, prev_total: float) -> float:
    if prev_total <= 0:
        return 1.0 if cur_total > 0 else 0.0
    return cur_total / prev_total

async def taker_snapshot_for_symbol(symbol: str, period: str = "15m", hist_points: int = 6) -> Dict[str, Any]:
    """
    Bir sembol için son N noktalık taker buy/sell verilerini getirir (varsayılan 6 nokta ~ son 90dk @ 15m).
    Dönüş: {
      'symbol': 'BTCUSDT',
      'period': '15m',
      'points': [{'ts':..., 'buy':float, 'sell':float, 'buy_ratio':float}, ...],
      'last': {'buy':..., 'sell':..., 'buy_ratio':...},
      'prev': {...} | None,
      'momentum': float (son / önceki toplam)
    }
    """
    rows = await _get_taker_long_short_ratio(symbol, period, limit=max(6, hist_points))
    pts = []
    for r in rows[-hist_points:]:
        buy = _as_float(r.get("buyVol"))
        sell = _as_float(r.get("sellVol"))
        ts = int(r.get("timestamp", 0))
        pts.append({"ts": ts, "buy": buy, "sell": sell, "buy_ratio": _ratio(buy, sell)})
    last, prev = _last_two(pts)
    momentum = _momentum_factor((last["buy"] + last["sell"]) if last else 0.0,
                                (prev["buy"] + prev["sell"]) if prev else 0.0) if last else 0.0
    return {
        "symbol": symbol,
        "period": period,
        "points": pts,
        "last": last,
        "prev": prev,
        "momentum": momentum,
    }

async def market_inout(intervals: List[str] = IO_DEFAULT_INTERVALS,
                       top_n_symbols: int = IO_TOP_SYMBOLS) -> Dict[str, Any]:
    """
    Piyasa geneli için alış/satış oranı (interval bazlı) ve Nakit Göçü listesi.
    - Semboller: 24h quoteVolume'a göre top N USDT-M (mümkünse) pariteler.
    - Flow: IO_TAKER_PERIOD_FOR_FLOW döneminde net(buy-sell) en yüksekler.
    """
    symbols = await _get_top_spot_by_quote_volume(limit=top_n_symbols)
    # interval bazlı piyasa oranı
    market_ratios: Dict[str, float] = {}
    for iv in intervals:
        buys, sells = 0.0, 0.0
        # concurrency
        snaps = await asyncio.gather(*[taker_snapshot_for_symbol(s, iv, hist_points=2) for s in symbols], return_exceptions=True)
        for sn in snaps:
            if isinstance(sn, Exception) or not sn.get("last"):
                continue
            last = sn["last"]
            buys += last["buy"]
            sells += last["sell"]
        market_ratios[iv] = _ratio(buys, sells)

    # Nakit Göçü (flow) - 15m default
    flow_iv = IO_TAKER_PERIOD_FOR_FLOW
    snaps = await asyncio.gather(*[taker_snapshot_for_symbol(s, flow_iv, hist_points=6) for s in symbols], return_exceptions=True)
    flows = []
    total_positive_net = 0.0
    for sn in snaps:
        if isinstance(sn, Exception) or not sn.get("last"):
            continue
        last = sn["last"]
        prev = sn.get("prev")
        net = last["buy"] - last["sell"]
        total_positive_net += max(net, 0.0)
        # 5 ok: son 5 noktanın buy_ratio >= 50 durumuna göre
        pts = sn.get("points", [])[-5:]
        trend = "".join([_arrow(p["buy_ratio"]) for p in pts]) if pts else ""
        flows.append({
            "symbol": sn["symbol"],
            "net": net,
            "buy_ratio_15m": last["buy_ratio"],
            "momentum": sn.get("momentum", 1.0),
            "trend_arrows": trend or "—",
        })

    flows.sort(key=lambda x: x["net"], reverse=True)
    top_flows = flows[:IO_SHOW_TOP_FLOWS]
    # yüzdelik pay (pozitif net'ler arasında)
    for f in top_flows:
        share = (max(0.0, f["net"]) / total_positive_net * 100.0) if total_positive_net > 0 else 0.0
        f["share_pct"] = share

    # Market “hacim payı” benzeri metrik (toplam son 15m taker toplamı / tüm seçili semboller)
    taker_total = sum([(sn["last"]["buy"] + sn["last"]["sell"]) for sn in snaps if not isinstance(sn, Exception) and sn.get("last")])
    # normalize: seçili sepetin kendisine göre %; burada 100'e sabitleyebiliriz
    market_volume_share_pct = 100.0 if taker_total > 0 else 0.0

    return {
        "symbols": symbols,
        "market_ratios": market_ratios,  # {'15m': 47.0, '1h': ...}
        "flows": top_flows,              # [{'symbol':..., 'share_pct':..., 'buy_ratio_15m':..., 'momentum':..., 'trend_arrows':...}]
        "market_volume_share_pct": market_volume_share_pct,
        "flow_interval": flow_iv,
    }

async def symbol_inout(symbol: str, intervals: List[str] = IO_DEFAULT_INTERVALS) -> Dict[str, Any]:
    """Tek sembol için tüm periyotlarda oran + 15m flow detayları."""
    out = {"symbol": symbol, "ratios": {}, "flow": None}
    # ratios
    for iv in intervals:
        snap = await taker_snapshot_for_symbol(symbol, iv, hist_points=6 if iv == "15m" else 2)
        last = snap.get("last")
        out["ratios"][iv] = last["buy_ratio"] if last else 0.0
        if iv == "15m":
            pts = snap.get("points", [])[-5:]
            trend = "".join([_arrow(p["buy_ratio"]) for p in pts]) if pts else "—"
            out["flow"] = {
                "share_pct": 100.0,  # tek coin olduğundan raporda %100 göstermek makul
                "buy_ratio_15m": last["buy_ratio"] if last else 0.0,
                "momentum": snap.get("momentum", 1.0),
                "trend_arrows": trend,
            }
    return out

def format_market_report(data: Dict[str, Any]) -> str:
    mr = data["market_ratios"]
    mv = data["market_volume_share_pct"]
    lines = []
    lines.append("Marketteki Tüm Coinlere Olan Nakit Girişi Raporu.")
    # Basit kısa vadeli alım gücü: 15m oranını 0.01x–2.0x bandına projekte eden hedonik bir gösterge
    short_power = max(0.1, min(2.0, (mr.get("15m", 0.0) / 50.0)))  # 50% = 1.0x
    lines.append(f"Kısa Vadeli Market Alım Gücü: {short_power:.1f}X")
    lines.append(f"Marketteki Hacim Payı:%{_format_pct(mv, 1)}\n")
    # periyotlar
    for iv in ["15m", "1h", "4h", "12h", "1d"]:
        if iv in mr:
            val = mr[iv]
            lines.append(f"{iv}=> %{_format_pct(val,1)} {'🔼' if val>=50 else '🔻'}")
    lines.append("\n")
    lines.append("En çok nakit girişi olanlar.(Sonunda 🔼 olanlarda nakit girişi daha sağlıklıdır)")
    lines.append("Nakitin nereye aktığını gösterir. (Nakit Göçü Raporu)\n")
    for f in data["flows"]:
        sym = f["symbol"]
        share = _format_pct(f["share_pct"], 1)
        br15 = _format_pct(f["buy_ratio_15m"], 0)
        mts = _format_pct(f["momentum"], 1)
        trend = f["trend_arrows"]
        # trendin son oku “sağlıklı” sayılır
        healthy = " 🔼" if trend.endswith("🔼") else ""
        lines.append(f"{sym} Nakit: %{share} 15m:%{br15} Mts: {mts} {trend}{healthy}")
    return "\n".join(lines)

def format_symbol_report(data: Dict[str, Any]) -> str:
    r = data["ratios"]
    lines = []
    lines.append(f"Belirtilen Coin Grubu İçin Nakit Girişi Raporu. ({data['symbol']} Grubu İçin)")
    short_power = max(0.1, min(2.0, (r.get("15m", 0.0) / 50.0)))
    lines.append(f"Bu Grup İçin Kısa Vadeli  Alım Gücü: {short_power:.1f}X")
    lines.append(f"Marketteki Hacim Payı:%{_format_pct(100.0,1)}\n")
    for iv in ["15m", "1h", "4h", "12h", "1d"]:
        if iv in r:
            val = r[iv]
            lines.append(f"{iv}=> %{_format_pct(val,1)} {'🔻' if val<50 else '🔼'}")
    lines.append("\n")
    f = data.get("flow") or {}
    br15 = _format_pct(f.get("buy_ratio_15m", 0.0), 0)
    mts = _format_pct(f.get("momentum", 1.0), 1)
    trend = f.get("trend_arrows", "—")
    lines.append("En çok nakit girişi olanlar.(Sonunda 🔼 olanlarda nakit girişi daha sağlıklıdır)")
    lines.append("Nakitin nereye aktığını gösterir. (Nakit Göçü Raporu)\n")
    lines.append(f"{data['symbol']} Nakit: %100,0 15m:%{br15} Mts: {mts} {trend}")
    return "\n".join(lines)
