#!/usr/bin/env python3
"""Личный бюджет Азиза — телеграм-бот.

Только личные деньги. Ничего рабочего: ни Poster, ни Notion, ни выручки,
ни сотрудников, ни групп. Отделён от операционной системы Ромашки
намеренно — чтобы личное и рабочее не смешивались ни в коде, ни в голове.

Что умеет:
  · записать расход, доход, накопление, погашение кредита;
  · сразу после записи сказать, сколько осталось в категории на месяц;
  · показать остатки по всем категориям;
  · принять пачку операций одним сообщением;
  · расшифровать голосовое;
  · прочитать чек с фото (нужен ключ Claude, необязательно).

Разбор ввода идёт БЕЗ модели. Это главное: одинаковая фраза всегда даёт
одинаковую запись, и запись не теряется, если модель недоступна.
"""
import os, sys, json, re, time, datetime, logging, threading, collections

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('budget')

# ── Настройки ────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(ROOT, 'scripts', 'credentials')


def _read(name):
    p = os.path.join(CRED, name)
    return open(p).read().strip() if os.path.exists(p) else ''


TG_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip() or _read('telegram.token')
ALLOWED = os.environ.get('TELEGRAM_CHAT_ID', '').strip() or _read('telegram_chat_id.txt')
GROQ_KEY = os.environ.get('GROQ_API_KEY', '').strip() or _read('groq.token')
ANTHRO_KEY = os.environ.get('ANTHROPIC_API_KEY', '').strip() or _read('anthropic.token')
# Список моделей по порядку. Первая не ответила — берём следующую.
# Одна модель = одна точка отказа: когда Groq снял llama-3.3-70b-versatile,
# бот два дня отвечал «Сбой мозга» на каждый вопрос.
GROQ_MODELS = [m.strip() for m in os.environ.get(
    'GROQ_MODELS', 'openai/gpt-oss-120b,openai/gpt-oss-20b').split(',') if m.strip()]
CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL', 'claude-opus-5').strip()
_LIVE = {'model': None}          # какая модель ответила в прошлый раз

TZ_OFFSET = datetime.timedelta(hours=5)          # Душанбе UTC+5, сервер в UTC


def now_local():
    return datetime.datetime.utcnow() + TZ_OFFSET


def today_local():
    return now_local().date()


def load_sa():
    raw = os.environ.get('ROMASHKA_SA_JSON')
    info = json.loads(raw) if raw else json.load(open(os.path.join(CRED, 'romashka-drive.json')))
    return service_account.Credentials.from_service_account_info(
        info, scopes=['https://www.googleapis.com/auth/spreadsheets',
                      'https://www.googleapis.com/auth/drive'])


SHEETS = AuthorizedSession(load_sa())
API = 'https://sheets.googleapis.com/v4/spreadsheets/'

BUDGET_SS = '1Cn3QwTy2AiW4Kjw2PLNniZuB_2LyQ2ES8nOCgHPKDIE'
# «Связь», «Уход за собой» и «Свидания» заведены 04.09.2026 по разбору:
# в «Прочее» падали стрижка, баланс телефона и вечера с девушкой — не потому
# что непонятно, а потому что подходящей категории не было.
BUDGET_CATS = {'Дом','Машина','Гаджеты','Подписки','Рассрочка','Связь','Кафе','Продукты','Лечение / Медикаменты','Спортивное питание','Абонемент в зал','БАДы','Массаж / Сауна','Уход за собой','Курение','Одежда/Обувь','Развлечение','Свидания','Обучение','Семья','Подарки','Путешествие','Прочее'}
DEBT_CATS = {'Оплата кредита'}  # тип «Погашение» — вне расходов (зона «Сбережения и долг»)
INCOME_CATS = {'Зарплата','Прочий доход'}
SAVINGS_CATS = {'Накопления / Подушка','Инвестиции'}  # тип «Накопление» — вне расходов

# ── Телеграм ─────────────────────────────────────────────────────────────────
def tg(method, **kw):
    """Длинный опрос держит соединение до kw['timeout']; ждать надо дольше."""
    wait = int(kw.get('timeout', 0)) + 20
    try:
        return requests.post(f'https://api.telegram.org/bot{TG_TOKEN}/{method}',
                             json=kw, timeout=wait).json()
    except Exception as e:
        return {'ok': False, 'description': f'{type(e).__name__}: {e}'}


def send(text, **kw):
    # Когда черновик ждёт категорию, к любому сообщению цепляем кнопки:
    # выбрать нажатием быстрее, чем набирать название, а у бота одна
    # переписка — путаницы, к какому вопросу кнопки, быть не может.
    if 'reply_markup' not in kw and (DRAFT.get(ALLOWED) or {}).get('need') == 'category':
        kw['reply_markup'] = cat_keyboard()
    # Пока операция ждёт «да», рядом висит кнопка сменить кошелёк: человек
    # видит, откуда спишется, и может поправить одним нажатием, не набирая
    # ничего. Спрашивать кошелёк у каждой траты нельзя — это лишний шаг
    # там, где вся ценность в одной фразе.
    elif 'reply_markup' not in kw and PENDING.get(ALLOWED):
        kw['reply_markup'] = CHANGE_WALLET
    tg('sendMessage', chat_id=ALLOWED, text=text, parse_mode='HTML',
       disable_web_page_preview=True, **kw)


def typing():
    tg('sendChatAction', chat_id=ALLOWED, action='typing')

def _budget_append(tab, row):
    # USER_ENTERED — дата (ISO) становится настоящей датой, суммы числами; месяца-колонки больше нет
    r = SHEETS.post(f'https://sheets.googleapis.com/v4/spreadsheets/{BUDGET_SS}/values/{tab}:append'
        '?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS', json={'values':[row]}, timeout=30)
    r.raise_for_status()
    # держим журнал отсортированным по дате, а не по порядку ввода (Loans — только A:E, сводку G:H не трогаем)
    gid={'Operations':0,'Loans':215071340}.get(tab.split('!')[0])
    if gid is not None:
        SHEETS.post(f'https://sheets.googleapis.com/v4/spreadsheets/{BUDGET_SS}:batchUpdate',
            json={'requests':[{'sortRange':{'range':{'sheetId':gid,'startRowIndex':1,'startColumnIndex':0,'endColumnIndex':8},
                'sortSpecs':[{'dimensionIndex':0,'sortOrder':'ASCENDING'}]}}]}, timeout=30).raise_for_status()
_cap = lambda x: (x[:1].upper()+x[1:]) if x else x
def _money(n):
    """Сумма для показа: целые — без дробей, дробные — как есть (не округляем, чтобы не врать)."""
    v=float(n)
    return f'{int(v):,}'.replace(',',' ') if v.is_integer() else f'{v:,.2f}'.replace(',',' ')
def _resolve_date(date_str):
    """Дата операции: переданная YYYY-MM-DD или сегодня. Возвращает (дата, месяц)."""
    d = None
    if date_str:
        try: d = datetime.date.fromisoformat(str(date_str)[:10])
        except Exception: d = None
    d = d or today_local()
    return str(d), d.strftime('%Y-%m')
# ── Быстрый ввод: «Категория Сумма [Дата] [Комментарий]» — без догадок модели ──
def _quick_map():
    m={}
    def add(name, kind, canon):
        m[name.lower().replace('ё','е')] = (kind, canon)
    for c in BUDGET_CATS: add(c,'расход',c)
    for c in INCOME_CATS: add(c,'доход',c)
    add('Кредит','доход','Кредит')
    for c in SAVINGS_CATS: add(c,'накопление',c)
    add('Оплата кредита','погашение','Оплата кредита')
    # синонимы/сокращения
    for alias,(k,c) in {
      'зп':('доход','Зарплата'),'зарплата':('доход','Зарплата'),
      'подушка':('накопление','Накопления / Подушка'),'накопления':('накопление','Накопления / Подушка'),
      'инвестиции':('накопление','Инвестиции'),'крипта':('накопление','Инвестиции'),
      'погашение':('погашение','Оплата кредита'),'погашение кредита':('погашение','Оплата кредита'),
      'лечение':('расход','Лечение / Медикаменты'),'медикаменты':('расход','Лечение / Медикаменты'),
      'аптека':('расход','Лечение / Медикаменты'),'врач':('расход','Лечение / Медикаменты'),
      'зал':('расход','Абонемент в зал'),'абонемент':('расход','Абонемент в зал'),'фитнес':('расход','Абонемент в зал'),
      'спортпит':('расход','Спортивное питание'),'протеин':('расход','Спортивное питание'),
      'массаж':('расход','Массаж / Сауна'),'сауна':('расход','Массаж / Сауна'),'баня':('расход','Массаж / Сауна'),
      'бады':('расход','БАДы'),'витамины':('расход','БАДы'),
      'одежда':('расход','Одежда/Обувь'),'обувь':('расход','Одежда/Обувь'),
      'сигареты':('расход','Курение'),'стики':('расход','Курение'),
      'бензин':('расход','Машина'),'авто':('расход','Машина'),
      'продукты':('расход','Продукты'),'базар':('расход','Продукты'),
      'аренда':('расход','Дом'),'коммуналка':('расход','Дом'),
      'такси':('расход','Прочее'),
      'парковка':('расход','Машина'),'оплата парковка':('расход','Машина'),
      'вода':('расход','Продукты'),'вода с магазина':('расход','Продукты'),
      'еда':('расход','Продукты'),'еда с магазина':('расход','Продукты'),
      'стройматериал':('расход','Дом'),'стройматериалы':('расход','Дом'),
      'помощь брату':('расход','Семья'),'помощь родителям':('расход','Семья'),
      'подарок':('расход','Подарки'),'цветы':('расход','Подарки'),
      'кофе':('расход','Кафе'),'ресторан':('расход','Кафе'),'обед':('расход','Кафе'),
      'интернет':('расход','Связь'),'телефон':('расход','Связь'),
      'баланс телефона':('расход','Связь'),'мобильная связь':('расход','Связь'),
      'стрижка':('расход','Уход за собой'),'барбер':('расход','Уход за собой'),
      'парикмахер':('расход','Уход за собой'),'уход':('расход','Уход за собой'),
      'свидание':('расход','Свидания'),'девушка':('расход','Свидания'),
      'вечер с девушкой':('расход','Свидания'),
      'мойка':('расход','Машина'),'ремонт авто':('расход','Машина'),
      # сервисы и подписки — на них ломался ввод «Сервер railway 46,35»
      'сервер':('расход','Подписки'),'хостинг':('расход','Подписки'),
      'railway':('расход','Подписки'),'домен':('расход','Подписки'),
      'подписка':('расход','Подписки'),'оплата подписки':('расход','Подписки'),
      'claude':('расход','Подписки'),'icloud':('расход','Подписки'),
      'telegram':('расход','Подписки'),'google':('расход','Подписки'),
      'чатгпт':('расход','Подписки'),'нейросеть':('расход','Подписки'),
      # прочие частые
      'вода и стики':('расход','Продукты'),
      'проезд':('расход','Прочее'),'маршрутка':('расход','Прочее'),
      'штраф':('расход','Прочее'),'комиссия':('расход','Прочее'),
      'стоматолог':('расход','Лечение / Медикаменты'),
      'зубной':('расход','Лечение / Медикаменты'),'зубы':('расход','Лечение / Медикаменты'),
      'лор':('расход','Лечение / Медикаменты'),'анализы':('расход','Лечение / Медикаменты'),
      'книга':('расход','Обучение'),'курс':('расход','Обучение'),
      'кино':('расход','Развлечение'),'игра':('расход','Развлечение'),
      'жена':('расход','Семья'),'дети':('расход','Семья'),'мама':('расход','Семья'),
      'отец':('расход','Семья'),'родители':('расход','Семья'),
      'билет':('расход','Путешествие'),'отель':('расход','Путешествие'),
    }.items(): add(alias,k,c)
    return m
QUICK_CATS=_quick_map()

CURRENCY = {'см','сом','сомони','смн','tjs','с','c'}
# Слова, после которых строка — не трата, а вопрос или задача
NOT_SPEND = ('напомн','покаж','скольк','выручк','задач','отчет','сделай','добав',
             'проверь','посчитай','что ','когда','почему','сводк','остаток')
# Полная дата где угодно в остатке строки: «Такси 11 - 23.08.2026»,
# «Машины - 24.08.2026». До 04.09.2026 дата искалась только в самом начале
# остатка, и тире перед ней всё ломало: 21 трата задним числом легла
# сегодняшним днём, а настоящая дата осталась в комментарии.
# Короткую форму «20.08» здесь не ищем — иначе «2.5 кг» станет 2 мая.
DATE_ANY = re.compile(r'(?<!\d)(\d{4}-\d{2}-\d{2}|\d{1,2}[./,]\d{1,2}[./,]\d{2,4})(?!\d)')


UNITS = {'кг', 'г', 'гр', 'л', 'мл', 'шт', 'км', 'м', 'м2', '%'}


def _pull_date(rest):
    """Вынуть полную дату из строки. → (ISO или None, остаток)."""
    m = DATE_ANY.search(rest or '')
    if not m:
        return None, rest
    s = m.group(1)
    try:
        if '-' in s:
            iso = str(datetime.date.fromisoformat(s))
        else:
            dd, mm, yy = re.split(r'[./,]', s)
            year = int(yy) + 2000 if len(yy) == 2 else int(yy)
            iso = str(datetime.date(year, int(mm), int(dd)))
    except ValueError:
        return None, rest
    left = (rest[:m.start()] + ' ' + rest[m.end():]).strip()
    return iso, re.sub(r'\s+', ' ', left).strip(' ,;:-–—.')


