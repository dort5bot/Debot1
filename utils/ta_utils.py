# ta_utils.py
# Free Render uyumlu hibrit TA pipeline
# - CPU-bound: ThreadPoolExecutor
# - IO-bound: asyncio
# - MAX_WORKERS: CONFIG.SYSTEM.MAX_WORKERS varsa kullanılır, yoksa 2

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio

from utils.config import CONFIG

# ------------------------------------------------------------
# İç yardımcılar
# ------------------------------------------------------------

def _get_max_workers(default: int = 2) -> int:
    # CONFIG.SYSTEM.MAX_WORKERS tanımlıysa onu kullan, değilse default
    system = getattr(CONFIG, "SYSTEM", None)
    if system is not None and hasattr(system, "MAX_WORKERS"):
        try:
            mw = int(getattr(system, "MAX_WORKERS"))
            return mw if mw > 0 else default
        except Exception:
            return default
    return default


# =============================================================
# Trend İndikatörleri
# =============================================================

def ema(df: pd.DataFrame, period: int = None, column: str = "close") -> pd.Series:
    """Exponential Moving Average (EMA) hesaplar."""
    period = period or CONFIG.TA.EMA_PERIOD
    return df[column].ewm(span=period, adjust=False).mean()


def macd(df: pd.DataFrame, fast: int = None, slow: int = None, signal: int = None, column: str = "close"):
    """MACD (Moving Average Convergence Divergence) hesaplar."""
    fast = fast or CONFIG.TA.MACD_FAST
    slow = slow or CONFIG.TA.MACD_SLOW
    signal = signal or CONFIG.TA.MACD_SIGNAL

    ema_fast = df[column].ewm(span=fast, adjust=False).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line

    return macd_line, signal_line, hist


def adx(df: pd.DataFrame, period: int = None):
    """Average Directional Index (ADX) hesaplar."""
    period = period or CONFIG.TA.ADX_PERIOD

    # Not: Bu fonksiyon df üzerinde yeni kolonlar oluşturur (TR, +DM, -DM).
    # Paralelde çakışmayı önlemek için MUTATING_FUNCTIONS ile kopya üzerinden çalıştıracağız.
    df["TR"] = np.maximum(df["high"] - df["low"],
                        np.maximum(abs(df["high"] - df["close"].shift(1)),
                                   abs(df["low"] - df["close"].shift(1))))
    df["+DM"] = np.where((df["high"] - df["high"].shift(1)) > (df["low"].shift(1) - df["low"]),
                         np.maximum(df["high"] - df["high"].shift(1), 0), 0)
    df["-DM"] = np.where((df["low"].shift(1) - df["low"]) > (df["high"] - df["high"].shift(1)),
                         np.maximum(df["low"].shift(1) - df["low"], 0), 0)

    tr_smooth = df["TR"].rolling(window=period).sum()
    plus_di = 100 * (df["+DM"].rolling(window=period).sum() / tr_smooth)
    minus_di = 100 * (df["-DM"].rolling(window=period).sum() / tr_smooth)
    dx = (100 * abs(plus_di - minus_di) / (plus_di + minus_di))
    adx_val = dx.rolling(window=period).mean()

    return adx_val


def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume Weighted Average Price (VWAP) hesaplar."""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()


def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Commodity Channel Index (CCI) hesaplar."""
    tp = (df['high'] + df['low'] + df['close']) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    return (tp - sma) / (0.015 * mad)


def momentum(df: pd.DataFrame, period: int = 10) -> pd.Series:
    """Momentum Oscillator hesaplar."""
    return df['close'] / df['close'].shift(period) * 100


# =============================================================
# Momentum İndikatörleri
# =============================================================

def rsi(df: pd.DataFrame, period: int = None, column: str = "close") -> pd.Series:
    """Relative Strength Index (RSI) hesaplar."""
    period = period or CONFIG.TA.RSI_PERIOD

    delta = df[column].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    avg_gain = pd.Series(gain).rolling(window=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period).mean()
    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def stochastic(df: pd.DataFrame, k_period: int = None, d_period: int = None):
    """Stochastic Oscillator hesaplar."""
    k_period = k_period or CONFIG.TA.STOCH_K
    d_period = d_period or CONFIG.TA.STOCH_D

    low_min = df["low"].rolling(window=k_period).min()
    high_max = df["high"].rolling(window=k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min)
    d = k.rolling(window=d_period).mean()
    return k, d


