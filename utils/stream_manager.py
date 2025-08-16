# utils/stream_manager.py
##♦️ grouped combined streams, http fallback scheduler

import asyncio
from typing import List, Callable
from utils.config import CONFIG
from utils.binance_api import BinanceClient
import logging
import time

LOG = logging.getLogger("stream_manager")

class StreamManager:
    """
    Builds grouped combined streams from a symbol list (to respect websocket URL length).
    Provides a simple HTTP fallback scheduler for endpoints missing in WS (e.g. futures funding).
    """
    def __init__(self, client: BinanceClient, loop=None):
        self.client = client
        self.loop = loop or asyncio.get_event_loop()
        self.tasks = []

    def group_streams(self, streams: List[str]) -> List[List[str]]:
        group_size = CONFIG.BINANCE.IO_CONCURRENCY  # eski STREAM_GROUP_SIZE yerine
        groups = []
        for i in range(0, len(streams), group_size):
            groups.append(streams[i:i+group_size])
        return groups

    def start_combined_groups(self, streams: List[str], message_handler: Callable):
        groups = self.group_streams(streams)
        LOG.info("Starting %s combined stream groups", len(groups))
        for grp in groups:
            # start as managed tasks through client
            t = self.client.start_combined(grp, message_handler)
            self.tasks.append(t)

    def start_periodic_funding_poll(self, symbols: List[str], interval_sec: int, callback: Callable):
        """
        Periodically poll REST funding endpoint (fapi) for symbols since WS funding stream not used here.
        callback: async fn(list_of_entries)
        """
        async def runner():
            while True:
                try:
                    for sym in symbols:
                        res = await self.client.funding(sym, limit=1)
                        if res:
                            # if list, take first
                            entry = res[0] if isinstance(res, list) and len(res) else res
                            await callback(entry)
                    await asyncio.sleep(interval_sec)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    LOG.exception("funding poll error: %s", e)
                    await asyncio.sleep(5)
        task = self.loop.create_task(runner())
        self.tasks.append(task)

    def cancel_all(self):
        for t in self.tasks:
            t.cancel()
        self.tasks = []