def _strip_currency(s):
    """Убирает хвост-валюту: «вода см» → «вода», «см» → «»."""
    w = [x for x in str(s).split() if x.lower().replace('ё','е').strip('.,;:') not in CURRENCY]
    return ' '.join(w).strip(' ,;:-.')

def _parse_quick(text):
    """«Курение 20 20.08.2026 Стики» → (kind, категория, сумма, ISO-дата, комментарий) или None."""
    t=' '.join(str(text).strip().split())
    if not t or '\n' in str(text).strip(): return None
    low=t.lower().replace('ё','е')
    # самое длинное совпадение имени категории в начале строки
    best=None
    for name in QUICK_CATS:
        if low.startswith(name) and (len(low)==len(name) or not low[len(name)].isalpha()):
            if best is None or len(name)>len(best): best=name
    if not best: return None
    kind,cat=QUICK_CATS[best]
    rest=t[len(best):].strip(' ,;:-')
    # сумма — первое число в остатке (не обязательно сразу после категории)
    m=re.search(r'(\d+(?:[.,]\d+)?)', rest)
    if not m: return None
    before=rest[:m.start()].strip(' ,;:-')      # текст между категорией и суммой → в комментарий
    amount=float(m.group(1).replace(',','.'))
    rest=rest[m.end():].strip()
    # дата: полная — где угодно в остатке; короткая «20.08» — только в начале
    iso, rest = _pull_date(rest)
    if not iso:
        dm=re.match(r'^(\d{1,2})[./,](\d{1,2})\b\s*(.*)$', rest, re.S)
        # «2.5 кг» — это вес, а не 2 мая: за единицей измерения даты не бывает
        if dm and dm.group(3).split()[:1] and dm.group(3).split()[0].lower() in UNITS:
            dm=None
        if dm:
            dd,mm=int(dm.group(1)),int(dm.group(2))
            try:
                iso=str(datetime.date(today_local().year,mm,dd)); rest=dm.group(3).strip()
            except ValueError: return None
    # комментарий: текст до суммы + хвост после даты, без мусора
    com=" ".join(x for x in (before, rest) if x).strip(' ,;:-.')
    com=re.sub(r'^\W+|\W+$', '', _strip_currency(com))
    return kind,cat,amount,iso,com,False

def _parse_quick_loose(text):
    """Строка вида «Доставка торта 40 см» — категории такой нет, но это явно трата.
    Не выбрасываем: пишем в «Прочее», текст — в комментарий, и помечаем флагом,
    чтобы в подтверждении было видно, что категорию я не распознал.
    Работает ТОЛЬКО внутри пачки — одиночное сообщение уходит модели, она умнее."""
    t=' '.join(str(text).strip().split())
    if not t or len(t)>70 or '?' in t: return None
    m=re.search(r'(\d+(?:[.,]\d+)?)', t)
    if not m: return None
    before=t[:m.start()].strip(' ,;:-')
    if not before or not (1 <= len(before.split()) <= 5): return None
    if not re.fullmatch(r'[^\d]+', before): return None
    amount=float(m.group(1).replace(',','.'))
    rest=t[m.end():].strip()
    iso, rest = _pull_date(rest)
    if not iso:
        dm=re.match(r'^(\d{1,2})[./,](\d{1,2})\b\s*(.*)$', rest, re.S)
        # «2.5 кг» — это вес, а не 2 мая: за единицей измерения даты не бывает
        if dm and dm.group(3).split()[:1] and dm.group(3).split()[0].lower() in UNITS:
            dm=None
        if dm:
            dd,mm=int(dm.group(1)),int(dm.group(2))
            try: iso=str(datetime.date(today_local().year,mm,dd)); rest=dm.group(3).strip()
            except ValueError: return None
    # после суммы и даты не должно остаться НИЧЕГО, кроме валюты:
    # «Напомни завтра в 10 позвонить в банк» — это не трата, а задача
    if _strip_currency(rest): return None
    com=re.sub(r'^\W+|\W+$', '', _strip_currency(before))
    if not com: return None
    if any(w in com.lower().replace('ё','е') for w in NOT_SPEND): return None
    return 'расход','Прочее',amount,iso,com,True

def _amount_first(text):
    """«250 помощь брату» → «помощь брату 250».

    Люди пишут сумму то впереди, то в конце. Раньше строка с суммой впереди
    не разбиралась и уходила в модель — а если модель недоступна, запись
    просто терялась. Переставляем и отдаём обычным разборщикам.
    """
    t = ' '.join(str(text).strip().split())
    m = re.match(r'^(\d+(?:[.,]\d+)?)\s+(\D.*)$', t)
    if not m:
        return None
    return f'{m.group(2).strip()} {m.group(1)}'


def _parse_quick_lines(text):
    """Многострочный быстрый ввод: разбирает КАЖДУЮ строку отдельно.
    Возвращает (список разобранных операций, список неразобранных строк).
    Нужно, чтобы пачка операций задним числом не терялась в модели."""
    lines = [l.strip() for l in str(text).splitlines() if l.strip()]
    if len(lines) < 2:
        return [], []
    ok, bad = [], []
    for ln in lines:
        q = _parse_quick(ln) or _parse_quick_loose(ln)
        if not q:
            swapped = _amount_first(ln)          # «250 помощь брату»
            if swapped:
                q = _parse_quick(swapped) or _parse_quick_loose(swapped)
        if q:
            ok.append(q)
        else:
            bad.append(ln)
    # считаем пачкой, только если разобралось большинство строк
    if len(ok) < 2 or len(ok) < len(lines) * 0.5:
        return [], []
    return ok, bad


# ── Лимиты по категориям ─────────────────────────────────────────────────────
# Лист «Лимиты»: Категория · Лимит в месяц · Активен.
# Заполняется руками — это решение Азиза, а не расчёт системы.
LIMITS_TAB = 'Лимиты'
LIMIT_COLS = ['Категория', 'Лимит в месяц', 'Активен']
_LIM = {'ts': None, 'map': {}}


def _rows(rng):
    """Строки диапазона. Пусто при сбое — читатель решает, что с этим делать."""
    try:
        r = SHEETS.get(API + BUDGET_SS + '/values/' + _q(rng), timeout=30)
        return r.json().get('values', []) if r.ok else []
    except Exception as e:
        log.warning('чтение %s: %s', rng, e)
        return []


# ── привычки: один тап вместо силы воли ──────────────────────────────────────
# Решено 11.09.2026. Задача не в мотивации, а в трении: у работы короткая
# петля обратной связи, у зала — длинная, и на этом фоне она всегда
# проигрывает. Поэтому здесь нет ни очков, ни уровней, ни персонажа:
# очки вытесняют интерес, а приложение, в которое надо заходить, требует
# ровно той воли, от которой мы уходим.
#
# Работают три вещи: вопрос приходит сам, ответ занимает один тап,
# и пропуск спрашивает «почему» вместо того, чтобы молча минусовать.
HABIT_TAB = 'Привычки'
HABIT_COLS = ['Дата', 'Направление', 'Ответ', 'Причина', 'Время ответа']
HABIT_CFG_TAB = 'Настройки привычек'
HABIT_CFG_COLS = ['Направление', 'Дни', 'Время', 'План в неделю', 'Активно']

# Причины пропуска. Список короткий намеренно: длинный превращает ответ
# в выбор, а выбор — это уже усилие.
SKIP_WHY = ['работа', 'самочувствие', 'не захотел', 'обстоятельства']
WEEK_RU = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']


def ensure_habit_tabs():
    """Листы привычек. Идемпотентно, как и «Лимиты»."""
    meta = SHEETS.get(API + BUDGET_SS, params={'fields': 'sheets.properties'},
                      timeout=30).json()
    have = {sh['properties']['title'] for sh in meta.get('sheets', [])}
    add = []
    if HABIT_TAB not in have:
        add.append((HABIT_TAB, HABIT_COLS, 500))
    if HABIT_CFG_TAB not in have:
        add.append((HABIT_CFG_TAB, HABIT_CFG_COLS, 20))
    for title, cols, rows in add:
        SHEETS.post(API + BUDGET_SS + ':batchUpdate', json={'requests': [
            {'addSheet': {'properties': {'title': title, 'gridProperties': {
                'rowCount': rows, 'columnCount': len(cols),
                'frozenRowCount': 1}}}}]}, timeout=30).raise_for_status()
        SHEETS.put(API + BUDGET_SS + '/values/' + _q(f'{title}!A1'),
                   params={'valueInputOption': 'USER_ENTERED'},
                   json={'values': [cols]}, timeout=30).raise_for_status()
        log.info('создан лист «%s»', title)
    if HABIT_CFG_TAB not in have:
        # Умолчание — из индекса Здоровья: зал четыре раза в неделю.
        SHEETS.post(API + BUDGET_SS + '/values/' + _q(f'{HABIT_CFG_TAB}!A1')
                    + ':append', params={'valueInputOption': 'USER_ENTERED',
                                         'insertDataOption': 'INSERT_ROWS'},
                    json={'values': [['Зал', 'пн,вт,чт,пт', '19:00', 4, 'да']]},
                    timeout=30).raise_for_status()


def habit_cfg():
    """[{направление, дни, время, план, активно}] из таблицы."""
    out = []
    for r in (_rows(f'{HABIT_CFG_TAB}!A2:E20') or []):
        r = list(r) + [''] * 5
        if not str(r[0]).strip():
            continue
        days = [d.strip().lower() for d in str(r[1]).split(',') if d.strip()]
        out.append({'name': str(r[0]).strip(), 'days': days,
                    'at': str(r[2]).strip() or '19:00',
                    'plan': int(float(str(r[3]).replace(',', '.') or 0) or 0),
                    'on': str(r[4]).strip().lower() in ('да', 'yes', '1', 'true')})
    return out


def habit_rows(name=None, days_back=60):
    """Ответы за последние дни. [(дата, направление, ответ, причина)]"""
    since = today_local() - datetime.timedelta(days=days_back)
    out = []
    for r in (_rows(f'{HABIT_TAB}!A2:E600') or []):
        r = list(r) + [''] * 5
        d = _row_date(r[0])
        if not d or d < since:
            continue
        if name and str(r[1]).strip().lower() != name.lower():
            continue
        out.append((d, str(r[1]).strip(), str(r[2]).strip(), str(r[3]).strip()))
    return out


def habit_asked_today(name):
    """Уже спрашивали сегодня? Проверяем по факту записи, а не по памяти:
    Railway перезапускает контейнер на каждой выкатке, и память обнуляется —
    на этом мы уже теряли резервные копии восемнадцать дней."""
    today = today_local()
    return any(d == today for d, n, _a, _w in habit_rows(name, days_back=3))


def habit_write(name, answer, why=''):
    _budget_append(f'{HABIT_TAB}!A1',
                   [today_local().isoformat(), name, answer, why,
                    now_local().strftime('%H:%M')])


def habit_set_why(name, why):
    """Дописать причину в сегодняшнюю строку."""
    vals = _rows(f'{HABIT_TAB}!A2:E600') or []
    today = today_local()
    for i, r in enumerate(vals, start=2):
        r = list(r) + [''] * 5
        if _row_date(r[0]) == today and str(r[1]).strip().lower() == name.lower():
            SHEETS.put(API + BUDGET_SS + '/values/' + _q(f'{HABIT_TAB}!D{i}'),
                       params={'valueInputOption': 'USER_ENTERED'},
                       json={'values': [[why]]}, timeout=30).raise_for_status()
            return True
    return False


def habit_streak(name, plan=4):
    """Строка обратной связи: сколько на этой неделе и сколько дней подряд.

    Единственная «геймификация», которая здесь нужна. Считаем выполнение,
    а не результат: результат у зала приходит через месяцы, а выполнение —
    сегодня, и именно оно держит регулярность.
    """
    rows = habit_rows(name, days_back=120)
    done = {d for d, _n, a, _w in rows if a == 'был'}
    today = today_local()
    week_start = today - datetime.timedelta(days=today.weekday())
    this_week = sum(1 for d in done if d >= week_start)
    # Серия — по дням, когда вопрос задавался: пропуск в нерабочий день
    # цепочку не рвёт, иначе она не значила бы ничего.
    asked = sorted({d for d, _n, a, _w in rows if a in ('был', 'не был')},
                   reverse=True)
    streak = 0
    for d in asked:
        ans = next((a for dd, _n, a, _w in rows if dd == d), '')
        if ans != 'был':
            break
        streak += 1
    part = f'{this_week} из {plan} на этой неделе'
    return part + (f' · подряд {streak}' if streak > 1 else '')


def habit_tick():
    """Раз в минуту: пора ли спрашивать. Вызывается фоновым потоком."""
    now = now_local()
    dow = WEEK_RU[now.weekday()]
    for c in habit_cfg():
        if not c['on'] or dow not in c['days']:
            continue
        if now.strftime('%H:%M') < c['at']:
            continue
        if habit_asked_today(c['name']):
            continue
        send(f'🏋️ <b>{c["name"]}</b> сегодня?',
             reply_markup={'inline_keyboard': [[
                 {'text': '✅ был', 'callback_data': f'h:1:{c["name"]}'},
                 {'text': '➖ не был', 'callback_data': f'h:0:{c["name"]}'}]]})
        # Строку пишем сразу пустым ответом: она же и есть защита от того,
        # что вопрос придёт второй раз после перезапуска.
        habit_write(c['name'], 'спросили')


