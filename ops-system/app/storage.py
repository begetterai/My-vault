#!/usr/bin/env python3
"""Хранилище: Google Sheets + Drive. Единственное место, где система пишет данные.

Структура таблицы создаётся автоматически при первом запуске — клиенту
не нужно ничего готовить руками, только дать доступ сервисному аккаунту.
"""
import os, json, time, base64, datetime, urllib.parse
os.environ.setdefault('REQUESTS_CA_BUNDLE', '/etc/ssl/certs/ca-certificates.crt')
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

from . import config as C

B = 'https://sheets.googleapis.com/v4/spreadsheets/'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive']

FILL_COLS = ['Дата', 'Точка', 'Кто заполнил', 'Заполнил в', 'Время',
             'Выполнено', 'Всего', '%', 'Не выполнены пункты', 'Комментарий',
             'Замеры', 'Фото', 'Минут на заполнение',
             'Проверил', 'Когда проверил', 'Расхождение при проверке',
             'Фото — проверка ИИ', 'Смена', 'Кому сдал']

PART_RU = {'open': 'открывающая', 'close': 'закрывающая',
           'one': 'одна на день'}

# Ознакомление с регламентом: подпись человека, что документ прочитан.
# Бумажный лист ознакомления умирает в папке — здесь видно, кто и когда.
READ_COLS = ['Дата', 'Время', 'Точка', 'Кто', 'Код', 'Документ', 'Ссылка']

# Работа на местах — журнал отрезков, а не отметка «где стоит сейчас».
# Человек за день бывает на двух местах: отработал саладетту в первую смену,
# сдал её и принял бар во вторую. Для зарплаты нужны именно отрезки —
# где, с какого по какое время и как он туда попал. Затирать прошлую запись
# нельзя: вместе с ней стирается отработанный час.
# Время в минутах, а не в часах: 0,72 часа таблица показывает как 0:43
# и перестаёт считать это числом. Минуты — целое, делить на 60 умеет любой.
STATION_COLS = ['Дата', 'Точка', 'Кто', 'Станция', 'Смена', 'Начало', 'Конец',
                'Минут', 'Как встал', 'От кого']
_S = {'v': None}


def session():
    if _S['v'] is None:
        info = json.loads(C.GOOGLE_SA) if C.GOOGLE_SA.strip().startswith('{') \
            else json.load(open(C.GOOGLE_SA))
        cr = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        if C.GOOGLE_SUBJECT:
            cr = cr.with_subject(C.GOOGLE_SUBJECT)
        _S['v'] = AuthorizedSession(cr)
    return _S['v']


def _rng(tab, a1=''):
    """Диапазон для АДРЕСА запроса — имя листа кодируется."""
    return urllib.parse.quote(tab) + (('!' + a1) if a1 else '')


def _a1(tab, a1):
    """Диапазон для ТЕЛА запроса — обычный A1, имя в одинарных кавычках.

    Внутри JSON кодировать нельзя: Google вернёт 400 Bad Request.
    """
    return f"'{tab}'!{a1}"


# Кэш чтений. У Google жёсткий предел: 60 чтений в минуту на один сервисный
# аккаунт — а аккаунт у нас один на всех. Приложение теперь обновляется живо,
# и несколько человек, читающих картину одновременно, этот предел выбирали.
# Сбитое чтение возвращалось как «пусто», и на пустоте система решала, что
# смена не открыта, а место свободно, — отсюда двойные приходы и «сброс».
#
# Ключ кэша — номер изменения ЛИСТА: запись в «Явку» не должна выбрасывать
# из памяти «Команду», «Точки» и «Пункты» — они меняются раз в неделю, а
# перечитывались после каждой отметки. Тридцать секунд сверху — на случай
# правки в таблице руками, мимо системы.
_CACHE = {}
_MANY = {}
CACHE_TTL = 30
# Сколько раз читали сеть, сколько взяли из кэша, сколько раз не смогли.
# Видно в /health — по нему считается, упираемся ли мы в предел Google.
_STAT = {'reads': 0, 'hits': 0, 'fails': 0}


