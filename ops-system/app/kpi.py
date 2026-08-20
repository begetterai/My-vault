#!/usr/bin/env python3
"""KPI операционного департамента.

ГЛАВНОЕ РЕШЕНИЕ: «процент выполнения чек-листа» НЕ является главным
показателем и вообще не входит в индекс.

Причина та же, по которой баллы не начисляются за галочки. Сделай «% выполнено»
главной цифрой — и через месяц у всех будет 100 %, потому что поставить
галочку дешевле, чем сходить и проверить. Показатель, которым легко управлять
напрямую, перестаёт что-либо измерять.

Поэтому здесь два разных инструмента, и их нельзя смешивать:

  ИНДЕКС (0–100) — измеряет ИСПОЛНЕНИЕ. Все его составляющие проверяются
  не словами заполняющего, а фактами: часами, вторым человеком, приборами.

  ФЛАГИ — ловят ИМИТАЦИЮ. Они не входят в индекс и не складываются с ним.
  Точка может иметь индекс 95 и при этом гореть флагом «неделю ни одной
  находки» — и это важнее самого индекса.

Смешать их в одну цифру — значит спрятать имитацию за хорошим средним.
"""
import datetime
from collections import Counter, defaultdict

from . import config as C
from . import storage as S
from . import reports as R

# составляющая → (вес, что означает)
PARTS = {
    'Исполнение': (30, 'чек-листы сданы в срок'),
    'Контроль':   (30, 'управляющий подтвердил заполнение'),
    'Норма':      (20, 'замеры в пределах нормы'),
    'Явка':       (10, 'смена вышла вовремя, место подтверждено'),
    'Спокойствие': (10, 'нет критических происшествий и жалоб'),
}


def _pct(a, b):
    return round(a / b * 100) if b else None


# ── данные ───────────────────────────────────────────────────────────────────
def shifts(since, until, point=None):
    out = []
    for r in S.get(C.TABS['shift'], 'A2:J'):
        r = list(r) + [''] * 10
        d = R._d(r[0])
        if not d or not (since <= d <= until):
            continue
        if point and r[1].strip() != point:
            continue
        out.append({'date': d, 'point': r[1].strip(), 'who': r[2].strip(),
                    'in': r[3].strip(), 'out': r[4].strip(),
                    'late': R._n(r[6]) or 0, 'geo': r[7].strip()})
    return out


def journals(since, until, point=None):
    """Записи всех журналов за период."""
    cls = [cl for cl in C.by_type('journal').values()]
    out = []
    for cl, rows in zip(cls, S.get_many([(cl['tab'], 'A2:M') for cl in cls])):
        for r in rows:
            r = list(r) + [''] * 13
            d = R._d(r[0])
            if not d or not (since <= d <= until):
                continue
            if point and r[2].strip() != point:
                continue
            out.append({'date': d, 'kind': cl['title'], 'point': r[2].strip(),
                        'who': r[3].strip(), 'what': r[4].strip(),
                        'severity': r[8].strip(), 'status': r[11].strip()})
    return out


def measures_stats(rows):
    """(всего замеров, вне нормы) за период."""
    norms = {}
    for cl in C.checklists().values():
        for m in cl['measures'].values():
            norms[m['q'].strip().lower()] = m
    total = bad = 0
    from . import bot as BOT
    for f in rows:
        for name, x in R.parse_meas(f['meas']):
            m = norms.get(name.lower())
            if not m or m.get('ok_min') is None and m.get('ok_max') is None:
                continue
            total += 1
            if BOT.out_of_norm(x, m):
                bad += 1
    return total, bad