def habit_answer(data):
    """Нажата кнопка привычки: h:1:Зал, h:0:Зал или hw:Зал:работа."""
    parts = data.split(':', 2)
    if data.startswith('hw:'):
        _, name, why = parts
        habit_set_why(name, why)
        cfg = next((c for c in habit_cfg() if c['name'] == name), {})
        send(f'Записал: {why}. {habit_streak(name, cfg.get("plan", 4))}\n\n'
             f'Причины копятся — через месяц станет видно, что мешает '
             f'на самом деле.')
        return
    _, flag, name = parts
    cfg = next((c for c in habit_cfg() if c['name'] == name), {})
    if flag == '1':
        habit_set_answer(name, 'был')
        send(f'✅ Отметил. {habit_streak(name, cfg.get("plan", 4))}')
        return
    habit_set_answer(name, 'не был')
    # Пропуск не наказываем: вместо минуса спрашиваем причину. Через месяц
    # это даёт данные о том, что мешает, а не чувство вины.
    send('Понял. А что помешало?',
         reply_markup={'inline_keyboard': [
             [{'text': w, 'callback_data': f'hw:{name}:{w}'}]
             for w in SKIP_WHY]})


def habit_set_answer(name, answer):
    """Проставить ответ в сегодняшнюю строку (её создал habit_tick)."""
    vals = _rows(f'{HABIT_TAB}!A2:E600') or []
    today = today_local()
    for i, r in enumerate(vals, start=2):
        r = list(r) + [''] * 5
        if _row_date(r[0]) == today and str(r[1]).strip().lower() == name.lower():
            SHEETS.put(API + BUDGET_SS + '/values/' + _q(f'{HABIT_TAB}!C{i}:E{i}'),
                       params={'valueInputOption': 'USER_ENTERED'},
                       json={'values': [[answer, r[3],
                                         now_local().strftime('%H:%M')]]},
                       timeout=30).raise_for_status()
            return True
    habit_write(name, answer)
    return True


def habit_status():
    """Что с привычкой: расписание, выполнение, причины пропусков."""
    out = []
    for c in habit_cfg():
        rows = habit_rows(c['name'], days_back=30)
        was = sum(1 for _d, _n, a, _w in rows if a == 'был')
        skip = [w for _d, _n, a, w in rows if a == 'не был' and w]
        out.append(f'🏋️ <b>{c["name"]}</b> · {", ".join(c["days"])} в {c["at"]}'
                   + ('' if c['on'] else ' · выключено'))
        out.append(f'{habit_streak(c["name"], c["plan"])}')
        out.append(f'За 30 дней: был {was} раз, пропусков {len(skip)}')
        if skip:
            top = collections.Counter(skip).most_common(3)
            out.append('Причины: ' + ', '.join(f'{w} — {n}' for w, n in top))
        out.append('')
    if not out:
        return 'Привычки не настроены.'
    out.append('<i>Расписание и план правятся в листе «Настройки привычек» '
               'таблицы бюджета — дни, время, сколько раз в неделю.</i>')
    return '\n'.join(out)


def quick_keyboard():
    """Кнопки частых трат — из собственной истории, а не из головы.

    Берём пары «категория + сумма», которые повторялись, и самые частые
    категории. Смысл тот же, что у привычек: убрать трение. Запись
    в один тап не даёт бросить на полпути и не зависит от того,
    разберёт ли бот текст.
    """
    rows = _rows('Operations!A2:H2000') or []
    pairs, cats = collections.Counter(), collections.Counter()
    for r in rows:
        r = list(r) + [''] * 5
        if str(r[1]).strip().lower() != 'расход':
            continue
        cat = str(r[2]).strip()
        try:
            amt = float(str(r[3]).replace(',', '.').replace(' ', ''))
        except ValueError:
            continue
        if not cat or amt <= 0:
            continue
        cats[cat] += 1
        if amt == int(amt):
            pairs[(cat, int(amt))] += 1
    top = [p for p, n in pairs.most_common(8) if n >= 2]
    buttons = [{'text': f'{c} · {a}', 'callback_data': f'q:{c}:{a}'}
               for c, a in top]
    # Плюс частые категории без суммы: нажал — бот спросит только сколько.
    for c, _n in cats.most_common(4):
        if not any(b['callback_data'].startswith(f'q:{c}:') for b in buttons):
            buttons.append({'text': f'{c} · ?', 'callback_data': f'q:{c}:0'})
    if not buttons:
        # Журнал очищен 04.09.2026, истории ещё нет. Стартовый набор —
        # бытовые категории; сумму бот спросит одним вопросом. Как только
        # записи накопятся, набор заменится настоящими частыми тратами.
        buttons = [{'text': f'{c} · ?', 'callback_data': f'q:{c}:0'}
                   for c in ('Кафе', 'Продукты', 'Связь', 'Уход за собой',
                             'Развлечение', 'Прочее')]
    rows_kb, row = [], []
    for b in buttons:
        row.append(b)
        if len(row) == 2:
            rows_kb.append(row)
            row = []
    if row:
        rows_kb.append(row)
    return {'inline_keyboard': rows_kb}


def quick_answer(data):
    """Нажата кнопка частой траты: q:Кафе:35 или q:Кафе:0 (спросить сумму)."""
    try:
        _, cat, amt = data.split(':', 2)
        amt = float(amt)
    except ValueError:
        return
    if amt <= 0:
        send(draft_start('', category=cat))
        return
    # Быстрая кнопка — это и есть «один тап»: спрашивать кошелёк здесь
    # нечего, берём тот, с которого платим чаще всего.
    try:
        w = default_wallet()
    except Exception as e:
        log.warning('кошелёк по умолчанию: %s', e)
        w = ''
    add_entry(amt, category=cat, kind='расход', comment=cat, wallet=w)
    send(f'✅ {cat} · {_money(amt)}' + (f' · {w}' if w else '')
         + f'\n{left_line(cat)}')


def habit_loop():
    while True:
        try:
            habit_tick()
        except Exception as e:
            log.warning('привычки: %s', e)
        time.sleep(60)


# ── кошельки ────────────────────────────────────────────────────────────────
# Заведено 14.09.2026. До этого журнал не помнил, откуда ушли деньги, и лист
# «Счета» приходилось заполнять руками: система не знала, что списалось
# с карты, а что из наличных. Теперь у каждой операции есть кошелёк, и
# остаток по каждому считается сам.
#
# Перевод между своими кошельками — не расход: снял с карты наличными, деньги
# те же. Поэтому у него свой тип и вторая колонка «Куда».
WALLET_TAB = 'Кошельки'
WALLET_COLS = ['Кошелёк', 'Стартовый остаток', 'Активен', 'По умолчанию',
               'Накопительный']
SAVE_NAME = 'Накопления'
WALLETS_DEFAULT = ['Наличные', 'Алиф кошелёк', 'Алиф Visa',
                   'Алиф Master Card', 'ДС кошелёк',
                   'Эсхата кошелёк', 'Эсхата Visa', SAVE_NAME]
_WAL = {'ts': None, 'list': []}


def ensure_wallet_tab():
    """Лист «Кошельки». Идемпотентно, как «Лимиты»."""
    meta = SHEETS.get(API + BUDGET_SS, params={'fields': 'sheets.properties'},
                      timeout=30).json()
    have = {sh['properties']['title'] for sh in meta.get('sheets', [])}
    if WALLET_TAB in have:
        return
    SHEETS.post(API + BUDGET_SS + ':batchUpdate', json={'requests': [
        {'addSheet': {'properties': {'title': WALLET_TAB, 'gridProperties': {
            'rowCount': 30, 'columnCount': 3, 'frozenRowCount': 1}}}}]},
        timeout=30).raise_for_status()
    rows = [WALLET_COLS] + [[w, '', 'да', 'да' if i == 0 else '',
                             'да' if w == SAVE_NAME else '']
                            for i, w in enumerate(WALLETS_DEFAULT)]
    SHEETS.put(API + BUDGET_SS + '/values/' + _q(f'{WALLET_TAB}!A1'),
               params={'valueInputOption': 'USER_ENTERED'},
               json={'values': rows}, timeout=30).raise_for_status()
    log.info('создан лист «%s»', WALLET_TAB)


def wallets(force=False):
    """[(кошелёк, стартовый остаток)] — активные, в порядке листа."""
    now = datetime.datetime.utcnow()
    if not force and _WAL['ts'] and (now - _WAL['ts']).seconds < 300:
        return _WAL['list']
    out, default, save = [], '', ''
    try:
        for row in (_rows(f'{WALLET_TAB}!A2:E30') or []):
            row = list(row) + [''] * 5
            name = str(row[0]).strip()
            act = str(row[2]).strip().lower() or 'да'
            if not name or act not in ('да', 'yes', '1', 'true'):
                continue
            try:
                start = float(str(row[1]).replace(' ', '').replace(',', '.'))
            except ValueError:
                start = 0.0
            if str(row[3]).strip().lower() in ('да', 'yes', '1', 'true') and not default:
                default = name
            if str(row[4]).strip().lower() in ('да', 'yes', '1', 'true') and not save:
                save = name
            out.append((name, start))
    except Exception as e:
        log.warning('кошельки: %s', e)
    _WAL['ts'], _WAL['list'] = now, out
    _WAL['default'] = default or (out[0][0] if out else '')
    # Накопительный кошелёк один. Если в таблице не помечен — ищем по имени,
    # чтобы механика работала и до того, как Азиз дойдёт до настроек.
    _WAL['save'] = save or (SAVE_NAME if any(n == SAVE_NAME for n, _ in out) else '')
    return out


def save_wallet():
    """Накопительный кошелёк. Пусто — накоплений ещё нет.

    Зачем отдельно: крупная редкая трата (зубы, спортпит на год) идёт
    из накопленного и в месячный лимит категории входить не должна.
    Иначе лечение на 5 570 даст чудовищный перебор по категории,
    и план месяца развалится, хотя человек сделал всё правильно.
    Признак несёт сам кошелёк — отдельного поля у операции не нужно.
    """
    wallets()
    return _WAL.get('save', '')


def default_wallet():
    """Кошелёк, с которого платим чаще всего.

    Нужен переписке: спрашивать «с какого кошелька?» на каждую трату
    значит убить то, ради чего бот и существует — одну фразу и «да».
    Подставляем умолчание, показываем его в подтверждении и даём кнопку
    сменить. Ошибиться не страшно: запись правится с экрана.
    """
    wallets()
    return _WAL.get('default', '')


def set_default_wallet(name):
    """Запомнить кошелёк как основной — колонка «По умолчанию»."""
    rows = _rows(f'{WALLET_TAB}!A2:D30') or []
    data = []
    for i, row in enumerate(rows):
        row = list(row) + [''] * 4
        if not str(row[0]).strip():
            continue
        want = 'да' if str(row[0]).strip() == name else ''
        if str(row[3]).strip().lower() != want:
            data.append({'range': f'{WALLET_TAB}!D{i + 2}', 'values': [[want]]})
    if data:
        SHEETS.post(API + BUDGET_SS + '/values:batchUpdate',
                    json={'valueInputOption': 'USER_ENTERED', 'data': data},
                    timeout=30).raise_for_status()
    _WAL['ts'] = None
    return name


# Как тип операции двигает деньги в кошельке, из которого она сделана.
WALLET_SIGN = {'Доход': 1, 'Расход': -1, 'Накопление': -1, 'Погашение': -1,
               'Перевод': -1}


def wallet_balances():
    """{кошелёк: остаток}. Стартовый остаток плюс всё движение по журналу."""
    bal = {name: start for name, start in wallets()}
    unknown = 0.0
    for row in (_rows('Operations!A2:H2000') or []):
        row = list(row) + [''] * 7
        try:
            amount = float(str(row[3]).replace(',', '.'))
        except (ValueError, TypeError):
            continue
        typ, src, dst = str(row[1]).strip(), str(row[5]).strip(), str(row[6]).strip()
        if src in bal:
            bal[src] += WALLET_SIGN.get(typ, -1) * amount
        elif not src:
            # Записи из переписки кошелька не знают. Не раскидываем их
            # по догадке: пусть видно, сколько денег «ничьих».
            unknown += WALLET_SIGN.get(typ, -1) * amount
        if typ == 'Перевод' and dst in bal:
            bal[dst] += amount
    return bal, unknown


# ── долги ───────────────────────────────────────────────────────────────────
# Долг 11 748 (Эсхата + рассрочки Alif) до 14.09.2026 жил только в таблице,
# и вопрос «заплатил ли я в этом месяце» решался по памяти — то есть
# не решался. Платёж — обычная операция типа «Погашение»; чтобы её можно
# было отнести к конкретному долгу, у журнала появилась колонка «Долг».
# Сопоставление точное, по имени: угадывать по комментарию значит
# однажды зачесть платёж не туда.
DEBT_TAB = 'Долги'
DEBT_COLS = ['Долг', 'Кому', 'Остаток', 'Платёж в месяц', 'День платежа',
             'Ставка, %', 'Активен']
_DEBT = {'ts': None, 'list': []}