def stats():
    return dict(_STAT, cached=len(_CACHE) + len(_MANY), version=_VER['n'])


def get(tab, a1='', render='FORMATTED_VALUE', strict=False):
    """Строки диапазона.

    strict=True — «этому чтению нельзя ошибиться»: не удалось прочитать,
    поднимаем ошибку вместо пустого списка. Так решают те, кто по чтению
    что-то запрещает или разрешает: пустота вместо данных снимает запрет.
    """
    key = (tab, a1, render)
    hit = _CACHE.get(key)
    if hit and hit[0] == _TABVER.get(tab, 0) and time.time() - hit[1] < CACHE_TTL:
        _STAT['hits'] += 1
        return hit[2]
    last = ''
    for n in range(3):
        try:
            r = session().get(B + C.DATA_SHEET + '/values/' + _rng(tab, a1),
                              params={'valueRenderOption': render}, timeout=60)
            _STAT['reads'] += 1
            if r.ok:
                rows = r.json().get('values', [])
                if len(_CACHE) > 200:
                    _CACHE.clear()
                _CACHE[key] = (_TABVER.get(tab, 0), time.time(), rows)
                return rows
            last = f'HTTP {r.status_code}'
            # Не наша ошибка — повторять бессмысленно (нет доступа, нет листа).
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:
            last = str(e)
        time.sleep(0.6 * (n + 1))
    _STAT['fails'] += 1
    print(f'чтение «{tab}»: {last}')
    if strict:
        raise IOError(f'таблица не отвечает ({last})')
    return []


def get_many(pairs):
    """Несколько диапазонов одним запросом. [(лист, A1)] → [[строки], ...]

    Шесть отдельных чтений — это шесть обращений к квоте Google и шесть
    сетевых задержек подряд, пока бот стоит. batchGet делает то же за один.
    """
    if not pairs:
        return []
    # Групповое чтение кэшируется так же, как обычное: пока ни один из его
    # листов не изменился, второй такой же запрос берётся из памяти. Именно
    # эти запросы и составляли основной расход — по восемь на каждое
    # открытие приложения.
    key = tuple(pairs)
    ver = tuple(_TABVER.get(t, 0) for t, _ in pairs)
    hit = _MANY.get(key)
    if hit and hit[0] == ver and time.time() - hit[1] < CACHE_TTL:
        _STAT['hits'] += 1
        return hit[2]
    q = '&'.join('ranges=' + urllib.parse.quote(f"'{t}'!{a}") for t, a in pairs)
    url = B + C.DATA_SHEET + '/values:batchGet?' + q + \
        '&valueRenderOption=FORMATTED_VALUE'
    last = ''
    for n in range(3):
        try:
            _STAT['reads'] += 1
            r = session().get(url, timeout=60)
            if r.ok:
                out = [v.get('values', [])
                       for v in r.json().get('valueRanges', [])]
                # Кэш не должен расти без края: разных запросов немного,
                # но данные в них с годами тяжелеют.
                if len(_MANY) > 40:
                    _MANY.clear()
                _MANY[key] = (ver, time.time(), out)
                return out
            last = f'HTTP {r.status_code}'
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:
            last = str(e)
        time.sleep(0.6 * (n + 1))
    _STAT['fails'] += 1
    print(f'групповое чтение: {last}')
    return [[] for _ in pairs]


# Счётчик изменений. Приложение не умеет узнавать «что-то произошло» иначе,
# как спросив. Спрашивать про всю картину дорого — это чтение таблицы; спросить
# номер изменения дёшево, он лежит в памяти. Номер меняется на любой записи,
# и телефон перечитывает данные только тогда, когда есть что перечитывать.
# Процесс один — бот и приложение живут вместе, поэтому счётчик общий.
_VER = {'n': 0}
_TABVER = {}
_LOG = []          # [(номер изменения, лист)] — что именно менялось


