#!/usr/bin/env python3
"""Операционный блок утреннего отчёта: что было с чек-листом открытия вчера.

Читает лист «ОПЕРАЦИОННЫЕ ДАННЫЕ (заполняет смена)» и отдаёт готовый текст
для телеграм-дайджеста. Отдельно запускается для проверки:

    python3 scripts/ops_daily_report.py            # за вчера
    python3 scripts/ops_daily_report.py 16.08.2026 # за конкретный день

Главный сигнал — не проценты, а факт: заполнен чек-лист или нет.
Незаполненный чек-лист хуже, чем чек-лист с невыполненными пунктами.
"""
import os, sys, json, datetime
os.environ.setdefault('REQUESTS_CA_BUNDLE', '/etc/ssl/certs/ca-certificates.crt')
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SS = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'
TAB = 'Открытие смены'
POINTS = ['ЗБ', 'ОВИР']
NFIXED = 4          # Дата · Точка · Старший смены · Время заполнения
CRED = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'credentials', 'romashka-drive.json')
USER = 'base@azizkhaidarov.com'
SC = ['https://www.googleapis.com/auth/spreadsheets']


def _session():
    raw = os.environ.get('ROMASHKA_SA_JSON')
    info = json.loads(raw) if raw else json.load(open(CRED))
    c = service_account.Credentials.from_service_account_info(info, scopes=SC)
    try:
        c = c.with_subject(USER)
    except Exception:
        pass
    return AuthorizedSession(c)


def _norm(d):
    """«16.08.2026», «2026-08-16», datetime → «16.08.2026»."""
    if isinstance(d, (datetime.date, datetime.datetime)):
        return d.strftime('%d.%m.%Y')
    t = str(d).strip()
    for f in ('%d.%m.%Y', '%Y-%m-%d', '%d.%m.%y'):
        try:
            return datetime.datetime.strptime(t, f).strftime('%d.%m.%Y')
        except ValueError:
            pass
    if t.isdigit():          # Sheets иногда отдаёт дату числом-серией
        base = datetime.date(1899, 12, 30)
        return (base + datetime.timedelta(days=int(t))).strftime('%d.%m.%Y')
    return t


def collect(s, day):
    """→ {точка: {'есть': bool, 'кто':…, 'всего':n, 'ок':n, 'провал':[(№,текст)]}}

    Читает сводный лист «Открытие смены» и детальный «Невыполнено».
    """
    v = s.get(B + SS + '/values:batchGet',
              params={'ranges': [TAB, 'Невыполнено'],
                      'valueRenderOption': 'FORMATTED_VALUE'}).json().get('valueRanges', [])
    summ = v[0].get('values', [])[1:] if v else []
    fails = v[1].get('values', [])[1:] if len(v) > 1 else []

    out = {p: {'есть': False, 'кто': '', 'открыли': '', 'всего': 0,
               'ок': 0, 'провал': [], 'коммент': ''} for p in POINTS}
    for r in summ:
        if len(r) < 7 or _norm(r[0]) != day:
            continue
        p = str(r[1]).strip()
        if p not in out:
            continue
        num = lambda x: int(str(x).replace(' ', '') or 0) if str(x).replace(' ', '').isdigit() else 0
        out[p].update({'есть': True, 'кто': r[2] if len(r) > 2 else '',
                       'открыли': r[4] if len(r) > 4 else '',
                       'ок': num(r[5]), 'всего': num(r[6]),
                       'коммент': r[9] if len(r) > 9 else ''})
    for r in fails:
        if len(r) < 6 or _norm(r[0]) != day:
            continue
        p = str(r[1]).strip()
        if p in out and out[p]['есть']:
            n = int(r[3]) if str(r[3]).isdigit() else 0
            out[p]['провал'].append((n, r[5]))
    for p in out:
        out[p]['провал'].sort()
    return out


def block(s, day):
    d = collect(s, day)
    lines = ['', '<b>🧾 Открытие смены — ' + day + '</b>']
    for p in POINTS:
        x = d[p]
        if not x['есть']:
            lines.append(f'• <b>{p}</b> — ⚠️ чек-лист НЕ заполнен')
            continue
        pct = round(x['ок'] / x['всего'] * 100) if x['всего'] else 0
        who = f" · {x['кто']}" if x['кто'] else ''
        mark = '✅' if pct == 100 else ('⚠️' if pct >= 80 else '❌')
        lines.append(f"• <b>{p}</b> {mark} {x['ок']}/{x['всего']} ({pct}%){who}")
        for n, t in x['провал'][:6]:
            lines.append(f'    ✗ {n}. {t}')
        if len(x['провал']) > 6:
            lines.append(f"    … и ещё {len(x['провал']) - 6}")
        if x['коммент']:
            lines.append(f"    💬 {x['коммент']}")
    if all(not d[p]['есть'] for p in POINTS):
        lines.append('')
        lines.append('<i>Ни одна точка не заполнила чек-лист. '
                     'Это первое, что нужно спросить на планёрке.</i>')
    return '\n'.join(lines)


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else _norm(
        datetime.date.today() - datetime.timedelta(days=1))
    print(block(_session(), _norm(day)).replace('<b>', '').replace('</b>', '')
          .replace('<i>', '').replace('</i>', ''))


if __name__ == '__main__':
    main()