def ensure_debt_tab():
    """Лист «Долги». Идемпотентно."""
    meta = SHEETS.get(API + BUDGET_SS, params={'fields': 'sheets.properties'},
                      timeout=30).json()
    have = {sh['properties']['title'] for sh in meta.get('sheets', [])}
    if DEBT_TAB in have:
        return
    SHEETS.post(API + BUDGET_SS + ':batchUpdate', json={'requests': [
        {'addSheet': {'properties': {'title': DEBT_TAB, 'gridProperties': {
            'rowCount': 30, 'columnCount': len(DEBT_COLS),
            'frozenRowCount': 1}}}}]}, timeout=30).raise_for_status()
    SHEETS.put(API + BUDGET_SS + '/values/' + _q(f'{DEBT_TAB}!A1'),
               params={'valueInputOption': 'USER_ENTERED'},
               json={'values': [DEBT_COLS]}, timeout=30).raise_for_status()
    log.info('создан лист «%s»', DEBT_TAB)


def _num(x, default=0.0):
    try:
        return float(str(x).replace(' ', '').replace(',', '.'))
    except (ValueError, TypeError):
        return default


def debts(force=False):
    """[{долг, кому, остаток, платёж, день, ставка}] — активные."""
    now = datetime.datetime.utcnow()
    if not force and _DEBT['ts'] and (now - _DEBT['ts']).seconds < 300:
        return _DEBT['list']
    out = []
    try:
        for row in (_rows(f'{DEBT_TAB}!A2:G30') or []):
            row = list(row) + [''] * 7
            name = str(row[0]).strip()
            act = str(row[6]).strip().lower() or 'да'
            if not name or act not in ('да', 'yes', '1', 'true'):
                continue
            out.append({'name': name, 'to': str(row[1]).strip(),
                        'left': _num(row[2]), 'pay': _num(row[3]),
                        'day': int(_num(row[4])), 'rate': _num(row[5])})
    except Exception as e:
        log.warning('долги: %s', e)
    _DEBT['ts'], _DEBT['list'] = now, out
    return out


def debt_paid(name, ym=None):
    """Сколько заплачено по этому долгу за месяц."""
    ym = ym or now_local().strftime('%Y-%m')
    total = 0.0
    for row in (_rows('Operations!A2:H2000') or []):
        row = list(row) + [''] * 8
        if str(row[1]).strip() != 'Погашение' or str(row[7]).strip() != name:
            continue
        d = _row_date(row[0])
        if d and d.strftime('%Y-%m') == ym:
            total += _num(row[3])
    return total


def debt_state():
    """Долги с расчётом: заплачено за месяц и сколько месяцев до нуля."""
    out = []
    for d in debts():
        paid = debt_paid(d['name'])
        left = d['left'] - paid
        # Месяцев до нуля — по нынешнему платежу, без процентов: ставку
        # считать честно можно только зная порядок начислений банка,
        # а выдуманная точность здесь хуже её отсутствия.
        months = int(-(-left // d['pay'])) if d['pay'] > 0 and left > 0 else 0
        out.append(dict(d, paid=paid, left=round(left, 2), months=months,
                        done=paid >= d['pay'] > 0))
    return out


def pay_debt(name, amount, wallet='', comment=''):
    """Платёж по долгу. Обычное «Погашение», но с именем долга в колонке."""
    if name not in [d['name'] for d in debts(force=True)]:
        return f'⚠️ Нет такого долга: {name}'
    d, _m = _resolve_date(None)
    com = _cap((comment or '').strip()) or name
    _budget_append('Operations!A:H',
                   [d, 'Погашение', 'Оплата кредита', float(amount), com,
                    str(wallet or '').strip(), '', name])
    LAST['data'] = [d, 'Погашение', 'Оплата кредита', float(amount), com]
    st = next((x for x in debt_state() if x['name'] == name), None)
    line = f'🏦 Погашение: {_money(amount)} с · {name}'
    if st:
        line += f'\nОстаток {_money(st["left"])} с'
        if st['months']:
            line += f' · при таком платеже {st["months"]} мес. до нуля'
    return line


# ── дела ────────────────────────────────────────────────────────────────────
# Задачи до 14.09.2026 жили в markdown-заметках с тегами #p1 и #next.
# В кармане их не было, а галочка должна ставиться одним тапом — писать
# в git с телефона приложение не умеет. Решение Азиза: задачи переезжают
# в таблицу, заметки остаются для мыслей и разборов. Мост между ними
# не строим: две правды об одной задаче всегда расходятся.
TASK_TAB = 'Дела'
TASK_COLS = ['Создано', 'Текст', 'Область', 'Проект', 'Срок', 'Повтор',
             'Переносов', 'Главная', 'Сделано', 'Когда']


def ensure_task_tab():
    """Лист «Дела». Идемпотентно."""
    meta = SHEETS.get(API + BUDGET_SS, params={'fields': 'sheets.properties'},
                      timeout=30).json()
    have = {sh['properties']['title'] for sh in meta.get('sheets', [])}
    if TASK_TAB in have:
        return
    SHEETS.post(API + BUDGET_SS + ':batchUpdate', json={'requests': [
        {'addSheet': {'properties': {'title': TASK_TAB, 'gridProperties': {
            'rowCount': 500, 'columnCount': len(TASK_COLS),
            'frozenRowCount': 1}}}}]}, timeout=30).raise_for_status()
    SHEETS.put(API + BUDGET_SS + '/values/' + _q(f'{TASK_TAB}!A1'),
               params={'valueInputOption': 'USER_ENTERED'},
               json={'values': [TASK_COLS]}, timeout=30).raise_for_status()
    log.info('создан лист «%s»', TASK_TAB)


def tasks(done=False):
    """Дела с номерами строк. По умолчанию только открытые."""
    out = []
    for i, row in enumerate(_rows(f'{TASK_TAB}!A2:J500') or []):
        row = list(row) + [''] * 10
        text = str(row[1]).strip()
        if not text:
            continue
        is_done = str(row[8]).strip().lower() in ('да', 'yes', '1', 'true')
        if is_done != done:
            continue
        # Дату читаем через _row_date: Google хранит её числом, и без
        # разбора в списке появлялось «46280» вместо срока.
        due = _row_date(row[4]) if str(row[4]).strip() else None
        out.append({'line': i + 2, 'created': str(row[0]).strip(), 'text': text,
                    'area': str(row[2]).strip(), 'project': str(row[3]).strip(),
                    'due': str(due) if due else '', 'repeat': str(row[5]).strip(),
                    'moved': int(_num(row[6])),
                    'top': str(row[7]).strip().lower() in ('да', 'yes', '1', 'true'),
                    'done': is_done, 'when': str(row[9]).strip()})
    return out


def add_task(text, area='', project='', due='', repeat=''):
    """Захват одной строкой: написал — попало в список, разбор потом."""
    text = _cap(str(text).strip())[:200]
    if not text:
        return '⚠️ Пустая задача.'
    _budget_append(f'{TASK_TAB}!A1',
                   [str(today_local()), text, area, project, due, repeat,
                    0, '', '', ''])
    return f'✚ {text}' + (f' · до {due}' if due else '')


def _task_put(line, col, value):
    SHEETS.put(API + BUDGET_SS + '/values/' + _q(f'{TASK_TAB}!{col}{line}'),
               params={'valueInputOption': 'USER_ENTERED'},
               json={'values': [[value]]}, timeout=30).raise_for_status()


def close_task(line):
    """Галочка. Повторяющееся дело закрывается и заводится заново."""
    t = next((x for x in tasks() if x['line'] == line), None)
    if not t:
        return '⚠️ Нет такой задачи.'
    SHEETS.post(API + BUDGET_SS + '/values:batchUpdate',
                json={'valueInputOption': 'USER_ENTERED', 'data': [
                    {'range': f'{TASK_TAB}!I{line}', 'values': [['да']]},
                    {'range': f'{TASK_TAB}!J{line}',
                     'values': [[str(today_local())]]}]},
                timeout=30).raise_for_status()
    if t['repeat']:
        nxt = _next_due(t['due'], t['repeat'])
        add_task(t['text'], t['area'], t['project'], nxt, t['repeat'])
        return f'✓ {t["text"]} · следующее {nxt}'
    return f'✓ {t["text"]}'


def _next_due(due, repeat):
    """Следующий срок повторяющегося дела."""
    try:
        d = datetime.date.fromisoformat(due) if due else today_local()
    except ValueError:
        d = today_local()
    r = str(repeat).strip().lower()
    if r.startswith('нед'):
        d += datetime.timedelta(days=7)
    elif r.startswith('год'):
        d = d.replace(year=d.year + 1)
    else:                                   # месяц — по умолчанию
        m, y = d.month + 1, d.year
        if m > 12:
            m, y = 1, y + 1
        day = min(d.day, [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31,
                          31, 30, 31, 30, 31][m - 1])
        d = datetime.date(y, m, day)
    return str(d)


def move_task(line, days=1):
    """Перенос. Считаем переносы: третий — повод спросить, нужна ли задача.

    Из Bullet Journal: дело, которое переносишь третий раз, чаще всего
    делать не собираются. Честнее спросить, чем копить мёртвый список.
    """
    t = next((x for x in tasks() if x['line'] == line), None)
    if not t:
        return '⚠️ Нет такой задачи.', 0
    try:
        base = datetime.date.fromisoformat(t['due']) if t['due'] else today_local()
    except ValueError:
        base = today_local()
    new_due = max(base, today_local()) + datetime.timedelta(days=days)
    moved = t['moved'] + 1
    SHEETS.post(API + BUDGET_SS + '/values:batchUpdate',
                json={'valueInputOption': 'USER_ENTERED', 'data': [
                    {'range': f'{TASK_TAB}!E{line}', 'values': [[str(new_due)]]},
                    {'range': f'{TASK_TAB}!G{line}', 'values': [[moved]]}]},
                timeout=30).raise_for_status()
    return f'→ {t["text"]} · до {new_due}', moved


def set_top(lines):
    """Три главные на завтра. Выбираются вечером — утром только исполняются."""
    data = []
    for t in tasks():
        want = 'да' if t['line'] in lines else ''
        if ('да' if t['top'] else '') != want:
            data.append({'range': f'{TASK_TAB}!H{t["line"]}', 'values': [[want]]})
    if data:
        SHEETS.post(API + BUDGET_SS + '/values:batchUpdate',
                    json={'valueInputOption': 'USER_ENTERED', 'data': data},
                    timeout=30).raise_for_status()
    return len(lines)


def ensure_limits_tab():
    """Создаёт лист «Лимиты» со всеми категориями расходов. Идемпотентно."""
    meta = SHEETS.get(API + BUDGET_SS, params={'fields': 'sheets.properties'},
                      timeout=30).json()
    have = {sh['properties']['title'] for sh in meta.get('sheets', [])}
    if LIMITS_TAB not in have:
        SHEETS.post(API + BUDGET_SS + ':batchUpdate', json={'requests': [
            {'addSheet': {'properties': {'title': LIMITS_TAB, 'gridProperties': {
                'rowCount': 60, 'columnCount': 4, 'frozenRowCount': 1}}}}]},
            timeout=30).raise_for_status()
        rows = [LIMIT_COLS] + [[c, '', 'да'] for c in sorted(BUDGET_CATS)]
        SHEETS.put(API + BUDGET_SS + '/values/' + _q(f'{LIMITS_TAB}!A1'),
                   params={'valueInputOption': 'USER_ENTERED'},
                   json={'values': rows}, timeout=30).raise_for_status()
        log.info('создан лист «Лимиты» с %d категориями', len(BUDGET_CATS))


def _q(rng):
    import urllib.parse
    return urllib.parse.quote(rng)


def limits(force=False):
    """{категория: лимит}. Пустая ячейка — категория без ограничения.

    Ноль — это ноль, а не «без ограничения». 14.09.2026 Азиз поставил 0
    восьми категориям: подарки, лечение, одежда, зал, гаджеты, свидания,
    обучение, путешествия. Раньше такая строка просто выпадала из лимитов,
    и категория, которую хотели закрыть, оставалась вообще без контроля —
    ровно наоборот замыслу. Теперь любая трата в неё считается перебором.
    """
    now = datetime.datetime.utcnow()
    if not force and _LIM['ts'] and (now - _LIM['ts']).seconds < 300:
        return _LIM['map']
    m = {}
    try:
        r = SHEETS.get(API + BUDGET_SS + '/values/' + _q(f'{LIMITS_TAB}!A2:C60'),
                       timeout=30)
        for row in (r.json().get('values', []) if r.ok else []):
            row = list(row) + ['', '', '']
            cat = str(row[0]).strip()
            act = str(row[2]).strip().lower() or 'да'
            if not cat or act not in ('да', 'yes', '1', 'true'):
                continue
            try:
                v = float(str(row[1]).replace(' ', '').replace(',', '.'))
            except ValueError:
                continue
            if v >= 0:
                m[cat] = v
    except Exception as e:
        log.warning('лимиты: %s', e)
    _LIM['ts'], _LIM['map'] = now, m
    return m


def spent_by_cat(ym=None, from_savings=False):
    """{категория: потрачено} за месяц. Только строки типа «Расход».

    По умолчанию траты с накопительного кошелька не считаются: они
    не из месячного бюджета. `from_savings=True` — наоборот, только они.
    """
    ym = ym or now_local().strftime('%Y-%m')
    sav = save_wallet()
    out = {}
    r = SHEETS.get(API + BUDGET_SS + '/values/' + _q('Operations!A2:H'),
                   params={'valueRenderOption': 'UNFORMATTED_VALUE'}, timeout=60)
    for row in (r.json().get('values', []) if r.ok else []):
        row = list(row) + ['', '', '', '', '']
        if str(row[1]).strip() != 'Расход':
            continue
        if sav and (str(row[5]).strip() == sav) != from_savings:
            continue
        d = _row_date(row[0])
        if not d or d.strftime('%Y-%m') != ym:
            continue
        try:
            amount = float(str(row[3]).replace(',', '.'))
        except (ValueError, TypeError):
            continue
        cat = str(row[2]).strip()
        out[cat] = out.get(cat, 0.0) + amount
    return out


def _row_date(x):
    """Дата из ячейки: ISO, дд.мм.гггг или серийный номер Google Sheets."""
    t = str(x).strip()
    for f in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.datetime.strptime(t[:10], f).date()
        except ValueError:
            pass
    try:
        return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(t)))
    except (ValueError, TypeError):
        return None


