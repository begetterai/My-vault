#!/usr/bin/env python3
"""Отметить людей как прошедших обучение — для тестов.

Нужен, чтобы не проходить полтора часа тренингов перед каждой проверкой
механики. Пишет ровно то, что записало бы приложение: сдачу тренинга
и подпись под регламентом. Баллы не начисляет — они за живую работу,
а не за отметку в таблице.

Запуск: python3 scripts/mark_trained.py Азиз Владимир
"""
import sys, datetime, urllib.parse
sys.path.insert(0, '/home/user/My-vault/scripts')
sys.path.insert(0, '/home/user/My-vault/ops-system')
from ops_docs import session
from app import config as C

SHEET = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'


def team(s):
    r = s.get(B + SHEET + '/values/' + urllib.parse.quote("'Команда'!A2:H50"),
              timeout=60).json().get('values', [])
    out = []
    for x in r:
        x = list(x) + [''] * 8
        if x[1].strip():
            out.append((x[1].strip(), x[2].strip(), x[3].strip().lower(),
                        x[5].strip().lower()))
    return out


ROLE = {'управляющий': 'manager', 'директор': 'coo',
        'старший смены': 'senior'}


def main(names):
    s = session()
    now = C.now()
    day, tm = now.strftime('%d.%m.%Y'), now.strftime('%H:%M')
    quiz_rows, read_rows = [], []
    for name, point, role_ru, dept in team(s):
        if names and not any(name.startswith(n) for n in names):
            continue
        role = ROLE.get(role_ru, 'staff')
        qs = C.visible(role, 'quiz', dept, point)
        seen = set()
        for k, cl in qs.items():
            n = len(cl.get('questions', []))
            quiz_rows.append([day, tm, point, name, cl['title'], n, n,
                              cl.get('pass', n), 'да', 1, 1.0, ''])
            d = cl.get('doc') or {}
            if d.get('code') and d['code'] not in seen:
                seen.add(d['code'])
                read_rows.append([day, tm, point, name, d['code'],
                                  d.get('title', ''), d.get('url', '')])
        print(f'{name:20} {role:8} {dept or "—":12} тренингов {len(qs)}, '
              f'регламентов {len(seen)}')
    for tab, rows in (('Обучение', quiz_rows), ('Ознакомление', read_rows)):
        if not rows:
            continue
        s.post(B + SHEET + '/values/' + urllib.parse.quote(f"'{tab}'!A2")
               + ':append', params={'valueInputOption': 'USER_ENTERED'},
               json={'values': rows}, timeout=120).raise_for_status()
        print(f'{tab}: записано строк {len(rows)}')


if __name__ == '__main__':
    main(sys.argv[1:])
