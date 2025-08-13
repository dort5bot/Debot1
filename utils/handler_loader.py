#otomotik handler ekleme dosyası 
#handler_loader.py
#get register+Handler 
import os
import importlib
import logging
from telegram.ext import CommandHandler

LOG = logging.getLogger("handler_loader")

def load_handlers(application, path="handlers"):
    """
    handlers klasöründeki tüm python dosyalarını tarar.
    - Eğer register(application) varsa onu çağırır.
    - Yoksa get_handler() varsa command handler ekler.
    """
    for file in os.listdir(path):
        if file.endswith(".py") and file != "__init__.py":
            module_name = f"{path}.{file[:-3]}"
            try:
                module = importlib.import_module(module_name)

                # 1️⃣ register(application) varsa onu kullan
                if hasattr(module, "register"):
                    module.register(application)
                    LOG.info(f"[PLUGIN] register() ile yüklendi: {module_name}")
                    continue

                # 2️⃣ get_handler() varsa otomatik CommandHandler ekle
                if hasattr(module, "get_handler"):
                    handler_info = module.get_handler()
                    if not isinstance(handler_info, dict):
                        raise TypeError("get_handler() bir dict döndürmeli.")

                    command = handler_info.get("command")
                    callback = handler_info.get("callback")
                    help_text = handler_info.get("help", "")

                    if not command or not callback:
                        raise ValueError(f"{module_name} geçersiz handler_info.")

                    application.add_handler(CommandHandler(command, callback))
                    LOG.info(f"[PLUGIN] get_handler() ile yüklendi: {module_name} — /{command}")

                else:
                    LOG.warning(f"[PLUGIN] {module_name} uyumlu bir arayüz sağlamıyor.")

            except Exception as e:
                LOG.exception(f"[PLUGIN] {module_name} yüklenemedi: {e}")
                
