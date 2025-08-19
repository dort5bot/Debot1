# io_handler.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import math
import time
from typing import Dict, Any, List, Optional, Tuple

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from utils.config import CONFIG
from utils.binance_api import get_binance_api
from utils import io_utils

# =========================
# --- Config Defaults -----
# =========================
def _ensure_config_defaults():
    IO = CONFIG.IO

    # Çoklu timeframe (dakika)
    if not hasattr(IO, "CASHFLOW_TIMEFRAMES"):
        IO.CASHFLOW_TIMEFRAMES = {
            "15m": 15,
            "1h": 60,
            "4h": 240,
            "12h": 720,
            "1d": 1440,
        }

    # RSI / momentum için period
    if not hasattr(IO, "RSI_PERIOD"):
        IO.RSI_PERIOD = getattr(CONFIG.TA, "RSI_PERIOD", 14)

    # Order Book Imbalance derinliği
    if not hasattr(IO, "OBI_DEPTH"):
        IO.OBI_DEPTH = getattr(CONFIG.TA, "ADX_PERIOD", 14)  # yoksa 14

    # Funding normalizasyonu için ortalama / std (yaklaşık varsayımlar)
    if not hasattr(IO, "FUNDING_AVG"):
        IO.FUNDING_AVG = 0.0
    if not hasattr(IO, "FUNDING_STD"):
        IO.FUNDING_STD = 0.0005  # 5 bps

    # OI / Likidasyon normalizasyonu için baseline
    if not hasattr(IO, "OI_BASELINE"):
        IO.OI_BASELINE = 1.0
    if not hasattr(IO, "LIQUIDATION_BASELINE"):
        IO.LIQUIDATION_BASELINE = 1.0

    # Nakit göçü listesi boyutu
    if not hasattr(IO, "TOP_N_MIGRATION"):
        IO.TOP_N_MIGRATION = 10

    # Market taraması için maksimum sembol sayısı (dinamik modda)
    if not hasattr(IO, "MAX_SYMBOLS_MARKET"):
        IO.MAX_SYMBOLS_MARKET = 30

    # Varsayılan quote para birimi
    if not hasattr(IO, "QUOTE_ASSET"):
        IO.QUOTE_ASSET = "USDT"

    # Cache TTL fallback
    if not hasattr(IO, "CACHE_TTL"):
        IO.CACHE_TTL = 10

_ensure_config_defaults()

# =========================
# --- Utils ---------------
# =========================

ARROW_UP = "🔼"
ARROW_DOWN = "🔻"
ARROW_NEUTRAL = "➖"
ARROW_NEUTRAL_X = "✖️"

def _buyers_percent_from_taker_ratio(taker_ratio: Optional[float]) -> Optional[float]:
    if taker_ratio is None:
        return None
    # buyers% = (1 + (buys - sells)/total) / 2 * 100
    return max(0.0, min(100.0, (1.0 + taker_ratio) * 50.0))

def _arrow_from_ratio(val: Optional[float], up_eps: float = 0.02, down_eps: float = -0.02) -> str:
    if val is None:
        return ARROW_NEUTRAL_X
    if val > up_eps:
        return ARROW_UP
    if val < down_eps:
        return ARROW_DOWN
    return ARROW_NEUTRAL

def _fmt_pct(x: Optional[float], nd=1) -> str:
    if x is None or math.isnan(x):
        return "—"
    return f"%{x:.{nd}f}".replace(".", ",")

def _fmt_ratio_as_power(x: Optional[float]) -> str:
    """
    vwap_taker_ratio ~ [-1, 1]  ->  power ≈ 1 + ratio
    Ör: 0.12 -> 1.1X
    """
    if x is None or math.isnan(x):
        return "—"
    power = max(0.1, min(2.0, 1.0 + x))
    return f"{power:.1f}X".replace(".", ",")

def _symbolize(arg: str) -> str:
    s = arg.upper()
    if s.endswith(CONFIG.IO.QUOTE_ASSET):
        return s
    return f"{s}{CONFIG.IO.QUOTE_ASSET}"

def _now_ms() -> int:
    return int(time.time() * 1000)

# =========================
# --- Data Fetch ----------
# =========================

