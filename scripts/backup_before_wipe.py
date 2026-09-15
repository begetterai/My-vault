#!/usr/bin/env python3
"""Копия операционной таблицы перед очисткой.

Правило Азиза после 14.09.2026: нет копии — не чистить. До сих пор оно
жило только текстом в AGENDA, а в коде очистки шага копирования не было.
Теперь он отдельный и обязательный: не получилось скопировать — выходим
с ошибкой, и очистка не запускается.

Копия кладётся рядом с оригиналом, в ту же папку Drive.

Запуск: python3 scripts/backup_before_wipe.py
"""
import os, sys, datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from ops_docs import session

SHEET = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'
DRIVE = 'https://www.googleapis.com/drive/v3/files/'
TZ = float(os.environ.get('TZ_OFFSET', '5'))


def main():
    s = session()
    day = (datetime.datetime.utcnow()
           + datetime.timedelta(hours=TZ)).strftime('%d.%m.%Y')
    name = f'Операционные данные — перед очисткой {day}'

    r = s.get(DRIVE + SHEET,
              params={'fields': 'parents', 'supportsAllDrives': 'true'},
              timeout=60)
    r.raise_for_status()
    parents = r.json().get('parents') or []

    body = {'name': name}
    if parents:
        body['parents'] = parents
    r = s.post(DRIVE + SHEET + '/copy',
               params={'supportsAllDrives': 'true', 'fields': 'id,name'},
               json=body, timeout=180)
    r.raise_for_status()
    j = r.json()
    print(f'копия готова: {j["name"]}')
    print(f'https://docs.google.com/spreadsheets/d/{j["id"]}/edit')


if __name__ == '__main__':
    main()
