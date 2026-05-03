#!/usr/bin/env python3
"""
Обновляет трекер инвентаризаций и списаний из Poster.
Cron: 0 8 * * 1  (каждый понедельник в 08:00)

Источник: storage.getInventories + storage.getInventoryIngredients
"""
import json, os, sys, time, datetime, urllib.request, urllib.parse
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from create_inventory_tracker import (
    get_session, setup_sheets, HDR_SVOD, HDR_DETAIL, HDR_SPIS,
    status_color, UNIT_MAP
)

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')
TRELLO_CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'credentials', 'trello.json')
POSTER_BASE = 'https://joinposter.com/api'

LOCATIONS = [
    {'name': 'ЗБ',   'token': '398711:8746917c4a23ea897774040e039dfb76'},
    {'name': 'ОВИР', 'token': '935215:79675564e3d086d7e03d5fd56b50c8df'},
]

# ID таблицы (задаётся после первого запуска create_inventory_tracker.py)
# Если пусто — скрипт создаст новую таблицу
TRACKER_SS_ID = os.environ.get('INVENTORY_SS_ID',
               '1a-jEdK8wyC7DNaBKfB8VERdtia7NzM6FnbI34PqUjRA')

# Trello
TRELLO_BOARD  = '68b331d46b2eb8ddb94bcc72'  # Ромашка
LIST_ASAP     = '68b40f0028bb9b30bfd2da11'   # ASAP
MEMBER_VL     = '695d2ace7d0ed18e4ed17dd7'   # Владимир
MEMBER_DL     = '6969f00f3ed7a6c2b8f02b1c'   # Дилчу


def poster_get(token, method, params=None):
    p = {'token': token}
    if params:
        p.update(params)
    url = f"{POSTER_BASE}/{method}?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={'User-Agent': 'RomashkaBot/1.0'}),
            timeout=25
        ) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f'    ⚠️  Poster {method}: {e}')
        return {}


def fmt_date(date_str):
    """'2026-04-26 06:00:00' → '26.04.2026'"""
    try:
        return datetime.datetime.strptime(date_str[:10], '%Y-%m-%d').strftime('%d.%m.%Y')
    except Exception:
        return date_str[:10]


def safe_float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def fetch_inventories(token, name):
    """Возвращает список инвентаризаций с детальными данными по позициям."""
    r = poster_get(token, 'storage.getInventories')
    invs = r.get('response', [])
    if not invs:
        print(f'    {name}: инвентаризаций не найдено')
        return []

    result = []
    for inv in invs:
        inv_id   = inv.get('inventory_id')
        date_str = inv.get('date_set') or inv.get('date_start') or ''
        date     = fmt_date(date_str)

        ri = poster_get(token, 'storage.getInventoryIngredients',
                        {'inventory_id': inv_id})
        items = ri.get('response', {}).get('ingredients', [])
        if not items:
            continue

        result.append({
            'inv_id':   inv_id,
            'date':     date,
            'location': name,
            'items':    items,
        })
        time.sleep(0.3)

    return result


def build_rows(all_inventories):
    """Формирует три набора строк для трёх листов таблицы."""
    svod_rows   = []
    detail_rows = []
    spis_rows   = []

    for inv in all_inventories:
        date     = inv['date']
        loc      = inv['location']
        inv_id   = inv['inv_id']
        items    = inv['items']

        total_diff_c   = 0.0
        total_spis_c   = 0.0
        total_start_c  = 0.0
        n_with_diff    = 0

        for it in items:
            name      = it.get('item', '')
            unit_raw  = it.get('unit', it.get('db_unit', ''))
            unit      = UNIT_MAP.get(unit_raw, unit_raw)
            start     = safe_float(it.get('startrest'))
            start_c   = safe_float(it.get('startrestcurrency'))
            income    = safe_float(it.get('income'))
            charges   = safe_float(it.get('charges'))
            writeoff  = safe_float(it.get('writeoff'))
            writeoff_c= safe_float(it.get('writeoffcurrency'))
            est_rest  = safe_float(it.get('estimatedrest'))
            primecost = safe_float(it.get('primecost'))
            fact_rest = safe_float(it.get('factrest') or it.get('fact_rest_sum'))
            diff      = safe_float(it.get('difference'))
            diff_c    = safe_float(it.get('diffcurrency'))

            total_diff_c  += diff_c
            total_spis_c  += writeoff_c
            total_start_c += start_c
            if abs(diff) > 0.01:
                n_with_diff += 1

            # Процент расхождения относительно расчётного остатка
            if est_rest and abs(est_rest) > 0.001:
                pct_diff = (diff / est_rest) * 100
            else:
                pct_diff = None

            clr, status = status_color(pct_diff)

            detail_rows.append([
                date, loc, inv_id, name, unit,
                round(start, 3), round(income, 3), round(charges, 3),
                round(writeoff, 3), round(writeoff_c, 2),
                round(est_rest, 3), round(fact_rest, 3),
                round(diff, 3), round(diff_c, 2),
                round(pct_diff, 1) if pct_diff is not None else '',
                status,
            ])

            if writeoff > 0.001:
                spis_rows.append([
                    date, loc, inv_id, name, unit,
                    round(writeoff, 3), round(writeoff_c, 2), round(primecost, 2),
                ])

        # Процент позиций с расхождениями
        n_total = len(items)
        pct_items = round(n_with_diff / n_total * 100, 1) if n_total else 0.0

        # Статус сводки — по общей сумме расхождения vs общей стоимости
        if total_start_c > 0:
            overall_pct = abs(total_diff_c) / total_start_c * 100
        else:
            overall_pct = 0.0
        _, svod_status = status_color(overall_pct)

        svod_rows.append([
            date, loc, inv_id, n_total, n_with_diff,
            f'{pct_items}%',
            round(total_diff_c, 2),
            round(total_spis_c, 2),
            round(total_start_c, 2),
            svod_status,
        ])

    # Сортировка по дате убыв. (новые сверху)
    svod_rows.sort(key=lambda r: r[0], reverse=True)

    return svod_rows, detail_rows, spis_rows