# =============================================================
# Volatilite & Risk
# =============================================================

def atr(df: pd.DataFrame, period: int = None):
    """Average True Range (ATR) hesaplar."""
    period = period or CONFIG.TA.ATR_PERIOD

    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def bollinger_bands(df: pd.DataFrame, period: int = None, column: str = "close"):
    """Bollinger Bands hesaplar."""
    period = period or CONFIG.TA.BB_PERIOD

    sma = df[column].rolling(window=period).mean()
    std = df[column].rolling(window=period).std()
    upper = sma + (CONFIG.TA.BB_STD * std)
    lower = sma - (CONFIG.TA.BB_STD * std)
    return upper, sma, lower


def sharpe_ratio(df: pd.DataFrame, risk_free_rate: float = 0.0, period: int = None, column: str = "close"):
    """Sharpe Ratio hesaplar."""
    period = period or CONFIG.TA.SHARPE_PERIOD
    returns = df[column].pct_change()
    excess = returns - risk_free_rate / period
    return (excess.mean() / excess.std()) * np.sqrt(period)


def max_drawdown(df: pd.DataFrame, column: str = "close"):
    """Max Drawdown hesaplar."""
    roll_max = df[column].cummax()
    drawdown = (df[column] - roll_max) / roll_max
    return drawdown.min()


def historical_volatility(df: pd.DataFrame, period: int = 30) -> pd.Series:
    """Historical Volatility (annualized, %) hesaplar."""
    log_returns = np.log(df['close'] / df['close'].shift(1))
    vol = log_returns.rolling(period).std() * np.sqrt(252) * 100
    return vol