def version():
    return _VER['n']


def _touch(tab=''):
    _VER['n'] += 1
    if tab:
        _TABVER[tab] = _TABVER.get(tab, 0) + 1
    _LOG.append((_VER['n'], tab))
    if len(_LOG) > 300:
        del _LOG[:150]


def changed_since(n):
    """Какие листы изменились после номера n.

    Нужно, чтобы телефон не перечитывал картину из-за чужой работы:
    бариста на соседней точке сдал лист — тебя это не касается. Пусто —
    ничего не изменилось. None — лог не помнит так далеко, надо перечитать
    всё на всякий случай.
    """
    if not _LOG or _LOG[0][0] > n + 1:
        return None
    return sorted({t for v, t in _LOG if v > n and t})


def append(tab, rows):
    r = session().post(B + C.DATA_SHEET + '/values/' + _rng(tab, 'A2') + ':append',
                       params={'valueInputOption': 'USER_ENTERED'},
                       json={'values': rows}, timeout=60)
    r.raise_for_status()
    _touch(tab)
    rng = (r.json().get('updates', {}) or {}).get('updatedRange', '')
    return ''.join(c for c in rng.split('!')[-1].split(':')[0] if c.isdigit())


def put(tab, a1, rows, raw=False):
    """raw=True — записать как есть.

    Иначе Google «умно» разбирает значение: 0.72 в колонке рядом с временем
    он показал как 0:43, и число часов перестало быть числом.
    """
    session().put(B + C.DATA_SHEET + '/values/' + _rng(tab, a1),
                  params={'valueInputOption': 'RAW' if raw else 'USER_ENTERED'},
                  json={'values': rows}, timeout=60)
    _touch(tab)


# ── подготовка таблицы ───────────────────────────────────────────────────────
def ensure_structure():
    """Создаёт недостающие листы и шапки. Идемпотентно."""
    from . import forms as F          # внутри: forms сам обращается к storage
    from . import tasks as TSK
    from . import equipment as EQ
    from . import score as SC
    from . import roster as RS
    s = session()
    want = {C.TABS['fails']: ['Дата', 'Точка', 'Кто', 'Документ', '№', 'Блок', 'Пункт'],
            C.TABS['ideas']: ['Дата', 'Кто', 'Точка', 'Откуда', 'Текст', 'Статус', 'Решение'],
            C.TABS['items']: ['Документ', '№', 'Блок', 'Пункт', 'Норматив', 'Фото',
                              'Эталонное фото — вставь ссылку'],
            C.TABS['team']: ['chat_id', 'Имя', 'Точка', 'Роль', 'Активен',
                             'Отдел', 'Может подменить (позиции)',
                             'Может быть старшим'],
            C.TABS['points']: ['Код', 'Название', 'Адрес', 'Активна',
                               'Широта', 'Долгота', 'Радиус, м'],
            C.TABS['shift']: F.SHIFT_COLS,
            C.TABS['score']: SC.COLS,
            RS.TAB: RS.COLS,
            C.TABS['fixes']: ['Дата', 'Кто', 'Форма', 'Блок', '№', 'Текст пункта',
                              'Что поправить', 'Документ', 'Статус', 'Решение'],
            C.TABS['tasks']: TSK.TASK_COLS,
            C.TABS['equip']: EQ.EQUIP_COLS,
            'Ознакомление': READ_COLS,
            'Станции': STATION_COLS}
    for key, cl in C.forms().items():
        cols = F.cols_for(cl)
        if cols:
            want[cl['tab']] = cols
    for key, cl in C.checklists().items():
        want[cl['tab']] = FILL_COLS
    meta = s.get(B + C.DATA_SHEET, params={'fields': 'sheets.properties'}, timeout=60).json()
    have = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}
    add = [{'addSheet': {'properties': {'title': t, 'gridProperties': {
        'rowCount': 2000, 'columnCount': max(len(h), 8), 'frozenRowCount': 1}}}}
        for t, h in want.items() if t not in have]
    # Колонку добавили в шапку — вкладка должна стать шире, иначе запись
    # упрётся в границу сетки и строка не сохранится.
    for t, h in want.items():
        p = have.get(t)
        if p and p['gridProperties'].get('columnCount', 0) < len(h):
            add.append({'appendDimension': {
                'sheetId': p['sheetId'], 'dimension': 'COLUMNS',
                'length': len(h) - p['gridProperties']['columnCount']}})
    if add:
        s.post(B + C.DATA_SHEET + ':batchUpdate', json={'requests': add}, timeout=60
               ).raise_for_status()
    data = [{'range': _a1(t, 'A1'), 'values': [h]} for t, h in want.items()]
    items = []
    for key, cl in C.checklists().items():
        for b in cl['blocks']:
            for it in b['items']:
                items.append([cl['title'], it['n'], b['name'], it['text'],
                              it.get('norm', ''), 'да' if it.get('photo') else ''])
    data.append({'range': _a1(C.TABS['items'], 'A2'), 'values': items})
    s.post(B + C.DATA_SHEET + '/values:batchUpdate',
           json={'valueInputOption': 'RAW', 'data': data}, timeout=60).raise_for_status()
    return list(want)


