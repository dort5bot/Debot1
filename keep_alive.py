# keep_alive.py
# self-ping buraya entegre main.py de yok

from aiohttp import web
import os
import logging
import asyncio
import aiohttp

LOG = logging.getLogger("keep_alive")

async def handle_root(request):
    return web.Response(text="Bot is alive!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle_root)

    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    LOG.info(f"Keep-alive server started on port {port}")
    return f"http://localhost:{port}/"

async def self_ping(url, interval=300):
    """Kendi kendine ping atarak free Render uyku önlemesi."""
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    LOG.info(f"[KEEPALIVE] Ping sent to {url}, status={resp.status}")
        except Exception as e:
            LOG.error(f"[KEEPALIVE] Ping error: {e}")
        await asyncio.sleep(interval)

def keep_alive(loop):
    """Keep-alive server ve self-ping başlat."""
    async def runner():
        url = await start_server()
        # Render’da gerçek URL kullan
        url = os.getenv("KEEPALIVE_URL", url)
        loop.create_task(self_ping(url))
    loop.create_task(runner())