def left_line(cat):
    """Строка «осталось» по категории — показывается сразу после записи."""
    lim = limits().get(cat)
    # `is None`, а не `not lim`: ноль — настоящий лимит, и молчать о нём
    # нельзя, иначе трата в закрытую категорию проходит незамеченной.
    if lim is None:
        return ''
    used = spent_by_cat().get(cat, 0.0)
    left = lim - used
    # Закрытая категория говорит словами, а не процентами: «0 из 0,
    # потрачено 100 %» человек не понимает, а «решено не тратить» — да.
    if not lim:
        if not used:
            return f'\n🟢 <b>{cat}</b>: закрыта — решено не тратить'
        return (f'\n🔴 <b>{cat}</b>: {_money(used)} с в закрытой категории '
                f'за месяц — решено было не тратить')
    pct = round(used / lim * 100)
    if left < 0:
        return (f'\n🔴 <b>{cat}</b>: перебор на {_money(-left)} с — '
                f'потрачено {_money(used)} из {_money(lim)} ({pct} %)')
    mark = '🟢' if pct < 70 else ('🟡' if pct < 90 else '🟠')
    return (f'\n{mark} <b>{cat}</b>: осталось {_money(left)} с '
            f'из {_money(lim)} на месяц (потрачено {pct} %)')


def limits_report():
    """Все категории с лимитом: потрачено, осталось, доля."""
    lim = limits()
    if not lim:
        return ('Лимиты не заданы.\n\nОткрой таблицу бюджета, лист '
                '<b>«Лимиты»</b> и впиши суммы в колонку «Лимит в месяц». '
                'Пустая строка — категория без ограничения.')
    used = spent_by_cat()
    ym = now_local().strftime('%m.%Y')
    # Доля от нулевого лимита не считается: любая трата там — сразу верх
    # списка, потому что категория закрыта.
    def share(cat, l):
        u = used.get(cat, 0.0)
        return u / l if l else (999 if u else 0)

    rows = sorted(lim.items(), key=lambda kv: -share(*kv))
    out = [f'📊 <b>Лимиты за {ym}</b>', '']
    tot_l = tot_u = 0.0
    for cat, l in rows:
        u = used.get(cat, 0.0)
        tot_l += l
        tot_u += u
        pct = round(u / l * 100) if l else (100 if u else 0)
        mark = '🔴' if u > l else ('🟠' if pct >= 90 else '🟡' if pct >= 70 else '🟢')
        out.append(f'{mark} {cat}: <b>{_money(l - u)}</b> из {_money(l)} '
                   f'· {pct} %')
    out.append('')
    out.append(f'Итого: осталось <b>{_money(tot_l - tot_u)}</b> из '
               f'{_money(tot_l)} с '
               f'({round(tot_u / tot_l * 100) if tot_l else 0} %)')
    no_limit = sorted(c for c in used if c not in lim and used[c] > 0)
    if no_limit:
        out.append('')
        out.append('<i>Без лимита: ' + ', '.join(
            f'{c} — {_money(used[c])}' for c in no_limit[:8]) + '</i>')
    return '\n'.join(out)


# Как каждый тип двигает деньги на руках. Погашение и накопление уменьшают
# кэш ровно так же, как расход: денег на руках после них меньше.
CASH_SIGN = {'Доход': 1, 'Расход': -1, 'Накопление': -1, 'Погашение': -1}


def month_report():
    """Итог месяца: результат месяца и остаток на руках.

    Раньше здесь была одна строка «Остаток» — доходы минус всё остальное
    ЗА МЕСЯЦ. Но в таблице строка «Остаток (кэш)» включает переходящий
    остаток с прошлых месяцев, и за август бот говорил −6082,51, а таблица
    +2005,39. Одно слово, два числа. Теперь считаем обе величины и обе
    называем своими именами; «Остаток (кэш)» сходится с таблицей.
    """
    ym = now_local().strftime('%Y-%m')
    r = SHEETS.get(API + BUDGET_SS + '/values/' + _q('Operations!A2:H'),
                   params={'valueRenderOption': 'UNFORMATTED_VALUE'}, timeout=60)
    by, carry = {}, 0.0
    for row in (r.json().get('values', []) if r.ok else []):
        row = list(row) + ['', '', '', '', '']
        d = _row_date(row[0])
        if not d:
            continue
        try:
            amount = float(str(row[3]).replace(',', '.'))
        except (ValueError, TypeError):
            continue
        kind = str(row[1]).strip()
        key = d.strftime('%Y-%m')
        if key < ym:
            carry += CASH_SIGN.get(kind, 0) * amount
        elif key == ym:
            by[kind] = by.get(kind, 0.0) + amount
    out = [f'📅 <b>Итог {now_local().strftime("%m.%Y")}</b>', '']
    for t in ('Доход', 'Расход', 'Накопление', 'Погашение'):
        if by.get(t):
            out.append(f'{t}: <b>{_money(by[t])}</b> с')
    month = sum(CASH_SIGN[t] * by.get(t, 0.0) for t in CASH_SIGN)
    out.append('')
    out.append(f'За месяц: <b>{_money(month)}</b> с')
    out.append(f'С прошлых месяцев: {_money(carry)} с')
    out.append(f'<b>Остаток (кэш): {_money(carry + month)} с</b>')
    return '\n'.join(out)


# ── Запись ───────────────────────────────────────────────────────────────────
def _row_exists(d, typ, cat, amount, com):
    """Есть ли уже точно такая строка в журнале."""
    try:
        r = SHEETS.get(API + BUDGET_SS + '/values/' + _q('Operations!A2:H'),
                       params={'valueRenderOption': 'UNFORMATTED_VALUE'},
                       timeout=60)
        for row in (r.json().get('values', []) if r.ok else []):
            row = list(row) + [''] * 5
            dd = _row_date(row[0])
            if (dd and str(dd) == d and str(row[1]).strip() == typ
                    and str(row[2]).strip() == cat
                    and str(row[4]).strip() == com):
                try:
                    if abs(float(row[3]) - amount) < 0.005:
                        return True
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        log.warning('проверка дубля: %s', e)
    return False


def add_entry(amount, category='Прочее', kind='расход', comment='', date=None,
              wallet='', **_):
    """Строка в лист Operations. Тип нормализуется, комментарий с заглавной."""
    k = str(kind).lower()
    if k.startswith('пог') or category == 'Оплата кредита':
        typ, cat = 'Погашение', 'Оплата кредита'
    elif k.startswith('нак') or category in SAVINGS_CATS:
        typ = 'Накопление'
        cat = category if category in SAVINGS_CATS else 'Накопления / Подушка'
    elif k.startswith('дох'):
        typ = 'Доход'
        cat = category if category in INCOME_CATS else 'Зарплата'
    else:
        typ = 'Расход'
        cat = category if category in BUDGET_CATS else 'Прочее'
    d, _m = _resolve_date(date)
    com = _cap((comment or '').strip())
    # Вторая опора против дублей: даже если сообщение придёт дважды,
    # одинаковая строка в журнал не ляжет второй раз.
    if _row_exists(d, typ, cat, float(amount), com):
        return (f'⚠️ Уже записано: {typ} {_money(amount)} с · {cat}'
                + (f' · {com}' if com else '')
                + '\nВторой раз не пишу. Если трата и правда повторилась — '
                  'добавь пояснение в комментарий.')
    w = str(wallet or '').strip()
    _budget_append('Operations!A:H', [d, typ, cat, float(amount), com, w, '', ''])
    # Запоминаем СОДЕРЖИМОЕ, а не номер строки: _budget_append сразу
    # сортирует журнал по дате, и номер протухает в тот же миг.
    LAST['data'] = [d, typ, cat, float(amount), com]
    when = '' if d == str(today_local()) else f' ({d})'
    line = f'💵 {typ}: {_money(amount)} с · {cat}{when}'
    if com:
        line += f' · {com}'
    if w:
        line += f' · {w}'
    # Сразу показываем остаток — ради этого лимиты и заводятся.
    if typ == 'Расход':
        try:
            line += left_line(cat)
        except Exception as e:
            log.warning('остаток: %s', e)
    return line


def add_transfer(amount, src, dst, comment='', date=None):
    """Перевод между своими кошельками. Не расход: деньги те же.

    Пишется одной строкой, а не двумя: две строки пришлось бы держать
    в паре — удалил одну, и деньги появились из ниоткуда.
    """
    if src == dst:
        return '⚠️ Кошельки одинаковые — переводить некуда.'
    names = [w for w, _ in wallets()]
    for w in (src, dst):
        if w not in names:
            return f'⚠️ Нет такого кошелька: {w}'
    d, _m = _resolve_date(date)
    com = _cap((comment or '').strip())
    _budget_append('Operations!A:H',
                   [d, 'Перевод', 'Перевод', float(amount), com, src, dst, ''])
    LAST['data'] = [d, 'Перевод', 'Перевод', float(amount), com]
    return f'🔁 Перевод: {_money(amount)} с · {src} → {dst}'


def _find_last_row():
    """Номер строки последней записи — поиском по её содержимому.

    Журнал пересортировывается после каждой записи, поэтому позицию
    не запоминаем, а находим заново. Совпасть должно всё: дата, тип,
    категория, сумма и комментарий.
    """
    want = LAST.get('data')
    if not want:
        return 0
    r = SHEETS.get(API + BUDGET_SS + '/values/' + _q('Operations!A2:H'),
                   params={'valueRenderOption': 'UNFORMATTED_VALUE'}, timeout=60)
    rows = r.json().get('values', []) if r.ok else []
    for i in range(len(rows) - 1, -1, -1):
        row = list(rows[i]) + [''] * 5
        d = _row_date(row[0])
        try:
            same = (d and str(d) == want[0]
                    and str(row[1]).strip() == want[1]
                    and str(row[2]).strip() == want[2]
                    and abs(float(row[3]) - want[3]) < 0.005
                    and str(row[4]).strip() == want[4])
        except (ValueError, TypeError):
            same = False
        if same:
            return i + 2
    return 0


def undo_last():
    """Убрать последнюю записанную операцию."""
    line = _find_last_row()
    if not line:
        return ('Нечего отменять — не помню последнюю запись. '
                'Поправь в таблице.')
    SHEETS.post(API + BUDGET_SS + ':batchUpdate', json={'requests': [
        {'deleteDimension': {'range': {'sheetId': 0, 'dimension': 'ROWS',
                                       'startIndex': line - 1,
                                       'endIndex': line}}}]},
        timeout=60).raise_for_status()
    was = LAST.pop('data')
    return (f'🗑 Убрал: {was[1]} {_money(was[3])} с · {was[2]}'
            + (f' · {was[4]}' if was[4] else ''))


FIX_FIELD = {'категор': (2, 'C'), 'сумм': (3, 'D'), 'коммент': (4, 'E')}


def fix_last(what, value):
    """Поправить поле последней записи: категорию, сумму или комментарий."""
    key = next((k for k in FIX_FIELD if what.startswith(k)), '')
    if not key:
        return 'Поправить можно категорию, сумму или комментарий.'
    idx, col = FIX_FIELD[key]
    line = _find_last_row()
    if not line:
        return 'Нечего править — не помню последнюю запись.'
    if key == 'сумм':
        m = re.search(r'(\d+(?:[.,]\d+)?)', value)
        if not m:
            return 'Нужно число.'
        new = float(m.group(1).replace(',', '.'))
    elif key == 'категор':
        hit = QUICK_CATS.get(value.strip().lower().replace('ё', 'е'))
        if not hit:
            return 'Такой категории нет. Напиши название из списка.'
        new = hit[1]
    else:
        new = _cap(value.strip())[:80]
    SHEETS.put(API + BUDGET_SS + '/values/' + _q(f'Operations!{col}{line}'),
               params={'valueInputOption': 'USER_ENTERED'},
               json={'values': [[new]]}, timeout=60).raise_for_status()
    LAST['data'][idx] = new
    was = LAST['data']
    return (f'✏️ Поправил: {was[1]} {_money(was[3])} с · {was[2]}'
            + (f' · {was[4]}' if was[4] else ''))


def add_credit(amount, kind='получен', name='', comment='', date=None, **_):
    """Кредит или заём: получен / погашен. Лист Loans."""
    d, _m = _resolve_date(date)
    typ = 'Погашен' if str(kind).lower().startswith('пог') else 'Получен'
    _budget_append('Loans!A:E', [d, typ, _cap(name or 'Кредит'),
                                 float(amount), _cap(comment)])
    return f'🏦 Кредит {typ.lower()}: {_money(amount)} с · {_cap(name or "—")}'


