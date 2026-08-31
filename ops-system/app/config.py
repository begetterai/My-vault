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


# Операционные сутки кончаются не в полночь: ЗБ закрывается в 00:30,
# ОВИР в 03:30. Без сдвига закрытие ложится в следующий день, и смена
# выглядит незакрытой, а закрытие — сделанным ни к чему.
DAY_ENDS = float(ENV('DAY_ENDS', '5'))


def biz_now():
    """Время в рамках операционных суток: ночь принадлежит прошедшему дню."""
    return now() - datetime.timedelta(hours=DAY_ENDS)


def today():
    return biz_now().date()


def day_str():
    return biz_now().strftime('%d.%m.%Y')


def op_minute(t):
    """Минута от начала операционных суток. 00:30 — это конец дня, не начало,
    иначе закрытие считается просроченным с самого утра."""
    h, m = str(t).split(':')
    return (int(h) * 60 + int(m) - int(DAY_ENDS * 60)) % 1440


def now_minute():
    n = now()
    return (n.hour * 60 + n.minute - int(DAY_ENDS * 60)) % 1440

# ── поведение ────────────────────────────────────────────────────────────────
PHOTOS_PER_RUN = int(ENV('PHOTOS_PER_RUN', '2'))
MIN_SECONDS = int(ENV('MIN_SECONDS', '180'))        # быстрее — формальное заполнение
MIN_GAP = float(ENV('MIN_GAP', '2.0'))              # секунд между отметками; меньше — тыкал не глядя
REPEAT_FAIL = int(ENV('REPEAT_FAIL', '3'))          # столько провалов = сломан процесс
CHECK_GAP = float(ENV('CHECK_GAP', '0.7'))          # ниже — второй контур не работает
# Режим правки: кнопка ✎ на каждом пункте. Выключен — сверка идёт глазами,
# не отвлекая от самого обхода. Включается переменной, без выката кода.
FIX_MODE = ENV('FIX_MODE', '').strip().lower() in ('1', 'on', 'да', 'true')

# Поэтапный запуск: кого пускаем в приложение. Начинаем вдвоём — COO
# и управляющие, потом добавляем позиции по одной. Роль не в списке —
# человек видит экран «скоро подключим», а не сырую систему.
# Пустая строка в переменной = пускаем всех.
# Кого пускаем в приложение. На обкатке были только руководители и старшие
# смены; с выходом на точки открыто всем — иначе кассир и бариста видят
# одно «скоро» вместо работы.
ROLLOUT = [x.strip() for x in ENV('ROLLOUT', 'coo,manager,senior,staff').split(',')
           if x.strip()]

# Сводки в бот: итог дня, неделя, баллы к собранию. На обкатке выключены —
# отчёт о том, чем ещё никто не пользуется, только приучает его пролистывать.
SUMMARIES = ENV('SUMMARIES', '').strip().lower() in ('1', 'on', 'да', 'true')

# Напоминания о дедлайне и «просрочено». Включены с полевых тестов 28.08:
# без них человек узнаёт о просрочке постфактум, а напоминание за 45 минут —
# это и есть то, что заставляет сдавать вовремя.
#
# Напоминание идёт тому, чей это лист (своя позиция, своя роль); «просрочено»
# после срока — управляющему. Кто не сдал тренинги позиции, из счёта выпадает:
# ему листы ещё не показывают, спрашивать за них нечестно.
REMINDERS = ENV('REMINDERS', 'on').strip().lower() in ('1', 'on', 'да', 'true')

# ── расписание ───────────────────────────────────────────────────────────────
DAILY_AT = ENV('DAILY_AT', '21:30')                 # итог дня руководителям
WEEKLY_AT = ENV('WEEKLY_AT', '09:30')               # сводка недели, по понедельникам
CHECK_DEADLINE = int(ENV('CHECK_DEADLINE', '120'))  # мин на подтверждение управляющим
BACKUP_AT = ENV('BACKUP_AT', '05:30')               # копии таблиц, пока никто не пишет
CLOSE_DAY_AT = ENV('CLOSE_DAY_AT', '04:30')         # после закрытия ОВИР (03:30)
ROSTER_AT = ENV('ROSTER_AT', '21:00')               # запрос состава смены на завтра
ROSTER_SUM_AT = ENV('ROSTER_SUM_AT', '21:30')       # сводка: кто подтвердил
ROSTER_FALLBACK_AT = ENV('ROSTER_FALLBACK_AT', '23:00')  # нет состава — берём вчерашний
SUMMARY_AT = ENV('SUMMARY_AT', '20:00')             # сводка баллов, суббота

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKLISTS_FILE = ENV('CHECKLISTS_FILE',
                      os.path.join(HERE, 'checklists.romashka.json'))

TABS = {
    'points': 'Точки',
    'shift': 'Явка',
    'score': 'Баллы',
    'fixes': 'Правки',
    'tasks': 'Задачи',
    'equip': 'Оборудование',
    'team': 'Команда',
    'ideas': 'Идеи и задачи',
    'fails': 'Невыполнено',
    'items': 'Пункты',
}