# ── команда ──────────────────────────────────────────────────────────────────
_TEAM = {'ts': None, 'map': {}}
_READ = {'ts': None, 'rows': []}


def team(force=False):
    """chat_id → (имя, точка, роль, отдел, подменяет, старший)

    Отдел появился 21.08.2026: чек-листы режутся по отделам, и без него
    система не знает, чьи пункты показывать и с кого спрашивать.

    Квалификации (22.08.2026, по образцу графика кухни): какие ещё позиции
    человек умеет закрывать и может ли быть старшим. Без этого при отказе
    «не смогу» управляющий подбирает замену по памяти.
    """
    now = datetime.datetime.utcnow()
    # Минута, а не десять: роли и отделы правятся руками в таблице, и человек
    # ждёт, что приложение подхватит это сразу. Десятиминутный кэш выглядел
    # как «не сработало» и заставлял править второй раз.
    if not force and _TEAM['ts'] and (now - _TEAM['ts']).seconds < 60:
        return _TEAM['map']
    m = {}
    for r in get(C.TABS['team'], 'A2:H200'):
        r = list(r) + [''] * (8 - len(r))
        if str(r[0]).strip() and str(r[1]).strip():
            act = (r[4].strip().lower() if r[4] else 'да')
            if act in ('да', 'yes', '1', 'true', ''):
                can = [x.strip().lower() for x in str(r[6]).replace(';', ',').split(',')
                       if x.strip()]
                senior = str(r[7]).strip().lower() in ('да', 'yes', '1', 'true')
                m[str(r[0]).strip()] = (str(r[1]).strip(), str(r[2]).strip(),
                                        str(r[3]).strip(), str(r[5]).strip().lower(),
                                        can, senior)
    # Пустой ответ — это почти всегда сбой чтения, а не пустая команда:
    # get() глотает ошибку сети и квоты и возвращает []. Записать такую
    # пустоту в кэш значит выкинуть из системы всех до конца его жизни —
    # человек посреди работы получает «нет доступа». Держим прошлый состав.
    if not m and _TEAM['map']:
        print('команда: пустой ответ таблицы, оставляю прошлый состав')
        return _TEAM['map']
    _TEAM['ts'], _TEAM['map'] = now, m
    return m


def can_cover(who, dept):
    """Может ли человек закрыть эту позицию: своя или в списке подмен."""
    d = (dept or '').lower()
    if not d:
        return True
    if dept_of(who) == d:
        return True
    return d in (who[4] if len(who) > 4 else [])


