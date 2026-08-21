#!/usr/bin/env python3
"""Баллы: надбавки и удержания. Механика решена с Азизом 21.08.2026.

Документ: 01-POL-02 «Баллы: надбавки и удержания».
Заметка: 1-Области/Ромашка/Баллы-штрафы-механика.md

Главный принцип: сначала своя ежедневная работа, потом всё остальное.
За обязанности деньги не платят — обязанности дают допуск. Деньгами
оплачивается только то, что сверх.

Два счёта:
  · базовый — своя работа: +4 за полностью закрытый день, минусы за срывы;
  · доп     — сверх обязанностей: находки, замены, обучение.

Правило приоритета: базовый счёт в минусе — доп. счёт не платится вообще.
Иначе находками всегда можно перекрыть завал своей работы, и приоритет,
ради которого всё строится, исчезает.

1 балл = 1 сомони. Одна валюта: то, что человек не может посчитать в уме,
он считает несправедливым.
"""
import datetime

from . import config as C
from . import storage as S

BASE, EXTRA = 'базовый', 'доп'

# событие → (баллы, счёт, за что)
RULES = {
    # базовый счёт — своя ежедневная работа
    'day_closed':     (4,   BASE,  'День закрыт полностью'),
    'fill_missed':    (-50, BASE,  'Чек-лист не сдан'),
    'item_fail':      (-10, BASE,  'Невыполненный пункт — вина смены'),
    'mismatch':       (-30, BASE,  'Расхождение при проверке управляющим'),
    'late':           (-1,  BASE,  'Опоздание, за минуту'),
    # доп. счёт — сверх обязанностей; даёт только подтверждение управляющего
    'found_issue':    (5,   EXTRA, 'Нашёл и записал проблему'),
    'idea_accepted':  (30,  EXTRA, 'Идея принята в работу'),
    'replace_shift':  (30,  EXTRA, 'Вышел на замену за другого'),
    'taught':         (20,  EXTRA, 'Обучил новичка, тот сдал тренинг'),
    'quiz_passed':    (20,  EXTRA, 'Сдал тренинг с первого раза'),
    # наблюдение без денег: пороги не проверены на живой смене (01-POL-02)
    'too_fast':       (0,   BASE,  'Заполнено быстрее норматива — наблюдение'),
    'geo_missing':    (0,   BASE,  'Отметка без подтверждения места — наблюдение'),
}

COLS = ['Дата', 'Точка', 'Кто', 'Событие', 'Баллы', 'За что', 'Ссылка',
        'Счёт', 'Период', 'Спор', 'Решение по спору']

# Потолок начислений в день: без него «нашёл проблему» превращается
# в двадцать записей за смену и сто баллов из воздуха.
DAY_CAP = {'found_issue': 3, 'replace_shift': 1, 'taught': 1,
           'idea_accepted': 2}

# Что управляющий может начислить руками из приложения.
AWARDABLE = ('replace_shift', 'taught', 'idea_accepted', 'found_issue')


def period_of(d=None):
    """(начало, конец, подпись) расчётного периода: 1–15 и 16–конец месяца."""
    d = d or C.today()
    if d.day <= 15:
        a = d.replace(day=1)
        b = d.replace(day=15)
    else:
        a = d.replace(day=16)
        nxt = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        b = nxt - datetime.timedelta(days=1)
    return a, b, f'{a.strftime("%d.%m")}–{b.strftime("%d.%m.%Y")}'


def add(point, who, event, link='', qty=1):
    """Записать балл. Тихо: человек видит итог в приложении, а не поток сообщений.

    qty — множитель для событий, которые считаются в единицах: минуты
    опоздания, количество невыполненных пунктов.
    """
    rule = RULES.get(event)
    if not rule:
        return 0
    pts, kind, why = rule
    cap = DAY_CAP.get(event)
    if cap and today_count(who, event) >= cap:
        return 0
    total = pts * max(1, int(qty))
    if qty and qty > 1 and event == 'late':
        why = f'Опоздание {int(qty)} мин'
    try:
        S.append(C.TABS['score'],
                 [[C.day_str(), point, who, event, total, why, link,
                   kind, period_of()[2], '', '']])
    except Exception as e:
        print('баллы:', e)
    return total


