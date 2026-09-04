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

Запуск: python3 scripts/clear_pilot_data.py        — только показать
        python3 scripts/clear_pilot_data.py --go   — сделать
"""
import sys, datetime, urllib.parse
sys.path.insert(0, '/home/user/My-vault/scripts')
sys.path.insert(0, '/home/user/My-vault/ops-system')
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


def main(go):
    s = session()
    today = C.today()
    meta = s.get(B + SHEET, params={'fields': 'sheets.properties'},
                 timeout=60).json()
    props = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}
    tabs = list(props)
    wipe = [t for t in tabs if t not in KEEP and t not in (ROSTER, DASH)]

    # ── что уйдёт с Drive ────────────────────────────────────────────────
    PHOTO_COL.update(photo_columns())
    ranges, names = [], []
    for t, c in PHOTO_COL.items():
        if t in props and t not in KEEP:
            ranges.append(f"'{t}'!{c}2:{c}")
            names.append(t)
    files = set()
    if ranges:
        q = '&'.join('ranges=' + urllib.parse.quote(r) for r in ranges)
        got = s.get(B + SHEET + '/values:batchGet?' + q, timeout=120).json()
        for vr in got.get('valueRanges', []):
            for row in vr.get('values', []):
                cell = str(row[0]) if row else ''
                if '/d/' in cell:
                    for part in cell.replace(',', ' ').split():
                        if '/d/' in part:
                            files.add(part.split('/d/')[1].split('/')[0])

    # ── график: прошлые дни ──────────────────────────────────────────────
    plan = rows_of(s, ROSTER, 'A2:J')
    stay = []
    for r in plan:
        if not r or not str(r[0]).strip():
            continue
        try:
            d = datetime.datetime.strptime(str(r[0]).strip(), '%d.%m.%Y').date()
        except ValueError:
            stay.append(r)                    # дату не разобрали — не трогаем
            continue
        if d >= today:
            stay.append(r)
    gone = len([r for r in plan if r and str(r[0]).strip()]) - len(stay)

    # ── отчёт ────────────────────────────────────────────────────────────
    counts = {}
    q = '&'.join('ranges=' + urllib.parse.quote(f"'{t}'!A2:A") for t in wipe)
    got = s.get(B + SHEET + '/values:batchGet?' + q, timeout=120).json()
    for t, vr in zip(wipe, got.get('valueRanges', [])):
        n = len([x for x in vr.get('values', []) if x and str(x[0]).strip()])
        if n:
            counts[t] = n
    print(f'сегодня: {today.strftime("%d.%m.%Y")}')
    print(f'\nОЧИСТИТЬ ПОЛНОСТЬЮ — вкладок {len(wipe)}, '
          f'с данными {len(counts)}, строк {sum(counts.values())}:')
    for t, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f'  {n:5d}  {t}')
    print(f'\n{ROSTER}: удалить {gone} строк прошлых дней, оставить {len(stay)}')
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
                 + [f"'{ROSTER}'!A2:J", f"'{DASH}'!A1:I400"]},
           timeout=180).raise_for_status()
    if stay:
        s.put(B + SHEET + '/values/' + urllib.parse.quote(f"'{ROSTER}'!A2"),
              params={'valueInputOption': 'USER_ENTERED'},
              json={'values': [list(r) + [''] * (10 - len(r)) for r in stay]},
              timeout=60).raise_for_status()
    print(f'Таблица: очищено {len(wipe)} вкладок, '
          f'в «{ROSTER}» оставлено {len(stay)} строк')


if __name__ == '__main__':
    main('--go' in sys.argv)