def can_be_senior(who):
    """Отмечен ли человек как способный быть старшим смены на кухне."""
    return bool(who[5]) if len(who) > 5 else role_of(who) == 'senior'


def cover_for(point, dept, exclude=()):
    """Кто на точке может подменить на этой позиции. → [имена]

    Подбор замены по памяти управляющего — это «кто первый вспомнился».
    Список умений отвечает, кто действительно умеет.
    """
    out = []
    for v in team().values():
        if v[1] != point or v[0] in exclude:
            continue
        if role_of(v) in ('manager', 'coo'):
            continue
        if can_cover(v, dept):
            out.append(v[0])
    return sorted(out)


def role_of(who):
    r = (who[2] if len(who) > 2 else '').lower()
    if 'coo' in r or 'директор' in r or 'owner' in r:
        return 'coo'
    if 'правляющ' in r or 'manager' in r:
        return 'manager'
    if 'старш' in r or 'senior' in r:
        return 'senior'
    return 'staff'


def dept_of(who):
    """Отдел человека: кухня, касса, бар, зал, цех, доставка. Пусто — не задан."""
    return (who[3] if len(who) > 3 else '') or ''


_PTS = {'ts': None, 'map': {}, 'geo': {}}


def points_map(force=False):
    """Код точки → (название, адрес). Лист «Точки».

    Код — это то, чем точка подписана во всех данных; менять его нельзя.
    Название и адрес — только для показа человеку.
    """
    now = datetime.datetime.utcnow()
    # Минута, как и у команды: координаты правятся руками, ждать десять
    # минут после правки человек не станет.
    if not force and _PTS['ts'] and (now - _PTS['ts']).seconds < 60:
        return _PTS['map']
    m, geo = {}, {}
    for r in get(C.TABS['points'], 'A2:G50'):
        r = list(r) + [''] * (7 - len(r))
        code = str(r[0]).strip()
        if not code:
            continue
        act = (r[3].strip().lower() if r[3] else 'да')
        if act not in ('да', 'yes', '1', 'true', ''):
            continue
        m[code] = (str(r[1]).strip(), str(r[2]).strip())
        try:
            lat, lon = float(str(r[4]).replace(',', '.')), float(str(r[5]).replace(',', '.'))
            rad = float(str(r[6]).replace(',', '.')) if str(r[6]).strip() else 150.0
            geo[code] = (lat, lon, rad)
        except (ValueError, TypeError):
            pass
    # Как и с командой: пустой ответ — это сбой чтения, а не «точек нет».
    if not m and _PTS['map']:
        print('точки: пустой ответ таблицы, оставляю прошлые')
        return _PTS['map']
    _PTS['ts'], _PTS['map'], _PTS['geo'] = now, m, geo
    return m


def point_geo(code):
    """(широта, долгота, радиус в метрах) или None, если координаты не заданы."""
    points_map()
    return _PTS.get('geo', {}).get(code)


def point_label(code):
    """«ЗБ · Лохути 11» — если адрес задан, иначе просто код."""
    name, addr = points_map().get(code, ('', ''))
    tail = addr or name
    return f'{code} · {tail}' if tail else code


def points():
    """Все точки: из листа «Точки», плюс те, что встречаются у людей."""
    return sorted(set(points_map()) | {v[1] for v in team().values() if v[1]})


def managers_of(point):
    return [cid for cid, v in team().items()
            if v[1] == point and role_of(v) in ('manager', 'coo')]


def staff_of(point):
    """Кто заполняет на точке. Старший смены на кухне — тоже: кухонные чек-листы его."""
    return [cid for cid, v in team().items()
            if v[1] == point and role_of(v) in ('staff', 'senior')]


