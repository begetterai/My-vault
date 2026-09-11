#!/usr/bin/env python3
"""Хранилище сайта: PostgreSQL. Единственное место, где система пишет данные.

Имена и сигнатуры функций намеренно повторяют `ops-system/app/storage.py`.
Механику — сроки, баллы, правила смены, обучение — мы переносим из
работающей системы почти без правок, и она обращается к хранилищу вот
этими именами. Совпадение имён и есть то, что превращает шесть недель
переписывания в перенос.

Чем отличается от предшественника:

  · человек опознаётся `person_id`, а не именем и не `chat_id`. Имя было
    ключом, и два тёзки означали общую явку и общие баллы;
  · запись всегда проверяется базой, а не молчит при отказе;
  · «не смог прочитать» и «ничего нет» — разные вещи: strict поднимает
    ошибку вместо пустого списка там, где по результату что-то запрещают.
"""
import os
import datetime
import hashlib
import hmac
import threading

import psycopg
from psycopg.rows import dict_row

DSN = os.environ.get('DATABASE_URL', 'postgresql:///romashka_test')

# Замок оставлен по той же причине, что и в работающей системе: все защиты
# устроены как «прочитал — решил — записал». В отличие от таблицы, здесь
# он нужен реже — часть гонок закрывают ограничения самой базы, — но
# операции, где решение принимается в коде, по-прежнему идут по одной.
WRITE_LOCK = threading.RLock()

_POOL = {'conn': None}


def conn():
    c = _POOL.get('conn')
    if c is None or c.closed:
        c = psycopg.connect(DSN, row_factory=dict_row, autocommit=True)
        _POOL['conn'] = c
    return c


def q(sql, *args, strict=False):
    """Строки запроса списком словарей."""
    try:
        with conn().cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall() if cur.description else []
    except Exception as e:
        print('чтение:', e)
        _POOL['conn'] = None
        if strict:
            raise IOError(f'база не отвечает ({e})')
        return []


def x(sql, *args):
    """Запись. Ошибка не проглатывается: «✅ записано» при пустой строке —
    это то, из-за чего терялись отметки ухода и часы смены."""
    with conn().cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone() if cur.description else None


def serial(fn):
    """Обёртка: выполняется по одному, без наложений."""
    def wrapped(*a, **kw):
        with WRITE_LOCK:
            return fn(*a, **kw)
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    return wrapped


# ── люди ─────────────────────────────────────────────────────────────────

def team():
    """{person_id: запись} по активным. Ключ — число, а не имя телеграма."""
    rows = q('SELECT id, name, point_code, role, dept, active, chat_id, '
             'can_cover, can_senior FROM people WHERE active ORDER BY name')
    return {r['id']: r for r in rows}


def person(pid, strict=False):
    r = q('SELECT * FROM people WHERE id = %s', pid, strict=strict)
    return r[0] if r else None


def by_login(login):
    r = q('SELECT * FROM people WHERE login = %s AND active', login)
    return r[0] if r else None


def role_of(v):
    return (v or {}).get('role', 'staff')


def dept_of(v):
    return (v or {}).get('dept', '')


def points_map():
    rows = q('SELECT * FROM points WHERE active ORDER BY code')
    return {r['code']: r for r in rows}


def points():
    return list(points_map())


def point_label(code):
    p = points_map().get(code)
    return p['label'] if p else code


def managers_of(point):
    """Кому идут тревоги точки: её управляющий и директор."""
    return [r['id'] for r in q(
        "SELECT id FROM people WHERE active AND (role = 'coo' "
        "OR (role = 'manager' AND point_code = %s))", point)]


def workers_of(point, dept=None, roles=None):
    """Кому адресован лист: своя точка, свой отдел, своя роль.

    Руководителей отсеиваем, только если лист не адресован им прямо.
    Иначе у управляющего выпадали из-под контроля его собственные листы —
    открытие и санитарный.
    """
    sql = ['SELECT id FROM people WHERE active AND point_code = %s']
    args = [point]
    if roles:
        sql.append('AND role = ANY(%s)')
        args.append(list(roles))
    else:
        sql.append("AND role NOT IN ('manager', 'coo')")
    if dept:
        ds = [dept] if isinstance(dept, str) else list(dept)
        sql.append('AND lower(dept) = ANY(%s)')
        args.append([d.lower() for d in ds])
    return [r['id'] for r in q(' '.join(sql), *args)]


# ── вход ─────────────────────────────────────────────────────────────────
# Алгоритм перенесён из работающей системы без изменений: PBKDF2-HMAC-SHA256,
# 200 000 повторов, отдельная соль на человека, сравнение без утечки времени.

ROUNDS = 200_000


def hash_password(password, salt=None):
    salt = salt or os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), ROUNDS)
    return f'{salt}${dk.hex()}'


def check_password(password, stored):
    try:
        salt, want = str(stored).split('$', 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), ROUNDS)
    return hmac.compare_digest(dk.hex(), want)


