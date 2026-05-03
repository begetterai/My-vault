#!/usr/bin/env python3
"""
Создаёт Google Sheets трекер инвентаризаций и списаний.
Запускать один раз для создания; потом — update_inventory_tracker.py

Листы:
  Сводка         — одна строка на инвентаризацию, итоги
  Инвентаризации — детально по позициям
  Списания       — только позиции с ненулевыми списаниями
"""
import json, os, sys, time
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from doc_styles import (CLR_HEADER, CLR_WHITE, SHEETS_FONT,
                        SHEETS_SIZE_BODY, SHEETS_SIZE_HEADING)

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')
FOLDER_ID = '14NnVXa9k1h0dyS-vNch61A3-aSpJG_Jn'

# ─── ЦВЕТА ────────────────────────────────────────────────────────────────────
CLR_GREEN  = {'red': 0.85, 'green': 0.93, 'blue': 0.83}  # расхождение < 5%
CLR_YELLOW = {'red': 1.00, 'green': 0.95, 'blue': 0.70}  # 5–15%
CLR_RED    = {'red': 0.96, 'green': 0.80, 'blue': 0.80}  # > 15%
CLR_LIGHT  = {'red': 0.96, 'green': 0.96, 'blue': 0.96}  # чередующийся фон

UNIT_MAP = {'pcs': 'шт', 'kg': 'кг', 'l': 'л', 'g': 'г', 'ml': 'мл',
            'p': 'шт', 'pc': 'шт', 'kг': 'кг'}

# ─── ЗАГОЛОВКИ ЛИСТОВ ─────────────────────────────────────────────────────────
HDR_SVOD = [
    'Дата', 'Точка', 'Инв.#', 'Позиций', 'С расхожд.', '%% позиций',
    'Расхожд.(с)', 'Списания(с)', 'Ст-ть нач.остатка(с)', 'Статус'
]
HDR_DETAIL = [
    'Дата', 'Точка', 'Инв.#', 'Наименование', 'Ед.изм.',
    'Нач.остаток', 'Приход', 'Продажи', 'Списания(кол)',
    'Списания(с)', 'Расч.остаток', 'Факт', 'Расхожд.',
    'Расхожд.(с)', '%%расхожд.', 'Статус'
]
HDR_SPIS = [
    'Дата', 'Точка', 'Инв.#', 'Наименование', 'Ед.изм.',
    'Кол-во', 'Сумма(с)', 'Себ-ть ед.'
]


def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/drive',
                       'https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)


def sheets(s, method, ss_id, body):
    # batchUpdate → :batchUpdate (colon); values:batchUpdate → /values:batchUpdate (slash)
    if method == 'batchUpdate':
        url = f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate'
    else:
        url = f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/{method}'
    r = s.post(url, json=body, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f'{method} → {r.status_code}: {r.text[:300]}')
    return r.json()


def create_spreadsheet(s):
    # Создаём через Drive API (сервис-аккаунт имеет доступ к диску, не к Sheets API напрямую)
    r = s.post(
        'https://www.googleapis.com/drive/v3/files?supportsAllDrives=true',
        headers={'Content-Type': 'application/json'},
        data=json.dumps({
            'name': 'Ромашка — Трекер инвентаризаций и списаний',
            'mimeType': 'application/vnd.google-apps.spreadsheet',
            'parents': [FOLDER_ID],
        }), timeout=30)
    resp = r.json()
    if 'id' not in resp:
        raise RuntimeError(f'Drive create failed: {resp}')
    ss_id = resp['id']
    time.sleep(2)  # дать Drive/Sheets API синхронизироваться

    # Переименовать Sheet1 → Сводка, добавить Инвентаризации и Списания
    # Сначала получаем sheetId существующего листа
    ri = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}', timeout=20)
    existing_sheet_id = ri.json()['sheets'][0]['properties']['sheetId']

    sheets(s, 'batchUpdate', ss_id, {'requests': [
        {'updateSheetProperties': {
            'properties': {'sheetId': existing_sheet_id, 'title': 'Сводка', 'index': 0},
            'fields': 'title,index'
        }},
        {'addSheet': {'properties': {'title': 'Инвентаризации', 'index': 1}}},
        {'addSheet': {'properties': {'title': 'Списания',        'index': 2}}},
    ]})

    print(f'  Создан: https://docs.google.com/spreadsheets/d/{ss_id}/edit')
    return ss_id


def fmt_header(sheet_id, num_cols):
    return [{
        'repeatCell': {
            'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 1,
                      'startColumnIndex': 0, 'endColumnIndex': num_cols},
            'cell': {'userEnteredFormat': {
                'textFormat': {'fontFamily': SHEETS_FONT, 'fontSize': SHEETS_SIZE_HEADING,
                               'bold': True, 'foregroundColor': CLR_WHITE},
                'backgroundColor': CLR_HEADER,
                'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE',
                'wrapStrategy': 'WRAP',
            }},
            'fields': 'userEnteredFormat(textFormat,backgroundColor,horizontalAlignment,verticalAlignment,wrapStrategy)'
        }
    }, {
        'updateSheetProperties': {
            'properties': {'sheetId': sheet_id, 'gridProperties': {'frozenRowCount': 1}},
            'fields': 'gridProperties.frozenRowCount'
        }
    }]


