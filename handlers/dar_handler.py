# handlers/dar_handler.py
# --------------------------------
# /dar      -> Dosya ağacı (daha okunabilir)
# /dar L    -> ZIP ile içerik + bağımlılık

import os
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

ROOT_DIR = '.'
TELEGRAM_MSG_LIMIT = 4000

# Dosya uzantısı -> dil eşlemesi
EXT_LANG_MAP = {
    '.py': 'Python',
    '.js': 'JavaScript',
    '.ts': 'TypeScript',
    '.java': 'Java',
    '.cpp': 'C++',
    '.c': 'C',
    '.html': 'HTML',
    '.css': 'CSS',
    '.json': 'JSON',
    '.csv': 'CSV',
    '.sh': 'Shell',
    '.md': 'Markdown',
}

# Dosya görevleri ve bağımlılık map (biliniyorsa)
FILE_INFO = {
    'main.py': ("Ana bot başlatma, handler kayıtları, JobQueue görevleri", None),
    'keep_alive.py': ("Render Free ping sistemi (bot uyumasını önler)", None),
    'io_handler.py': ("/io → In-Out Alış Satış Baskısı raporu", "utils.io_utils"),
    'nls_handler.py': ("/nls → Balina hareketleri ve yoğunluk (NLS analizi)", None),
    'npr_handler.py': ("/npr → Nakit Piyasa Raporu", None),
    'eft_handler.py': ("/eft → ETF & ABD piyasaları", None),
    'ap_handler.py': ("/ap → Altların Güç Endeksi (AP)", "utils.ap_utils"),
    'price_handler.py': ("/p → Anlık fiyat, 24h değişim, hacim bilgisi", None),
    'p_handler.py': ("/p_ekle, /p_fav, /p_sil → Favori coin listesi yönetimi", None),
    'fr_handler.py': ("/fr → Funding Rate komutu ve günlük CSV kaydı", None),
    'whale_handler.py': ("/whale → Whale Alerts komutu ve günlük CSV kaydı", None),
    'binance_utils.py': ("Binance API'den veri çekme ve metrik fonksiyonlar", None),
    'csv_utils.py': ("CSV okuma/yazma ve Funding Rate, Whale CSV kayıt fonksiyonları", None),
    'trend_utils.py': ("Trend okları, yüzde değişim hesaplama ve formatlama", None),
    'fav_list.json': (None, None),
    'runtime.txt': (None, None),
    '.env': (None, None),
}

def format_tree(root_dir):
    tree_lines = []

    def walk(dir_path, prefix=""):
        items = sorted(os.listdir(dir_path))
        for i, item in enumerate(items):
            path = os.path.join(dir_path, item)
            connector = "└── " if i == len(items) - 1 else "├── "
            if os.path.isdir(path):
                # __pycache__ vb. gizli klasörleri atla
                if item.startswith("__") or item.startswith("."):
                    continue
                tree_lines.append(f"{prefix}{connector}{item}/")
                walk(path, prefix + ("    " if i == len(items) - 1 else "│   "))
            else:
                ext = os.path.splitext(item)[1]
                if ext not in EXT_LANG_MAP and not item.endswith(('.txt', '.csv', '.json', '.md')):
                    continue  # gereksiz dosya
                desc, dep = FILE_INFO.get(item, (None, None))
                extra = f" # {desc}" if desc else ""
                extra += f" ♻️{dep}" if dep else ""
                tree_lines.append(f"{prefix}{connector}{item}{extra}")

    walk(root_dir)
    return "\n".join(tree_lines)


async def dar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tree_text = format_tree(ROOT_DIR)
    if len(tree_text) <= TELEGRAM_MSG_LIMIT:
        await update.message.reply_text(f"<pre>{tree_text}</pre>", parse_mode="HTML")
    else:
        # Dosya ile gönder
        timestamp = datetime.now().strftime("%m%d_%H%M%S")
        txt_filename = f"Bot_dar_{timestamp}.txt"
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write(tree_text)
        with open(txt_filename, 'rb') as f:
            await update.message.reply_document(document=f)


# Plugin loader uyumlu
def register(app):
    app.add_handler(CommandHandler("dar", dar_command))
