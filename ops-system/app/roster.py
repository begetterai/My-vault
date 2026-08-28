#!/usr/bin/env python3
"""Состав смены на завтра: кто выходит, на какую позицию, во сколько.

Решение Азиза 21.08.2026. В 21:00 управляющий получает черновик — состав
предыдущего рабочего дня — правит его и отправляет. Людям сразу уходит
вопрос «Буду / Не смогу», к 21:30 состав завтрашней смены известен.

Почему состав, а не постоянный график: выходные у сети — это когда кто-то
кого-то заменяет. Постоянное расписание в такой схеме устаревает в первый же
день, а вечерний состав всегда описывает реальность.

Состав действует независимо от подтверждения. Иначе «не подтвердил» станет
способом уйти от ответственности за смену: промолчал — и завтра как будто
не работаешь.
"""
import datetime

from . import config as C
from . import storage as S

TAB = 'График'
COLS = ['Дата', 'Точка', 'Кто', 'Позиция', 'Начало', 'Вместо кого',
        'Подтверждение', 'Отметка', 'Составил', 'Когда составлен']

YES, NO, WAIT = 'буду', 'не смогу', ''

# Во сколько по умолчанию начинается смена позиции. Берётся из дедлайна
# чек-листа открытия минус час — но проще и честнее задать явно.
# Во сколько заступает каждая позиция. Задано Азизом 28.08.2026.
# Отсюда берётся время в составе смены и от него считается опоздание.
START = {'кухня': '08:00', 'цех': '08:00', 'зал': '08:00',
         'касса': '09:00', 'бар': '09:00', 'доставка': '10:00',
         # Управляющий приходит после открытия и уходит до закрытия —
         # у него свой час, и позиция ему нужна своя, иначе он попадает
         # в состав «на кухню» и получает кухонные станции.
         'управление': '10:00'}


def day_str(d):
    return d.strftime('%d.%m.%Y')


def hhmm(t):
    """«9:00» → «09:00». Таблица показывает время без ведущего нуля, и без
    нормализации повторная отправка состава выглядит как изменение времени —
    людям заново уходит вопрос «Буду / Не смогу»."""
    s = str(t).strip()
    if ':' not in s:
        return s
    h, m = s.split(':')[:2]
    try:
        return f'{int(h):02d}:{int(m):02d}'
    except ValueError:
        return s


def rows(day=None, point=None):
    out = []
    for i, r in enumerate(S.get(TAB, 'A2:J')):
        r = list(r) + [''] * (10 - len(r))
        if not str(r[0]).strip():
            continue
        if day and str(r[0]).strip() != day_str(day):
            continue
        if point and str(r[1]).strip() != point:
            continue
        out.append({'line': i + 2, 'day': r[0].strip(), 'point': r[1].strip(),
                    'who': r[2].strip(), 'dept': r[3].strip().lower(),
                    'start': hhmm(r[4]), 'instead': r[5].strip(),
                    'confirm': r[6].strip().lower(), 'mark': r[7].strip(),
                    'by': r[8].strip(), 'at': r[9].strip()})
    return out


def planned(day, point=None):
    """Кто по составу выходит в этот день."""
    return rows(day, point)


def for_person(day, who):
    """Строка состава конкретного человека или None."""
    return next((r for r in rows(day) if r['who'] == who), None)


def dept_of(day, who, fallback=''):
    """Позиция на день: состав главнее того, что записано в «Команде».

    Человек может завтра стоять на кассе, а послезавтра в зале — и чек-листы
    должны открыться те, что нужно.
    """
    r = for_person(day, who)
    return (r['dept'] if r and r['dept'] else fallback)


def start_of(day, who, fallback=''):
    """Во сколько у человека начинается смена — от этого считается опоздание."""
    r = for_person(day, who)
    return (r['start'] if r and r['start'] else fallback)


def last_roster(point, before):
    """Состав последнего дня, когда он был. По нему делается черновик."""
    days = {}
    for r in rows(point=point):
        try:
            d = datetime.datetime.strptime(r['day'], '%d.%m.%Y').date()
        except ValueError:
            continue
        if d < before:
            days.setdefault(d, []).append(r)
    if not days:
        return []
    return days[max(days)]