def fmt_body(sheet_id, num_rows, num_cols):
    return [{
        'repeatCell': {
            'range': {'sheetId': sheet_id, 'startRowIndex': 1, 'endRowIndex': num_rows + 1,
                      'startColumnIndex': 0, 'endColumnIndex': num_cols},
            'cell': {'userEnteredFormat': {
                'textFormat': {'fontFamily': SHEETS_FONT, 'fontSize': SHEETS_SIZE_BODY}
            }},
            'fields': 'userEnteredFormat.textFormat'
        }
    }]


def fmt_col_widths(sheet_id, widths):
    reqs = []
    for i, w in enumerate(widths):
        reqs.append({'updateDimensionProperties': {
            'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS',
                      'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w},
            'fields': 'pixelSize'
        }})
    return reqs


def color_row(sheet_id, row_idx, num_cols, color):
    return [{
        'repeatCell': {
            'range': {'sheetId': sheet_id, 'startRowIndex': row_idx, 'endRowIndex': row_idx + 1,
                      'startColumnIndex': 0, 'endColumnIndex': num_cols},
            'cell': {'userEnteredFormat': {'backgroundColor': color}},
            'fields': 'userEnteredFormat.backgroundColor'
        }
    }]


def status_color(pct_diff):
    if pct_diff is None:
        return None, '—'
    pct = abs(pct_diff)
    if pct < 5:
        return CLR_GREEN, 'Норма'
    elif pct < 15:
        return CLR_YELLOW, 'Проверить'
    else:
        return CLR_RED, 'Критично'


def get_sheet_ids(s, ss_id):
    """Возвращает {title: sheetId} для всех листов таблицы."""
    r = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}', timeout=20)
    return {sh['properties']['title']: sh['properties']['sheetId']
            for sh in r.json().get('sheets', [])}


def setup_sheets(s, ss_id, svod_rows, detail_rows, spis_rows):
    """Записать заголовки, данные, форматирование в три листа."""
    # ── Реальные sheetId ───────────────────────────────────────────
    sids = get_sheet_ids(s, ss_id)
    sid_svod   = sids.get('Сводка', 0)
    sid_detail = sids.get('Инвентаризации', 1)
    sid_spis   = sids.get('Списания', 2)

    # ── Запись данных ──────────────────────────────────────────────
    def write(sheet_name, headers, rows):
        values = [headers] + rows
        body = {'valueInputOption': 'USER_ENTERED', 'data': [
            {'range': f"'{sheet_name}'!A1", 'values': values}
        ]}
        sheets(s, 'values:batchUpdate', ss_id, body)

    write('Сводка',         HDR_SVOD,   svod_rows)
    write('Инвентаризации', HDR_DETAIL, detail_rows)
    write('Списания',        HDR_SPIS,   spis_rows)

    # ── Форматирование ─────────────────────────────────────────────
    requests = []

    # Заголовки + тело
    for sid, ncols, nrows in [
        (sid_svod,   len(HDR_SVOD),   len(svod_rows)),
        (sid_detail, len(HDR_DETAIL), len(detail_rows)),
        (sid_spis,   len(HDR_SPIS),   len(spis_rows)),
    ]:
        requests += fmt_header(sid, ncols)
        if nrows:
            requests += fmt_body(sid, nrows, ncols)

    # Ширины столбцов
    requests += fmt_col_widths(sid_svod,   [85, 70, 60, 70, 90, 85, 100, 100, 130, 90])
    requests += fmt_col_widths(sid_detail, [85, 60, 55, 200, 65, 85, 70, 75, 90, 90, 90, 70, 80, 90, 85, 80])
    requests += fmt_col_widths(sid_spis,   [85, 60, 55, 200, 65, 80, 90, 90])

    # Цвет строк Сводки по статусу
    for i, row in enumerate(svod_rows, start=1):
        status = row[-1] if row else '—'
        if status == 'Норма':
            requests += color_row(sid_svod, i, len(HDR_SVOD), CLR_GREEN)
        elif status == 'Проверить':
            requests += color_row(sid_svod, i, len(HDR_SVOD), CLR_YELLOW)
        elif status == 'Критично':
            requests += color_row(sid_svod, i, len(HDR_SVOD), CLR_RED)
        elif i % 2 == 0:
            requests += color_row(sid_svod, i, len(HDR_SVOD), CLR_LIGHT)

    # Цвет строк детального листа
    for i, row in enumerate(detail_rows, start=1):
        status = row[-1] if row else '—'
        if status == 'Критично':
            requests += color_row(sid_detail, i, len(HDR_DETAIL), CLR_RED)
        elif status == 'Проверить':
            requests += color_row(sid_detail, i, len(HDR_DETAIL), CLR_YELLOW)
        elif i % 2 == 0:
            requests += color_row(sid_detail, i, len(HDR_DETAIL), CLR_LIGHT)

    # Чередование строк в Списаниях
    for i in range(0, len(spis_rows), 2):
        requests += color_row(sid_spis, i + 1, len(HDR_SPIS), CLR_LIGHT)

    # Отправить одним батчем
    if requests:
        sheets(s, 'batchUpdate', ss_id, {'requests': requests})

    print('  Форматирование применено.')


def main():
    s = get_session()
    print('Создаю трекер...')
    ss_id = create_spreadsheet(s)

    # Данные из Poster грузит update_inventory_tracker.py
    # Здесь только структура + пустые заголовки
    setup_sheets(s, ss_id, [], [], [])

    print(f'\nID таблицы: {ss_id}')
    print('Теперь запусти: python3 update_inventory_tracker.py\n')
    return ss_id


if __name__ == '__main__':
    main()
