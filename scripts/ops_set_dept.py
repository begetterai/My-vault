"""Проставляет отдел в листе «Команда». Руководителям — «управление»:
фильтр по отделу их не касается (они видят все чек-листы), но пустая ячейка
выглядит как незаполненная работа.
"""
import sys, urllib.parse
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session

SH = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'
TAB = 'Команда'
# кого куда: имя → отдел
DEPT = {'Азиз': 'управление',
        'Владимир Митюков': 'управление',
        'Дилчу Шодибеков': 'управление'}

s = session()
rng = urllib.parse.quote(TAB) + '!A1:F200'
rows = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SH}/values/{rng}',
             timeout=60).json().get('values', [])
data, report = [], []
for i, r in enumerate(rows[1:], start=2):
    r = list(r) + [''] * (6 - len(r))
    name = r[1].strip()
    want = DEPT.get(name)
    if not want:
        report.append((name, r[3], r[5] or '—', 'не задан — нет в списке'))
        continue
    if r[5].strip().lower() == want:
        report.append((name, r[3], r[5], 'уже стоял'))
        continue
    data.append({'range': f"'{TAB}'!F{i}", 'values': [[want]]})
    report.append((name, r[3], want, 'проставлен'))

if data:
    resp = s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SH}/values:batchUpdate',
                  json={'valueInputOption': 'RAW', 'data': data}, timeout=60)
    resp.raise_for_status()

for name, role, dept, what in report:
    print(f'{name:22s} {role:14s} отдел: {dept:12s} {what}')