# ── индекс ───────────────────────────────────────────────────────────────────
def point_index(point, since, until):
    """Индекс точки 0–100 и его составляющие. None у составляющей — нет данных."""
    fills = [x for x in R.fills(since, until) if x['point'] == point]
    sched = {cl['title'] for cl in C.scheduled().values()}
    reg = [x for x in fills if x['kind'] in sched]
    days = (until - since).days + 1
    expect = days * len(C.scheduled())

    comp = {}

    # Исполнение: сдано в срок от того, сколько ожидалось.
    # Проверяется часами, а не словами.
    comp['Исполнение'] = _pct(min(len(reg), expect), expect)

    # Контроль: подтверждено вторым человеком. Заполняющий на это не влияет.
    chk = sum(1 for x in fills if x['chk'])
    comp['Контроль'] = _pct(chk, len(fills)) if fills else None

    # Норма: замеры в пределах нормы. Это прибор, а не мнение.
    tot_m, bad_m = measures_stats(fills)
    comp['Норма'] = _pct(tot_m - bad_m, tot_m) if tot_m else None

    # Явка: вышел вовремя и место подтверждено.
    sh = shifts(since, until, point)
    if sh:
        good = sum(1 for s in sh
                   if s['late'] <= 0 and 'ВНЕ ТОЧКИ' not in s['geo']
                   and 'не подтверждено' not in s['geo'])
        comp['Явка'] = _pct(good, len(sh))
    else:
        comp['Явка'] = None

    # Спокойствие: критические события бьют по показателю.
    jr = journals(since, until, point)
    heavy = sum(1 for j in jr if j['severity'] in ('Серьёзное', 'Критично')
                or j['severity'] in ('Недовольным', 'Скандал'))
    if reg:
        comp['Спокойствие'] = max(0, 100 - round(heavy / max(1, len(reg)) * 100 * 2))
    else:
        comp['Спокойствие'] = None

    # Итог считаем только по составляющим, где есть данные — иначе пустая
    # неделя выглядела бы как провал, а это враньё.
    num = den = 0
    for name, (w, _why) in PARTS.items():
        v = comp.get(name)
        if v is not None:
            num += v * w
            den += w
    total = round(num / den) if den else None
    return {'point': point, 'total': total, 'parts': comp,
            'fills': len(reg), 'expect': expect, 'checked': chk,
            'measures': (tot_m, bad_m), 'shifts': len(sh), 'heavy': heavy}


# ── флаги: ловят имитацию, в индекс не входят ────────────────────────────────
def flags(point, since, until):
    """Признаки того, что цифры красивые, а работы нет."""
    out = []
    fills = [x for x in R.fills(since, until) if x['point'] == point]
    if not fills:
        return out

    # 1. Ни одной находки. Идеальная точка не существует: если за неделю
    #    не нашли ни одного невыполненного пункта — значит не смотрели.
    with_fails = sum(1 for x in fills if x['ok'] < x['tot'])
    if len(fills) >= 5 and with_fails == 0:
        out.append(('Ни одной находки', len(fills),
                    f'{len(fills)} заполнений подряд без единого ❌. '
                    f'Так не бывает — почти наверняка отмечают не глядя.'))

    # 2. Заполняют быстрее норматива.
    fast = [x for x in fills if x['min'] is not None
            and x['min'] * 60 < C.MIN_SECONDS]
    if fast:
        who = ', '.join(sorted({x['who'] for x in fast}))
        out.append(('Быстрее норматива', len(fast),
                    f'{len(fast)} заполнений быстрее {C.MIN_SECONDS // 60} мин ({who})'))

    # 3. Управляющий подтверждает всё подряд без единого расхождения.
    chk = [x for x in fills if x['chk']]
    diff = [x for x in chk if x['diff']]
    if len(chk) >= 7 and not diff:
        out.append(('Проверка без расхождений', len(chk),
                    f'{len(chk)} подтверждений подряд и ни одного расхождения. '
                    f'Либо идеально, либо подтверждают не глядя.'))

    # 4. Один и тот же пункт валится раз за разом — это процесс, не человек.
    fl = [r for r in S.get(C.TABS['fails'], 'A2:G')
          if len(r) > 6 and R._d(r[0]) and since <= R._d(r[0]) <= until
          and r[1].strip() == point]
    cnt = Counter(r[6] for r in fl)
    for text, c in cnt.most_common(3):
        if c >= C.REPEAT_FAIL:
            out.append(('Повторяющийся провал', c, f'«{text[:60]}» — {c} раз'))

    # 5. Явка без подтверждения места.
    sh = shifts(since, until, point)
    nogeo = [s for s in sh if 'не подтверждено' in s['geo'] or 'ВНЕ ТОЧКИ' in s['geo']]
    if sh and len(nogeo) / len(sh) > 0.3:
        out.append(('Явка без места', len(nogeo),
                    f'{len(nogeo)} из {len(sh)} отметок без подтверждения точки'))

    # 6. Ни одного происшествия и ни одной жалобы за месяц — тоже сигнал.
    if (until - since).days >= 25 and not journals(since, until, point):
        out.append(('Тишина в журналах', 0,
                    'За месяц ни одного происшествия, поломки или жалобы. '
                    'Либо идеально, либо не записывают.'))
    return out