def ulcer_index(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Ulcer Index hesaplar."""
    rolling_max = df['close'].rolling(period).max()
    drawdown = (df['close'] - rolling_max) / rolling_max * 100
    return np.sqrt((drawdown.pow(2)).rolling(period).mean())


# =============================================================
# Hacim & Likidite
# =============================================================

def obv(df: pd.DataFrame):
    """On-Balance Volume (OBV) hesaplar."""
    obv = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()
    return obv


def cmf(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Chaikin Money Flow (CMF) hesaplar."""
    mfm = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
    mfv = mfm * df['volume']
    return mfv.rolling(period).sum() / df['volume'].rolling(period).sum()


def order_book_imbalance(bids: list, asks: list):
    """Order Book Imbalance (OBI) hesaplar."""
    bid_vol = sum([b[1] for b in bids])
    ask_vol = sum([a[1] for a in asks])
    return (bid_vol - ask_vol) / (bid_vol + ask_vol)


def open_interest_placeholder():
    """Open Interest için placeholder (borsa API ile entegre edilecek)."""
    return None


# =============================================================
# Market Structure
# =============================================================

def market_structure(df: pd.DataFrame) -> pd.DataFrame:
    """Market Structure High/Low (MSH/MSL) hesaplar."""
    highs = df['high']
    lows = df['low']
    structure = pd.DataFrame(index=df.index)
    structure['higher_high'] = highs > highs.shift(1)
    structure['lower_low'] = lows < lows.shift(1)
    return structure


def breakout(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Breakout (Donchian Channel tarzı) sinyal döndürür."""
    rolling_high = df['close'].rolling(period).max()
    rolling_low = df['close'].rolling(period).min()

    cond_long = df['close'] > rolling_high.shift(1)
    cond_short = df['close'] < rolling_low.shift(1)

    signal = pd.Series(index=df.index, dtype=float)
    signal[cond_long] = 1.0   # Long breakout
    signal[cond_short] = -1.0 # Short breakout
    signal.fillna(0, inplace=True)

    return signal


# =============================================================
# Sentiment (I/O-bound placeholders)
# =============================================================

async def funding_rate_placeholder_async():
    """Asenkron funding rate placeholder (gerçek API ile değiştir)."""
    await asyncio.sleep(0.05)
    return 0.001

async def social_sentiment_placeholder_async():
    """Asenkron sosyal sentiment placeholder (gerçek API ile değiştir)."""
    await asyncio.sleep(0.05)
    return {"sentiment": 0.5}

def funding_rate_placeholder():
    """Senkron placeholder (registry kullanım kolaylığı için)."""
    return None

def social_sentiment_placeholder():
    """Senkron placeholder (registry kullanım kolaylığı için)."""
    return None


# =============================================================
# Registry
# =============================================================

# CPU-bound olarak toplu hesaplanacak fonksiyonlar
CPU_FUNCTIONS = {
    "ema": ema,
    "macd": macd,
    "adx": adx,  # df üzerinde kolon eklediği için MUTATING_FUNCTIONS'la kopya üzerinden çalıştıracağız
    "vwap": vwap,
    "cci": cci,
    "momentum": momentum,
    "rsi": rsi,
    "stochastic": stochastic,
    "atr": atr,
    "bollinger_bands": bollinger_bands,
    "sharpe_ratio": sharpe_ratio,
    "max_drawdown": max_drawdown,
    "historical_volatility": historical_volatility,
    "ulcer_index": ulcer_index,
    "obv": obv,
    "cmf": cmf,
    "market_structure": market_structure,
    "breakout": breakout,
}

# Paralelde çalıştırılırken df'yi mutate eden (yan etki oluşturan) fonksiyonlar
MUTATING_FUNCTIONS = {"adx"}

# I/O-bound asenkron fonksiyonlar (gerçek API'lerle değiştirilebilir)
IO_FUNCTIONS = {
    "funding_rate": funding_rate_placeholder_async,
    "social_sentiment": social_sentiment_placeholder_async,
}

# Genel amaçlı string-çağrı registry (senkron kullanımlar için)
# Not: IO fonksiyonlarının asenkron versiyonları burada yok; toplu IO için calculate_io_functions kullanın.
TA_FUNCTIONS = {
    **CPU_FUNCTIONS,
    "order_book_imbalance": order_book_imbalance,
    "open_interest_placeholder": open_interest_placeholder,
    "funding_rate_placeholder": funding_rate_placeholder,
    "social_sentiment_placeholder": social_sentiment_placeholder,
}


# =============================================================
# Hibrit Pipeline
# =============================================================

def calculate_cpu_functions(df: pd.DataFrame, max_workers: int | None = None) -> dict:
    """
    CPU-bound fonksiyonları paralelde hesaplar.
    - Free Render için default max_workers=2 (CONFIG.SYSTEM.MAX_WORKERS yoksa).
    - MUTATING_FUNCTIONS için df.copy() ile izole çalıştırır.
    """
    results: dict = {}
    max_workers = max_workers or _get_max_workers(default=2)

    # Hafıza ve stabilite açısından Free Render'da 2 önerilir.
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for name, func in CPU_FUNCTIONS.items():
            # Yan etki oluşturan fonksiyonlara izolasyon
            arg_df = df.copy(deep=True) if name in MUTATING_FUNCTIONS else df
            futures[executor.submit(func, arg_df)] = name

        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = None
                print(f"[CPU TA ERROR] {name} hesaplanamadı: {e}")
    return results


async def calculate_io_functions() -> dict:
    """
    I/O-bound (asenkron) fonksiyonları birlikte yürütür.
    """
    results: dict = {}
    names = list(IO_FUNCTIONS.keys())
    tasks = [IO_FUNCTIONS[n]() for n in names]
    completed = await asyncio.gather(*tasks, return_exceptions=True)
    for name, res in zip(names, completed):
        if isinstance(res, Exception):
            results[name] = None
            print(f"[I/O TA ERROR] {name} hesaplanamadı: {res}")
        else:
            results[name] = res
    return results


def _run_asyncio(coro):
    """
    Jupyter / Bot / Web server ortamlarında güvenli asyncio çalıştırma.
    - Çalışan bir loop varsa yeni loop açar.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # yeni event loop oluştur ve orada çalıştır
            new_loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(new_loop)
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
                asyncio.set_event_loop(loop)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # loop yoksa
        new_loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(new_loop)
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
            asyncio.set_event_loop(None)


def calculate_all_ta_hybrid(df: pd.DataFrame, max_workers: int | None = None) -> dict:
    """
    Tüm TA'leri hibrit olarak hesaplar:
      - CPU-bound: ThreadPoolExecutor
      - I/O-bound: asyncio
    Dönen sonuç: { indicator_name: value_or_series_or_df }
    """
    cpu_results = calculate_cpu_functions(df, max_workers=max_workers)
    io_results = _run_asyncio(calculate_io_functions())
    return {**cpu_results, **io_results}