def describe(fn, args):
    if fn == 'add_entry':
        k = str(args.get('kind', 'расход')).lower()
        typ = ('Доход' if k.startswith('дох') else
               'Накопление' if k.startswith('нак') else
               'Погашение' if k.startswith('пог') else 'Расход')
        c = args.get('comment', '')
        w = args.get('wallet', '')
        return (f'💵 {typ}: {_money(args.get("amount", 0))} с · '
                f'{args.get("category", "Прочее")}' + (f' · {c}' if c else '')
                + (f' · {w}' if w else ''))
    if fn == 'add_credit':
        return f'🏦 Кредит: {_money(args.get("amount", 0))} с · {args.get("name", "")}'
    return f'{fn}({args})'


TOOLS = {'add_entry': add_entry, 'add_credit': add_credit,
         'limits_report': lambda **_: limits_report(),
         'month_report': lambda **_: month_report()}
WRITE_TOOLS = {'add_entry', 'add_credit'}
PENDING = {}
AFFIRM = {'да', 'ага', 'угу', 'подтверждаю', 'ок', 'окей', 'ok', 'yes', '+',
          'давай', 'верно', 'точно', 'да.', 'ок.'}
DENY = {'нет', 'не', 'отмена', 'отмени', 'отменить', 'no', 'неверно',
        'не надо', 'нет.'}

# ── Черновик: незаконченная запись ───────────────────────────────────────────
# До 04.09.2026 всё, что бот не разобрал целиком, выбрасывалось: «Не понял,
# повтори иначе», «Комментарий обязателен», «НЕ РАСПОЗНАЛ (не запишу)».
# Трата при этом уже случилась, и человек набирал её заново — а на ходу,
# у кассы, это значит «запишу потом» и не записать никогда.
# Теперь известное сохраняется, и бот спрашивает ровно то, чего не хватает.
DRAFT = {}          # chat_id → {kind, category, amount, comment, date, raw, need, queue}
LAST = {}           # что записали последним — для «отмени» и «поправь»
ASK = {'amount': 'Сколько? Ответь числом.',
       'comment': 'На что? Ответь одним словом.',
       'category': 'Категорию не понял — выбери кнопкой ниже.'}

# Порядок кнопок фиксирован: положение категории не должно прыгать
# от раза к разу, иначе рука не запоминает, куда жать.
CAT_LIST = sorted(BUDGET_CATS) + sorted(SAVINGS_CATS) + sorted(INCOME_CATS)


def cat_keyboard():
    """Кнопки категорий — по две в ряд, чтобы названия помещались."""
    rows, row = [], []
    for i, c in enumerate(CAT_LIST):
        row.append({'text': c, 'callback_data': f'c:{i}'})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {'inline_keyboard': rows}


def wallet_keyboard():
    """Кнопки выбора кошелька. В данных номер, а не имя: имена меняются,
    а кнопка со старым именем записала бы не туда."""
    ws = [w for w, _ in wallets()]
    rows, row = [], []
    for i, w in enumerate(ws):
        row.append({'text': w, 'callback_data': f'w:{i}'})
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return {'inline_keyboard': rows}


CHANGE_WALLET = {'inline_keyboard': [[
    {'text': '💳 Другой кошелёк', 'callback_data': 'w:ask'}]]}


def pend_add(acts):
    """Добавить операции к ожидающим подтверждения. → текст для человека.

    Раньше новая операция ЗАТИРАЛА предыдущую: три траты подряд тремя
    сообщениями — записывалась одна последняя, две пропадали с сообщением
    «предыдущая запись НЕ сохранена». Теперь они копятся, и одно «да»
    записывает все.
    """
    try:
        w = default_wallet()
    except Exception as e:
        log.warning('кошелёк по умолчанию: %s', e)
        w = ''
    for fn, a in acts:
        if fn == 'add_entry' and w and not a.get('wallet'):
            a['wallet'] = w
    cur = (PENDING.get(ALLOWED) or []) + list(acts)
    PENDING[ALLOWED] = cur
    if len(cur) == 1:
        fn, a = cur[0]
        return (describe(fn, a) + f' · {a.get("date") or "сегодня"}'
                + '\n\nЗаписать? (да/нет)')
    lines = [f'{i}. ' + describe(fn, a) + f' · {a.get("date") or "сегодня"}'
             for i, (fn, a) in enumerate(cur, 1)]
    return (f'❓ Ждут записи — {len(cur)}:\n\n' + '\n'.join(lines)
            + '\n\n«да» — запишу все, «нет» — отменю.')


def draft_need(d):
    """Чего не хватает черновику: сумма, пояснение, категория.

    Категорию спрашиваем кнопками — правка Азиза 04.09.2026: «чтобы я мог
    выбрать сам, в какую категорию его вписать». Раньше непонятое молча
    уходило в «Прочее», и разгребать приходилось потом.
    """
    if not d.get('amount'):
        return 'amount'
    if not str(d.get('comment') or '').strip():
        return 'comment'
    if not d.get('category'):
        return 'category'
    return ''


def draft_start(text, queue=None, **known):
    """Завести черновик из того, что известно, и спросить недостающее."""
    d = {'kind': 'расход', 'category': '', 'amount': None, 'comment': '',
         'date': None, 'raw': str(text or '').strip(), 'queue': list(queue or [])}
    d.update({k: v for k, v in known.items() if v not in (None, '')})
    # Сумма могла остаться в сырой фразе — вытаскиваем, чтобы не спрашивать зря.
    if not d['amount'] and d['raw']:
        m = re.search(r'(\d+(?:[.,]\d+)?)', d['raw'])
        if m:
            d['amount'] = float(m.group(1).replace(',', '.'))
            # то, что осталось от фразы, — готовый комментарий
            left = _strip_currency((d['raw'][:m.start()] + ' '
                                    + d['raw'][m.end():]).strip())
            if not d['comment'] and left:
                d['comment'] = re.sub(r'^\W+|\W+$', '', left)[:80]
    if not d['comment'] and d['raw'] and not re.fullmatch(r'[\d.,\s]+', d['raw']):
        d['comment'] = re.sub(r'^\W+|\W+$', '', _strip_currency(d['raw']))[:80]
    return draft_ask(d)


def draft_ask(d, prefix=''):
    """Показать вопрос по черновику либо перейти к подтверждению."""
    need = draft_need(d)
    if not need:
        DRAFT.pop(ALLOWED, None)
        args = {'amount': d['amount'], 'category': d['category'],
                'kind': d.get('kind') or 'расход', 'comment': d['comment']}
        if d.get('date'):
            args['date'] = d['date']
        queue = d.get('queue') or []
        out = pend_add([('add_entry', args)])
        if queue:
            DRAFT[ALLOWED] = {'queue': queue}      # очередь переживает подтверждение
        return prefix + out
    d['need'] = need
    DRAFT[ALLOWED] = d
    have = []
    if d.get('amount'):
        have.append(f'{_money(d["amount"])} с')
    if d.get('comment'):
        have.append(d['comment'])
    if d.get('category'):
        have.append(d['category'])
    seen = ' · '.join(have)
    return (prefix + (f'📝 Записал пока: {seen}\n' if seen else '')
            + ASK[need] + '\n<i>Не нужно — ответь «отмена».</i>')


def draft_fill(d, text):
    """Ответ на доспрос достраивает черновик. → текст для человека."""
    t = ' '.join(str(text).strip().split())
    need = d.get('need')
    if need == 'amount':
        m = re.search(r'(\d+(?:[.,]\d+)?)', t)
        if not m:
            return 'Нужно число. Сколько?'
        d['amount'] = float(m.group(1).replace(',', '.'))
        rest = _strip_currency((t[:m.start()] + ' ' + t[m.end():]).strip())
        if rest and not d.get('comment'):
            d['comment'] = re.sub(r'^\W+|\W+$', '', rest)[:80]
    elif need == 'comment':
        com = re.sub(r'^\W+|\W+$', '', _strip_currency(t))[:80]
        if not com:
            return 'Напиши словом, на что.'
        d['comment'] = com
        # Ответ мог заодно назвать категорию: «кафе» → и комментарий, и она.
        if not d.get('category'):
            hit = QUICK_CATS.get(com.lower().replace('ё', 'е'))
            if hit:
                d['kind'], d['category'] = hit
    elif need == 'category':
        # Кнопкой быстрее, но набрать название тоже можно.
        hit = QUICK_CATS.get(t.lower().replace('ё', 'е'))
        if not hit:
            return 'Не нашёл такой категории. Нажми кнопку ниже.'
        d['kind'], d['category'] = hit
    return draft_ask(d)


def draft_next(prefix=''):
    """Взять следующую нераспознанную строку пачки, если очередь не пуста."""
    d = DRAFT.get(ALLOWED) or {}
    queue = d.get('queue') or []
    if not queue:
        DRAFT.pop(ALLOWED, None)
        return ''
    line = queue.pop(0)
    left = f' (осталось разобрать: {len(queue)})' if queue else ''
    # Строка могла быть понятной сама по себе — тогда вопрос лишний.
    q = _parse_quick(line) or _parse_quick_loose(line)
    if not q:
        sw = _amount_first(line)
        if sw:
            q = _parse_quick(sw) or _parse_quick_loose(sw)
    if q:
        # Разобралась — записываем как обычную операцию, без вопросов.
        # Спрашивать про неё комментарий значило бы вести себя иначе, чем
        # с той же строкой, присланной отдельным сообщением.
        k2, cat, amount, iso, com, _l = q
        a = {'amount': amount, 'category': cat, 'kind': k2, 'comment': com}
        if iso:
            a['date'] = iso
        out = pend_add([('add_entry', a)])
        DRAFT[ALLOWED] = {'queue': queue}
    else:
        out = draft_start(line, queue=queue)
    return f'{prefix}📋 Строка «{line[:60]}»{left}\n{out}'

TOOLS_SPEC = [
    {'type': 'function', 'function': {
        'name': 'add_entry',
        'description': 'Записать расход, доход, накопление или погашение кредита '
                       'в личный бюджет.',
        'parameters': {'type': 'object', 'properties': {
            'amount': {'type': 'number', 'description': 'Сумма в сомони'},
            'category': {'type': 'string',
                         'description': 'Категория: ' + ', '.join(sorted(BUDGET_CATS))},
            'kind': {'type': 'string', 'enum': ['расход', 'доход', 'накопление',
                                                'погашение']},
            'comment': {'type': 'string', 'description': 'На что именно — обязательно'},
            'date': {'type': 'string', 'description': 'YYYY-MM-DD, если не сегодня'},
        }, 'required': ['amount', 'comment']}}},
    {'type': 'function', 'function': {
        'name': 'add_credit',
        'description': 'Записать получение или погашение кредита/займа.',
        'parameters': {'type': 'object', 'properties': {
            'amount': {'type': 'number'},
            'kind': {'type': 'string', 'enum': ['получен', 'погашен']},
            'name': {'type': 'string', 'description': 'Кто дал или кому платим'},
            'comment': {'type': 'string'},
            'date': {'type': 'string'},
        }, 'required': ['amount']}}},
    {'type': 'function', 'function': {
        'name': 'limits_report',
        'description': 'Показать лимиты по категориям: сколько потрачено и '
                       'сколько осталось в этом месяце.',
        'parameters': {'type': 'object', 'properties': {}}}},
    {'type': 'function', 'function': {
        'name': 'month_report',
        'description': 'Итог текущего месяца: доходы, расходы, накопления, остаток.',
        'parameters': {'type': 'object', 'properties': {}}}},
]

SYSTEM = (
    'Ты — помощник по ЛИЧНОМУ бюджету Азиза. Только личные деньги: расходы, '
    'доходы, накопления, кредиты, лимиты по категориям. Ничего рабочего.\n'
    'Валюта — сомони (с). Сегодня: {today}.\n'
    'Отвечай коротко и по делу, по-русски, на «ты».\n'
    'Записи делаешь только через инструменты. Комментарий к трате обязателен: '
    'если непонятно, на что потрачено — переспроси, не выдумывай.\n'
    'Если вопрос не про личные деньги — скажи, что этот бот только про бюджет.'
)


# ── Мозг ─────────────────────────────────────────────────────────────────────
def _order():
    """Модели в порядке пробы: та, что отвечала в прошлый раз, — первой."""
    live = _LIVE['model']
    if live and live in GROQ_MODELS:
        return [live] + [m for m in GROQ_MODELS if m != live]
    return list(GROQ_MODELS)


def _ask_groq(model, msgs):
    """→ (сообщение, причина отказа). Причина есть — пробуем следующую."""
    try:
        r = requests.post('https://api.groq.com/openai/v1/chat/completions',
                          headers={'Authorization': f'Bearer {GROQ_KEY}',
                                   'Content-Type': 'application/json'},
                          json={'model': model, 'messages': msgs,
                                'tools': TOOLS_SPEC, 'tool_choice': 'auto',
                                'temperature': 0.2}, timeout=90)
    except requests.RequestException as e:
        return None, f'сеть: {e}'
    if r.status_code in (400, 404):
        # модель снята или не существует — на неё больше не тратим попытки
        return None, f'модель недоступна ({r.status_code})'
    if r.status_code == 429:
        return None, 'лимит запросов'
    if r.status_code >= 500:
        return None, f'сбой провайдера ({r.status_code})'
    if not r.ok:
        return None, f'ошибка {r.status_code}'
    try:
        return r.json()['choices'][0]['message'], None
    except Exception as e:
        return None, f'непонятный ответ: {e}'


