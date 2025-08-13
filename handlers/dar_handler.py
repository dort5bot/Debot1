# handlers/dar_handler.py
# --------------------------------
# /dar      -> Dosya ağacı
# /dar L    -> Dosya içeriği + bağımlılık bilgisi, zip olarak gönderir

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

# -------------------------------
# Dosya bağımlılıklarını okuma
def get_dependencies(filepath, lang):
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

# -------------------------------
# /dar komutu
async def dar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    include_content = len(args) > 0 and args[0].lower() == 'l'
    startpath = '.'  # Bot root dizini

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"Bot_dar_{timestamp}.zip"
    txt_filename = f"Bot_dar_{timestamp}.txt"

    output_lines = []

    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * level
        output_lines.append(f"{indent}{os.path.basename(root)}/")
        for f in files:
            filepath = os.path.join(root, f)
            ext = os.path.splitext(f)[1]
            lang = EXT_LANG_MAP.get(ext, 'Text')

            if not include_content:
                desc = f" # {lang}" if lang != 'Text' else ''
                output_lines.append(f"{indent}    {f}{desc}")
            else:
                deps = get_dependencies(filepath, lang)
                try:
                    with open(filepath, 'r', encoding='utf-8') as file:
                        content = file.read()
                    deps_section = ''
                    if deps:
                        deps_section = "# Dependencies:\n" + "\n".join(deps) + "\n\n"
                    file_content = f"# {os.path.relpath(filepath, startpath)} [{lang}]\n{deps_section}{content}\n\n"
                except Exception:
                    file_content = f"# {os.path.relpath(filepath, startpath)} [{lang}]\n[Dosya okunamadı]\n"
                output_lines.append(file_content)

    output_text = "\n".join(output_lines)

    if include_content:
        # /dar L -> zip gönder
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(startpath):
                for f in files:
                    filepath = os.path.join(root, f)
                    ext = os.path.splitext(f)[1]
                    lang = EXT_LANG_MAP.get(ext, 'Text')
                    deps = get_dependencies(filepath, lang)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as file:
                            content = file.read()
                        deps_section = ''
                        if deps:
                            deps_section = "# Dependencies:\n" + "\n".join(deps) + "\n\n"
                        content_with_header = f"# {os.path.relpath(filepath, startpath)} [{lang}]\n{deps_section}{content}\n\n"
                        zipf.writestr(os.path.relpath(filepath, startpath), content_with_header)
                    except Exception:
                        zipf.writestr(os.path.relpath(filepath, startpath), f"# {os.path.relpath(filepath, startpath)} [{lang}]\n[Dosya okunamadı]\n")
        with open(zip_filename, 'rb') as f:
            await update.message.reply_document(document=f)
    else:
        # /dar -> mesaj veya txt
        if len(output_text) <= TELEGRAM_MSG_LIMIT:
            await update.message.reply_text(f"<pre>{output_text}</pre>", parse_mode="HTML")
        else:
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(output_text)
            with open(txt_filename, 'rb') as f:
                await update.message.reply_document(document=f)

# -------------------------------
# Plugin loader uyumlu
def register_handlers(app):
    app.add_handler(CommandHandler("dar", dar_command))
