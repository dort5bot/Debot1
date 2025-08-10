# utils/indicators.py
from typing import List, Optional, Tuple
import math

def sma(values: List[float], period: int) -> List[Optional[float]]:
    out = [None] * len(values)
    if period <= 0:
        return out
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= period:
            s -= values[i-period]
        if i >= period-1:
            out[i] = s / period
    return out

def ema(values: List[float], period: int) -> List[Optional[float]]:
    out = [None] * len(values)
    if period <= 0 or not values:
        return out
    k = 2 / (period + 1)
    prev = None
    for i, v in enumerate(values):
        if i == 0:
            prev = v
            out[i] = prev
        else:
            prev = (v - prev) * k + prev
            out[i] = prev
    return out

def rsi(values: List[float], period: int = 14) -> List[Optional[float]]:
    out = [None] * len(values)
    if len(values) < period + 1:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period+1):
        diff = values[i] - values[i-1]
        if diff > 0:
            gains += diff
        else:
            losses += -diff
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = 100 - (100 / (1 + (avg_gain / avg_loss) if avg_loss != 0 else 1e9))
    for i in range(period+1, len(values)):
        diff = values[i] - values[i-1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 1e9
        out[i] = 100 - (100 / (1 + rs))
    return out

def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    macd_line = [None]*len(values)
    for i in range(len(values)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]
    signal_line = ema([v if v is not None else 0.0 for v in macd_line], signal)
    hist = [ (macd_line[i] - signal_line[i]) if macd_line[i] is not None and signal_line[i] is not None else None for i in range(len(values))]
    return macd_line, signal_line, hist

def bollinger_bands(values: List[float], period: int = 20, mult: float = 2.0):
    sma_vals = sma(values, period)
    upper = [None]*len(values)
    lower = [None]*len(values)
    for i in range(len(values)):
        if i >= period-1 and sma_vals[i] is not None:
            slice_vals = values[i-period+1:i+1]
            mean = sma_vals[i]
            variance = sum((x-mean)**2 for x in slice_vals) / period
            sd = math.sqrt(variance)
            upper[i] = mean + mult*sd
            lower[i] = mean - mult*sd
    return upper, sma_vals, lower