@serial
def set_login(pid, login, password):
    x('UPDATE people SET login = %s, pass_hash = %s WHERE id = %s',
      login, hash_password(password), pid)


# ── смена ────────────────────────────────────────────────────────────────

def shift_row(day, point, pid, strict=False):
    r = q('SELECT * FROM shifts WHERE day = %s AND person_id = %s'
          + (' AND point_code = %s' if point else ''),
          *( (day, pid, point) if point else (day, pid) ), strict=strict)
    return r[0] if r else None


@serial
def start_day(day, point, pid, part='one', at=None):
    """Отметка прихода. Повторная не пишется — и не задваивает опоздание."""
    if shift_row(day, None, pid):
        return False
    at = at or datetime.datetime.now().strftime('%H:%M')
    x('INSERT INTO shifts (day, point_code, person_id, part, came_at) '
      'VALUES (%s, %s, %s, %s, %s)', day, point, pid, part, at)
    return True


@serial
def close_day_shift(day, pid, at, hours):
    x('UPDATE shifts SET left_at = %s, hours = %s WHERE day = %s '
      'AND person_id = %s', at, hours, day, pid)


def segments(day, point=None, pid=None, strict=True):
    """Отрезки работы на местах. strict по умолчанию: по этому чтению
    решается, занято ли место — пустота вместо данных означала бы
    «всё свободно», и двое встали бы на одну станцию."""
    sql = 'SELECT * FROM segments WHERE day = %s'
    args = [day]
    if point:
        sql += ' AND point_code = %s'
        args.append(point)
    if pid:
        sql += ' AND person_id = %s'
        args.append(pid)
    return q(sql + ' ORDER BY id', *args, strict=strict)


def stations_taken(day, point):
    """{станция: person_id} — места, где сейчас кто-то стоит."""
    return {r['station']: r['person_id']
            for r in q("SELECT station, person_id FROM segments "
                       "WHERE day = %s AND point_code = %s AND end_at = ''",
                       day, point, strict=True)}


@serial
def take_station(day, point, station, pid, part='one', how='выбрал сам',
                 from_pid=None):
    """Встать на место. Одно место — один человек: это же гарантирует
    ограничение базы, так что гонка двух быстрых нажатий не пройдёт."""
    at = datetime.datetime.now().strftime('%H:%M')
    # Свои прошлые открытые отрезки закрываем: человек стоит на одном месте.
    x("UPDATE segments SET end_at = %s WHERE day = %s AND person_id = %s "
      "AND end_at = ''", at, day, pid)
    try:
        x('INSERT INTO segments (day, point_code, person_id, station, part, '
          'start_at, how, from_person) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
          day, point, pid, station, part, at, how, from_pid)
    except psycopg.errors.UniqueViolation:
        return False           # место успели занять
    return True


# ── заполнения ───────────────────────────────────────────────────────────

def filled_today(day, point, keys=None, strict=False):
    """{ключ: запись} по сданным сегодня листам точки."""
    sql = ('SELECT f.*, p.name AS who FROM fills f '
           'JOIN people p ON p.id = f.person_id '
           'WHERE f.day = %s AND f.point_code = %s')
    args = [day, point]
    if keys:
        sql += ' AND f.key = ANY(%s)'
        args.append(list(keys))
    return {r['key']: r for r in q(sql, *args, strict=strict)}


@serial
def save_fill(day, point, key, pid, marks, measured, total, comment='',
              part='', to_pid=None, minutes=None):
    """Записать заполнение вместе с отметками. Одной транзакцией:
    строка без отметок бесполезна, отметки без строки — мусор."""
    done = sum(1 for v in marks.values() if v)
    with conn().transaction():
        with conn().cursor() as cur:
            cur.execute(
                'INSERT INTO fills (day, point_code, key, person_id, done, '
                'total, minutes, comment, part, handed_to) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',
                (day, point, key, pid, done, total, minutes, comment,
                 part, to_pid))
            fid = cur.fetchone()['id']
            for n, ok in marks.items():
                cur.execute('INSERT INTO fill_marks (fill_id, n, ok, measured) '
                            'VALUES (%s,%s,%s,%s)',
                            (fid, int(n), bool(ok), str(measured.get(n, ''))))
    return fid


def add_photo(fill_id, n, path, sha=''):
    """Фото записывается только когда файл есть. Пустой путь база не примет:
    строка «фото есть» без файла хуже, чем честное «фото нет»."""
    x('INSERT INTO fill_photos (fill_id, n, path, sha256) VALUES (%s,%s,%s,%s)',
      fill_id, n, path, sha)


# ── служебное ────────────────────────────────────────────────────────────

def marked(day, key):
    return bool(q('SELECT 1 FROM done_log WHERE day = %s AND key = %s',
                  day, key))


def mark(day, key):
    """Отметить сделанным — после успеха, а не после попытки."""
    x('INSERT INTO done_log (day, key) VALUES (%s, %s) ON CONFLICT DO NOTHING',
      day, key)