def today_count(who, event):
    """Сколько раз событие уже начислено человеку сегодня."""
    d = C.today()
    return sum(1 for r in rows(since=d, until=d, who=who) if r['event'] == event)


def rows(since=None, until=None, point=None, who=None):
    out = []
    for r in S.get(C.TABS['score'], 'A2:K'):
        if len(r) < 5:
            continue
        r = list(r) + [''] * (11 - len(r))
        d = _date(r[0])
        if not d:
            continue
        if since and d < since or until and d > until:
            continue
        if point and r[1].strip() != point:
            continue
        if who and r[2].strip() != who:
            continue
        try:
            pts = int(float(str(r[4]).replace(',', '.')))
        except ValueError:
            continue
        out.append({'date': d, 'point': r[1].strip(), 'who': r[2].strip(),
                    'event': r[3].strip(), 'pts': pts, 'why': r[5],
                    'link': r[6], 'kind': (r[7] or BASE).strip(),
                    'period': r[8], 'dispute': r[9], 'verdict': r[10]})
    return out


def _date(x):
    for f in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(str(x).strip(), f).date()
        except ValueError:
            pass
    return None


def balance(who, point=None, d=None):
    """Итог периода по правилу приоритета.

    Возвращает оба счёта и то, что реально пойдёт в ведомость.
    """
    a, b, label = period_of(d)
    rs = [r for r in rows(since=a, until=b, point=point, who=who)
          if not _dropped(r)]
    base = sum(r['pts'] for r in rs if r['kind'] != EXTRA)
    extra = sum(r['pts'] for r in rs if r['kind'] == EXTRA)
    # Базовый в минусе — доп. не платится. Ровно это заставляет делать
    # свою работу раньше, чем искать сверх.
    payable = base + (extra if base >= 0 else 0)
    return {'period': label, 'from': a.strftime('%d.%m'), 'to': b.strftime('%d.%m'),
            'base': base, 'extra': extra, 'payable': payable,
            'blocked': base < 0,
            'days_left': max(0, (b - min(C.today(), b)).days),
            'lines': [{'date': r['date'].strftime('%d.%m'), 'pts': r['pts'],
                       'why': r['why'], 'kind': r['kind'], 'event': r['event'],
                       'dispute': r['dispute'], 'verdict': r['verdict'],
                       'line': i}
                      for i, r in _numbered(rs)]}


def _dropped(r):
    """Списание, снятое управляющим после спора, в счёт не идёт."""
    return str(r.get('verdict', '')).strip().lower().startswith('снят')


def _numbered(rs):
    """Строки с номерами в таблице — по ним приложение шлёт спор."""
    out, seen = [], {}
    all_rows = S.get(C.TABS['score'], 'A2:K')
    for i, raw in enumerate(all_rows):
        key = (str(raw[0]).strip() if raw else '', str(raw[2]).strip() if len(raw) > 2 else '',
               str(raw[3]).strip() if len(raw) > 3 else '',
               str(raw[4]).strip() if len(raw) > 4 else '')
        seen.setdefault(key, []).append(i + 2)
    for r in rs:
        key = (r['date'].strftime('%d.%m.%Y'), r['who'], r['event'], str(r['pts']))
        line = seen.get(key, [None]).pop(0) if seen.get(key) else None
        out.append((line, r))
    return out


def dispute(line, who, text):
    """Сотрудник не согласен со списанием. Пишем в строку, решает управляющий."""
    if not str(line).isdigit():
        return False
    r = S.get(C.TABS['score'], f'A{line}:K{line}')
    if not r or len(r[0]) < 3 or str(r[0][2]).strip() != who:
        return False
    S.put(C.TABS['score'], f'J{line}:K{line}', [[text[:300], '']])
    return True