def workers_of(point, dept=None, roles=None):
    """Кому адресован конкретный чек-лист: своя точка, свой отдел, своя роль.

    Без этого напоминание про кухню приходит кассиру и уборщице — а шум
    в уведомлениях люди отключают вместе с полезным.
    """
    ds = [x.lower() for x in ([dept] if isinstance(dept, str) else (dept or [])) if x]
    out = []
    for cid, v in team().items():
        if v[1] != point:
            continue
        r = role_of(v)
        if r in ('manager', 'coo'):
            continue
        if roles and r not in roles:
            continue
        if ds and (dept_of(v) or '').lower() not in ds:
            continue
        out.append(cid)
    return out


def managers():
    """chat_id → точка, по всем управляющим. COO сюда не входит."""
    return {cid: v[1] for cid, v in team().items() if role_of(v) == 'manager'}


# ── фото ─────────────────────────────────────────────────────────────────────
def save_photo(raw_bytes, name):
    meta = {'name': name + '.jpg'}
    if C.PHOTO_FOLDER:
        meta['parents'] = [C.PHOTO_FOLDER]
    try:
        r = session().post(
            'https://www.googleapis.com/upload/drive/v3/files'
            '?uploadType=multipart&supportsAllDrives=true&fields=webViewLink',
            files={'data': ('m', json.dumps(meta), 'application/json'),
                   'file': (meta['name'], raw_bytes, 'image/jpeg')}, timeout=120)
        return r.json().get('webViewLink', '')
    except Exception:
        return ''


def save_photo_data_url(url, name):
    try:
        return save_photo(base64.b64decode(url.split(',', 1)[1]), name)
    except Exception:
        return ''


# ── запись заполнения ────────────────────────────────────────────────────────
def already_filled(key, day, point):
    """Кто и во сколько уже заполнял этот лист сегодня на этой точке.

    Этапы дня разведены по разным листам, и каждый этап делает одна смена —
    повтор здесь означает именно повтор, а не вторую смену.
    """
    cl = C.checklists()[key]
    for r in get(cl['tab'], 'A2:D'):
        if len(r) >= 4 and str(r[0]).strip() == day and str(r[1]).strip() == point:
            return f'{r[2]} в {r[3]}'
    return None


def filled_today(day, point, keys):
    """{ключ: {кто, во сколько, кому сдал}} по листам за один запрос.

    Нужно, чтобы приложение знало, какой этап уже сдан и кому именно сдают
    смену: приём открывается только названному человеку.
    """
    cls = C.checklists()
    keys = [k for k in keys if k in cls]
    out = {}
    for k, rows in zip(keys, get_many([(cls[k]['tab'], 'A2:S') for k in keys])):
        for r in rows:
            if len(r) >= 4 and str(r[0]).strip() == day and str(r[1]).strip() == point:
                out[k] = {'who': str(r[2]).strip(), 'at': str(r[3]).strip(),
                          'to': str(r[18]).strip() if len(r) > 18 else '',
                          'line': ''}
                break
    return out


def save_fill(key, day, point, who, marks, measured, photos, time_s,
              comment, seconds, part=None, to=''):
    """→ (выполнено, всего, [№ невыполненных], номер строки)"""
    cl = C.checklists()[key]
    names = {n: (b, t) for n, b, t in C.flat(key)}
    fails = sorted(n for n, v in marks.items() if not v)
    tot = cl['total']
    ok = tot - len(fails)
    meas = '; '.join(f'{cl["measures"][n]["q"]}: {v}' for n, v in measured.items()
                     if n in cl['measures'])
    row = [day, point, who, C.now().strftime('%H:%M'), time_s,
           ok, tot, round(ok / tot, 4) if tot else 0,
           ', '.join(str(n) for n in fails) if fails else '—', comment,
           meas, ' '.join(photos), round(seconds / 60, 1),
           '', '', '', '', PART_RU.get(part, ''), to]
    line = append(cl['tab'], [row])
    if fails:
        append(C.TABS['fails'], [[day, point, who, cl['title'], n,
                                  names[n][0], names[n][1]] for n in fails])
    return ok, tot, fails, line