# Типы форм. Приложение умеет пять — всё остальное описывается данными.
#   checklist — обход по расписанию: пункты, замеры, фото, дедлайн
#   shift     — явка: одна отметка прихода или ухода, с геометкой
#   journal   — событие: случилось, записал; дедлайна нет
#   form      — бланк: таблица позиций, строки добавляются на ходу
#   quiz      — обучение: теория экранами, потом вопросы с порогом
TYPES = ('checklist', 'shift', 'journal', 'form', 'quiz')


@functools.lru_cache(maxsize=1)
def forms():
    """Все формы приложения из JSON, с проставленной нумерацией пунктов."""
    raw = json.load(open(CHECKLISTS_FILE, encoding='utf-8'))
    for key, cl in raw.items():
        cl['key'] = key
        cl.setdefault('type', 'checklist')
        cl['tab'] = cl.get('tab') or cl['title']
        n = 0
        for b in cl.get('blocks') or []:
            for it in b['items']:
                n += 1
                it['n'] = n
        cl['total'] = n
        cl['measures'] = {int(k): v for k, v in (cl.get('measures') or {}).items()}
    return raw


def checklists():
    """Только чек-листы — обходы по пунктам."""
    return {k: cl for k, cl in forms().items() if cl['type'] == 'checklist'}


def by_type(t):
    return {k: cl for k, cl in forms().items() if cl['type'] == t}


def visible(role, t=None, dept=None, point=None):
    """Формы, доступные человеку. Пусто в roles/dept/points — доступно всем.

    Без этого бариста видит в меню «Визит собственника», а управляющий —
    форму, которая к его работе не относится.

    Отдел (21.08.2026): каждый видит чек-листы только своей позиции. Руководитель
    видит все — он проверяет точку целиком. Отдел не задан — человеку видно
    только то, что без отдела, иначе он получит чужие пункты.
    """
    boss = role in ('manager', 'coo')
    out = {}
    for k, cl in forms().items():
        if cl.get('roles') and role not in cl['roles']:
            continue
        if t is not None and cl['type'] != t:
            continue
        if point and cl.get('points') and point not in cl['points']:
            continue
        # Отдел — строка или список: маркировку сдают и кухня, и цех, и бар.
        d = cl.get('dept') or ''
        ds = [x.lower() for x in ([d] if isinstance(d, str) else d) if x]
        if ds and not boss and (dept or '').lower() not in ds:
            continue
        out[k] = cl
    return out


def for_role(role, dept=None, point=None):
    """Чек-листы, которые человек заполняет сам.

    Руководитель заполняет только свой лист. Чужие он не заполняет — он их
    проверяет, и это другое действие: заполнить за повара значит стереть
    единственного ответственного за пункт. Чужие листы приходят ему
    в блок «Проверка» уже заполненными.
    """
    out = visible(role, 'checklist', dept, point)
    if role == 'coo':
        # Директор смену не ведёт: ежедневные листы точки — работа
        # управляющего, а директор их проверяет. Оставляем только событийные:
        # визит, открытие точки, аттестация — они случаются, а не «каждый день
        # до 10:30». Иначе у него с утра висит чужая просрочка.
        out = {k: cl for k, cl in out.items()
               if 'coo' in (cl.get('roles') or []) and not cl.get('deadline')}
    elif role == 'manager':
        out = {k: cl for k, cl in out.items()
               if 'manager' in (cl.get('roles') or [])}
    return out


def scheduled():
    """Чек-листы с дедлайном — только их ждут каждый день и по ним считают
    процент заполнения. Событийные (визит, собеседование, приёмка точки)
    в норму дня не входят и пропущенными не считаются."""
    return {k: cl for k, cl in checklists().items() if cl.get('deadline')}


def form(key):
    return forms()[key]


def flat(key):
    """[(№, блок, текст)]"""
    cl = checklists()[key]
    return [(it['n'], b['name'], it['text']) for b in cl['blocks'] for it in b['items']]


# Этапы дня идут в этом порядке. Приём не открыть, пока предыдущая смена
# не сдала передачу: иначе принимать нечего.
STAGES = ('open', 'give', 'take', 'close')


def deadline_for(cl, point=None):
    """Срок этапа. По точкам он разный: ОВИР закрывается на три часа позже."""
    by = cl.get('deadline_point') or {}
    return by.get(point) or cl.get('deadline', '')


# Зона цеха закреплена за ролью: заготовщик лавашей не должен выбирать
# зону мяса. У кухни иначе — там повар встаёт на любую свободную станцию.
# Три роли цеха названы Владимиром 30.08.
STATION_BY_ROLE = {
 'заготовщик — лаваши': 'shift_ceh_l',
 'заготовщик — мясо и соусы': 'shift_ceh_m',
 'заготовщик — выпечка и десерты': 'shift_ceh_h',
}


def station_for(role_text):
    """Станция, закреплённая за ролью, либо пусто — выбирает сам."""
    return STATION_BY_ROLE.get(str(role_text or '').strip().lower(), '')


def stations():
    """Рабочие места: ключ, название, отдел. Одно место — четыре листа."""
    out = {}
    for cl in checklists().values():
        st = cl.get('station')
        if not st or st in out:
            continue
        out[st] = {'key': st, 'title': cl['title'].split(' · ')[0],
                   'dept': cl.get('dept', ''), 'points': cl.get('points') or []}
    return out


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
