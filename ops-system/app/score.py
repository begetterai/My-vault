#!/usr/bin/env python3
"""Баллы и уровни.

САМОЕ ВАЖНОЕ РЕШЕНИЕ ЗДЕСЬ — за что баллы НЕ начисляются.

Не начисляем за «выполнено 34 из 34». Кажется логичным, но это прямой
приказ ставить галочки не глядя: чем больше ✅, тем больше баллов. Через
месяц у всех будет 100 %, а на точках — грязь. Ровно так убивают
любую систему чек-листов.

Начисляем за поведение, которое нельзя подделать в свою пользу:
  · заполнил вовремя — проверяется часами, не словами;
  · управляющий подтвердил без расхождений — судит другой человек;
  · НАШЁЛ и записал проблему — награда за честность, а не за красивую цифру;
  · записал происшествие и что с ним сделал;
  · подал идею, которую приняли.

Штрафуем за просрочку, за расхождение при проверке и за заполнение
быстрее норматива.

Итог: выгодно ходить и смотреть, а не выгодно рисовать.
"""
import datetime

from . import config as C
from . import storage as S

# событие → (баллы, за что)
RULES = {
    'shift_on_time':  (3,  'Пришёл вовремя'),
    'fill_on_time':   (10, 'Чек-лист сдан в срок'),
    'fill_late':      (-5, 'Чек-лист сдан после дедлайна'),
    'fill_missed':    (-15, 'Чек-лист не сдан'),
    'found_issue':    (5,  'Нашёл и записал невыполненный пункт'),
    'confirmed':      (10, 'Управляющий подтвердил без расхождений'),
    'mismatch':       (-15, 'При проверке нашли расхождение'),
    'too_fast':       (-10, 'Заполнено быстрее норматива'),
    'journal':        (5,  'Записал происшествие или поломку'),
    'idea_accepted':  (15, 'Идея принята в работу'),
    'geo_missing':    (-3, 'Отметка без подтверждения места'),
    'check_done':     (5,  'Проверил заполнение смены'),
    'quiz_passed':    (20, 'Сдал тренинг'),
}

LEVELS = [(0, 'Новичок'), (150, 'Уверенный'), (400, 'Опора'),
          (800, 'Наставник'), (1500, 'Мастер')]


def add(point, who, event, link=''):
    """Записать балл. Тихо: человек видит итог в приложении, а не поток сообщений."""
    rule = RULES.get(event)
    if not rule:
        return
    pts, why = rule
    try:
        S.append(C.TABS['score'], [[C.day_str(), point, who, event, pts, why, link]])
    except Exception as e:
        print('баллы:', e)


def rows(since=None, until=None, point=None, who=None):
    out = []
    for r in S.get(C.TABS['score'], 'A2:G'):
        if len(r) < 5:
            continue
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
                    'event': r[3].strip(), 'pts': pts,
                    'why': r[5] if len(r) > 5 else ''})
    return out


def _date(x):
    for f in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(str(x).strip(), f).date()
        except ValueError:
            pass
    return None


def level(total):
    name = LEVELS[0][1]
    nxt = None
    for need, title in LEVELS:
        if total >= need:
            name = title
        elif nxt is None:
            nxt = (need, title)
    return name, nxt


def totals(since=None, until=None, point=None):
    """{имя: баллы} за период."""
    t = {}
    for r in rows(since, until, point):
        t[r['who']] = t.get(r['who'], 0) + r['pts']
    return dict(sorted(t.items(), key=lambda x: -x[1]))


def streak(who, point=None):
    """Сколько дней подряд человек сдавал чек-листы без просрочек."""
    bad = set()
    good = set()
    for r in rows(point=point, who=who):
        if r['event'] in ('fill_late', 'fill_missed', 'mismatch', 'too_fast'):
            bad.add(r['date'])
        if r['event'] in ('fill_on_time', 'confirmed'):
            good.add(r['date'])
    d, n = C.today(), 0
    while d in good and d not in bad:
        n += 1
        d -= datetime.timedelta(days=1)
    return n


def card(who, point):
    """Личная карточка для приложения."""
    today = C.today()
    week_start = today - datetime.timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    all_pts = sum(r['pts'] for r in rows(who=who))
    wk = sum(r['pts'] for r in rows(since=week_start, who=who))
    mo = sum(r['pts'] for r in rows(since=month_start, who=who))
    name, nxt = level(all_pts)
    board = totals(since=week_start, point=point)
    place = list(board).index(who) + 1 if who in board else None
    return {'total': all_pts, 'week': wk, 'month': mo, 'level': name,
            'next': ({'need': nxt[0] - all_pts, 'title': nxt[1]} if nxt else None),
            'streak': streak(who, point), 'place': place, 'of': len(board),
            'board': [{'who': k, 'pts': v} for k, v in list(board.items())[:5]]}


def week_board(point=None):
    today = C.today()
    mon = today - datetime.timedelta(days=today.weekday())
    return totals(since=mon, point=point)
