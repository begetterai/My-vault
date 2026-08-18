#!/usr/bin/env python3
"""Хранилище: Google Sheets + Drive. Единственное место, где система пишет данные.

Структура таблицы создаётся автоматически при первом запуске — клиенту
не нужно ничего готовить руками, только дать доступ сервисному аккаунту.
"""
import os, json, base64, datetime, urllib.parse
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
             'Фото — проверка ИИ']
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


def get(tab, a1='', render='FORMATTED_VALUE'):
    r = session().get(B + C.DATA_SHEET + '/values/' + _rng(tab, a1),
                      params={'valueRenderOption': render}, timeout=60)
    return r.json().get('values', []) if r.ok else []


def get_many(pairs):
    """Несколько диапазонов одним запросом. [(лист, A1)] → [[строки], ...]

    Шесть отдельных чтений — это шесть обращений к квоте Google и шесть
    сетевых задержек подряд, пока бот стоит. batchGet делает то же за один.
    """
    if not pairs:
        return []
    q = '&'.join('ranges=' + urllib.parse.quote(f"'{t}'!{a}") for t, a in pairs)
    r = session().get(B + C.DATA_SHEET + '/values:batchGet?' + q +
                      '&valueRenderOption=FORMATTED_VALUE', timeout=60)
    if not r.ok:
        return [[] for _ in pairs]
    return [v.get('values', []) for v in r.json().get('valueRanges', [])]


def append(tab, rows):
    r = session().post(B + C.DATA_SHEET + '/values/' + _rng(tab, 'A2') + ':append',
                       params={'valueInputOption': 'USER_ENTERED'},
                       json={'values': rows}, timeout=60)
    r.raise_for_status()
    rng = (r.json().get('updates', {}) or {}).get('updatedRange', '')
    return ''.join(c for c in rng.split('!')[-1].split(':')[0] if c.isdigit())


def put(tab, a1, rows):
    session().put(B + C.DATA_SHEET + '/values/' + _rng(tab, a1),
                  params={'valueInputOption': 'USER_ENTERED'},
                  json={'values': rows}, timeout=60)


# ── подготовка таблицы ───────────────────────────────────────────────────────
def ensure_structure():
    """Создаёт недостающие листы и шапки. Идемпотентно."""
    s = session()
    want = {C.TABS['fails']: ['Дата', 'Точка', 'Кто', 'Документ', '№', 'Блок', 'Пункт'],
            C.TABS['ideas']: ['Дата', 'Кто', 'Точка', 'Откуда', 'Текст', 'Статус', 'Решение'],
            C.TABS['items']: ['Документ', '№', 'Блок', 'Пункт', 'Норматив', 'Фото',
                              'Эталонное фото — вставь ссылку'],
            C.TABS['team']: ['chat_id', 'Имя', 'Точка', 'Роль', 'Активен']}
    for key, cl in C.checklists().items():
        want[cl['tab']] = FILL_COLS
    meta = s.get(B + C.DATA_SHEET, params={'fields': 'sheets.properties'}, timeout=60).json()
    have = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}
    add = [{'addSheet': {'properties': {'title': t, 'gridProperties': {
        'rowCount': 2000, 'columnCount': max(len(h), 8), 'frozenRowCount': 1}}}}
        for t, h in want.items() if t not in have]
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


def team(force=False):
    """chat_id → (имя, точка, роль)"""
    now = datetime.datetime.utcnow()
    if not force and _TEAM['ts'] and (now - _TEAM['ts']).seconds < 600:
        return _TEAM['map']
    m = {}
    for r in get(C.TABS['team'], 'A2:E200'):
        if len(r) >= 3 and str(r[0]).strip():
            act = (r[4].strip().lower() if len(r) > 4 and r[4] else 'да')
            if act in ('да', 'yes', '1', 'true', ''):
                m[str(r[0]).strip()] = (str(r[1]).strip(), str(r[2]).strip(),
                                        (r[3].strip() if len(r) > 3 else ''))
    _TEAM['ts'], _TEAM['map'] = now, m
    return m


def role_of(who):
    r = (who[2] if len(who) > 2 else '').lower()
    if 'coo' in r or 'директор' in r or 'owner' in r:
        return 'coo'
    if 'правляющ' in r or 'manager' in r:
        return 'manager'
    return 'staff'


def points():
    return sorted({v[1] for v in team().values() if v[1]})


def managers_of(point):
    return [cid for cid, v in team().items()
            if v[1] == point and role_of(v) in ('manager', 'coo')]


def staff_of(point):
    """Линейные сотрудники точки — те, кто заполняет."""
    return [cid for cid, v in team().items()
            if v[1] == point and role_of(v) == 'staff']


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
    """Кто и во сколько уже заполнял этот чек-лист сегодня на этой точке."""
    cl = C.checklists()[key]
    for r in get(cl['tab'], 'A2:D'):
        if len(r) >= 4 and str(r[0]).strip() == day and str(r[1]).strip() == point:
            return f'{r[2]} в {r[3]}'
    return None


def save_fill(key, day, point, who, marks, measured, photos, time_s,
              comment, seconds):
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
           meas, ' '.join(photos), round(seconds / 60, 1)]
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


def add_member(chat_id, name, point, role):
    """Строка в «Команду». Повторный вызов обновляет, а не дублирует."""
    rows = get(C.TABS['team'], 'A2:E200')
    for i, r in enumerate(rows):
        if r and str(r[0]).strip() == str(chat_id):
            put(C.TABS['team'], f'A{i + 2}:E{i + 2}',
                [[str(chat_id), name, point, role, 'да']])
            break
    else:
        append(C.TABS['team'], [[str(chat_id), name, point, role, 'да']])
    team(force=True)
    return True


def save_note(day, who, point, source, text):
    append(C.TABS['ideas'], [[day, who, point, source, text, 'Новая', '']])
