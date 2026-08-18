#!/usr/bin/env python3
"""Конфигурация системы. Ничего про конкретную компанию в коде нет.

Всё, что отличает одного клиента от другого, приходит из двух мест:
  · переменные окружения — секреты и адреса;
  · файл чек-листов (JSON) — что именно проверяют на точках.

Так система ставится новому клиенту без единой правки кода.
"""
import os, json, functools, datetime

ENV = os.environ.get

# ── секреты и адреса ─────────────────────────────────────────────────────────
BOT_TOKEN = ENV('BOT_TOKEN', '').strip()
ADMIN_CHAT = ENV('ADMIN_CHAT', '').strip()          # кому уходят сводки
DATA_SHEET = ENV('DATA_SHEET', '').strip()          # таблица операционных данных
PHOTO_FOLDER = ENV('PHOTO_FOLDER', '').strip()      # папка Drive под фото
WEBAPP_URL = ENV('WEBAPP_URL', '').strip()          # адрес Mini App
GOOGLE_SA = ENV('GOOGLE_SA_JSON', '')               # сервисный аккаунт, JSON строкой
GOOGLE_SUBJECT = ENV('GOOGLE_SUBJECT', '').strip()  # если нужен доступ от имени пользователя
PORT = int(ENV('PORT', '8080'))
COMPANY = ENV('COMPANY', 'Компания')

# Сервер живёт по UTC, точка — по своему времени. Без сдвига в таблице
# оказывается чужой час, и все отчёты по времени врут.
TZ_OFFSET = float(ENV('TZ_OFFSET', '5'))            # Душанбе = UTC+5
MAX_BODY = int(ENV('MAX_BODY', str(12 * 1024 * 1024)))
INIT_MAX_AGE = int(ENV('INIT_MAX_AGE', '86400'))    # старше — подпись не принимаем


def now():
    """Местное время точки."""
    return datetime.datetime.utcnow() + datetime.timedelta(hours=TZ_OFFSET)


def today():
    return now().date()


def day_str():
    return now().strftime('%d.%m.%Y')

# ── поведение ────────────────────────────────────────────────────────────────
PHOTOS_PER_RUN = int(ENV('PHOTOS_PER_RUN', '2'))
MIN_SECONDS = int(ENV('MIN_SECONDS', '180'))        # быстрее — формальное заполнение
REPEAT_FAIL = int(ENV('REPEAT_FAIL', '3'))          # столько провалов = сломан процесс
CHECK_GAP = float(ENV('CHECK_GAP', '0.7'))          # ниже — второй контур не работает

# ── расписание ───────────────────────────────────────────────────────────────
DAILY_AT = ENV('DAILY_AT', '21:30')                 # итог дня руководителям
WEEKLY_AT = ENV('WEEKLY_AT', '09:30')               # сводка недели, по понедельникам
CHECK_DEADLINE = int(ENV('CHECK_DEADLINE', '120'))  # мин на подтверждение управляющим

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKLISTS_FILE = ENV('CHECKLISTS_FILE',
                      os.path.join(HERE, 'checklists.romashka.json'))

TABS = {
    'points': 'Точки',
    'team': 'Команда',
    'ideas': 'Идеи и задачи',
    'fails': 'Невыполнено',
    'items': 'Пункты',
}


@functools.lru_cache(maxsize=1)
def checklists():
    """{key: {title, code, ask_time, blocks:[{name, items:[{text,norm,photo}]}],
              measures:{№: {q,norm,unit}}}} — с проставленной сквозной нумерацией."""
    raw = json.load(open(CHECKLISTS_FILE, encoding='utf-8'))
    for key, cl in raw.items():
        n = 0
        for b in cl['blocks']:
            for it in b['items']:
                n += 1
                it['n'] = n
        cl['total'] = n
        cl['tab'] = cl.get('tab') or cl['title']
        cl['measures'] = {int(k): v for k, v in (cl.get('measures') or {}).items()}
    return raw


def for_role(role):
    """Чек-листы, доступные роли. Пусто в roles — доступен всем.

    Без этого бариста видит в меню «Визит собственника», а управляющий —
    чек-лист, который к его работе не относится.
    """
    return {key: cl for key, cl in checklists().items()
            if not cl.get('roles') or role in cl['roles']}


def scheduled():
    """Чек-листы с дедлайном — только их ждут каждый день и по ним считают
    процент заполнения. Событийные (визит, собеседование, приёмка точки)
    в норму дня не входят и пропущенными не считаются."""
    return {k: cl for k, cl in checklists().items() if cl.get('deadline')}


def flat(key):
    """[(№, блок, текст)]"""
    cl = checklists()[key]
    return [(it['n'], b['name'], it['text']) for b in cl['blocks'] for it in b['items']]


def photo_items(key):
    """[(№, текст)] по пунктам, где нужен снимок."""
    cl = checklists()[key]
    return [(it['n'], it['text']) for b in cl['blocks'] for it in b['items']
            if it.get('photo')]


def total(key):
    return checklists()[key]['total']


def missing():
    """Чего не хватает для запуска — говорим сразу, а не падаем в рантайме."""
    need = {'BOT_TOKEN': BOT_TOKEN, 'DATA_SHEET': DATA_SHEET,
            'GOOGLE_SA_JSON': GOOGLE_SA}
    return [k for k, v in need.items() if not v]
