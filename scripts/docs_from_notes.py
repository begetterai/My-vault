#!/usr/bin/env python3
"""Переносит разборы из базы знаний в Google Docs.

Раньше эти материалы жили артефактами на claude.ai. Артефакт нельзя дать
управляющему: он открывается только из аккаунта Азиза, его не подписать
и не положить в общую папку. Поэтому всё, чем нужно делиться, живёт
в Google Docs по стандарту оформления (Times New Roman 13, без заливки).

Источник — markdown-заметки репозитория, они и остаются оригиналом.
Docs — то, что можно открыть человеку со стороны.

Запуск: python3 scripts/docs_from_notes.py [часть имени документа]
Без аргумента переносятся все заметки списка, с аргументом — только те,
в чьём имени встречается эта подстрока.
"""
import sys, re, datetime
sys.path.insert(0, '/home/user/My-vault/scripts')
import markdown as MD
from ops_docs import (session, STYLE, COMPANY, put_doc, folder_by_name, find,
                      enforce_font, add_footer)

ROOT = '1cSLEkOXikhTv0g6lPxZ31xJca1Yu-q43'
FOLDER = '11 Разборы и аналитика'
V = '/home/user/My-vault/'

# заметка → имя документа (третий элемент — вид документа в шапке,
# по умолчанию «РАЗБОР»)
NOTES = [
    ('1-Области/Ромашка/Структура-Ромашка-финал.md',
     'Структура Ромашка — 12 шагов'),
    ('1-Области/Ромашка/Разбор-отчёта-AP-2026.md',
     'Разбор отчёта AP 2026'),
    ('1-Области/Ромашка/Система-документов-операций.md',
     'Система документов операционного отдела'),
    ('1-Области/Ромашка/Логика-мини-аппа.md',
     'Логика мини-аппа'),
    ('1-Области/Ромашка/Разбор-структуры-операционки.md',
     'Разбор структуры операционки'),
    ('1-Области/Ромашка/Разбор-рынка-и-модульность.md',
     'Разбор рынка и модульность'),
    ('1-Области/Ромашка/Разбор-личного-бота.md',
     'Разбор личного бота'),
    ('1-Области/Ромашка/Баллы-штрафы-механика.md',
     'Баллы и штрафы — механика'),
    ('1-Области/Ромашка/Баллы-правила.md',
     'Баллы — правила для смены', 'ПРАВИЛА'),
    # Таджикский — отдельным документом: смешивать два языка в одном
    # файле нельзя, его не дашь человеку в руки.
    ('1-Области/Ромашка/Баллы-правила-тоҷикӣ.md',
     'Холҳо — қоидаҳо барои смена', 'ҚОИДАҲО', 'tj'),
    ('ops-system/ARCHITECTURE.md',
     'Операционная система точек — архитектура'),
]


def wiki_out(text):
    """Wiki-ссылки Obsidian в Docs не работают — оставляем только текст."""
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', lambda m: m.group(1).split('/')[-1], text)
    return text


# Шапка и подпись документа. Русский и таджикский лежат в разных файлах,
# и рамка документа должна быть на том же языке, что и текст внутри.
FRAME = {
    'ru': ('перенесено из базы знаний',
           'Оригинал документа ведётся в базе знаний Азиза. Эта копия — '
           'для тех, кому нужен доступ со стороны; при расхождении верна '
           'версия в базе.'),
    'tj': ('аз пойгоҳи дониш кӯчонида шуд',
           'Асли ҳуҷҷат дар пойгоҳи дониши Азиз нигоҳ дошта мешавад. Ин '
           'нусха барои онҳоест, ки дастрасии беруна лозим доранд; ҳангоми '
           'ихтилоф матни русӣ дуруст аст.'),
}


def to_html(md_text, title, kind='РАЗБОР', lang='ru'):
    body = MD.markdown(wiki_out(md_text),
                       extensions=['tables', 'sane_lists', 'nl2br'])
    today = datetime.date.today().strftime('%d.%m.%Y')
    moved, note = FRAME[lang]
    head = (f'<div class="rk-top"><div class="rk-co">{COMPANY}</div>'
            f'<div class="rk-kind">{kind} · {moved} {today}</div>'
            f'</div><h1>{title}</h1>')
    tail = f'<p class="note">{note}</p>'
    return f'<!doctype html><html><head><meta charset="utf-8">{STYLE}' \
           f'</head><body>{head}{body}{tail}</body></html>'


def main():
    s = session()
    folder = folder_by_name(s, FOLDER, ROOT)
    if not folder:
        r = s.post('https://www.googleapis.com/drive/v3/files',
                   params={'supportsAllDrives': 'true'},
                   json={'name': FOLDER, 'parents': [ROOT],
                         'mimeType': 'application/vnd.google-apps.folder'},
                   timeout=60)
        r.raise_for_status()
        folder = r.json()['id']
        print('создана папка:', FOLDER)

    only = sys.argv[1] if len(sys.argv) > 1 else ''
    seen = set()
    for note in NOTES:
        path, title = note[0], note[1]
        kind = note[2] if len(note) > 2 else 'РАЗБОР'
        lang = note[3] if len(note) > 3 else 'ru'
        if title in seen or (only and only.lower() not in title.lower()):
            continue
        try:
            text = open(V + path, encoding='utf-8').read()
        except FileNotFoundError:
            print(f'НЕТ ФАЙЛА: {path}')
            continue
        seen.add(title)
        fid, act = put_doc(s, title, folder,
                           to_html(text, title, kind, lang))
        enforce_font(s, fid)
        add_footer(s, fid, f'{COMPANY} · {title} · {FRAME[lang][0]}')
        print(f'{title:52s} {act:9s} '
              f'https://docs.google.com/document/d/{fid}')


if __name__ == '__main__':
    main()