def update_sheets(s, ss_id, svod_rows, detail_rows, spis_rows):
    from create_inventory_tracker import sheets

    def clear_write(sheet_name, headers, rows):
        # Очистить лист
        s.post(
            f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}'
            f'/values/{urllib.parse.quote(sheet_name)}:clear',
            json={}, timeout=30
        )
        # Записать
        values = [headers] + rows
        body = {'valueInputOption': 'USER_ENTERED', 'data': [
            {'range': f"'{sheet_name}'!A1", 'values': values}
        ]}
        sheets(s, 'values:batchUpdate', ss_id, body)

    clear_write('Сводка',         HDR_SVOD,   svod_rows)
    clear_write('Инвентаризации', HDR_DETAIL, detail_rows)
    clear_write('Списания',        HDR_SPIS,   spis_rows)


def trello_create_task(title, desc, due_date, member_ids):
    """Создаёт карточку в Trello."""
    try:
        creds = json.load(open(TRELLO_CREDS))
        key, token = creds['api_key'], creds['token']
        params = {
            'key': key, 'token': token,
            'idList': LIST_ASAP,
            'name': title,
            'desc': desc,
            'due': due_date,
            'idMembers': ','.join(member_ids),
        }
        url = f"https://api.trello.com/1/cards?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, method='POST',
                                     headers={'User-Agent': 'RomashkaBot/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            card = json.loads(r.read().decode())
        print(f'  ✅ Trello: {title}')
        return card.get('id')
    except Exception as e:
        print(f'  ⚠️  Trello: {e}')
        return None


def add_checklist(card_id, items):
    try:
        creds = json.load(open(TRELLO_CREDS))
        key, token = creds['api_key'], creds['token']

        # Создать чеклист
        params = {'key': key, 'token': token, 'idCard': card_id, 'name': 'Чеклист'}
        url = f"https://api.trello.com/1/checklists?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, method='POST', headers={'User-Agent': 'Bot/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            cl = json.loads(r.read().decode())
        cl_id = cl['id']

        # Добавить пункты
        for item in items:
            p2 = {'key': key, 'token': token, 'name': item, 'checked': 'false'}
            u2 = f"https://api.trello.com/1/checklists/{cl_id}/checkItems?{urllib.parse.urlencode(p2)}"
            r2 = urllib.request.Request(u2, method='POST', headers={'User-Agent': 'Bot/1.0'})
            with urllib.request.urlopen(r2, timeout=15) as rr:
                pass
    except Exception as e:
        print(f'  ⚠️  Checklist: {e}')


def create_trello_tasks():
    """Создаёт задачи на инвентаризацию для управляющих."""
    today   = datetime.date.today()
    # Следующий понедельник
    days_ahead = (7 - today.weekday()) % 7 or 7
    next_monday = (today + datetime.timedelta(days=days_ahead)).isoformat() + 'T10:00:00.000Z'
    week = today.strftime('%d.%m')

    checklist = [
        'Все поставки дня оприходованы в Poster',
        'Все списания дня внесены в Poster',
        'Физический подсчёт проведён (весы, штуки)',
        'Данные внесены в Poster (Склад → Инвентаризации)',
        'Расхождения просмотрены',
        'Расхождения > 500с — сообщено директору',
    ]

    for loc, member_id in [('ЗБ', MEMBER_VL), ('ОВИР', MEMBER_DL)]:
        title = f'Еженедельная инвентаризация — {loc} (от {week})'
        desc  = (
            f'Провести полную инвентаризацию склада {loc}.\n\n'
            f'Инструкция: Drive → УК Ромашка → Тренинг по инвентаризации (V.1)\n\n'
            f'После завершения: результаты автоматически попадут в трекер.'
        )
        card_id = trello_create_task(title, desc, next_monday, [member_id])
        if card_id:
            add_checklist(card_id, checklist)
            time.sleep(0.3)


def main(create_new=False, ss_id=None):
    s = get_session()

    if not ss_id:
        ss_id = TRACKER_SS_ID
    if not ss_id or create_new:
        from create_inventory_tracker import create_spreadsheet, setup_sheets
        print('Создаю новую таблицу...')
        ss_id = create_spreadsheet(s)
        setup_sheets(s, ss_id, [], [], [])

    print(f'Таблица: https://docs.google.com/spreadsheets/d/{ss_id}/edit\n')

    # Fetch Poster data
    all_invs = []
    for loc in LOCATIONS:
        print(f'  {loc["name"]}: загружаю инвентаризации...')
        invs = fetch_inventories(loc['token'], loc['name'])
        print(f'    → {len(invs)} инвентаризаций')
        all_invs.extend(invs)
        time.sleep(0.5)

    if not all_invs:
        print('Нет данных из Poster.')
        return ss_id

    print('\nФормирую строки...')
    svod_rows, detail_rows, spis_rows = build_rows(all_invs)
    print(f'  Сводка: {len(svod_rows)} стр. | Детали: {len(detail_rows)} стр. | Списания: {len(spis_rows)} стр.')

    print('Обновляю таблицу...')
    update_sheets(s, ss_id, svod_rows, detail_rows, spis_rows)

    # Применить форматирование — используем реальные sheetId
    from create_inventory_tracker import (fmt_header, fmt_body, fmt_col_widths,
                                           color_row, CLR_GREEN, CLR_YELLOW,
                                           CLR_RED, CLR_LIGHT, sheets,
                                           get_sheet_ids)
    sids = get_sheet_ids(s, ss_id)
    sid_svod   = sids.get('Сводка', 0)
    sid_detail = sids.get('Инвентаризации', 1)
    sid_spis   = sids.get('Списания', 2)

    requests = []
    for sid, ncols, nrows in [
        (sid_svod,   len(HDR_SVOD),   len(svod_rows)),
        (sid_detail, len(HDR_DETAIL), len(detail_rows)),
        (sid_spis,   len(HDR_SPIS),   len(spis_rows)),
    ]:
        requests += fmt_header(sid, ncols)
        if nrows:
            requests += fmt_body(sid, nrows, ncols)

    requests += fmt_col_widths(sid_svod,   [85, 70, 60, 70, 90, 85, 100, 100, 130, 90])
    requests += fmt_col_widths(sid_detail, [85, 60, 55, 200, 65, 85, 70, 75, 90, 90, 90, 70, 80, 90, 85, 80])
    requests += fmt_col_widths(sid_spis,   [85, 60, 55, 200, 65, 80, 90, 90])

    for i, row in enumerate(svod_rows, start=1):
        status = row[-1]
        if status == 'Норма':        requests += color_row(sid_svod, i, len(HDR_SVOD), CLR_GREEN)
        elif status == 'Проверить':  requests += color_row(sid_svod, i, len(HDR_SVOD), CLR_YELLOW)
        elif status == 'Критично':   requests += color_row(sid_svod, i, len(HDR_SVOD), CLR_RED)
        elif i % 2 == 0:             requests += color_row(sid_svod, i, len(HDR_SVOD), CLR_LIGHT)

    for i, row in enumerate(detail_rows, start=1):
        status = row[-1]
        if status == 'Критично':     requests += color_row(sid_detail, i, len(HDR_DETAIL), CLR_RED)
        elif status == 'Проверить':  requests += color_row(sid_detail, i, len(HDR_DETAIL), CLR_YELLOW)
        elif i % 2 == 0:             requests += color_row(sid_detail, i, len(HDR_DETAIL), CLR_LIGHT)

    for i in range(0, len(spis_rows), 2):
        requests += color_row(sid_spis, i + 1, len(HDR_SPIS), CLR_LIGHT)

    if requests:
        sheets(s, 'batchUpdate', ss_id, {'requests': requests})
    print('  ✅ Форматирование применено.')

    # Trello задачи
    print('\nСоздаю Trello задачи...')
    create_trello_tasks()

    print(f'\n✅ Готово. Таблица: https://docs.google.com/spreadsheets/d/{ss_id}/edit')
    return ss_id


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--new',  action='store_true', help='Создать новую таблицу')
    ap.add_argument('--ss-id', default='', help='ID существующей таблицы')
    args = ap.parse_args()
    main(create_new=args.new, ss_id=args.ss_id or None)
