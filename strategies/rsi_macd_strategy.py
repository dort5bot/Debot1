# strategies/rsi_macd_strategy.py
##♦️ pluggable strategy wrapper
from collections import deque
from utils import indicators
from handlers.signal_handler import publish_signal

class RSI_MACD_Strategy:
    """
    Lightweight class-based strategy that consumes closed klines and emits signals.
    Use by feeding closed close prices.
    """
    def __init__(self, symbol: str, lookback: int = 500, rsi_period: int = 14):
        self.symbol = symbol
        self.closes = deque(maxlen=lookback)
        self.rsi_period = rsi_period

    def on_new_close(self, close: float):
        self.closes.append(close)
        if len(self.closes) < self.rsi_period + 1:
            return
        arr = list(self.closes)
        rsi_val = indicators.rsi(arr, period=self.rsi_period)[-1]
        macd_line, macd_signal, macd_hist = indicators.macd(arr)
        macd_h = macd_hist[-1] if macd_hist else None
        if rsi_val is None or macd_h is None:
            return
        # simple rules
        if rsi_val < 30 and macd_h > 0:
            # emit BUY
            return {"type": "BUY", "strength": 0.6, "payload": {"rsi": rsi_val, "macd_h": macd_h, "price": close}}
        elif rsi_val > 70 and macd_h < 0:
            return {"type": "SELL", "strength": 0.6, "payload": {"rsi": rsi_val, "macd_h": macd_h, "price": close}}
        return None