# ── отчёт ────────────────────────────────────────────────────────────────────
def period(kind, ref=None):
    """(начало, конец, подпись) для 'week' | 'month' | 'quarter' | 'year'."""
    d = ref or C.today()
    if kind == 'week':
        mon = d - datetime.timedelta(days=d.weekday())
        return mon, mon + datetime.timedelta(days=6), \
            f'неделя {mon.strftime("%d.%m")}–{(mon + datetime.timedelta(days=6)).strftime("%d.%m.%Y")}'
    if kind == 'month':
        a = d.replace(day=1)
        b = (a + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
        return a, b, a.strftime('%m.%Y')
    if kind == 'quarter':
        q = (d.month - 1) // 3
        a = d.replace(month=q * 3 + 1, day=1)
        end_m = q * 3 + 3
        b = (a.replace(month=end_m, day=28) + datetime.timedelta(days=4))
        b = b.replace(day=1) - datetime.timedelta(days=1)
        return a, b, f'{q + 1} квартал {d.year}'
    a = d.replace(month=1, day=1)
    return a, d.replace(month=12, day=31), str(d.year)


BAR = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']


def bar(v):
    if v is None:
        return '·'
    return BAR[min(7, max(0, int(v / 100 * 7)))]


def mark(v):
    if v is None:
        return '·'
    return '🟢' if v >= 85 else ('🟡' if v >= 70 else ('🟠' if v >= 50 else '🔴'))


def report(kind='week', point=None, ref=None):
    since, until, label = period(kind, ref)
    pts = [point] if point else S.points()
    L = [f'📈 <b>{C.COMPANY} · KPI · {label}</b>', '']
    for p in pts:
        ix = point_index(p, since, until)
        head = (f'{mark(ix["total"])} <b>{S.point_label(p)}</b> — '
                + (f'индекс <b>{ix["total"]}</b>' if ix['total'] is not None
                   else 'данных нет'))
        L.append(head)
        for name, (w, why) in PARTS.items():
            v = ix['parts'].get(name)
            L.append(f'   {bar(v)} {name}: '
                     + (f'<b>{v}%</b>' if v is not None else '—')
                     + f' <i>· {why}</i>')
        L.append(f'   <i>сдано {ix["fills"]} из {ix["expect"]} · '
                 f'подтверждено {ix["checked"]} · '
                 f'замеров {ix["measures"][0]}, вне нормы {ix["measures"][1]}</i>')
        fl = flags(p, since, until)
        if fl:
            L.append('   ⚠️ <b>Флаги внимания</b>')
            for title, n, why in fl:
                L.append(f'      · {title}: {why}')
        L.append('')
    L.append('<i>Индекс измеряет исполнение — то, что проверяется часами, '
             'вторым человеком и приборами. Флаги ловят имитацию и в индекс '
             'НЕ входят: точка может иметь высокий индекс и гореть флагом.</i>')
    return '\n'.join(L)


def people(kind='week', point=None, ref=None):
    """Кто как отработал за период. Без рейтинга «лучший» — только факты."""
    since, until, label = period(kind, ref)
    fills = R.fills(since, until)
    if point:
        fills = [x for x in fills if x['point'] == point]
    by = defaultdict(lambda: {'n': 0, 'ok': 0, 'tot': 0, 'fast': 0,
                              'found': 0, 'min': []})
    for x in fills:
        d = by[x['who']]
        d['n'] += 1
        d['ok'] += x['ok']
        d['tot'] += x['tot']
        if x['min'] is not None:
            d['min'].append(x['min'])
            if x['min'] * 60 < C.MIN_SECONDS:
                d['fast'] += 1
        if x['ok'] < x['tot']:
            d['found'] += 1
    sh = shifts(since, until, point)
    late = Counter(s['who'] for s in sh if s['late'] > 0)
    L = [f'👥 <b>Люди · {label}</b>', '']
    if not by:
        L.append('Заполнений за период нет.')
        return '\n'.join(L)
    for who, d in sorted(by.items(), key=lambda kv: -kv[1]['n']):
        mins = round(sum(d['min']) / len(d['min'])) if d['min'] else '—'
        L.append(f'<b>{who}</b> — {d["n"]} заполнений')
        L.append(f'   в среднем {mins} мин · нашёл проблемы в {d["found"]} из {d["n"]}'
                 + (f' · ⚠️ быстрее норматива: {d["fast"]}' if d['fast'] else ''))
        if late.get(who):
            L.append(f'   ⏰ опозданий: {late[who]}')
    L.append('')
    L.append('<i>«Нашёл проблемы» — это хорошо, а не плохо. Ноль находок '
             'при десятке заполнений — повод присмотреться.</i>')
    return '\n'.join(L)