async def _get_dynamic_usdt_symbols(api, max_symbols: int) -> List[str]:
    """
    Tüm USDT paritelerini çek, 24h quoteVolume'a göre sırala ve top N döndür.
    """
    ex = await api.exchange_info_details()
    usdt_symbols: List[str] = [
        s["symbol"] for s in ex.get("symbols", [])
        if s.get("status") == "TRADING" and s.get("quoteAsset") == CONFIG.IO.QUOTE_ASSET
    ]

    # 24h tickers ile hacme göre sırala
    tickers = await api.get_all_24h_tickers()
    vol_map: Dict[str, float] = {}
    for t in tickers:
        sym = t.get("symbol")
        if sym in usdt_symbols:
            try:
                vol_map[sym] = float(t.get("quoteVolume", 0.0))
            except Exception:
                vol_map[sym] = 0.0

    ranked = sorted(usdt_symbols, key=lambda s: vol_map.get(s, 0.0), reverse=True)
    return ranked[:max_symbols]

async def _resolve_market_symbol_list(api) -> List[str]:
    """
    CONFIG.BINANCE.TOP_SYMBOLS_FOR_IO:
      - Belirlenmişse onu kullan
      - "AUTO" içeriyorsa dinamik olarak top N seç
      - Hiç yoksa BTCUSDT, ETHUSDT fallback
    """
    raw = getattr(CONFIG.BINANCE, "TOP_SYMBOLS_FOR_IO", ["BTCUSDT", "ETHUSDT"])
    if isinstance(raw, str):
        raw = [s.strip().upper() for s in raw.split(",") if s.strip()]

    if any(s in ("AUTO", "ALL") for s in raw):
        return await _get_dynamic_usdt_symbols(api, CONFIG.IO.MAX_SYMBOLS_MARKET)

    return [s.upper() for s in raw]

async def _fetch_symbol_pack(api, symbol: str) -> Dict[str, Any]:
    """
    Bir sembol için analizde kullanılacak paket verileri çek.
    Funding/oi/liquidations sınırlıysa None geçilir.
    """
    kl = await api.get_klines(symbol, interval=CONFIG.BINANCE.STREAM_INTERVAL, limit= max(100, CONFIG.TA.EMA_PERIOD*3) if hasattr(CONFIG, "TA") else 200)
    ob = await api.get_order_book(symbol, limit=100)
    tr = await api.get_recent_trades(symbol, limit=CONFIG.BINANCE.TRADES_LIMIT)
    tk = await api.get_24h_ticker(symbol)
    # funding (futures) – spot semboller için de deneyip olmazsa default
    try:
        fr = await api.get_funding_rate(symbol, limit=1)
        funding = fr[0] if isinstance(fr, list) and fr else {"fundingRate": 0}
    except Exception:
        funding = {"fundingRate": 0}

    # Open interest / liquidations -> şu an mevcut API sarmalayıcısında yok, None
    oi = None
    liq = None

    # trades zaman damgası normalize:
    now = _now_ms()
    norm_trades = []
    for t in tr:
        # recentTrades endpoint'i ts vermez; tradeId ~ yok. Takribi now kullan.
        t2 = dict(t)
        t2.setdefault("ts", now)
        # isBuyerMaker alanı recentTrades'te 'isBuyerMaker' yerine 'isBuyerMaker' yok; 'isBuyerMaker' taklidi için 'isBuyerMaker' := t['isBuyerMaker']?
        # recentTrades dönen alanlar: id, price, qty, quoteQty, time, isBuyerMaker, isBestMatch
        if "isBuyerMaker" in t2:
            pass
        else:
            # aggTrades kullanılsaydı 'm' alanı vardı. recentTrades'te 'isBuyerMaker' var.
            pass
        norm_trades.append(t2)

    return {
        "klines": kl,
        "order_book": ob,
        "trades": norm_trades,
        "ticker": tk,
        "funding": funding,
        "oi": oi,
        "liquidations": liq,
    }

async def _build_snapshot(symbol: str) -> Dict[str, Any]:
    api = get_binance_api()
    data = await _fetch_symbol_pack(api, symbol)
    snap = io_utils.build_io_snapshot(
        symbol=symbol,
        klines=data["klines"],
        order_book=data["order_book"],
        trades=data["trades"],
        ticker=data["ticker"],
        funding=data["funding"],
        oi=data["oi"],
        liquidations=data["liquidations"],
        with_cashflow=True,
    )
    return snap

