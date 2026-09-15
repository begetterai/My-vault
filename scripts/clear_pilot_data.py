#!/usr/bin/env python3
"""Очистка следов обкатки: начать отмечаться с чистого листа.

Решение Азиза 04.09.2026 после обкатки 29.08–03.09: стереть данные,
оставить пройденное обучение.

Что остаётся:
  · справочники — Команда, Точки, Пункты, Оборудование;
  · обучение — «Обучение» (сданные тренинги) и «Ознакомление» (подписи
    «регламент прочитан»): это один учебный контур, и стереть его значит
    заставить людей перечитывать 46 документов заново;
  · «Служебное» — журнал того, что расписание уже отправило сегодня;
    стереть его значит получить утренние напоминания второй раз;
  · «График» — только сегодняшний день и дальше: от состава берётся время
    начала смены, по нему считается опоздание (roster.start_of). Прошлые
    дни удаляются построчно.

Что стирается: явка, отрезки работы, баллы, правки, задачи, невыполнено,
идеи, журнал людей, все заполнения чек-листов, журналы и бланки. Плюс
снимки с Drive — строго из столбцов «Фото» этих вкладок.

Ссылки на регламенты («Ознакомление»), документы («Правки») и эталонные
фото («Пункты») не трогаем: это рабочие документы, а не следы обкатки.

Запуск: python3 scripts/clear_pilot_data.py         — только показать
        python3 scripts/clear_pilot_data.py --go    — сделать
        python3 scripts/clear_pilot_data.py --all   — стереть и сегодня
"""
import os, sys, datetime, urllib.parse
# Пути от самого файла, а не от /home/user: на GitHub Actions каталог
# другой, и с абсолютным путём импорт app.config не находится.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), 'ops-system'))
from ops_docs import session
from app import config as C

SHEET = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'
DRIVE = 'https://www.googleapis.com/drive/v3/files/'

KEEP = {'Команда', 'Точки', 'Пункты', 'Оборудование', 'Обучение',
        'Ознакомление', 'Служебное', 'Пример — как это выглядит'}
ROSTER = 'График'
DASH = 'Дашборд'

# Где в какой вкладке лежит столбец «Фото». Берём именно его, а не «любую
# ссылку вида /d/»: по соседству лежат регламенты и эталонные снимки,
# и удалить их значит сломать систему.
PHOTO_COL = {}          # вкладка → буква столбца


def photo_columns():
    """Столбцы «Фото» по типам форм — из тех же описаний, что и у сервера."""
    from app import forms as F
    from app import storage as S
    out = {'Явка': 'K'}                      # фото прихода
    def col(cols, name='Фото'):
        return chr(ord('A') + cols.index(name)) if name in cols else ''
    for cl in C.forms().values():
        cols = F.cols_for(cl) or (S.FILL_COLS if cl['type'] == 'checklist' else [])
        c = col(cols)
        if c:
            out[cl['tab']] = c
    return out


def rows_of(s, tab, a1):
    q = urllib.parse.quote(f"'{tab}'!{a1}")
    return s.get(B + SHEET + '/values/' + q, timeout=60).json().get('values', [])


def split_by_date(rows, today, everything=False):
    """(что стереть, что оставить). Оставляем сегодня и дальше.

    14.09.2026 это стоило смене ЗБ утра работы. Скрипт чистил вкладки
    целиком и различал дату только в «Графике»; запуск ушёл на полтора
    часа позже плана, люди уже отметились — и явка, станции, заполнения
    и 56 снимков за сегодня исчезли вместе с обкаткой. Правило Азиза:
    стираем прошлое, сегодняшнее не трогаем никогда.

    Дату не разобрали — строку оставляем: лучше лишняя строка, чем
    стёртая по ошибке.

    `everything` — разовый режим «--all»: сегодняшнее тоже стереть,
    смена проходит день заново. К «Графику» не применяется.
    """
    gone, stay = [], []
    for r in rows:
        if not r or not str(r[0]).strip():
            continue
        if everything:
            gone.append(r)
            continue
        try:
            d = datetime.datetime.strptime(str(r[0]).strip(), '%d.%m.%Y').date()
        except ValueError:
            stay.append(r)
            continue
        (stay if d >= today else gone).append(r)
    return gone, stay