def resolve(line, verdict, note=''):
    """Управляющий разобрал спор: «снято» или «оставлено»."""
    if not str(line).isdigit():
        return False
    S.put(C.TABS['score'], f'K{line}:K{line}',
          [[('снято — ' if verdict == 'drop' else 'оставлено — ') + note[:200]]])
    return True


def disputes(point=None):
    """Споры, которые ещё не разобраны."""
    a, b, _ = period_of()
    out = []
    for line, r in _numbered([x for x in rows(since=a, until=b, point=point)
                              if x['dispute'] and not x['verdict']]):
        out.append({'line': line, 'who': r['who'], 'point': r['point'],
                    'date': r['date'].strftime('%d.%m'), 'pts': r['pts'],
                    'why': r['why'], 'text': r['dispute']})
    return out


def close_day(d=None):
    """Раз в сутки: кто закрыл все свои чек-листы — тому +4.

    Считается по факту, а не по обещанию: берём людей, отметивших приход,
    и смотрим, сданы ли чек-листы их отдела за этот день.
    """
    from . import forms as F
    d = d or C.today()
    day = d.strftime('%d.%m.%Y')
    done = 0
    try:
        shifts = [r for r in S.get(C.TABS['shift'], 'A2:K')
                  if len(r) >= 4 and r[0].strip() == day and r[3].strip()]
    except Exception as e:
        print('закрытие дня:', e)
        return 0
    for r in shifts:
        point, who = r[1].strip(), r[2].strip()
        info = S.team()
        me = next((v for v in info.values() if v[0] == who and v[1] == point), None)
        role = S.role_of(me) if me else 'staff'
        dept = S.dept_of(me) if me else ''
        need = [cl for cl in C.for_role(role, dept, point).values()
                if cl.get('deadline')]
        if not need:
            continue
        if any(not S.already_filled(cl['key'], day, point) for cl in need):
            continue
        if any(x['event'] == 'day_closed' for x in rows(since=d, until=d, who=who)):
            continue
        add(point, who, 'day_closed')
        done += 1
    return done


def totals(since=None, until=None, point=None):
    """{имя: баллы} за период."""
    t = {}
    for r in rows(since, until, point):
        if _dropped(r):
            continue
        t[r['who']] = t.get(r['who'], 0) + r['pts']
    return dict(sorted(t.items(), key=lambda x: -x[1]))


def period_totals(point=None, d=None):
    """Итоги текущего периода по людям — для сводки к собранию."""
    a, b, label = period_of(d)
    people = {}
    for r in rows(since=a, until=b, point=point):
        if _dropped(r):
            continue
        p = people.setdefault(r['who'], {'who': r['who'], 'point': r['point'],
                                         'base': 0, 'extra': 0})
        p['extra' if r['kind'] == EXTRA else 'base'] += r['pts']
    for p in people.values():
        p['payable'] = p['base'] + (p['extra'] if p['base'] >= 0 else 0)
    return label, sorted(people.values(), key=lambda x: -x['payable'])


def streak(who, point=None):
    """Сколько дней подряд человек закрывал день полностью."""
    good, bad = set(), set()
    for r in rows(point=point, who=who):
        if r['event'] == 'day_closed':
            good.add(r['date'])
        if r['pts'] < 0:
            bad.add(r['date'])
    d, n = C.today(), 0
    while d in good and d not in bad:
        n += 1
        d -= datetime.timedelta(days=1)
    return n


def card(who, point):
    """Личная карточка для приложения: баланс периода и место в списке."""
    bal = balance(who, None)
    a, b, _ = period_of()
    board = totals(since=a, until=b, point=point)
    place = list(board).index(who) + 1 if who in board else None
    bal.update({'streak': streak(who, point), 'place': place, 'of': len(board),
                'board': [{'who': k, 'pts': v} for k, v in list(board.items())[:5]]})
    return bal


def week_board(point=None):
    a, b, _ = period_of()
    return totals(since=a, until=b, point=point)
