# handlers/dar_handler.py
# --------------------------------
# /dar      -> Dosya ağacı
# /dar L    -> Dosya içerikleri + bağımlılık bilgisi (ZIP ile)

import os
import zipfile
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

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
    '.sh': 'Shell',
    '.md': 'Markdown',
}

TELEGRAM_MSG_LIMIT = 4000  # Karakter limiti
ROOT_DIR = '.'  # Bot root dizini


def get_dependencies(filepath, lang):
    """Belirtilen dosyanın bağımlılıklarını okur."""
    deps = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if lang == 'Python' and (line.startswith('import ') or line.startswith('from ')):
                    deps.append(line)
                elif lang in ['JavaScript', 'TypeScript'] and (line.startswith('import ') or 'require(' in line):
                    deps.append(line)
                elif lang in ['C', 'C++'] and line.startswith('#include'):
                    deps.append(line)
                elif lang == 'Java' and line.startswith('import '):
                    deps.append(line)
    except Exception:
        deps.append('[Dependencies could not be read]')
    return deps


async def dar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    include_content = len(args) > 0 and args[0].lower() == 'l'

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"Bot_dar_{timestamp}.zip"
    txt_filename = f"Bot_dar_{timestamp}.txt"

    output_lines = []

    # ZIP hazırlama
    zipf = zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) if include_content else None

    for root, dirs, files in os.walk(ROOT_DIR):
        # Klasör adı ekle
        level = root.replace(ROOT_DIR, '').count(os.sep)
        indent = ' ' * 4 * level
        output_lines.append(f"{indent}{os.path.basename(root)}/")

        for fname in files:
            filepath = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1]
            lang = EXT_LANG_MAP.get(ext, 'Text')

            if not include_content:
                # Sadece dosya adı + dil bilgisi
                desc = f" # {lang}" if lang != 'Text' else ''
                output_lines.append(f"{indent}    {fname}{desc}")
            else:
                # İçerik + bağımlılık ekleme
                deps = get_dependencies(filepath, lang)
                try:
                    with open(filepath, 'r', encoding='utf-8') as file:
                        content = file.read()
                    deps_section = f"# Dependencies:\n" + "\n".join(deps) + "\n\n" if deps else ''
                    content_with_header = (
                        f"# {os.path.relpath(filepath, ROOT_DIR)} [{lang}]\n"
                        f"{deps_section}{content}\n\n"
                    )
                except Exception:
                    content_with_header = (
                        f"# {os.path.relpath(filepath, ROOT_DIR)} [{lang}]\n[Dosya okunamadı]\n"
                    )

                # ZIP içine yaz
                zipf.writestr(os.path.relpath(filepath, ROOT_DIR), content_with_header)

    # ZIP veya TXT gönder
    if include_content:
        zipf.close()
        with open(zip_filename, 'rb') as f:
            await update.message.reply_document(document=f)
    else:
        output_text = "\n".join(output_lines)
        if len(output_text) <= TELEGRAM_MSG_LIMIT:
            await update.message.reply_text(f"<pre>{output_text}</pre>", parse_mode="HTML")
        else:
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(output_text)
            with open(txt_filename, 'rb') as f:
                await update.message.reply_document(document=f)


# Plugin loader uyumlu
def register(app):
    app.add_handler(CommandHandler("dar", dar_command))
