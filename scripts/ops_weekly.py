#!/usr/bin/env python3
"""Недельный отчёт COO — по понедельникам в 07:00.

Считает по фактическим данным, ничего не выдумывает. Если данных нет —
так и пишет: данных нет. Выводы делаются по правилам, и рядом с каждым
выводом стоит число, из которого он следует.

    python3 scripts/ops_weekly.py              # прошлая неделя (пн–вс)
    python3 scripts/ops_weekly.py 11.08.2026   # неделя, в которую попадает дата
    python3 scripts/ops_weekly.py --send       # посчитать и отправить в телеграм
"""
import os, sys, json, re, datetime
from collections import Counter, defaultdict
os.environ.setdefault('REQUESTS_CA_BUNDLE', '/etc/ssl/certs/ca-certificates.crt')
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

OPS = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'      # операционные данные
FIN = '1bTDELaAo8Ft9WIQqeWDFQQzp5rrDDHiRZ4VpFo-D4m8'      # Ромашка — Финансы 2026
B = 'https://sheets.googleapis.com/v4/spreadsheets/'
POINTS = ['ЗБ', 'ОВИР']
KINDS = [('Открытие смены', 'открытие'), ('Закрытие смены', 'закрытие')]
CRED = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'credentials', 'romashka-drive.json')
USER = 'base@azizkhaidarov.com'
SC = ['https://www.googleapis.com/auth/spreadsheets']

# пороги, по которым делаются выводы
MIN_MINUTES = 3          # быстрее — формальное заполнение
REPEAT_FAIL = 3          # столько раз за неделю — уже процесс, а не забывчивость
CHECK_GAP = 0.7          # доля проверенных управляющим ниже этой — второй контур не работает
TEMP_FRIDGE = (2, 6)
TEMP_FREEZER = -18


def _session():
    raw = os.environ.get('ROMASHKA_SA_JSON')
    info = json.loads(raw) if raw else json.load(open(CRED))
    c = service_account.Credentials.from_service_account_info(info, scopes=SC)
    try:
        c = c.with_subject(USER)
    except Exception:
        pass
    return AuthorizedSession(c)


def _d(s):
    t = str(s).strip()
    for f in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(t, f).date()
        except ValueError:
            pass
    if t.isdigit():          # Sheets отдаёт дату числом-серией, если формат слетел
        return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(t))
    return None


def plural(n, one, few, many):
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def week_of(day):
    """Понедельник и воскресенье недели, в которую попадает день."""
    mon = day - datetime.timedelta(days=day.weekday())
    return mon, mon + datetime.timedelta(days=6)


def _num(x):
    try:
        return float(str(x).replace(' ', '').replace(',', '.').replace('%', ''))
    except ValueError:
        return None


def collect(s, mon, sun):
    ranges = [t for t, _ in KINDS] + ['Невыполнено', 'Идеи и задачи']
    vr = s.get(B + OPS + '/values:batchGet',
               params={'ranges': ranges, 'valueRenderOption': 'FORMATTED_VALUE'},
               timeout=60).json().get('valueRanges', [])
    got = [(v.get('values') or [])[1:] for v in vr]
    inwk = lambda r: r and _d(r[0]) and mon <= _d(r[0]) <= sun

    fills = []
    for (tab, short), rows in zip(KINDS, got[:2]):
        for r in rows:
            if not inwk(r) or len(r) < 8:
                continue
            fills.append({
                'date': _d(r[0]), 'point': r[1], 'who': r[2], 'kind': short,
                'ok': _num(r[5]) or 0, 'tot': _num(r[6]) or 0,
                'fails': r[8] if len(r) > 8 else '',
                'meas': r[10] if len(r) > 10 else '',
                'min': _num(r[12]) if len(r) > 12 else None,
                'chk': (r[13].strip() if len(r) > 13 else ''),
                'diff': (r[15].strip() if len(r) > 15 else ''),
            })
    fails = [r for r in got[2] if inwk(r) and len(r) > 6]
    ideas = [r for r in got[3] if inwk(r) and len(r) > 4]
    return fills, fails, ideas


def revenue(s, mon, sun):
    """Выручка по точкам за неделю — из листа Данные_Poster."""
    v = s.get(B + FIN + '/values/Данные_Poster!A2:K',
              params={'valueRenderOption': 'FORMATTED_VALUE'},
              timeout=60).json().get('values', [])
    out = defaultdict(float)
    for r in v:
        if len(r) < 3:
            continue
        d = _d(r[0])
        if not d or not (mon <= d <= sun):
            continue
        val = _num(r[2])
        if val:
            out[str(r[1]).strip()] += val
    return out


def temps_out(fills):
    """Замеры вне нормы: (дата, точка, что, значение)."""
    bad = []
    for f in fills:
        for part in str(f['meas']).split(';'):
            if ':' not in part:
                continue
            name, val = part.split(':', 1)
            x = _num(val)
            if x is None:
                continue
            n = name.strip().lower()
            if 'холодильник' in n and not (TEMP_FRIDGE[0] <= x <= TEMP_FRIDGE[1]):
                bad.append((f['date'], f['point'], name.strip(), x))
            elif 'морозильник' in n and x > TEMP_FREEZER:
                bad.append((f['date'], f['point'], name.strip(), x))
    return bad


