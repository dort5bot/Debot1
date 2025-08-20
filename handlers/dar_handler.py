# handlers/dar_handler.py
# --------------------------------
# /dar      -> Dosya ağacı (mesaj, uzun olursa TXT)
# /dar Z    -> ZIP (tree.txt + içerikler, sadece listelenen dosyalar + .env + .gitignore)
# /dar k    -> Botun komut listesi

import os
import zipfile
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

ROOT_DIR = '.'
TELEGRAM_MSG_LIMIT = 4000

#--komut listesi---
COMMAND_LIST = {
    "/io": "In-Out Alış Satış Baskısı raporu",
    "/nls": "Balina hareketleri ve yoğunluk (NLS analizi)",
    "/npr": "Nakit Piyasa Raporu",
    "/eft": "ETF & ABD piyasaları",
    "/ap": "Altların Güç Endeksi (AP)",
    "/p": "Anlık fiyat, 24h değişim, hacim bilgisi",
    "/p_ekle": "Favori coin ekleme",
    "/p_fav": "Favori coinleri listeleme",
    "/p_sil": "Favori coin silme",
    "/fr": "Funding Rate raporu + CSV kaydı",
    "/whale": "Whale Alerts + CSV kaydı",
    "/dar": "Dosya ağacı (Z=zip, k=komut listesi)",
}

#--dosya uzantısı -> dil eşlemesi---
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
    '.txt': 'Text',
}

#--dosya görevleri---
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
    '.gitignore': (None, None),
}

#--dar komutu---
def format_tree(root_dir):
    tree_lines = []
    valid_files = []  # sadece eklenecek dosyalar

    def walk(dir_path, prefix=""):
        items = sorted(os.listdir(dir_path))
        for i, item in enumerate(items):
            path = os.path.join(dir_path, item)
            connector = "└── " if i == len(items) - 1 else "├── "

            if os.path.isdir(path):
                if item.startswith("__") or (item.startswith(".") and item not in [".gitignore", ".env"]):
                    continue
                tree_lines.append(f"{prefix}{connector}{item}/")
                walk(path, prefix + ("    " if i == len(items) - 1 else "│   "))
            else:
                if item.startswith(".") and item not in [".env", ".gitignore"]:
                    continue
                ext = os.path.splitext(item)[1]
                if (ext not in EXT_LANG_MAP 
                        and not item.endswith(('.txt', '.csv', '.json', '.md'))
                        and item not in [".env", ".gitignore"]):
                    continue
                desc, dep = FILE_INFO.get(item, (None, None))
                extra = f" # {desc}" if desc else ""
                extra += f" ♻️{dep}" if dep else ""
                tree_lines.append(f"{prefix}{connector}{item}{extra}")
                valid_files.append(path)

    walk(root_dir)
    return "\n".join(tree_lines), valid_files

#--ZIP oluşturucu---
def create_zip_with_tree_and_files(root_dir, zip_filename):
    tree_text, valid_files = format_tree(root_dir)
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr("tree.txt", tree_text)
        for filepath in valid_files:
            arcname = os.path.relpath(filepath, root_dir)
            try:
                zipf.write(filepath, arcname)
            except Exception:
                pass
    return zip_filename

#--dar komutu handler---
async def dar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    mode = args[0].upper() if args else ""

    # k => komut listesi
    if mode == "K":
        text = "🤖 Bot Komut Listesi:\n\n"
        for cmd, desc in COMMAND_LIST.items():
            text += f"{cmd:<10} → {desc}\n"
        await update.message.reply_text(f"<pre>{text}</pre>", parse_mode="HTML")
        return

    tree_text, _ = format_tree(ROOT_DIR)
    timestamp = datetime.now().strftime("%m%d_%H%M%S")

    if mode == "Z":
        zip_filename = f"Dbot_{timestamp}.zip"
        create_zip_with_tree_and_files(ROOT_DIR, zip_filename)
        with open(zip_filename, "rb") as f:
            await update.message.reply_document(document=f, filename=zip_filename)
        os.remove(zip_filename)
        return

    if len(tree_text) > TELEGRAM_MSG_LIMIT:
        txt_filename = f"Dbot_{timestamp}.txt"
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write(tree_text)
        with open(txt_filename, 'rb') as f:
            await update.message.reply_document(document=f)
        os.remove(txt_filename)
        return

    await update.message.reply_text(f"<pre>{tree_text}</pre>", parse_mode="HTML")

#--plugin loader---
def register(app):
    app.add_handler(CommandHandler("dar", dar_command))
