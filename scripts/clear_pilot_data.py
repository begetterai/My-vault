#!/usr/bin/env python3
"""Очистка данных обкатки перед тестовым запуском.

Чистит операционные вкладки: явка, баллы, обучение, заполнения чек-листов,
журналы, бланки, задачи, правки, невыполнено, график.
НЕ трогает справочники: Команда, Точки, Пункты, Оборудование, Дашборд.
Селфи прихода удаляются с Drive по ссылкам из «Явки».
"""
import sys, json, urllib.parse
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session

SHEET = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'

# Справочники — данные вводились руками, не обкаткой.
# «График» тоже не трогаем: это план на завтра, а не след обкатки. Стереть
# его значит снять с людей время начала смены, по которому считается
# опоздание, и позицию на день.
KEEP = {'Команда', 'Точки', 'Пункты', 'Оборудование', 'Дашборд',
        'График', 'Пример — как это выглядит'}


def main():
    s = session()
    meta = s.get(B + SHEET, params={'fields': 'sheets.properties'},
                 timeout=60).json()
    tabs = [sh['properties']['title'] for sh in meta['sheets']]
    wipe = [t for t in tabs if t not in KEEP]

    # селфи прихода — с Drive
    q = urllib.parse.quote("'Явка'!A2:K")
    rows = s.get(B + SHEET + '/values/' + q, timeout=60).json().get('values', [])
    files = []
    for r in rows:
        link = r[10] if len(r) > 10 else ''
        if '/d/' in link:
            files.append(link.split('/d/')[1].split('/')[0])
    for fid in files:
        r = s.delete(f'https://www.googleapis.com/drive/v3/files/{fid}'
                     '?supportsAllDrives=true', timeout=60)
        print(f'фото {fid} — {"удалено" if r.ok else r.status_code}')

    # строки данных, шапка остаётся
    r = s.post(B + SHEET + '/values:batchClear',
               json={'ranges': [f"'{t}'!A2:Z" for t in wipe]}, timeout=120)
    r.raise_for_status()
    print(f'очищено вкладок: {len(wipe)}, сохранено: {len(tabs) - len(wipe)}')
    print('сохранены:', ', '.join(t for t in tabs if t in KEEP))


if __name__ == '__main__':
    main()
