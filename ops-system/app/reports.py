#!/usr/bin/env python3
"""Отчёты: дневной блок и недельная сводка с выводами.

Выводы делаются по правилам с порогами из конфига. Рядом с каждым выводом
стоит число, из которого он следует. Ничего не выдумывается.
"""
import datetime
from collections import Counter

from . import config as C
from . import storage as S
from . import bot as BOT


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
    cls = list(C.checklists().values())
    chunks = S.get_many([(cl['tab'], 'A2:P') for cl in cls])
    for cl, rows in zip(cls, chunks):
        for r in rows:
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


def day_block(day, point=None):
    """Короткий блок за день. point — сузить до одной точки (для управляющего)."""
    f = fills(day, day)
    pts = [point] if point else S.points()
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


def day_full(day, point=None):
    """Итог дня целиком: по каждой точке и каждому чек-листу — заполнен или нет,
    сколько выполнено, подтвердил ли управляющий."""
    f = fills(day, day)
    pts = [point] if point else S.points()
    L = [f'📅 <b>Итог дня — {day.strftime("%d.%m.%Y")}</b>'
         + (f' · {point}' if point else ''), '']
    for p in pts:
        L.append(f'<b>{p}</b>')
        for key, cl in C.checklists().items():
            x = next((y for y in f if y['point'] == p and y['kind'] == cl['title']), None)
            if not x:
                # событийный чек-лист не ждут каждый день — молчим о нём
                if cl.get('deadline'):
                    L.append(f'   ❌ {cl["title"].lower()} — <b>не заполнен</b>')
                continue
            pc = round(x['ok'] / x['tot'] * 100) if x['tot'] else 0
            chk = f'✅ подтвердил {x["chk"]}' if x['chk'] else '⚠️ не подтверждено'
            L.append(f'   {"✅" if pc == 100 else "⚠️"} {cl["title"].lower()}: '
                     f'{int(x["ok"])}/{int(x["tot"])} ({pc}%) · {x["who"]}')
            L.append(f'      {chk}')
            if x['diff']:
                L.append(f'      ⚠️ расхождение: {x["diff"][:120]}')
        L.append('')
    fl = [r for r in S.get(C.TABS['fails'], 'A2:G')
          if len(r) > 6 and _d(r[0]) == day and (not point or r[1] == point)]
    if fl:
        L.append('<b>Не выполнено за день</b>')
        L += [f'   ❌ {r[1]} · {r[6][:70]}' for r in fl[:20]]
        if len(fl) > 20:
            L.append(f'   … и ещё {len(fl) - 20}')
    else:
        L.append('<b>Невыполненных пунктов нет.</b>')
    bad = temps_out([x for x in f if not point or x['point'] == point])
    if bad:
        L.append('')
        L.append('<b>Замеры вне нормы</b>')
        L += [f'   ⚠️ {p} · {name}: <b>{x}</b> (норма {norm})'
              for d, p, name, x, norm in bad]
    return '\n'.join(L)


def temps_out(rows):
    """Замеры вне нормы. Нормы берём из чек-листов — другого источника нет.

    Раньше пороги были вписаны сюда числами, и отчёт мог противоречить тому,
    что система сказала человеку при вводе. Теперь правило одно на всех.
    """
    norms = {}
    for cl in C.checklists().values():
        for m in cl['measures'].values():
            norms[m['q'].strip().lower()] = m
    bad = []
    for f in rows:
        for name, x in parse_meas(f['meas']):
            m = norms.get(name.lower())
            if m and BOT.out_of_norm(x, m):
                bad.append((f['date'], f['point'], name, x, m['norm']))
    return bad


def parse_meas(text):
    """«Вопрос: 4; Другой вопрос: -20» → [(вопрос, число)]"""
    out = []
    for part in str(text).split(';'):
        if ':' not in part:
            continue
        name, val = part.rsplit(':', 1)
        x = _n(val)
        if x is not None:
            out.append((name.strip(), x))
    return out


def week(mon=None, point=None):
    today = C.today()
    mon = mon or (today - datetime.timedelta(days=today.weekday() + 7))
    sun = mon + datetime.timedelta(days=6)
    rows = fills(mon, sun)
    pts = [point] if point else S.points()
    if point:
        rows = [x for x in rows if x['point'] == point]
    kinds = len(C.scheduled())          # событийные в норму недели не входят
    expect = len(pts) * 7 * kinds

    L = [f'📊 <b>{C.COMPANY} · неделя {mon.strftime("%d.%m")} — '
         f'{sun.strftime("%d.%m.%Y")}</b>', '']

    L.append('<b>1. Заполнение</b>')
    sched = {cl['title'] for cl in C.scheduled().values()}
    reg = [x for x in rows if x['kind'] in sched]
    extra = len(rows) - len(reg)
    L.append(f'Ожидалось {expect} · заполнено <b>{len(reg)}</b>'
             + (f' ({round(len(reg) / expect * 100)}%)' if expect else '')
             + (f'\nПлюс разовых проверок: {extra}' if extra else ''))
    for p in pts:
        pf = [x for x in rows if x['point'] == p]
        if not pf:
            L.append(f'   {p}: <b>ни одного</b>')
            continue
        q = sum(x['ok'] / x['tot'] for x in pf if x['tot']) / len(pf) * 100
        mins = [x['min'] for x in pf if x['min'] is not None]
        sched = {cl['title'] for cl in C.scheduled().values()}
        reg = [x for x in pf if x['kind'] in sched]
        L.append(f'   {p}: {len(reg)} из {7 * kinds} · качество {round(q)}%'
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

    fl = [r for r in S.get(C.TABS['fails'], 'A2:G')
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
        for d, p, name, x, norm in bad[:6]:
            L.append(f'   {d.strftime("%d.%m")} {p} · {name}: <b>{x}</b> '
                     f'<i>(норма {norm})</i>')
    else:
        L.append('   Все замеры в норме' if rows else '   Данных нет')
    L.append('')

    ideas = [r for r in S.get(C.TABS['ideas'], 'A2:G')
             if len(r) > 4 and _d(r[0]) and mon <= _d(r[0]) <= sun]
    L.append('<b>5. Идеи и задачи с точек</b>')
    L += [f'   • {r[4][:90]} <i>({r[1]})</i>' for r in ideas[:6]] or ['   Новых нет']
    L.append('')

    out = []
    if expect and len(reg) / expect < 0.7:
        out.append(f'Заполняют {round(len(reg) / expect * 100)}% смен — '
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
