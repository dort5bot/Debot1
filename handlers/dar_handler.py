# dar_handler.py
# agac, içerik
# /dar, /dar L 

import os
import zipfile
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
import re

#--- plugin--- EN ALTTA 
# Bu kısım plugin uyumlu hale getirildi.
# register(application) fonksiyonu ile loader tarafından otomatik çağrılabilir.
#--- 

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

async def dar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    include_content = len(args) > 0 and args[0].lower() == 'l'
    startpath = '.'

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"Bot_dar_{timestamp}.zip"

    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(startpath):
            for f in files:
                filepath = os.path.join(root, f)
                arcname = os.path.relpath(filepath, startpath)
                ext = os.path.splitext(f)[1]
                lang = EXT_LANG_MAP.get(ext, 'Text')

                if include_content:
                    try:
                        deps = get_dependencies(filepath, lang)
                        with open(filepath, 'r', encoding='utf-8') as file:
                            content = file.read()
                        deps_section = ''
                        if deps:
                            deps_section = "# Dependencies:\n" + "\n".join(deps) + "\n\n"
                        content_with_header = f"# {arcname} [{lang}]\n{deps_section}{content}\n\n"
                        zipf.writestr(arcname, content_with_header)
                    except Exception:
                        zipf.writestr(arcname, f"# {arcname} [{lang}]\n[Dosya okunamadı]\n")
                else:
                    desc = lang if lang != 'Text' else ''
                    zipf.writestr(arcname, f"# {arcname} [{desc}]\n")

    with open(zip_filename, 'rb') as f:
        await update.message.reply_document(document=f)

#--- plugin---
def register(application):
    """
    Plugin uyumlu register fonksiyonu.
    loader bu fonksiyonu çağırarak dar_command handler'ını ekler.
    """
    application.add_handler(CommandHandler("dar", dar_command))
#---
