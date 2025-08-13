# keep_alive.py
# self-ping buraya entegre main.py de yok

# keep_alive.py
from aiohttp import web
import os
import logging
import asyncio
import aiohttp

LOG = logging.getLogger("keep_alive")

async def handle_root(request):
    """Basit health check endpoint."""
    return web.Response(text="Bot is alive!")

async def start_server():
    """Web server başlatır ve portu dinler."""
    app = web.Application()
    app.router.add_get('/', handle_root)

    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    LOG.info(f"Keep-alive server started on port {port}")

    # Render veya localhost URL
    url = os.getenv("KEEPALIVE_URL", f"http://localhost:{port}/")
    return url

async def self_ping(url: str, interval: int = 300):
    """Render free tier için botun uykuya girmesini önlemek amacıyla periyodik ping atar."""
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    LOG.info(f"[KEEPALIVE] Ping sent to {url}, status={resp.status}")
        except Exception as e:
            LOG.error(f"[KEEPALIVE] Ping error: {e}")
        await asyncio.sleep(interval)

def keep_alive(loop: asyncio.AbstractEventLoop):
    """Web server ve self-ping başlatır. Tek çağrı yeterlidir."""
    async def runner():
        url = await start_server()
        # Self-ping görevini başlat
        loop.create_task(self_ping(url))
    loop.create_task(runner())