def _ask_claude(text):
    """Запасной провайдер. Без инструментов — просто ответ словами."""
    if not ANTHRO_KEY:
        return None
    try:
        r = requests.post('https://api.anthropic.com/v1/messages',
                          headers={'x-api-key': ANTHRO_KEY,
                                   'anthropic-version': '2023-06-01',
                                   'content-type': 'application/json'},
                          json={'model': CLAUDE_MODEL, 'max_tokens': 4096,
                                'output_config': {'effort': 'low'},
                                'system': SYSTEM.format(today=today_local()),
                                'messages': [{'role': 'user', 'content': text}]},
                          timeout=120)
        if not r.ok:
            return None
        return ''.join(b.get('text', '') for b in r.json().get('content', [])
                       if b.get('type') == 'text').strip() or None
    except Exception:
        return None


def brain(text):
    """Свободный вопрос. Перебираем модели, пока одна не ответит."""
    msgs = [{'role': 'system', 'content': SYSTEM.format(today=today_local())},
            {'role': 'user', 'content': text}]
    tried = []
    for model in _order():
        m, why = _ask_groq(model, msgs)
        if m is None:
            tried.append(f'{model}: {why}')
            log.warning('модель %s не ответила — %s', model, why)
            continue
        if _LIVE['model'] != model:
            log.info('работаю на модели %s', model)
            _LIVE['model'] = model
        if m.get('tool_calls'):
            calls = [(tc['function']['name'],
                      json.loads(tc['function']['arguments'] or '{}'))
                     for tc in m['tool_calls']]
            return run_calls(calls)
        return m.get('content') or 'Не понял, повтори иначе.'

    # Все модели Groq молчат — пробуем другого провайдера.
    alt = _ask_claude(text)
    if alt:
        log.info('ответил запасной провайдер')
        return alt
    _LIVE['model'] = None
    return ('⚠️ Ни одна модель не ответила.\n\n'
            + '\n'.join('· ' + t for t in tried)
            + '\n\nЗапись расходов работает как обычно — '
              'пиши «Продукты 120 вода».')


def run_calls(calls):
    """Чтение — сразу. Запись — откладываем до «да»."""
    reads, writes = [], []
    for fn, args in calls:
        if fn == 'add_entry' and not str(args.get('comment', '')).strip():
            # Сумму и категорию модель уже поняла — выбрасывать их из-за
            # отсутствующего комментария значит заставить набрать всё заново.
            return draft_start('', amount=args.get('amount'),
                               category=args.get('category'),
                               kind=args.get('kind') or 'расход',
                               date=args.get('date'))
        if fn in WRITE_TOOLS:
            writes.append((fn, args))
        elif fn in TOOLS:
            try:
                reads.append(TOOLS[fn](**args))
            except Exception as e:
                reads.append(f'⚠️ Ошибка «{fn}»: {e}')
    out = list(reads)
    if writes:
        out.append(pend_add(writes))
    return '\n'.join(out) if out else 'Не понял, повтори иначе.'


# ── Голос ────────────────────────────────────────────────────────────────────
WHISPER_PROMPT = ('сомони, расход, доход, накопления, кредит, лимит, продукты, '
                  'кафе, курение, стики, аренда, подписка, лечение, аптека, '
                  'массаж, зал, одежда, подарки, путешествие, семья, машина.')


def transcribe(file_id):
    info = tg('getFile', file_id=file_id)
    path = info['result']['file_path']
    audio = requests.get(
        f'https://api.telegram.org/file/bot{TG_TOKEN}/{path}', timeout=60).content
    r = requests.post('https://api.groq.com/openai/v1/audio/transcriptions',
                      headers={'Authorization': f'Bearer {GROQ_KEY}'},
                      files={'file': ('audio.ogg', audio, 'audio/ogg')},
                      data={'model': 'whisper-large-v3', 'language': 'ru',
                            'prompt': WHISPER_PROMPT, 'temperature': '0'}, timeout=90)
    r.raise_for_status()
    return r.json().get('text', '').strip()


# ── Чек с фото ───────────────────────────────────────────────────────────────
VISION_MODELS = [m.strip() for m in os.environ.get(
    'VISION_MODELS', 'meta-llama/llama-4-scout-17b-16e-instruct').split(',') if m.strip()]


def _receipt_groq(b64, q):
    """Запасное чтение чека: зрение Groq, если Claude недоступен."""
    for model in VISION_MODELS:
        try:
            r = requests.post('https://api.groq.com/openai/v1/chat/completions',
                              headers={'Authorization': f'Bearer {GROQ_KEY}',
                                       'Content-Type': 'application/json'},
                              json={'model': model, 'temperature': 0,
                                    'messages': [{'role': 'user', 'content': [
                                        {'type': 'text', 'text': q},
                                        {'type': 'image_url', 'image_url': {
                                            'url': f'data:image/jpeg;base64,{b64}'}}]}]},
                              timeout=90)
            if not r.ok:
                log.warning('зрение %s: %s', model, r.status_code)
                continue
            txt = r.json()['choices'][0]['message'].get('content', '')
            m = re.search(r'\{.*\}', txt, re.S)
            if m:
                return json.loads(m.group(0))
        except Exception as e:
            log.warning('зрение %s: %s', model, e)
    return {}


def read_receipt(content):
    import base64
    q = ('Это фото чека. Верни СТРОГО JSON без пояснений: '
         '{"total": число_итого, "merchant": "магазин", '
         f'"category": "одна из: {", ".join(sorted(BUDGET_CATS))}", '
         '"summary": "кратко что куплено"}. Сумму не видно — total:0.')
    b64 = base64.b64encode(content).decode()
    try:
        r = requests.post('https://api.anthropic.com/v1/messages',
                      headers={'x-api-key': ANTHRO_KEY,
                               'anthropic-version': '2023-06-01',
                               'content-type': 'application/json'},
                      json={'model': CLAUDE_MODEL, 'max_tokens': 4096,
                            'output_config': {'effort': 'low'},
                            'messages': [{'role': 'user', 'content': [
                                {'type': 'image', 'source': {
                                    'type': 'base64', 'media_type': 'image/jpeg',
                                    'data': b64}},
                                {'type': 'text', 'text': q}]}]}, timeout=120)
        if r.ok:
            txt = ''.join(b.get('text', '') for b in r.json().get('content', [])
                          if b.get('type') == 'text')
            m = re.search(r'\{.*\}', txt, re.S)
            if m:
                return json.loads(m.group(0))
        log.warning('чек через Claude: %s', r.status_code)
    except Exception as e:
        log.warning('чек через Claude: %s', e)
    return _receipt_groq(b64, q)


# ── Аудит ────────────────────────────────────────────────────────────────────
AUDIT_TAB = 'Аудит'


def audit(kind, text, result):
    try:
        SHEETS.post(API + BUDGET_SS + '/values/' + _q(f'{AUDIT_TAB}!A:D')
                    + ':append?valueInputOption=RAW&insertDataOption=INSERT_ROWS',
                    json={'values': [[now_local().strftime('%Y-%m-%d %H:%M'),
                                      kind, text[:400], result[:400]]]}, timeout=20)
    except Exception as e:
        log.warning('аудит: %s', e)


# Номер последнего обработанного сообщения. В памяти он не переживает
# перезапуск, а Railway перезапускает контейнер на каждой выкатке —
# телеграм в этот момент присылает неподтверждённые сообщения заново.
OFFSET_CELL = f'{AUDIT_TAB}!F1'


def load_offset():
    try:
        v = SHEETS.get(API + BUDGET_SS + '/values/' + _q(OFFSET_CELL),
                       timeout=30).json().get('values') or []
        return int(v[0][0]) if v and v[0] else 0
    except Exception as e:
        log.warning('offset: %s', e)
        return 0


def save_offset(n):
    try:
        SHEETS.put(API + BUDGET_SS + '/values/' + _q(OFFSET_CELL),
                   params={'valueInputOption': 'RAW'},
                   json={'values': [[str(n)]]}, timeout=20)
    except Exception as e:
        log.warning('offset: %s', e)


def ensure_audit_tab():
    meta = SHEETS.get(API + BUDGET_SS, params={'fields': 'sheets.properties'},
                      timeout=30).json()
    have = {sh['properties']['title'] for sh in meta.get('sheets', [])}
    if AUDIT_TAB not in have:
        SHEETS.post(API + BUDGET_SS + ':batchUpdate', json={'requests': [
            {'addSheet': {'properties': {'title': AUDIT_TAB, 'gridProperties': {
                'rowCount': 5000, 'columnCount': 4, 'frozenRowCount': 1}}}}]},
            timeout=30).raise_for_status()
        SHEETS.put(API + BUDGET_SS + '/values/' + _q(f'{AUDIT_TAB}!A1'),
                   params={'valueInputOption': 'RAW'},
                   json={'values': [['Когда', 'Тип', 'Сообщение', 'Ответ']]},
                   timeout=30)


# ── Обработка сообщений ──────────────────────────────────────────────────────
HELP = (
    '💰 <b>Личный бюджет</b>\n\n'
    '<b>Записать трату</b> — одной строкой:\n'
    '<code>Продукты 120 вода</code>\n'
    '<code>Курение 20 18.08.2026 стики</code>\n'
    'Можно наоборот: <code>250 помощь брату</code>\n\n'
    '<b>Пачкой</b> — каждая операция своей строкой, подтверждение одно.\n\n'
    '<b>Команды</b>\n'
    '<code>экран</code> — записать кнопками, без подтверждения\n'
    '<code>лимиты</code> — сколько осталось по каждой категории\n'
    '<code>месяц</code> — итог месяца: доходы, расходы, остаток\n'
    '<code>отмени последнюю</code> — убрать последнюю запись\n'
    '<code>поправь категорию Кафе</code> · <code>поправь сумму 120</code> · '
    '<code>поправь комментарий вода</code>\n\n'
    '<b>Если не понял</b> — не выбрасываю, а спрашиваю недостающее: '
    '«Сколько?» или «На что?». Отвечаешь одним словом или числом, '
    'фразу целиком набирать не надо. Категорию покажу кнопками — '
    'выбираешь сам. Не нужно — ответь «отмена».\n\n'
    'Дата: 18.08.2026 · 18.08.26 · 18.08 · 2026-08-18. Без даты — сегодня.\n'
    'Валюту (см, сом, с) можно писать — отбрасывается.\n'
    'Голосовое расшифрую. Фото чека прочитаю и предложу запись.\n'
    '<code>модель</code> — на какой модели сейчас работаю.'
)
MODEL_WORDS = ('модель', '/модель', 'какая модель')
LIMIT_WORDS = ('лимиты', 'лимит', '/лимиты', 'остаток', 'остатки', 'сколько осталось')
MONTH_WORDS = ('месяц', '/месяц', 'итог месяца', 'итоги месяца')
# «Старт» словом, а не только командой: 14.09 Азиз написал именно так,
# бот команды не узнал и ответил свободным текстом от модели — без кнопки.
HELP_WORDS = ('/start', 'старт', 'начать', '/help', '/помощь', 'помощь',
              'что умеешь')
SCREEN_WORDS = ('/экран', 'экран', '/деньги', 'деньги')
# Адрес экрана. Его отдаёт эта же служба, домен выдан Railway 14.09.2026.
WEBAPP_URL = os.environ.get(
    'BUDGET_WEBAPP_URL', 'https://my-vault-production-b39f.up.railway.app/').strip()


def screen_button():
    """Кнопка, открывающая экран денег прямо в телеграме."""
    return {'inline_keyboard': [[{'text': '💳 Открыть экран',
                                 'web_app': {'url': WEBAPP_URL}}]]}


def set_menu_button():
    """Постоянная кнопка слева от поля ввода — открывает экран.

    Команду надо вспомнить и набрать, а кнопка просто есть. Ради этого
    экран и делался: убрать трение, а не добавить ещё один способ.
    """
    return tg('setChatMenuButton', chat_id=int(ALLOWED),
              menu_button={'type': 'web_app', 'text': 'Деньги',
                           'web_app': {'url': WEBAPP_URL}})
HABIT_WORDS = ('/зал', 'зал', '/привычки', 'привычки')
QUICK_WORDS = ('/быстро', 'быстро', 'частые', '/частые')
UNDO_WORDS = ('отмени последнюю', 'отмени запись', 'удали последнюю',
              'убери последнюю', '/отмена')