async def _build_snapshots(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    api = get_binance_api()
    # Paralel çekim
    packs: Dict[str, Dict[str, Any]] = await api.fetch_many(_fetch_symbol_pack, symbols)
    # Snapshot’a dönüştür
    result: Dict[str, Dict[str, Any]] = {}
    for sym, dat in packs.items():
        if isinstance(dat, Exception):
            continue
        snap = io_utils.build_io_snapshot(
            symbol=sym,
            klines=dat.get("klines", []),
            order_book=dat.get("order_book", {}),
            trades=dat.get("trades", []),
            ticker=dat.get("ticker", {}),
            funding=dat.get("funding", {}),
            oi=dat.get("oi"),
            liquidations=dat.get("liquidations"),
            with_cashflow=True,
        )
        result[sym] = snap
    return result

# =========================
# --- Formatting ----------
# =========================

def _format_timeframes_line(ratios: Dict[str, Dict[str, Optional[float]]]) -> List[str]:
    """
    ratios => {"ratios": {"15m":{"taker_ratio":..,"vwap_taker_ratio":..}, ...}}
    """
    out = []
    order = ["15m", "1h", "4h", "12h", "1d"]
    rmap = ratios.get("ratios", {})
    for k in order:
        v = rmap.get(k, {})
        tr = v.get("taker_ratio")
        pct = _buyers_percent_from_taker_ratio(tr)
        arrow = _arrow_from_ratio(tr)
        out.append(f"{k}=> {_fmt_pct(pct)} {arrow}")
    return out

def _calc_short_term_power(ratios: Dict[str, Dict[str, Optional[float]]]) -> str:
    vwap15 = ratios.get("ratios", {}).get("15m", {}).get("vwap_taker_ratio")
    return _fmt_ratio_as_power(vwap15)

def _calc_group_volume_share(tickers: Dict[str, Dict[str, Any]], group: Optional[List[str]] = None) -> float:
    """
    group hacminin (quoteVolume) tüm USDT grubuna oranı
    """
    all_total = 0.0
    grp_total = 0.0
    for sym, tk in tickers.items():
        try:
            qv = float(tk.get("quoteVolume", 0.0))
        except Exception:
            qv = 0.0
        all_total += qv
        if group is None or sym in group:
            grp_total += qv
    if all_total <= 0:
        return 0.0
    return 100.0 * grp_total / all_total

def _build_cash_migration_table(snaps: Dict[str, Dict[str, Any]]) -> List[Tuple[str, float, float, float, str]]:
    """
    Her coin için:
      - Nakit% (grup içi alış notyonal payı ~ vwap_taker_ratio proxy'si olarak 15m buyers% * 24h vol ağırlığı)
      - 15m alıcı %
      - Mts puanı
      - 5 zaman oku pattern (15m,1h,4h,12h,1d)
    Dönüş: list of tuples: (symbol, cash_share%, buyers15m%, mts_score, pattern_str)
    """
    # 24h volume ağırlıkları:
    vol_map = {}
    for sym, s in snaps.items():
        tk = s.get("ticker", {})
        try:
            vol_map[sym] = float(tk.get("quoteVolume", 0.0))
        except Exception:
            vol_map[sym] = 0.0

    # 15m buyers%
    buyers15 = {}
    mts = {}
    pattern = {}
    weight_raw = {}

    for sym, s in snaps.items():
        ratios = s.get("ratios", {})
        r15 = ratios.get("15m", {})
        tr15 = r15.get("taker_ratio")
        buyers15[sym] = _buyers_percent_from_taker_ratio(tr15) or 0.0
        mts[sym] = float(s.get("mts_score", 0.0))

        # pattern okları
        seq = []
        for k in ["15m", "1h", "4h", "12h", "1d"]:
            tr = ratios.get(k, {}).get("taker_ratio")
            seq.append(_arrow_from_ratio(tr))
        pattern[sym] = "".join(seq)

        # kaba "nakit payı" — 15m buyers% * 24h vol
        weight_raw[sym] = (buyers15[sym] / 100.0) * max(0.0, vol_map.get(sym, 0.0))

    total_w = sum(weight_raw.values()) or 1.0
    rows: List[Tuple[str, float, float, float, str]] = []
    for sym in snaps.keys():
        cash_share = 100.0 * weight_raw[sym] / total_w
        rows.append((sym, cash_share, buyers15[sym], mts[sym], pattern[sym]))

    # Mts skora göre (yüksek -> yukarı iştah) sırala, sonra nakit payına göre
    rows.sort(key=lambda r: (round(r[3], 4), round(r[1], 4)), reverse=True)
    return rows

def _format_market_report(snaps: Dict[str, Dict[str, Any]]) -> str:
    # Market kısa vadeli güç (15m vwap taker ratio ortalaması)
    vwap15_list = []
    tickers = {}
    for sym, s in snaps.items():
        tickers[sym] = s.get("ticker", {})
        v = s.get("ratios", {}).get("15m", {}).get("vwap_taker_ratio")
        if v is not None:
            vwap15_list.append(v)
    avg_vwap15 = io_utils.safe_mean(vwap15_list) or 0.0
    short_power = _fmt_ratio_as_power(avg_vwap15)

    # Hacim payı: Top taranan grubun payı / tüm USDT
    vol_share = _calc_group_volume_share(tickers)

    # 5 zaman dilimi (market ortalama)
    merged_ratios: Dict[str, Dict[str, Optional[float]]] = {"ratios": {}}
    for tf in CONFIG.IO.CASHFLOW_TIMEFRAMES.keys():
        vals = []
        for s in snaps.values():
            tr = s.get("ratios", {}).get(tf, {}).get("taker_ratio")
            if tr is not None:
                vals.append(tr)
        merged_ratios["ratios"][tf] = {"taker_ratio": io_utils.safe_mean(vals), "vwap_taker_ratio": None}
    tf_lines = _format_timeframes_line(merged_ratios)

    # Nakit göçü tablosu
    rows = _build_cash_migration_table(snaps)[:CONFIG.IO.TOP_N_MIGRATION]

    # Yorum (basit kural: 1d buyers% < 50 riskli)
    buyers_1d = _buyers_percent_from_taker_ratio(merged_ratios["ratios"]["1d"]["taker_ratio"]) or 0.0
    if buyers_1d < 49.0:
        yorum = (
            "Piyasa ciddi anlamda risk barındırıyor. Alım Yapma!\n"
            "Günlük nakit giriş oranı (1d) %50 üzerine çıkarsa risk azalacaktır. "
            "Bu değer %49 altında oldukça piyasaya bulaşma!"
        )
    else:
        yorum = (
            "Piyasa günlük nakit giriş oranı bakımından kötü durumda değil. "
            "Durum böyle oldukça sert düşüş beklentim yok."
        )

    # Metni oluştur
    parts = []
    parts.append("⚡ Market Nakit raporu\nMarketteki Tüm Coinlere Olan Nakit Girişi Raporu.")
    parts.append(f"Kısa Vadeli Market Alım Gücü: {short_power}")
    parts.append(f"Marketteki Hacim Payı:{_fmt_pct(vol_share, nd=1)}\n")
    parts.append("⚡ Market ait 5 zamana ait nakit yüzdesi")
    parts.append("\n".join(tf_lines))
    parts.append("\n⚡ Coin Nakit Göçü Raporu \nEn çok nakit girişi olanlar. (Sonunda 🔼 olanlarda nakit girişi daha sağlıklıdır)\nNakitin nereye aktığını gösterir. (Nakit Göçü Raporu)")
    for sym, cash_share, buyers15, mts, pat in rows:
        arrow15 = ARROW_UP if buyers15 >= 50.0 else ARROW_DOWN
        parts.append(f"{sym.replace(CONFIG.IO.QUOTE_ASSET, '')} Nakit: {_fmt_pct(cash_share)} 15m:{_fmt_pct(buyers15, nd=0)} Mts: {mts:.1f} {pat}")
    parts.append("\n⚡ Yorum")
    parts.append(yorum)
    return "\n".join(parts)

def _format_coin_report(symbol: str, snap: Dict[str, Any], group_snapshots: Dict[str, Dict[str, Any]]) -> str:
    # Kısa vadeli güç
    short_power = _fmt_ratio_as_power(snap.get("ratios", {}).get("15m", {}).get("vwap_taker_ratio"))

    # Grup hacim payı: seçilen sembolün, analiz edilen grup içindeki payı
    tickers = {s: d.get("ticker", {}) for s, d in group_snapshots.items()}
    share = _calc_group_volume_share(tickers, group=[symbol])

    # 5 zaman dilimi çizgileri
    tf_lines = _format_timeframes_line(snap)

    # Nakit göçü (sadece bu sembol grubunda kendisi %100 olur — örnek formatı taklit)
    buyers15 = _buyers_percent_from_taker_ratio(snap.get("ratios", {}).get("15m", {}).get("taker_ratio")) or 0.0
    mts = float(snap.get("mts_score", 0.0))
    pat = "".join(_arrow_from_ratio(snap.get("ratios", {}).get(k, {}).get("taker_ratio")) for k in ["15m","1h","4h","12h","1d"])
    line = f"{symbol.replace(CONFIG.IO.QUOTE_ASSET,'')} Nakit: %100,0 15m:{_fmt_pct(buyers15, nd=0)} Mts: {mts:.1f} {pat}"

    # Yorum (1d eşiği)
    buyers_1d = _buyers_percent_from_taker_ratio(snap.get("ratios", {}).get("1d", {}).get("taker_ratio")) or 0.0
    if buyers_1d < 49.0:
        yorum = (
            "Piyasa ciddi anlamda risk barındırıyor. Alım Yapma!\n"
            "Günlük nakit giriş oranı (1d) %50 üzerine çıkarsa risk azalacaktır. "
            "Bu değer %49 altında oldukça piyasaya bulaşma!"
        )
    else:
        yorum = (
            "Piyasa günlük nakit giriş oranı bakımından kötü durumda değil. "
            "Kısa vadede marketteki tüm coinlerin alıcıları ve satıcılarının kafası karışık"
        )

    parts = []
    base = symbol.replace(CONFIG.IO.QUOTE_ASSET, "")
    parts.append(f"Belirtilen Coin Grubu İçin Nakit Girişi Raporu. ({symbol} Grubu İçin)")
    parts.append(f"Bu Grup İçin Kısa Vadeli Alım Gücü: {short_power}")
    parts.append(f"Marketteki Hacim Payı:{_fmt_pct(share, nd=1)}\n")
    parts.append("\n".join(tf_lines))
    parts.append("\nEn çok nakit girişi olanlar. (Sonunda 🔼 olanlarda nakit girişi daha sağlıklıdır)\nNakitin nereye aktığını gösterir. (Nakit Göçü Raporu)\n")
    parts.append(line)
    parts.append("\n" + yorum)
    return "\n".join(parts)

# =========================
# --- Telegram Handlers ---
# =========================

async def io_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /io  veya  /io <coin>
    """
    try:
        api = get_binance_api()

        # Arguman varsa coin raporu
        target_symbol: Optional[str] = None
        if context.args:
            target_symbol = _symbolize(context.args[0])

        # Sembol listesi (market raporu için)
        symbols = await _resolve_market_symbol_list(api)
        if not symbols:
            await update.message.reply_text("Uygun sembol bulunamadı.")
            return

        # Snapshotları çek
        snaps = await _build_snapshots(symbols)

        if target_symbol:
            # Coin raporu
            symbol = target_symbol
            if symbol not in snaps:
                # Liste dışındaysa tek başına çek
                snap = await _build_snapshot(symbol)
                # Grup olarak yine market symbols kullan (hacim payı için)
                text = _format_coin_report(symbol, snap, snaps)
            else:
                text = _format_coin_report(symbol, snaps[symbol], snaps)

            header = "inOut Raporu (/io coin)\n\n"
            await update.message.reply_text(header + text)
            return

        # Market raporu
        text = _format_market_report(snaps)
        header = "inOut Raporu (/io)\n\n"
        await update.message.reply_text(header + text)

    except Exception as e:
        await update.message.reply_text(f"IO raporu oluşturulamadı: {e}")

# =========================
# --- Plugin Loader API ---
# =========================

def register(app) -> None:
    """
    Plugin loader uyumlu kayıt noktası.
    Örn:
        from io_handler import register
        register(application)
    """
    app.add_handler(CommandHandler("io", io_command))