def template(point, day):
    """Черновик состава: состав предыдущего дня, а если его нет — команда точки.

    Черновик — это не догма, а способ не набирать одно и то же вручную:
    иначе управляющий начнёт отправлять состав не глядя.
    """
    prev = last_roster(point, day)
    if prev:
        return [{'who': r['who'], 'dept': r['dept'],
                 'start': r['start'] or START.get(r['dept'], ''),
                 'instead': ''} for r in prev]
    out = []
    for v in S.team().values():
        if v[1] != point or S.role_of(v) in ('coo',):
            continue
        d = (v[3] or '').lower()
        if d in ('', 'управление'):
            continue
        out.append({'who': v[0], 'dept': d, 'start': START.get(d, ''),
                    'instead': ''})
    return sorted(out, key=lambda x: (x['dept'], x['who']))


def save(day, point, people, author):
    """Записать состав на день. Повторная отправка заменяет прежний.

    → список тех, кому надо отправить вопрос «Буду / Не смогу».
    """
    ds = day_str(day)
    old = {r['who']: r for r in rows(day, point)}
    keep, seen = [], set()
    for p in people:
        who = str(p.get('who', '')).strip()
        # Один человек — одна строка на день: иначе состав врёт, а с ним
        # врут явка, опоздания и закрытый день.
        if not who or who in seen:
            continue
        seen.add(who)
        dept = str(p.get('dept', '')).strip().lower()
        start = hhmm(p.get('start', '')) or START.get(dept, '')
        instead = str(p.get('instead', '')).strip()
        was = old.get(who)
        # Уже подтверждённое не сбрасываем: человек ответил, повторно
        # дёргать его из-за правки в чужой строке незачем.
        same = was and was['dept'] == dept and was['start'] == start
        keep.append([ds, point, who, dept, start, instead,
                     was['confirm'] if same else WAIT,
                     was['mark'] if was else '', author,
                     C.now().strftime('%d.%m.%Y %H:%M')])
    _rewrite(day, point, keep)
    return [r[2] for r in keep if not r[6]]


def _rewrite(day, point, new_rows):
    """Состав дня переписывается целиком: старые строки этого дня гасим."""
    ds = day_str(day)
    all_rows = S.get(TAB, 'A2:J')
    out = []
    for r in all_rows:
        r = list(r) + [''] * (10 - len(r))
        if str(r[0]).strip() == ds and str(r[1]).strip() == point:
            continue
        if str(r[0]).strip():
            out.append(r)
    out += new_rows
    S.put(TAB, f'A2:J{len(out) + 1}', out)
    # хвост старых строк, если их стало меньше
    if len(all_rows) > len(out):
        blank = [[''] * 10 for _ in range(len(all_rows) - len(out))]
        S.put(TAB, f'A{len(out) + 2}:J{len(all_rows) + 1}', blank)


def confirm(day, who, answer):
    """Ответ сотрудника: «буду» или «не смогу»."""
    r = for_person(day, who)
    if not r:
        return False
    S.put(TAB, f'G{r["line"]}:G{r["line"]}', [[YES if answer else NO]])
    return True


def mark_show(day):
    """Проставить по факту явки: вышел или нет. Минусов не ставим — отметка.

    Причин невыхода слишком много: заболел, отпросился устно, семейное.
    Автомат ошибётся в половине случаев, разбирается это на собрании.
    """
    ds = day_str(day)
    came = {(r[1].strip(), r[2].strip()) for r in S.get(C.TABS['shift'], 'A2:K')
            if len(r) >= 4 and r[0].strip() == ds and r[3].strip()}
    out = []
    for r in rows(day):
        mark = 'вышел' if (r['point'], r['who']) in came else 'не вышел'
        if r['mark'] != mark:
            S.put(TAB, f'H{r["line"]}:H{r["line"]}', [[mark]])
        if mark == 'не вышел':
            out.append(r)
    return out


def summary(day, point=None):
    """Сводка по составу: кто подтвердил, кто нет, кто отказался."""
    rs = rows(day, point)
    if not rs:
        return None
    yes = [r for r in rs if r['confirm'] == YES]
    no = [r for r in rs if r['confirm'] == NO]
    wait = [r for r in rs if not r['confirm']]
    return {'day': day_str(day), 'all': rs, 'yes': yes, 'no': no, 'wait': wait}