def handle(msg):
    chat_id = str(msg.get('chat', {}).get('id', ''))
    if ALLOWED and chat_id != ALLOWED:
        tg('sendMessage', chat_id=chat_id,
           text='Это личный бот, он отвечает только владельцу.')
        return

    kind, text = 'text', (msg.get('text') or msg.get('caption') or '')

    # Фото: чек → предложить запись
    if 'photo' in msg:
        typing()
        try:
            info = tg('getFile', file_id=msg['photo'][-1]['file_id'])
            path = info['result']['file_path']
            content = requests.get(
                f'https://api.telegram.org/file/bot{TG_TOKEN}/{path}',
                timeout=120).content
            if not ANTHRO_KEY and not GROQ_KEY:
                send('📷 Читать чеки нечем — нет ни одного ключа. '
                     'Напиши сумму текстом.')
                return
            rc = read_receipt(content)
            total = float(rc.get('total') or 0)
            if total <= 0:
                # Магазин с чека обычно читается, даже когда сумма — нет.
                # Держим его как комментарий и спрашиваем только сумму.
                shop = _cap((rc.get('merchant') or rc.get('summary') or '').strip())
                send('🧾 Сумму на чеке не разобрал.\n'
                     + draft_start('', comment=shop,
                                   category=rc.get('category')
                                   if rc.get('category') in BUDGET_CATS else ''))
                return
            cat = rc.get('category') if rc.get('category') in BUDGET_CATS else 'Прочее'
            com = _cap((rc.get('merchant') or rc.get('summary') or 'чек').strip())
            args = {'amount': total, 'category': cat, 'kind': 'расход', 'comment': com}
            send('🧾 Чек прочитан.\n' + pend_add([('add_entry', args)]))
        except Exception as e:
            send(f'⚠️ Не смог прочитать чек: {e}')
        return

    # Голос
    if 'voice' in msg or 'audio' in msg:
        kind = 'voice'
        typing()
        try:
            text = transcribe((msg.get('voice') or msg.get('audio'))['file_id'])
            send(f'🎙 <i>{text}</i>')
        except Exception as e:
            send(f'⚠️ Не смог расшифровать: {e}')
            return

    if not text:
        return
    low = text.strip().lower().replace('ё', 'е').rstrip('!.')

    # Ждём подтверждения?
    if PENDING.get(ALLOWED):
        if low in AFFIRM:
            acts = PENDING.pop(ALLOWED)
            res = []
            for fn, args in acts:
                try:
                    res.append(TOOLS[fn](**args))
                except Exception as e:
                    res.append(f'⚠️ Ошибка «{fn}»: {e}')
            out = '\n'.join(res)
            # Нераспознанные строки пачки — по одной, пока не кончатся.
            nxt = draft_next('\n\n')
            send(out + nxt)
            audit('confirm', text, out)
            return
        if low in DENY:
            PENDING.pop(ALLOWED, None)
            DRAFT.pop(ALLOWED, None)
            send('Отменил, ничего не записал.')
            return
    # Ответ на доспрос по черновику — РАНЬШЕ, чем «жду да/нет»: когда висят
    # и вопрос, и подтверждение, короткий ответ вроде «15» относится
    # к вопросу, иначе бот отвечал «жду да/нет» и вопрос было не закрыть.
    d = DRAFT.get(ALLOWED)
    if d and d.get('need'):
        if low in DENY:
            DRAFT.pop(ALLOWED, None)
            send('Убрал черновик.' + draft_next('\n\n'))
            return
        # Пришла законченная операция, а не ответ на вопрос: следующая трата
        # не должна съедать черновик. Записываем её отдельно и переспрашиваем.
        whole = _parse_quick(text)
        if not whole:
            sw = _amount_first(text)
            whole = _parse_quick(sw) if sw else None
        if whole:
            k2, cat, amount, iso, com, _l = whole
            a = {'amount': amount, 'category': cat, 'kind': k2, 'comment': com}
            if iso:
                a['date'] = iso
            send(pend_add([('add_entry', a)]) + '\n\n' + draft_ask(d))
            return
        out = draft_fill(d, text)
        send(out)
        audit('черновик', text, out[:200])
        return

    # Подтверждение висит, а сообщение — не операция: не теряем его, ждём.
    if PENDING.get(ALLOWED) and not (
            _parse_quick(text) or _parse_quick_lines(text)[0]
            or _amount_first(text) or len(text.strip().splitlines()) > 1):
        send('Жду ответа: <b>да</b> — записать, <b>нет</b> — отменить.')
        return

    if low in HELP_WORDS:
        send(HELP, reply_markup=screen_button())
        return
    if low in SCREEN_WORDS:
        send('Экран денег: сумма, категория кнопкой — запись сразу, '
             'без подтверждения. Там же лимиты, итог месяца и счета.',
             reply_markup=screen_button())
        return
    if low in MODEL_WORDS:
        live = _LIVE['model'] or 'ещё не проверялась'
        send(f'🧠 Сейчас работает: <b>{live}</b>\n\n'
             'Очередь моделей:\n'
             + '\n'.join(f'{i}. {m}' for i, m in enumerate(GROQ_MODELS, 1))
             + ('\n\nЗапасной провайдер: Claude ' + CLAUDE_MODEL
                if ANTHRO_KEY else '\n\nЗапасного провайдера нет — '
                                   'не задан ANTHROPIC_API_KEY'))
        return

    # Отмена и правка последней записи. Стоят до разбора операций: «отмени» —
    # это команда, а не трата.
    if low in UNDO_WORDS:
        typing()
        try:
            out = undo_last()
        except Exception as e:
            out = f'⚠️ Не смог отменить: {e}'
        send(out)
        audit('отмена', text, out[:200])
        return
    m_fix = re.match(r'^поправь\s+(\S+)\s+(.+)$', low)
    if m_fix:
        typing()
        try:
            out = fix_last(m_fix.group(1), text.split(None, 2)[2])
        except Exception as e:
            out = f'⚠️ Не смог поправить: {e}'
        send(out)
        audit('правка', text, out[:200])
        return

    if low in HABIT_WORDS:
        send(habit_status())
        return
    if low in QUICK_WORDS:
        kb = quick_keyboard()
        if not kb:
            send('Частых трат пока не набралось — нужно хотя бы несколько '
                 'записей по одной категории. Пиши как обычно, а через неделю '
                 'кнопки появятся сами.')
            return
        send('Частое — жми, запишу сразу:', reply_markup=kb)
        return
    if low in LIMIT_WORDS:
        typing()
        out = limits_report()
        send(out)
        audit('limits', text, out[:200])
        return
    if low in MONTH_WORDS:
        typing()
        out = month_report()
        send(out)
        audit('month', text, out[:200])
        return

    # Пачка операций
    multi, bad = _parse_quick_lines(text)
    if multi:
        acts = []
        for k2, cat, amount, iso, com, _loose in multi:
            amt = str(int(amount)) if float(amount).is_integer() else str(amount)
            a = {'amount': amt, 'category': cat, 'kind': k2, 'comment': com}
            if iso:
                a['date'] = iso
            acts.append(('add_entry', a))
        out = pend_add(acts)
        if bad:
            # Не выбрасываем: после «да» пройдём по ним по одной и доспросим.
            DRAFT[ALLOWED] = {'queue': list(bad)}
            out += ('\n\n📋 Не разобрал сам, спрошу после «да»:\n'
                    + '\n'.join('· ' + b[:60] for b in bad))
        send(out)
        audit('пачка', text, f'ожидает подтверждения: {len(acts)}')
        return

    # Несколько строк, но пачкой не признано: разобралось меньше половины.
    # Раньше такой блок уходил в модель ОДНИМ куском, и бот спрашивал про
    # три траты как про одну — две пропадали. Ставим строки в очередь
    # и разбираем по одной.
    raw_lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if len(raw_lines) > 1 and '?' not in text \
            and not any(w in low for w in NOT_SPEND):
        DRAFT[ALLOWED] = {'queue': raw_lines}
        out = draft_next()
        send(out)
        audit('очередь строк', text, out[:200])
        return

    # Одиночная операция
    q = _parse_quick(text)
    if not q:
        swapped = _amount_first(text)
        if swapped:
            q = _parse_quick(swapped) or _parse_quick_loose(swapped)
    if q:
        k2, cat, amount, iso, com, _l = q
        amt = str(int(amount)) if float(amount).is_integer() else str(amount)
        args = {'amount': amt, 'category': cat, 'kind': k2, 'comment': com}
        if iso:
            args['date'] = iso
        send(pend_add([('add_entry', args)]))
        audit('быстрый ввод', text, 'ожидает подтверждения')
        return

    # Всё остальное — модели
    typing()
    try:
        reply = brain(text)
    except Exception as e:
        reply = f'⚠️ Сбой: {e}'
    # Модель не записала операцию и не ответила по делу, а в сообщении есть
    # число — почти наверняка это трата, которую иначе пришлось бы набирать
    # заново. Заводим черновик и доспрашиваем.
    low_t = text.lower().replace('ё', 'е')
    lost = reply.startswith(('Не понял', '⚠️ Ни одна модель', '⚠️ Сбой'))
    if (lost and not PENDING.get(ALLOWED) and not DRAFT.get(ALLOWED)
            and '?' not in text and not any(w in low_t for w in NOT_SPEND)):
        reply = draft_start(text)
    send(reply)
    audit(kind, text, reply)


def wallet_answer(data):
    """Нажата кнопка кошелька: показать список или выбрать из него."""
    if data == 'w:ask':
        kb = wallet_keyboard()
        if not kb['inline_keyboard']:
            return send('Кошельков нет — заведи их в листе «Кошельки».')
        return send('С какого кошелька?', reply_markup=kb)
    ws = [w for w, _ in wallets()]
    try:
        name = ws[int(data[2:])]
    except (ValueError, IndexError):
        # Список мог поменяться, пока сообщение висело. Молчать нельзя:
        # человек нажал и ждёт.
        return send('Этого кошелька больше нет — открой список заново.')
    try:
        set_default_wallet(name)
    except Exception as e:
        log.warning('кошелёк по умолчанию: %s', e)
    for fn, a in (PENDING.get(ALLOWED) or []):
        if fn == 'add_entry':
            a['wallet'] = name
    left = PENDING.get(ALLOWED) or []
    if left:
        return send(f'💳 Кошелёк: <b>{name}</b>\n\n'
                    + '\n'.join(describe(fn, a) for fn, a in left)
                    + '\n\n«да» — запишу, «нет» — отменю.')
    send(f'💳 Теперь по умолчанию: <b>{name}</b>')


def on_callback(cq):
    """Нажата кнопка категории."""
    tg('answerCallbackQuery', callback_query_id=cq.get('id'))
    if str((cq.get('from') or {}).get('id', '')) != ALLOWED:
        return
    data = str(cq.get('data') or '')
    msg = cq.get('message') or {}
    if msg.get('message_id'):
        # Убираем кнопки со старого сообщения, чтобы по ним нельзя было
        # нажать второй раз и попасть в уже закрытый вопрос.
        tg('editMessageReplyMarkup', chat_id=ALLOWED,
           message_id=msg['message_id'], reply_markup={'inline_keyboard': []})
    # Привычка: «был» / «не был» и причина пропуска.
    if data.startswith('h:') or data.startswith('hw:'):
        return habit_answer(data)
    if data.startswith('q:'):
        return quick_answer(data)
    if data.startswith('w:'):
        return wallet_answer(data)
    if not data.startswith('c:'):
        return
    try:
        cat = CAT_LIST[int(data[2:])]
    except (ValueError, IndexError):
        return
    d = DRAFT.get(ALLOWED)
    if not d or d.get('need') != 'category':
        send(f'Этот вопрос уже закрыт. Если нужно поправить последнюю запись — '
             f'«поправь категорию {cat}».')
        return
    d['kind'], d['category'] = QUICK_CATS.get(
        cat.lower().replace('ё', 'е'), ('расход', cat))
    out = draft_ask(d)
    send(out)
    audit('категория кнопкой', cat, out[:200])


def run():
    for need, name in ((TG_TOKEN, 'TELEGRAM_BOT_TOKEN'), (ALLOWED, 'TELEGRAM_CHAT_ID')):
        if not need:
            log.error('Нет %s', name)
            sys.exit(1)
    if not GROQ_KEY:
        log.warning('Нет GROQ_API_KEY — свободные вопросы и голос работать не будут')
    me = tg('getMe')
    if not me.get('ok'):
        log.error('Телеграм отклонил токен: %s', me.get('description') or me)
        sys.exit(1)
    log.info('бот: @%s', me['result'].get('username'))
    try:
        ensure_limits_tab()
        ensure_audit_tab()
        ensure_habit_tabs()
        ensure_wallet_tab()
        ensure_debt_tab()
        ensure_task_tab()
        # Вопрос про привычку должен приходить сам, а не ждать, пока
        # откроешь бота: в этом вся суть — не заставлять себя заходить.
        threading.Thread(target=habit_loop, daemon=True).start()
    except Exception as e:
        log.warning('подготовка таблицы: %s', e)
    # Экран денег. Отдельным потоком в том же процессе: пишем в одну
    # таблицу, и разводить это по двум службам значит держать два ключа
    # и два деплоя. Не поднялся — бот всё равно работает как раньше.
    try:
        import budget_web
        threading.Thread(target=budget_web.serve, daemon=True).start()
        log.info('экран денег на порту %s', os.environ.get('PORT', '8080'))
        r = set_menu_button()
        log.info('кнопка меню: %s', r.get('description') or r.get('ok'))
    except Exception as e:
        log.warning('экран денег не поднялся: %s', e)
    log.info('💰 Бюджетный бот запущен')

    offset, bad = load_offset(), 0
    while True:
        try:
            res = tg('getUpdates', offset=offset, timeout=25,
                     allowed_updates=['message', 'callback_query'])
            if not res.get('ok'):
                bad += 1
                if bad in (1, 10, 100):
                    log.warning('телеграм: %s', res.get('description') or res)
                time.sleep(3)
                continue
            bad = 0
            for upd in res.get('result') or []:
                offset = upd['update_id'] + 1
                # Запоминаем ДО обработки: контейнер могут перезапустить
                # посреди записи, и тогда телеграм пришлёт то же сообщение
                # заново. 04.09.2026 так вышло: пачка из 12 трат обработалась
                # трижды, и 11 операций записались дважды.
                save_offset(offset)
                try:
                    if 'message' in upd:
                        handle(upd['message'])
                    elif 'callback_query' in upd:
                        on_callback(upd['callback_query'])
                except Exception as e:
                    log.error('обработка: %s', e)
                    try:
                        send(f'⚠️ Ошибка: {e}')
                    except Exception:
                        pass
        except requests.RequestException as e:
            log.warning('сеть: %s', e)
            time.sleep(5)
        except Exception as e:
            log.error('цикл: %s', e)
            time.sleep(5)


if __name__ == '__main__':
    run()
