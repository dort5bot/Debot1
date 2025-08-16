#ta_utils.py


import numpy as np
import pandas as pd
from utils.config import CONFIG

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

# =============================================================
# Hacim & Likidite
# =============================================================

def obv(df: pd.DataFrame):
    """On-Balance Volume (OBV) hesaplar."""
    obv = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()
    return obv


def order_book_imbalance(bids: list, asks: list):
    """Order Book Imbalance (OBI) hesaplar."""
    bid_vol = sum([b[1] for b in bids])
    ask_vol = sum([a[1] for a in asks])
    return (bid_vol - ask_vol) / (bid_vol + ask_vol)


def open_interest_placeholder():
    """Open Interest için placeholder (borsa API ile entegre edilecek)."""
    return None

# =============================================================
# Sentiment
# =============================================================

def funding_rate_placeholder():
    """Funding Rate için placeholder (borsa API ile entegre edilecek)."""
    return None


def social_sentiment_placeholder():
    """Sosyal medya sentiment analizi için placeholder."""
    return None
