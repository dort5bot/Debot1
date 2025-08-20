# ta_utils.py 399+=970
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
    upper = sma + (CONFIG.TA.BB_STDDEV * std)
    lower = sma - (CONFIG.TA.BB_STDDEV * std)
    return upper, sma, lower


def sharpe_ratio(df: pd.DataFrame, risk_free_rate: float = None, period: int = None, column: str = "close"):
    """Sharpe Ratio hesaplar."""
    period = period or CONFIG.TA.SHARPE_PERIOD
    risk_free_rate = risk_free_rate or CONFIG.TA.SHARPE_RISK_FREE_RATE

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


#♦️

# =============================================================
# Signal Generator & Market Scanner
# =============================================================

def generate_signals(df: pd.DataFrame) -> dict:
    """
    Tek sembol için indikatörleri birleştirerek al/sat sinyali üretir.
    Dönen yapı:
      {
        "signal": 1 / -1 / 0,
        "score": float,
        "indicators": { "ema": ..., "rsi": ..., ... }
      }
    """
    try:
        indicators = {}

        # --- Trend ---
        ema_fast = ema(df, period=CONFIG.TA.EMA_PERIODS[0])
        ema_slow = ema(df, period=CONFIG.TA.EMA_PERIODS[1])
        indicators["ema_fast"] = ema_fast.iloc[-1]
        indicators["ema_slow"] = ema_slow.iloc[-1]
        ema_signal = 1 if ema_fast.iloc[-1] > ema_slow.iloc[-1] else -1

        macd_line, signal_line, _ = macd(df)
        indicators["macd"] = macd_line.iloc[-1] - signal_line.iloc[-1]
        macd_signal = 1 if indicators["macd"] > 0 else -1

        # --- Momentum ---
        rsi_val = rsi(df).iloc[-1]
        indicators["rsi"] = rsi_val
        if rsi_val < 30:
            rsi_signal = 1
        elif rsi_val > 70:
            rsi_signal = -1
        else:
            rsi_signal = 0

        # --- Volatilite ---
        atr_val = atr(df).iloc[-1]
        indicators["atr"] = atr_val

        # --- Hacim / Likidite ---
        obv_val = obv(df).iloc[-1]
        indicators["obv"] = obv_val
        obv_signal = 1 if obv_val > obv(df).iloc[-20] else -1  # son 20 bara göre OBV trendi

        # --- Sinyal Skorlaması ---
        weights = {
            "ema": 0.3,
            "macd": 0.3,
            "rsi": 0.2,
            "obv": 0.2,
        }
        score = (
            ema_signal * weights["ema"]
            + macd_signal * weights["macd"]
            + rsi_signal * weights["rsi"]
            + obv_signal * weights["obv"]
        )

        # Son sinyal
        if score > 0.5:
            signal = 1   # Long
        elif score < -0.5:
            signal = -1  # Short
        else:
            signal = 0   # Neutral

        return {
            "signal": signal,
            "score": round(score, 3),
            "indicators": indicators,
        }

    except Exception as e:
        print(f"[SIGNAL ERROR] Sinyal hesaplanamadı: {e}")
        return {"signal": 0, "score": 0.0, "indicators": {}}


def scan_market(market_data: dict) -> dict:
    """
    Çoklu coin için market taraması yapar.
    market_data: { "BTCUSDT": df, "ETHUSDT": df, ... }
    Dönen yapı:
      {
        "BTCUSDT": {"signal": 1, "score": 0.75, "indicators": {...}},
        "ETHUSDT": {"signal": -1, "score": -0.66, "indicators": {...}}
      }
    """
    results = {}
    for symbol, df in market_data.items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            results[symbol] = {"signal": 0, "score": 0.0, "indicators": {}}
            continue
        try:
            results[symbol] = generate_signals(df)
        except Exception as e:
            print(f"[SCAN ERROR] {symbol} analiz edilemedi: {e}")
            results[symbol] = {"signal": 0, "score": 0.0, "indicators": {}}
    return results

#✅


# =============================================================
# Advanced Signal Stack: alpha_ta
# - Kalman filter (1D, random-walk) ile smooth fiyat
# - Hilbert/Wavelet trend-cycle sezgisi (fallbacks)
# - Entropy ölçüleri (ApEn, SampEn, Permutation Entropy)
# - Rejim tespiti (heuristic; hmmlearn varsa kullanır)
# - Lead-Lag (BTC vs alt) ve basit Transfer Entropy (binned)
# - Ağırlıklı birleşik skor: alpha_ta
# - Dinamik eşikler: entropy / rejim ile ayarlı
# =============================================================

import math

