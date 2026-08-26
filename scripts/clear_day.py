#!/usr/bin/env python3
"""Удалить действия за один день. По умолчанию — за сегодня.

Чистит только следы работы: явку, отрезки, баллы, заполнения, журналы,
бланки, задачи. Справочники и обучение не трогает — иначе человек снова
становится новичком и теряет доступ к чек-листам.

Запуск: python3 scripts/clear_day.py [ДД.ММ.ГГГГ]
"""
import sys, urllib.parse
sys.path.insert(0, '/home/user/My-vault/scripts')
sys.path.insert(0, '/home/user/My-vault/ops-system')
from ops_docs import session
from app import config as C

SHEET = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'

# Справочники и то, что не является следом одного дня.
KEEP = {'Команда', 'Точки', 'Пункты', 'Оборудование', 'Дашборд', 'График',
        'Обучение', 'Ознакомление', 'Пример — как это выглядит'}


def main(day):
    s = session()
    meta = s.get(B + SHEET, params={'fields': 'sheets.properties'},
                 timeout=60).json()
    tabs = [x['properties']['title'] for x in meta['sheets']
            if x['properties']['title'] not in KEEP]
    q = '&'.join('ranges=' + urllib.parse.quote(f"'{t}'!A2:Z") for t in tabs)
    got = s.get(B + SHEET + '/values:batchGet?' + q, timeout=180).json()
    wiped, kept, files = 0, 0, []
    data = []
    for t, v in zip(tabs, got.get('valueRanges', [])):
        rows = v.get('values', [])
        if not rows:
            continue
        stay = [r for r in rows if not (r and str(r[0]).strip() == day)]
        gone = len(rows) - len(stay)
        if not gone:
            continue
        wiped += gone
        kept += len(stay)
        # Фото прихода — вместе со строкой явки, иначе останутся на Drive.
        for r in rows:
            if r and str(r[0]).strip() == day:
                for cell in r:
                    if isinstance(cell, str) and '/d/' in cell:
                        files.append(cell.split('/d/')[1].split('/')[0])
        data.append((t, stay, len(rows)))
        print(f'  {t[:40]:42}убрано {gone}, осталось {len(stay)}')

    for t, stay, was in data:
        s.post(B + SHEET + '/values:batchClear',
               json={'ranges': [f"'{t}'!A2:Z"]}, timeout=60).raise_for_status()
        if stay:
            s.post(B + SHEET + '/values/' + urllib.parse.quote(f"'{t}'!A2")
                   + ':append', params={'valueInputOption': 'USER_ENTERED'},
                   json={'values': stay}, timeout=120).raise_for_status()

    for fid in set(files):
        r = s.delete(f'https://www.googleapis.com/drive/v3/files/{fid}'
                     '?supportsAllDrives=true', timeout=60)
        print(f'  фото {fid} — {"удалено" if r.ok else r.status_code}')

    print(f'\nза {day}: убрано строк {wiped}, сохранено {kept}, '
          f'фото удалено {len(set(files))}')
    print('не тронуты:', ', '.join(sorted(KEEP)))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else C.day_str())