def build(s, mon, sun):
    fills, fails, ideas = collect(s, mon, sun)
    rev = revenue(s, mon, sun)
    days = (sun - mon).days + 1
    expect = len(POINTS) * days * len(KINDS)

    L = [f'📊 <b>Неделя {mon.strftime("%d.%m")} — {sun.strftime("%d.%m.%Y")}</b>', '']

    # 1. дисциплина
    L.append(f'<b>1. Заполнение</b>')
    L.append(f'Ожидалось {expect} · заполнено <b>{len(fills)}</b> '
             f'({round(len(fills) / expect * 100) if expect else 0}%)')
    for p in POINTS:
        pf = [f for f in fills if f['point'] == p]
        if not pf:
            L.append(f'   {p}: <b>ни одного</b>')
            continue
        avg = sum(f['ok'] / f['tot'] for f in pf if f['tot']) / len(pf) * 100
        mins = [f['min'] for f in pf if f['min'] is not None]
        am = f' · в среднем {round(sum(mins) / len(mins))} мин' if mins else ''
        L.append(f'   {p}: {len(pf)} из {days * len(KINDS)} · '
                 f'качество {round(avg)}%{am}')
    L.append('')

    # 2. второй контур
    chk = sum(1 for f in fills if f['chk'])
    L.append('<b>2. Проверка управляющим</b>')
    if fills:
        L.append(f'Проверено {chk} из {len(fills)} '
                 f'({round(chk / len(fills) * 100)}%)')
        diffs = [f for f in fills if f['diff']]
        for f in diffs[:5]:
            L.append(f'   ⚠️ {f["date"].strftime("%d.%m")} {f["point"]}: {f["diff"][:90]}')
    else:
        L.append('Проверять нечего — заполнений не было')
    L.append('')

    # 3. что валится чаще всего
    L.append('<b>3. Чаще всего не выполняется</b>')
    cnt = Counter((r[3], r[4], r[6]) for r in fails)     # документ, №, текст
    if cnt:
        for (doc, num, text), c in cnt.most_common(6):
            L.append(f'   {c}× · {text[:64]}')
    else:
        L.append('   Невыполненных пунктов нет' if fills else '   Данных нет')
    L.append('')

    # 4. замеры вне нормы
    bad = temps_out(fills)
    L.append('<b>4. Замеры вне нормы</b>')
    if bad:
        for d, p, name, x in bad[:6]:
            L.append(f'   {d.strftime("%d.%m")} {p} · {name}: <b>{x}</b>')
    else:
        L.append('   Все замеры в норме' if fills else '   Данных нет')
    L.append('')

    # 5. выручка
    if rev:
        L.append('<b>5. Выручка за неделю</b>')
        tot = 0
        for p in POINTS:
            if rev.get(p):
                tot += rev[p]
                L.append(f'   {p}: {rev[p]:,.0f} с'.replace(',', ' '))
        L.append(f'   <b>Сеть: {tot:,.0f} с</b>'.replace(',', ' '))
        L.append('')

    # 6. идеи с точек
    L.append('<b>6. Идеи и задачи с точек</b>')
    if ideas:
        for r in ideas[:6]:
            L.append(f'   • {r[4][:90]} <i>({r[1]}, {r[3]})</i>')
    else:
        L.append('   Новых нет')
    L.append('')

    # 7. выводы — только по правилам, с числом рядом
    L.append('<b>7. Выводы</b>')
    out = []
    if expect and len(fills) / expect < 0.7:
        out.append(f'Заполняют {round(len(fills) / expect * 100)}% смен — '
                   f'система пока не в работе. Это первое, что надо чинить: '
                   f'без ввода отчёт бессмысленный.')
    for p in POINTS:
        if not [f for f in fills if f['point'] == p] and expect:
            out.append(f'{p} не заполнила ни разу за неделю.')
    if fills and chk / len(fills) < CHECK_GAP:
        out.append(f'Управляющие подтвердили только {round(chk / len(fills) * 100)}% '
                   f'заполнений — второй контур не работает, проверять некому.')
    fast = [f for f in fills if f['min'] is not None and f['min'] < MIN_MINUTES]
    if fast:
        who = ', '.join(sorted({f['who'] for f in fast}))
        out.append(f'{len(fast)} {plural(len(fast), "заполнение", "заполнения", "заполнений")} '
                   f'быстрее {MIN_MINUTES} минут ({who}) — обойти точку за это время '
                   f'нельзя, скорее всего отмечали не глядя.')
    for (doc, num, text), c in cnt.most_common(3):
        if c >= REPEAT_FAIL:
            out.append(f'«{text[:60]}» не выполнен {c} '
                       f'{plural(c, "раз", "раза", "раз")} за неделю — '
                       f'это не забывчивость, а процесс. Разбирать причину, '
                       f'а не человека.')
    if bad:
        out.append(f'{len(bad)} {plural(len(bad), "замер", "замера", "замеров")} '
                   f'вне нормы — риск по пищевой безопасности. '
                   f'Проверить оборудование, а не только записи.')
    if not out:
        out.append('Отклонений, требующих вмешательства, не нашёл.' if fills
                   else 'Данных за неделю нет — выводы делать не из чего.')
    L += [f'   {i}. {x}' for i, x in enumerate(out, 1)]
    return '\n'.join(L)


def main():
    args = [a for a in sys.argv[1:] if a != '--send']
    day = _d(args[0]) if args else (datetime.date.today() - datetime.timedelta(days=7))
    mon, sun = week_of(day or datetime.date.today())
    s = _session()
    txt = build(s, mon, sun)
    if '--send' in sys.argv:
        tok = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        cid = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        if not tok or not cid:
            print('Нет TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID'); sys.exit(1)
        r = requests.post(f'https://api.telegram.org/bot{tok}/sendMessage',
                          json={'chat_id': cid, 'text': txt, 'parse_mode': 'HTML'},
                          timeout=30).json()
        print('отправлено' if r.get('ok') else r)
    else:
        print(re.sub(r'<[^>]+>', '', txt))


if __name__ == '__main__':
    main()