# --------------------------
# 1) Kalman Filter (1D)
# --------------------------
def kalman_filter_series(prices: pd.Series, q: float | None = None, r: float | None = None) -> pd.Series:
    """
    Minimal 1D random-walk Kalman.
    Q: process noise, R: measurement noise
    CONFIG fallback: TA.KALMAN_Q, TA.KALMAN_R
    """
    if q is None:
        q = getattr(CONFIG.TA, "KALMAN_Q", 1e-5)
    if r is None:
        r = getattr(CONFIG.TA, "KALMAN_R", 1e-2)

    x = 0.0
    p = 1.0
    z_prev = None
    out = []

    for z in prices.fillna(method="ffill").values:
        if z_prev is None:
            x = z
            z_prev = z

        # predict
        x_prior = x
        p_prior = p + q

        # update
        k = p_prior / (p_prior + r)
        x = x_prior + k * (z - x_prior)
        p = (1 - k) * p_prior
        out.append(x)
    return pd.Series(out, index=prices.index, name="kalman")

# --------------------------
# 2) Hilbert & Wavelet (fallback)
# --------------------------
def _hilbert_analytic(x: np.ndarray) -> np.ndarray:
    """
    SciPy yoksa FFT tabanlı analitik sinyal.
    """
    n = len(x)
    Xf = np.fft.fft(x)
    h = np.zeros(n)
    if n % 2 == 0:
        h[0] = 1
        h[n//2] = 1
        h[1:n//2] = 2
    else:
        h[0] = 1
        h[1:(n+1)//2] = 2
    return np.fft.ifft(Xf * h)

def hilbert_features(prices: pd.Series) -> dict:
    """
    Hilbert ile anlık faz/frekans ve genlik sezgisi.
    """
    x = prices.fillna(method="ffill").values.astype(float)
    try:
        # varsa scipy
        from scipy.signal import hilbert
        analytic = hilbert(x)
    except Exception:
        analytic = _hilbert_analytic(x)

    amp = np.abs(analytic)
    phase = np.unwrap(np.angle(analytic))
    inst_freq = np.diff(phase, prepend=phase[0])
    return {
        "amp": pd.Series(amp, index=prices.index),
        "inst_freq": pd.Series(inst_freq, index=prices.index),
    }

def wavelet_trend(prices: pd.Series) -> pd.Series:
    """
    PyWavelets varsa düşük ölçek trend; yoksa EMA fallback.
    """
    try:
        import pywt
        coeffs = pywt.wavedec(prices.fillna(method="ffill").values, "db4", level=2)
        # yüksek frekans detayları sıfırla (soft denoise)
        for i in range(1, len(coeffs)):
            coeffs[i] = np.zeros_like(coeffs[i])
        rec = pywt.waverec(coeffs, "db4")
        rec = rec[:len(prices)]
        return pd.Series(rec, index=prices.index, name="wavelet_trend")
    except Exception:
        return prices.ewm(span=CONFIG.TA.EMA_PERIODS[1], adjust=False).mean().rename("wavelet_trend")

# --------------------------
# 3) Entropy Ölçüleri
# --------------------------
def _phi_apen(U: np.ndarray, m: int, r: float) -> float:
    N = len(U)
    if N <= m + 1:
        return np.nan
    x = np.array([U[i:i+m] for i in range(N - m + 1)])
    C = np.zeros(len(x))
    for i in range(len(x)):
        dist = np.max(np.abs(x - x[i]), axis=1)
        C[i] = np.mean(dist <= r)
    C = C[C > 0]
    return np.mean(np.log(C)) if len(C) else np.nan

def approximate_entropy(series: pd.Series, m: int = None, r: float | None = None) -> float:
    m = m or getattr(CONFIG.TA, "ENTROPY_M", 2)
    if r is None:
        r_factor = getattr(CONFIG.TA, "ENTROPY_R_FACTOR", 0.2)
        r = r_factor * np.std(series.dropna().values)
    U = series.dropna().values
    return float(_phi_apen(U, m, r) - _phi_apen(U, m+1, r))

def sample_entropy(series: pd.Series, m: int = None, r: float | None = None) -> float:
    m = m or getattr(CONFIG.TA, "ENTROPY_M", 2)
    if r is None:
        r_factor = getattr(CONFIG.TA, "ENTROPY_R_FACTOR", 0.2)
        r = r_factor * np.std(series.dropna().values)
    U = series.dropna().values
    N = len(U)
    if N <= m + 1:
        return np.nan
    def _count(matches):
        cnt = 0
        for i in range(N - matches):
            for j in range(i + 1, N - matches + 1):
                if np.max(np.abs(U[i:i+matches] - U[j:j+matches])) <= r:
                    cnt += 1
        return cnt
    A = _count(m + 1)
    B = _count(m)
    return float(-np.log(A / B)) if A > 0 and B > 0 else np.nan

def permutation_entropy(series: pd.Series, m: int = None, tau: int = 1) -> float:
    m = m or getattr(CONFIG.TA, "ENTROPY_M", 3)
    X = series.dropna().values
    N = len(X) - (m - 1) * tau
    if N <= 0:
        return np.nan
    patterns = {}
    for i in range(N):
        window = X[i:i + m * tau:tau]
        order = tuple(np.argsort(window))
        patterns[order] = patterns.get(order, 0) + 1
    probs = np.array(list(patterns.values()), dtype=float)
    probs /= probs.sum()
    pe = -np.sum(probs * np.log(probs))
    # normalize by log(m!)
    return float(pe / np.log(math.factorial(m)))

def entropy_features(prices: pd.Series) -> dict:
    apen = approximate_entropy(prices)
    sampen = sample_entropy(prices)
    pent = permutation_entropy(prices)
    # normalize [0..1] safe
    pent_norm = np.clip(pent, 0.0, 1.0) if not np.isnan(pent) else 0.5
    return {"apen": apen, "sampen": sampen, "pent": pent, "pent_norm": pent_norm}

# --------------------------
# 4) Rejim Tespiti (heuristic / HMM opsiyonel)
# --------------------------
def regime_detection(df: pd.DataFrame, window: int | None = None) -> str:
    """
    Heuristic: volatilite + trend + drawdown
    hmmlearn varsa 2-3 state HMM denenir, yoksa heuristic döner.
    """
    window = window or getattr(CONFIG.TA, "REGIME_WINDOW", 80)
    close = df["close"].dropna()
    if len(close) < max(window, 50):
        return "unknown"

    rets = close.pct_change()
    vol = rets.rolling(window).std().iloc[-1]
    ema_fast = close.ewm(span=CONFIG.TA.EMA_PERIODS[0], adjust=False).mean().iloc[-1]
    ema_slow = close.ewm(span=CONFIG.TA.EMA_PERIODS[1], adjust=False).mean().iloc[-1]
    trend_sign = 1 if ema_fast > ema_slow else -1

    rolling_max = close.rolling(window).max().iloc[-1]
    dd = (close.iloc[-1] - rolling_max) / rolling_max  # ~[-1,0]

    # HMM varsa deneyelim
    try:
        from hmmlearn.hmm import GaussianHMM
        X = rets.dropna().values[-(window*3):].reshape(-1, 1)
        if len(X) > 20:
            model = GaussianHMM(n_components=3, covariance_type="diag", n_iter=50)
            model.fit(X)
            state = model.predict(X)[-1]
            # state -> vol ortalamasına göre sınıflandır
            states_vol = []
            for s in range(model.n_components):
                states_vol.append(np.std(X[model.predict(X)==s]))
            order = np.argsort(states_vol)  # low vol -> high vol
            if state == order[0]:
                hmm_regime = "range"
            elif state == order[-1]:
                hmm_regime = "crash" if trend_sign < 0 else "trend"
            else:
                hmm_regime = "trend"
            return hmm_regime
    except Exception:
        pass

    # Heuristic
    if dd < -0.12 and trend_sign < 0:
        return "crash"
    if vol < rets.rolling(window).std().quantile(0.4):
        return "range"
    return "trend" if trend_sign > 0 else "downtrend"

# --------------------------
# 5) Lead-Lag & Transfer Entropy (basit)
# --------------------------
def lead_lag_max_corr(series: pd.Series, ref_series: pd.Series, max_lag: int | None = None) -> tuple[int, float]:
    """
    Lag in [-max_lag, +max_lag] aralığında en yüksek Pearson corr.
    +lag => series lagged (series t-lag vs ref t)
    """
    max_lag = max_lag or getattr(CONFIG.TA, "LEADLAG_MAX_LAG", 10)
    s = series.dropna()
    r = ref_series.dropna()
    idx = s.index.intersection(r.index)
    s = s.loc[idx].values
    r = r.loc[idx].values
    best_lag, best_corr = 0, 0.0
    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            s_shift, r_shift = s[-lag:], r[:len(r)+lag]
        elif lag > 0:
            s_shift, r_shift = s[:len(s)-lag], r[lag:]
        else:
            s_shift, r_shift = s, r
        if len(s_shift) < 10:
            continue
        c = np.corrcoef(s_shift, r_shift)[0, 1]
        if np.isfinite(c) and abs(c) > abs(best_corr):
            best_corr, best_lag = c, lag
    return best_lag, float(best_corr)

def transfer_entropy_binned(x: pd.Series, y: pd.Series, lag: int = 1, bins: int = 8) -> float:
    """
    Basit TE(X->Y): eşit genişlikte binleme + bilgi teorisi.
    Sadece göreli karşılaştırma için kullan.
    """
    xi = pd.cut(x.shift(lag).dropna(), bins, labels=False)
    yi = pd.cut(y.dropna(), bins, labels=False)
    yi_1 = pd.cut(y.shift(lag).dropna(), bins, labels=False)

    idx = xi.index.intersection(yi.index).intersection(yi_1.index)
    xi, yi, yi_1 = xi.loc[idx], yi.loc[idx], yi_1.loc[idx]

    # p(y_t, y_{t-1}, x_{t-1})
    p_xyz = pd.crosstab(index=[yi, yi_1], columns=xi, normalize=True)
    # p(y_t, y_{t-1})
    p_yz = pd.crosstab(index=[yi, yi_1], columns=None, normalize=True)
    # p(y_{t-1}, x_{t-1})
    p_zx = pd.crosstab(index=yi_1, columns=xi, normalize=True)
    # p(y_{t-1})
    p_z = yi_1.value_counts(normalize=True)

    te = 0.0
    for (y_t, y_tm1), row in p_xyz.iterrows():
        for x_tm1, p_val in row.items():
            if p_val <= 0:
                continue
            pyz = p_yz.loc[(y_t, y_tm1)]
            pzx = p_zx.loc[y_tm1, x_tm1] if (y_tm1 in p_zx.index and x_tm1 in p_zx.columns) else 0
            pz = p_z.loc[y_tm1] if y_tm1 in p_z.index else 0
            denom = (pyz * pzx) if (pyz > 0 and pzx > 0) else 0
            if denom > 0:
                te += p_val * np.log(p_val / denom)
    return float(max(te, 0.0))

# --------------------------
# 6) alpha_ta: birleşik skor + sinyal
# --------------------------
def _clip(v, low=-1.0, high=1.0):
    return float(np.clip(v, low, high))

def compute_alpha_ta(df: pd.DataFrame, ref_close: pd.Series | None = None) -> dict:
    """
    Döndürür:
      {
        "alpha_ta": float,
        "signal": -1/0/1,
        "components": {...},
        "regime": str,
        "diagnostics": {...}
      }
    """
    try:
        close = df["close"].astype(float)
        vol = df["volume"] if "volume" in df.columns else pd.Series(index=df.index, dtype=float)

        # Smooth / Trend-Cycle
        kal = kalman_filter_series(close)
        wav = wavelet_trend(close)
        hil = hilbert_features(close)
        ent = entropy_features(close)

        # Baz indikatörler (smooth seriye uygula)
        base_df = df.copy()
        base_df["close"] = kal  # gürültü azaltılmış fiyat
        ema_fast = ema(base_df, period=CONFIG.TA.EMA_PERIODS[0])
        ema_slow = ema(base_df, period=CONFIG.TA.EMA_PERIODS[1])
        macd_line, macd_sig, macd_hist = macd(base_df)
        rsi_val = rsi(base_df).iloc[-1]
        obv_val = obv(df).iloc[-1]

        ema_sig = 1 if ema_fast.iloc[-1] > ema_slow.iloc[-1] else -1
        macd_sig_bin = 1 if (macd_line.iloc[-1] - macd_sig.iloc[-1]) > 0 else -1

        # OBV trend (20-bar)
        obv20_prev = obv(df).iloc[-20] if len(df) > 20 else obv(df).iloc[0]
        obv_sig = 1 if obv_val > obv20_prev else -1

        # RSI soft bin
        if rsi_val < 30:
            rsi_sig = 1
        elif rsi_val > 70:
            rsi_sig = -1
        else:
            # orta bölgede zayıf ağırlık
            rsi_sig = 0.5 if rsi_val < 50 else -0.5

        # Rejim
        regime = regime_detection(df)
        # Hilbert frekans düşükse (trend baskın) trend ağırlıkları ↑
        trend_strength = float(1.0 / (1.0 + np.abs(hil["inst_freq"].iloc[-1])))
        # Entropy normalize (Permutation)
        ent_norm = ent["pent_norm"]
        entropy_attn = float(1.0 - 0.5 * ent_norm)  # yüksek entropy -> güven azalt

        # Lead-Lag (opsiyonel)
        leadlag = None
        leadcorr = None
        te_xy = None
        if isinstance(ref_close, pd.Series) and len(ref_close) > 50:
            leadlag, leadcorr = lead_lag_max_corr(close, ref_close)
            te_xy = transfer_entropy_binned(ref_close.pct_change(), close.pct_change(), lag=1, bins=8)

        # Ağırlık seti (rejim-aware)
        w_trend = 0.35
        w_mom = 0.25
        w_vol = 0.15
        w_volflow = 0.25

        if regime in ("trend", "downtrend"):
            w_trend *= 1.2 * (1 + 0.5 * trend_strength)
            w_mom *= 0.9
        elif regime == "range":
            w_trend *= 0.8
            w_mom *= 1.2
        elif regime == "crash":
            w_trend *= 1.1
            w_mom *= 0.9
            w_vol *= 1.3

        # Normalize ağırlıklar
        w_sum = (w_trend + w_mom + w_vol + w_volflow)
        w_trend, w_mom, w_vol, w_volflow = [w / w_sum for w in (w_trend, w_mom, w_vol, w_volflow)]

        # Bileşen skorları
        comp_trend = 0.6 * ema_sig + 0.4 * macd_sig_bin
        comp_mom = rsi_sig
        # Volatilite tabanlı breakout (Donchian sinyali mevcut fonksiyonda var)
        br = breakout(df).iloc[-1] if len(df) > 30 else 0.0
        comp_vol = br
        comp_volflow = obv_sig

        # Birleşik skor (entropy atten.)
        raw_score = (
            w_trend * comp_trend +
            w_mom * comp_mom +
            w_vol * comp_vol +
            w_volflow * comp_volflow
        )
        alpha = float(raw_score * entropy_attn)

        # Dinamik eşik: entropy & rejim etkisi
        thr_long = getattr(CONFIG.TA, "ALPHA_LONG_THRESHOLD", 0.6)
        thr_short = getattr(CONFIG.TA, "ALPHA_SHORT_THRESHOLD", -0.6)

        # entropy yüksekse eşikleri biraz aç
        widen = 1.0 + 0.3 * ent_norm
        thr_long *= widen
        thr_short *= widen

        if regime == "crash":
            thr_long *= 1.1  # long için daha seçici
        if regime in ("trend", "downtrend"):
            thr_short *= 0.95  # trendde short tetik daha kolay olsun (downtrend için)

        signal = 1 if alpha > thr_long else (-1 if alpha < thr_short else 0)

        return {
            "alpha_ta": round(alpha, 4),
            "signal": int(signal),
            "components": {
                "comp_trend": round(_clip(comp_trend), 3),
                "comp_mom": round(_clip(comp_mom), 3),
                "comp_vol": round(_clip(comp_vol), 3),
                "comp_volflow": round(_clip(comp_volflow), 3),
                "weights": {
                    "trend": round(w_trend, 3),
                    "momentum": round(w_mom, 3),
                    "vol": round(w_vol, 3),
                    "volflow": round(w_volflow, 3),
                }
            },
            "regime": regime,
            "diagnostics": {
                "entropy_perm_norm": round(ent_norm, 3),
                "trend_strength_hilbert": round(trend_strength, 3),
                "lead_lag": int(leadlag) if leadlag is not None else None,
                "lead_corr": round(leadcorr, 3) if leadcorr is not None else None,
                "transfer_entropy_ref_to_price": round(te_xy, 6) if te_xy is not None else None,
            }
        }
    except Exception as e:
        print(f"[ALPHA_TA ERROR] {e}")
        return {"alpha_ta": 0.0, "signal": 0, "components": {}, "regime": "unknown", "diagnostics": {}}

# --------------------------
# 7) generate_signals & scan_market (alpha_ta tabanlı)
# --------------------------
def generate_signals(df: pd.DataFrame, ref_close: pd.Series | None = None) -> dict:
    """
    Tek sembol: alpha_ta + sinyal.
    """
    return compute_alpha_ta(df, ref_close=ref_close)

def scan_market(market_data: dict, ref_close: pd.Series | None = None) -> dict:
    """
    Çoklu sembol taraması:
      market_data: { "BTCUSDT": df, "ETHUSDT": df, ... }
      ref_close  : opsiyonel referans seri (örn. BTC close) lead-lag için
    """
    results = {}
    for symbol, df in market_data.items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            results[symbol] = {"alpha_ta": 0.0, "signal": 0}
            continue
        try:
            results[symbol] = compute_alpha_ta(df, ref_close=ref_close)
        except Exception as e:
            print(f"[SCAN ERROR] {symbol}: {e}")
            results[symbol] = {"alpha_ta": 0.0, "signal": 0}
    return results