def main(go, everything=False):
    s = session()
    today = C.today()
    meta = s.get(B + SHEET, params={'fields': 'sheets.properties'},
                 timeout=60).json()
    props = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}
    tabs = list(props)
    wipe = [t for t in tabs if t not in KEEP and t not in (ROSTER, DASH)]

    # ── что где остаётся ─────────────────────────────────────────────────
    # Читаем строки целиком, а не один столбец: то, что останется,
    # придётся записать обратно, а обрезанная строка потеряет данные.
    # «График» — та же обработка, что и остальные: A2:K, чтобы колонка
    # «Смена» не переехала напротив чужих людей.
    q = '&'.join('ranges=' + urllib.parse.quote(f"'{t}'!A2:Z") for t in wipe)
    got = s.get(B + SHEET + '/values:batchGet?' + q, timeout=120).json()
    data = {}
    for t, vr in zip(wipe, got.get('valueRanges', [])):
        data[t] = split_by_date(vr.get('values', []), today, everything)
    data[ROSTER] = split_by_date(rows_of(s, ROSTER, 'A2:K'), today)

    # ── что уйдёт с Drive ────────────────────────────────────────────────
    # Только из тех строк, которые стираем: снимок сегодняшнего дня
    # нужен вместе со своей строкой.
    PHOTO_COL.update(photo_columns())
    files, names = set(), []
    for t, c in PHOTO_COL.items():
        if t not in data or t in KEEP:
            continue
        names.append(t)
        i = ord(c) - ord('A')
        for row in data[t][0]:
            cell = str(row[i]) if len(row) > i else ''
            for part in cell.replace(',', ' ').split():
                if '/d/' in part:
                    files.add(part.split('/d/')[1].split('/')[0])

    # ── отчёт ────────────────────────────────────────────────────────────
    counts = {t: len(v[0]) for t, v in data.items() if t != ROSTER and v[0]}
    keep_n = sum(len(v[1]) for t, v in data.items() if t != ROSTER)
    print(f'сегодня: {today.strftime("%d.%m.%Y")}')
    print(f'\nСТЕРЕТЬ строки '
          f'{"ЦЕЛИКОМ, включая сегодня" if everything else "до сегодня"} — '
          f'вкладок {len(wipe)}, '
          f'с данными {len(counts)}, строк {sum(counts.values())}:')
    for t, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f'  {n:5d}  {t}')
    print(f'\nОСТАВИТЬ строк за сегодня и дальше: {keep_n}')
    print(f'{ROSTER}: удалить {len(data[ROSTER][0])} строк прошлых дней, '
          f'оставить {len(data[ROSTER][1])}')
    print(f'{DASH}: очистить целиком, пересоберётся сам в течение часа')
    print(f'\nУДАЛИТЬ С DRIVE: {len(files)} снимков '
          f'(столбцы «Фото» в {len(names)} вкладках)')
    print('\nОСТАВИТЬ НЕТРОНУТЫМ: ' + ', '.join(sorted(KEEP & set(tabs))))
    if not go:
        print('\nЭто был показ. Чтобы сделать: --go')
        return

    # ── делаем ───────────────────────────────────────────────────────────
    bad = 0
    for fid in sorted(files):
        r = s.delete(DRIVE + fid + '?supportsAllDrives=true', timeout=60)
        if not r.ok:
            bad += 1
    print(f'\nDrive: удалено {len(files) - bad} из {len(files)}'
          + (f', не удалось {bad}' if bad else ''))

    s.post(B + SHEET + '/values:batchClear',
           json={'ranges': [f"'{t}'!A2:Z" for t in wipe]
                 + [f"'{ROSTER}'!A2:K", f"'{DASH}'!A1:I400"]},
           timeout=180).raise_for_status()
    back = []
    for t, (_, stay) in data.items():
        if not stay:
            continue
        w = max(len(r) for r in stay)
        back.append({'range': f"'{t}'!A2",
                     'values': [list(r) + [''] * (w - len(r)) for r in stay]})
    if back:
        s.post(B + SHEET + '/values:batchUpdate',
               json={'valueInputOption': 'USER_ENTERED', 'data': back},
               timeout=180).raise_for_status()
    print(f'Таблица: очищено {len(wipe)} вкладок, '
          f'возвращено {keep_n + len(data[ROSTER][1])} строк за сегодня')


if __name__ == '__main__':
    main('--go' in sys.argv, '--all' in sys.argv)
