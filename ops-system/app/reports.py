#!/usr/bin/env python3
"""Отчёты: дневной блок и недельная сводка с выводами.

Выводы делаются по правилам с порогами из конфига. Рядом с каждым выводом
стоит число, из которого он следует. Ничего не выдумывается.
"""
import datetime
from collections import Counter

from . import config as C
from . import storage as S


def _d(x):
    t = str(x).strip()
    for f in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(t, f).date()
        except ValueError:
            pass
    if t.isdigit():
        return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(t))
    return None


def _n(x):
    try:
        return float(str(x).replace(' ', '').replace(',', '.').replace('%', ''))
    except ValueError:
        return None


def plural(n, one, few, many):
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def fills(since, until):
    out = []
    for key, cl in C.checklists().items():
        for r in S.get(cl['tab'], 'A2:P1000'):
            d = _d(r[0]) if r else None
            if not d or not (since <= d <= until) or len(r) < 8:
                continue
            out.append({'date': d, 'point': r[1], 'who': r[2], 'kind': cl['title'],
                        'ok': _n(r[5]) or 0, 'tot': _n(r[6]) or 0,
                        'meas': r[10] if len(r) > 10 else '',
                        'min': _n(r[12]) if len(r) > 12 else None,
                        'chk': (r[13].strip() if len(r) > 13 else ''),
                        'diff': (r[15].strip() if len(r) > 15 else '')})
    return out


def day_block(day):
    """Короткий блок за день — для утреннего дайджеста."""
    f = fills(day, day)
    pts = S.points()
    L = [f'<b>🧾 Чек-листы — {day.strftime("%d.%m.%Y")}</b>']
    for p in pts:
        pf = [x for x in f if x['point'] == p]
        if not pf:
            L.append(f'• <b>{p}</b> — ⚠️ не заполнено')
            continue
        for x in pf:
            pct = round(x['ok'] / x['tot'] * 100) if x['tot'] else 0
            mark = '✅' if pct == 100 else ('⚠️' if pct >= 80 else '❌')
            chk = '' if x['chk'] else ' · ⚠️ не проверено'
            L.append(f'• <b>{p}</b> {mark} {x["kind"].lower()} '
                     f'{int(x["ok"])}/{int(x["tot"])} ({pct}%) · {x["who"]}{chk}')
    return '\n'.join(L)


def temps_out(rows):
    bad = []
    for f in rows:
        for part in str(f['meas']).split(';'):
            if ':' not in part:
                continue
            name, val = part.split(':', 1)
            x = _n(val)
            if x is None:
                continue
            n = name.strip().lower()
            if 'холодильник' in n and not (2 <= x <= 6):
                bad.append((f['date'], f['point'], name.strip(), x))
            elif 'морозильник' in n and x > -18:
                bad.append((f['date'], f['point'], name.strip(), x))
    return bad


def week(mon=None):
    today = datetime.date.today()
    mon = mon or (today - datetime.timedelta(days=today.weekday() + 7))
    sun = mon + datetime.timedelta(days=6)
    rows = fills(mon, sun)
    pts = S.points()
    kinds = len(C.checklists())
    expect = len(pts) * 7 * kinds

    L = [f'📊 <b>{C.COMPANY} · неделя {mon.strftime("%d.%m")} — '
         f'{sun.strftime("%d.%m.%Y")}</b>', '']

    L.append('<b>1. Заполнение</b>')
    L.append(f'Ожидалось {expect} · заполнено <b>{len(rows)}</b>'
             + (f' ({round(len(rows) / expect * 100)}%)' if expect else ''))
    for p in pts:
        pf = [x for x in rows if x['point'] == p]
        if not pf:
            L.append(f'   {p}: <b>ни одного</b>')
            continue
        q = sum(x['ok'] / x['tot'] for x in pf if x['tot']) / len(pf) * 100
        mins = [x['min'] for x in pf if x['min'] is not None]
        L.append(f'   {p}: {len(pf)} из {7 * kinds} · качество {round(q)}%'
                 + (f' · в среднем {round(sum(mins) / len(mins))} мин' if mins else ''))
    L.append('')

    chk = sum(1 for x in rows if x['chk'])
    L.append('<b>2. Проверка управляющим</b>')
    L.append(f'Проверено {chk} из {len(rows)}'
             + (f' ({round(chk / len(rows) * 100)}%)' if rows else '')
             if rows else 'Заполнений не было')
    for x in [x for x in rows if x['diff']][:5]:
        L.append(f'   ⚠️ {x["date"].strftime("%d.%m")} {x["point"]}: {x["diff"][:90]}')
    L.append('')

    fl = [r for r in S.get(C.TABS['fails'], 'A2:G1000')
          if len(r) > 6 and _d(r[0]) and mon <= _d(r[0]) <= sun]
    cnt = Counter(r[6] for r in fl)
    L.append('<b>3. Чаще всего не выполняется</b>')
    if cnt:
        for text, c in cnt.most_common(6):
            L.append(f'   {c}× · {text[:64]}')
    else:
        L.append('   Невыполненных пунктов нет' if rows else '   Данных нет')
    L.append('')

    bad = temps_out(rows)
    L.append('<b>4. Замеры вне нормы</b>')
    if bad:
        for d, p, name, x in bad[:6]:
            L.append(f'   {d.strftime("%d.%m")} {p} · {name}: <b>{x}</b>')
    else:
        L.append('   Все замеры в норме' if rows else '   Данных нет')
    L.append('')

    ideas = [r for r in S.get(C.TABS['ideas'], 'A2:G500')
             if len(r) > 4 and _d(r[0]) and mon <= _d(r[0]) <= sun]
    L.append('<b>5. Идеи и задачи с точек</b>')
    L += [f'   • {r[4][:90]} <i>({r[1]})</i>' for r in ideas[:6]] or ['   Новых нет']
    L.append('')

    out = []
    if expect and len(rows) / expect < 0.7:
        out.append(f'Заполняют {round(len(rows) / expect * 100)}% смен — '
                   f'система пока не в работе.')
    for p in pts:
        if not [x for x in rows if x['point'] == p]:
            out.append(f'{p} не заполнила ни разу за неделю.')
    if rows and chk / len(rows) < C.CHECK_GAP:
        out.append(f'Управляющие подтвердили {round(chk / len(rows) * 100)}% '
                   f'заполнений — второй контур не работает.')
    fast = [x for x in rows if x['min'] is not None and x['min'] * 60 < C.MIN_SECONDS]
    if fast:
        who = ', '.join(sorted({x['who'] for x in fast}))
        out.append(f'{len(fast)} {plural(len(fast), "заполнение", "заполнения", "заполнений")} '
                   f'быстрее норматива ({who}) — скорее всего отмечали не глядя.')
    for text, c in cnt.most_common(3):
        if c >= C.REPEAT_FAIL:
            out.append(f'«{text[:60]}» не выполнен {c} {plural(c, "раз", "раза", "раз")} '
                       f'— это процесс, а не человек.')
    if bad:
        out.append(f'{len(bad)} {plural(len(bad), "замер", "замера", "замеров")} '
                   f'вне нормы — риск по пищевой безопасности.')
    L.append('<b>6. Выводы</b>')
    L += [f'   {i}. {x}' for i, x in enumerate(
        out or ['Отклонений, требующих вмешательства, нет.' if rows
                else 'Данных за неделю нет.'], 1)]
    return '\n'.join(L)
