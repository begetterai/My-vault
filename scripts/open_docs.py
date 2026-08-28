#!/usr/bin/env python3
"""Открыть рабочие регламенты на чтение по ссылке.

Человек в смене должен мочь открыть инструкцию прямо из чек-листа или
тренинга — иначе ссылка есть, а по ней «нет доступа», и первоисточник
так никто и не читает.

Открываем только то, что нужно в работе. Закрытыми остаются:
  · кадровые и дисциплинарные (договор, сетка, профили, найм, аттестация),
  · схема баллов и реестры,
  · всё про открытие новых точек,
  · техкарты — там себестоимость и рецептура.

Запуск:  python3 scripts/open_docs.py [--do]
Без --do только показывает, что будет открыто.
"""
import sys
sys.path.insert(0, '/home/user/My-vault/scripts')
sys.path.insert(0, '/home/user/My-vault/ops-system')
from ops_docs import session
from app import config as C

# Группы кодов, которые НЕ открываем.
CLOSED_PREFIX = ('02-', '10-')          # кадры и дисциплина; открытие точки
CLOSED_CODES = {'00-REF-01',            # реестр всех документов
                '01-POL-02',            # баллы: надбавки и удержания
                '05-REF-01',            # реестр поставщиков
                '02-FRM-01'}            # трудовой договор
CLOSED_MARK = ('TTK', 'ТТК')            # техкарты

# Исключения: формально кадровые, но по сути правила смены — их человек
# должен читать, на них ссылаются тренинги «Гигиена и внешний вид».
OPEN_ANYWAY = {'02-POL-02',             # правило телефонов
               '02-POL-03'}             # внешний вид и личная гигиена


def docs():
    """{код: (название, id файла)} — по всем ссылкам в формах и блоках."""
    out = {}
    for cl in C.forms().values():
        for d in [cl.get('doc')] + [b.get('doc') for b in (cl.get('blocks') or [])]:
            if not d or not d.get('url'):
                continue
            url = d['url']
            fid = url.split('/d/')[1].split('/')[0] if '/d/' in url else ''
            if fid:
                out[d['code']] = (d.get('title', ''), fid)
    return out


def closed(code):
    up = code.upper()
    if code in OPEN_ANYWAY:
        return False
    return (code.startswith(CLOSED_PREFIX) or code in CLOSED_CODES
            or any(m in up for m in CLOSED_MARK))


def main(do=False):
    s = session()
    all_docs = docs()
    opening = {c: v for c, v in all_docs.items() if not closed(c)}
    keeping = {c: v for c, v in all_docs.items() if closed(c)}

    print(f'документов со ссылками: {len(all_docs)}')
    print(f'открываем: {len(opening)} · оставляем закрытыми: {len(keeping)}\n')
    for c, (t, _) in sorted(keeping.items()):
        print(f'  закрыт  {c:12} {t[:44]}')
    print()
    ok = err = 0
    for c, (t, fid) in sorted(opening.items()):
        if not do:
            print(f'  открыть {c:12} {t[:44]}')
            continue
        r = s.post(f'https://www.googleapis.com/drive/v3/files/{fid}/permissions'
                   '?supportsAllDrives=true&sendNotificationEmail=false',
                   json={'role': 'reader', 'type': 'anyone'}, timeout=60)
        if r.ok:
            ok += 1
            print(f'  ✓ {c:12} {t[:40]}')
        else:
            err += 1
            print(f'  ✗ {c:12} {t[:34]} — HTTP {r.status_code} {r.text[:60]}')
    if do:
        print(f'\nоткрыто: {ok} · не удалось: {err}')
    else:
        print('\nэто был показ. Запусти с --do, чтобы открыть.')


if __name__ == '__main__':
    main('--do' in sys.argv)