def save_check(key, line, name, verdict, text=''):
    cl = C.checklists()[key]
    put(cl['tab'], f'N{line}:P{line}',
        [[name, C.now().strftime('%d.%m %H:%M'),
          text if verdict != 'ok' else '']])


def read_rows(force=False):
    """Лист ознакомлений целиком, с коротким кэшем."""
    now = datetime.datetime.utcnow()
    if not force and _READ['ts'] and (now - _READ['ts']).seconds < 60:
        return _READ['rows']
    try:
        rows = get('Ознакомление', 'A2:G')
    except Exception:
        rows = []
    _READ['ts'], _READ['rows'] = now, rows
    return rows


def read_codes(who):
    """Коды документов, с которыми человек уже ознакомился."""
    return {r[4].strip() for r in read_rows() if len(r) >= 5 and r[3].strip() == who}


def save_read(point, who, code, title, url):
    """Записать подпись «прочитал и согласился». Повтор не дублируем."""
    if code in read_codes(who):
        return False
    n = C.now()
    append('Ознакомление', [[n.strftime('%d.%m.%Y'), n.strftime('%H:%M'),
                             point, who, code, title, url]])
    _READ['ts'] = None
    return True


def _int(x):
    try:
        return int(float(str(x).replace(',', '.')))
    except (ValueError, TypeError):
        return 0


def _mins(t):
    try:
        h, m = str(t).split(':')
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def segments(day, point=None, who=None):
    """Отрезки работы на местах. [(номер строки, поля)]

    Основа для будущего расчёта зарплаты: где человек стоял, с какого
    по какое время и как туда попал — сам выбрал или принял смену.
    """
    out = []
    # strict: по этому чтению решается, занято ли место и открыт ли отрезок.
    # Пустота вместо данных означала бы «всё свободно» — и человек вставал
    # бы вторым на ту же станцию.
    for i, r in enumerate(get('Станции', 'A2:J', strict=True)):
        r = list(r) + [''] * 10
        if r[0].strip() != day:
            continue
        if point and r[1].strip() != point:
            continue
        if who and r[2].strip() != who:
            continue
        out.append((i + 2, {'point': r[1].strip(), 'who': r[2].strip(),
                            'station': r[3].strip(), 'part': r[4].strip(),
                            'start': r[5].strip(), 'end': r[6].strip(),
                            'minutes': _int(r[7]), 'how': r[8].strip(),
                            'from': r[9].strip()}))
    return out


def stations_taken(day, point):
    """{станция: имя} — места, на которых прямо сейчас кто-то стоит.

    Занято, пока отрезок открыт. Ушёл — место освободилось: делить
    занятость по «смене дня» неточно, человек мог уйти раньше.

    Один человек — одно место: если у него почему-то осталось несколько
    открытых отрезков, считаем текущим последний. Иначе он «занимает»
    полкухни, и приложение показывает ему чужой выбор вместо своего.
    """
    live = {}
    for line, v in segments(day, point):
        if not v['end']:
            live[v['who']] = (line, v['station'])
    return {st: who for who, (_, st) in live.items()}


def station_of(day, point, who):
    """Место, на котором человек стоит сейчас."""
    for _, v in segments(day, point, who):
        if not v['end']:
            return v['station']
    return ''


def close_segments(day, who, at=None):
    """Закрыть все открытые отрезки человека за день — на любой точке.

    Точку не спрашиваем нарочно: человек мог открыть смену на одной точке,
    передать её и поехать на другую. Оставить там открытый отрезок значит
    начислить ему часы за место, где его уже нет.
    """
    at = at or C.now().strftime('%H:%M')
    n = 0
    for line, v in segments(day, who=who):
        if v['end']:
            continue
        close_line(line, v, at)
        n += 1
    return n


def close_line(line, v, at):
    """Поставить конец отрезку и посчитать минуты."""
    a, b = _mins(v['start']), _mins(at)
    mins = ''
    if a is not None and b is not None:
        # За полночь смена переходит только если началась после полудня.
        # Иначе «конец раньше начала» — это сбитое время, и наивный
        # перенос на сутки записал бы человеку 23 часа работы.
        if b < a and a >= 12 * 60:
            b += 24 * 60
        if b < a:
            print(f'отрезок «{v["station"]}» у {v["who"]}: конец {at} раньше '
                  f'начала {v["start"]} — часы не посчитаны')
            mins = '0'
        else:
            mins = str(b - a)
    put('Станции', f'G{line}:H{line}', [[at, mins]], raw=True)


def hanging(day):
    """Отрезки, оставшиеся открытыми: человек не отметил уход.

    Без ночной уборки такой отрезок висит вечно, минуты не посчитаны,
    и в зарплате появляется дыра ровно там, где человек работал.
    → [(строка, поля)]
    """
    return [(line, v) for line, v in segments(day) if not v['end']]


def take_station(day, point, part, station, who, how='выбрал сам', frm=''):
    """Встать на место. → (получилось, кто его держит)

    Одно место — один человек одновременно. Прошлый отрезок этого человека
    закрывается: перешёл на другое место — предыдущее время посчитано,
    а не потеряно.
    """
    now = C.now().strftime('%H:%M')
    holder = stations_taken(day, point).get(station)
    if holder and holder != who:
        return False, holder
    if holder == who:
        return True, who              # уже стоит здесь — второй раз не пишем
    close_segments(day, who, now)
    line = append('Станции', [[day, point, who, station, part or '', now, '', '',
                               how, frm]])
    # Таблица отдаёт запись не мгновенно: два быстрых нажатия подряд читают
    # ещё старый список, и предыдущее место остаётся открытым. Тогда человек
    # числится сразу на трёх станциях. Подчищаем сразу — всё, кроме только
    # что записанной строки, закрываем.
    for l, v in segments(day, who=who):
        if not v['end'] and str(l) != str(line):
            close_line(l, v, now)
    return True, who


def start_day(day, point, who, part='', at=None):
    """Отметился на точке — время пошло, место ещё не выбрано.

    Иначе первые минуты дня не попадают ни в один отрезок, и сумма часов
    по местам всегда меньше явки. Пустая станция закроется, как только
    человек встанет на место.
    """
    if any(not v['end'] for _, v in segments(day, who=who)):
        return False
    append('Станции', [[day, point, who, '', part or '',
                        at or C.now().strftime('%H:%M'), '', '',
                        'отметил приход', '']])
    return True


def add_member(chat_id, name, point, role, dept=''):
    """Строка в «Команду». Повторный вызов обновляет, а не дублирует.

    Отдел не затираем: его проставляет управляющий руками, а бот при
    повторном добавлении человека о нём не знает.
    """
    rows = get(C.TABS['team'], 'A2:H200')
    for i, r in enumerate(rows):
        if r and str(r[0]).strip() == str(chat_id):
            r = list(r) + [''] * (8 - len(r))
            put(C.TABS['team'], f'A{i + 2}:H{i + 2}',
                [[str(chat_id), name, point, role, 'да', dept or r[5],
                  r[6], r[7]]])
            break
    else:
        append(C.TABS['team'],
               [[str(chat_id), name, point, role, 'да', dept, '', '']])
    team(force=True)
    return True


def save_fix(who, form, block, n, text, comment, doc=''):
    """Правка к пункту — прямо во время обхода, пока видно проблему."""
    return append(C.TABS['fixes'],
                  [[C.day_str(), who, form, block, n, text, comment, doc, 'Новая', '']])


def save_note(day, who, point, source, text):
    append(C.TABS['ideas'], [[day, who, point, source, text, 'Новая', '']])
