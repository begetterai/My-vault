#!/usr/bin/env python3
"""
Трекер инвентаризаций v2 — пивот-формат.

Структура:
  "ЗБ"    — пивот: строки = позиции по цехам, столбцы = даты инвентаризаций
  "ОВИР"  — то же
  "Сводка"— одна строка на инвентаризацию: дата, расхождение (с), списания (с)
  "Списания по периодам" — позиции с writeoff > 0, сгруппированы по периоду

Источник: Poster API → storage.getInventories + storage.getInventoryIngredients
Cron: 0 8 * * 1  (каждый понедельник после воскресной инвентаризации)
"""
import json, os, sys, time, urllib.request, urllib.parse, datetime
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from doc_styles import (CLR_HEADER, CLR_WHITE, SHEETS_FONT,
                        SHEETS_SIZE_BODY, SHEETS_SIZE_HEADING)

CREDS     = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'credentials', 'romashka-drive.json')
FOLDER_ID = '14NnVXa9k1h0dyS-vNch61A3-aSpJG_Jn'
POSTER_BASE = 'https://joinposter.com/api'

LOCATIONS = [
    {'name': 'ЗБ',   'token': '398711:8746917c4a23ea897774040e039dfb76'},
    {'name': 'ОВИР', 'token': '935215:79675564e3d086d7e03d5fd56b50c8df'},
]

# Сколько последних инвентаризаций показывать в пивоте
N_DATES = 10

# ─── ЦВЕТА ────────────────────────────────────────────────────────────────────
CLR_SECTION  = {'red': 0.18, 'green': 0.31, 'blue': 0.18}   # заголовок цеха
CLR_HDR_DATE = {'red': 0.23, 'green': 0.40, 'blue': 0.55}   # шапка даты
CLR_WHITE_C  = {'red': 1.0,  'green': 1.0,  'blue': 1.0}
CLR_LIGHT    = {'red': 0.96, 'green': 0.96, 'blue': 0.96}
CLR_GREEN    = {'red': 0.85, 'green': 0.93, 'blue': 0.83}
CLR_YELLOW   = {'red': 1.00, 'green': 0.95, 'blue': 0.70}
CLR_RED      = {'red': 0.96, 'green': 0.80, 'blue': 0.80}
CLR_ZERO     = {'red': 0.90, 'green': 0.90, 'blue': 0.90}   # нулевой остаток

UNIT_MAP = {'pcs': 'шт', 'kg': 'кг', 'l': 'л', 'g': 'г',
            'ml': 'мл', 'p': 'шт', 'pc': 'шт'}

# ─── КАТЕГОРИЗАЦИЯ ИНГРЕДИЕНТОВ ───────────────────────────────────────────────
CATEGORIES_ORDER = [
    'Чаи и кофе', 'Сиропы', 'Пюре', 'Мороженое',
    'Фрукты и зелень', 'Молочные', 'Готовые напитки', 'Прочее'
]

def categorize(name):
    n = name.lower()
    if any(x in n for x in ['сироп']):                                        return 'Сиропы'
    if any(x in n for x in ['пюре']):                                         return 'Пюре'
    if 'мороженое' in n:                                                       return 'Мороженое'
    if any(x in n for x in ['чай', 'ассам', 'сенча', 'каркаде',
                             'nice', 'кофе']):                                 return 'Чаи и кофе'
    if any(x in n for x in ['молоко', 'топпинг', 'сливки']):                  return 'Молочные'
    if any(x in n for x in ['апельсин', 'лимон', 'клубника', 'банан',
                             'мята', 'базилик', 'имбирь', 'щавель',
                             'яблоко', 'апельсиновая', 'цедра']):             return 'Фрукты и зелень'
    if any(x in n for x in ['кола', 'фанта', 'аква', 'боржоми',
                             'лаймон', 'горилла', 'фьюс', 'ментос',
                             'сок ', 'добрый']):                               return 'Готовые напитки'
    return 'Прочее'


# ─── POSTER API ───────────────────────────────────────────────────────────────
def poster_get(token, method, params=None):
    p = {'token': token}
    if params:
        p.update(params)
    url = f'{POSTER_BASE}/{method}?{urllib.parse.urlencode(p)}'
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={'User-Agent': 'RomashkaBot/1.0'}),
            timeout=25) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f'    ⚠️  {method}: {e}')
        return {}


def fmt_date(date_str):
    try:
        return datetime.datetime.strptime(date_str[:10], '%Y-%m-%d').strftime('%d.%m.%Y')
    except Exception:
        return date_str[:10]


def safe_float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def fetch_location_data(token, loc_name):
    """Возвращает список инвентаризаций с деталями — от новых к старым."""
    r = poster_get(token, 'storage.getInventories')
    invs = sorted(r.get('response', []),
                  key=lambda x: x.get('date_set', x.get('date_start', '')),
                  reverse=True)

    result = []
    for inv in invs[:N_DATES]:
        inv_id   = inv['inventory_id']
        date_raw = inv.get('date_set') or inv.get('date_start') or ''
        date     = fmt_date(date_raw)

        ri = poster_get(token, 'storage.getInventoryIngredients',
                        {'inventory_id': inv_id})
        items = ri.get('response', {}).get('ingredients', [])
        if not items:
            continue

        by_id = {}
        for it in items:
            by_id[it['item_id']] = it

        result.append({'inv_id': inv_id, 'date': date, 'items': by_id})
        time.sleep(0.3)

    return result  # list от новой к старой


# ─── GOOGLE API ───────────────────────────────────────────────────────────────
def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/drive',
                       'https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)


def sheets_batch(s, ss_id, requests):
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate'
    r = s.post(url, json={'requests': requests}, timeout=90)
    if r.status_code != 200:
        raise RuntimeError(f'batchUpdate {r.status_code}: {r.text[:300]}')
    return r.json()


def values_write(s, ss_id, sheet_name, values):
    rng = urllib.parse.quote(f"'{sheet_name}'!A1")
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/values/{rng}:clear'
    s.post(url, json={}, timeout=30)
    url2 = f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/values:batchUpdate'
    body = {'valueInputOption': 'USER_ENTERED',
            'data': [{'range': f"'{sheet_name}'!A1", 'values': values}]}
    r = s.post(url2, json=body, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f'values_write {r.status_code}: {r.text[:300]}')


def get_sheet_ids(s, ss_id):
    r = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}', timeout=20)
    return {sh['properties']['title']: sh['properties']['sheetId']
            for sh in r.json().get('sheets', [])}


def create_spreadsheet(s, title):
    r = s.post(
        'https://www.googleapis.com/drive/v3/files?supportsAllDrives=true',
        headers={'Content-Type': 'application/json'},
        data=json.dumps({
            'name': title,
            'mimeType': 'application/vnd.google-apps.spreadsheet',
            'parents': [FOLDER_ID],
        }), timeout=30)
    resp = r.json()
    if 'id' not in resp:
        raise RuntimeError(f'Create failed: {resp}')
    ss_id = resp['id']
    time.sleep(2)
    return ss_id


def ensure_sheets(s, ss_id, sheet_names):
    """Создаёт листы если их нет, возвращает {name: sheetId}."""
    r = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}', timeout=20)
    existing = {sh['properties']['title']: sh['properties']['sheetId']
                for sh in r.json().get('sheets', [])}

    reqs = []
    # Переименовать первый лист под первое имя
    first_title = list(existing.keys())[0]
    first_id    = list(existing.values())[0]
    if first_title != sheet_names[0] and sheet_names[0] not in existing:
        reqs.append({'updateSheetProperties': {
            'properties': {'sheetId': first_id, 'title': sheet_names[0]},
            'fields': 'title'
        }})
        existing[sheet_names[0]] = first_id
        if first_title in existing:
            del existing[first_title]

    # Добавить остальные листы
    for name in sheet_names[1:]:
        if name not in existing:
            reqs.append({'addSheet': {'properties': {'title': name}}})

    if reqs:
        sheets_batch(s, ss_id, reqs)
        time.sleep(1)

    return get_sheet_ids(s, ss_id)


# ─── ПОСТРОЕНИЕ ПИВОТА ───────────────────────────────────────────────────────
def build_master_list(all_invs_by_loc):
    """Строит единый мастер-список позиций по всем локациям и датам."""
    seen = {}  # item_id → {'name', 'unit', 'cost', 'cat'}
    for loc_name, invs in all_invs_by_loc.items():
        for inv in invs:
            for item_id, it in inv['items'].items():
                if item_id not in seen:
                    name = it.get('item', '')
                    unit = UNIT_MAP.get(it.get('unit', it.get('db_unit', '')),
                                       it.get('unit', ''))
                    cost = safe_float(it.get('primecost'))
                    seen[item_id] = {
                        'name': name, 'unit': unit,
                        'cost': cost, 'cat': categorize(name)
                    }
    return seen  # {item_id: {...}}


def pivot_rows(loc_invs, master, n_dates):
    """
    Возвращает:
      header_row1 — ['', '', '', '', 'Дата1', '', 'Дата2', '', ...]  (merged)
      header_row2 — ['Наименование', 'Ед.', 'Себ-ть', 'Дата1 Факт', 'Дата1 Расх.', ...]
      data_rows   — per category: [cat_header_row, item_row, ...]
      merge_reqs  — для дат в шапке
      color_map   — {row_idx: color} для цветовой разметки
    """
    dates = [inv['date'] for inv in loc_invs[:n_dates]]  # новые → старые
    n_d   = len(dates)
    FIXED = 4   # Категория, Наименование, Ед., Себ-ть

    # Заголовки
    h1 = ['', 'Наименование', 'Ед.', 'Себ-ть(с)']
    for d in dates:
        h1 += [d, '']    # каждая дата занимает 2 колонки (факт + расхожд)
    h2 = ['Категория', 'Наименование', 'Ед.', 'Себ-ть(с)']
    for _ in dates:
        h2 += ['Факт', 'Расх.(с)']

    # Группировка позиций по категории
    cats = {c: [] for c in CATEGORIES_ORDER}
    for item_id, info in sorted(master.items(),
                                 key=lambda x: (x[1]['cat'], x[1]['name'])):
        cats[info['cat']].append((item_id, info))

    data_rows  = []
    color_map  = {}   # {row_idx_in_data: color}
    row_idx    = 2    # 0=h1, 1=h2

    for cat in CATEGORIES_ORDER:
        items = cats[cat]
        if not items:
            continue

        # Строка-заголовок категории
        cat_row = [cat] + [''] * (FIXED - 1 + n_d * 2)
        data_rows.append(cat_row)
        color_map[row_idx] = 'section'
        row_idx += 1

        for item_id, info in items:
            row = ['', info['name'], info['unit'],
                   info['cost'] if info['cost'] else '']
            cell_colors = []   # per date-pair

            for inv in loc_invs[:n_d]:
                it = inv['items'].get(item_id)
                if it is None:
                    row += ['—', '—']
                    cell_colors.append(None)
                else:
                    fact    = safe_float(it.get('factrest') or it.get('fact_rest_sum'))
                    diff_c  = safe_float(it.get('diffcurrency'))
                    est     = safe_float(it.get('estimatedrest'))
                    row += [round(fact, 3) if fact else 0,
                            round(diff_c, 2) if diff_c else 0]

                    # Цвет по расхождению
                    if est and abs(est) > 0.001:
                        pct = abs(diff_c / (est * info['cost'] or 1)) * 100 if info['cost'] else 0
                        pct_qty = abs(safe_float(it.get('difference')) / est) * 100
                        pct = pct_qty
                    else:
                        pct = 0
                    if fact == 0:
                        cell_colors.append('zero')
                    elif pct > 15:
                        cell_colors.append('red')
                    elif pct > 5:
                        cell_colors.append('yellow')
                    else:
                        cell_colors.append('green')

            data_rows.append(row)
            color_map[row_idx] = ('item', cell_colors, row_idx % 2 == 0)
            row_idx += 1

    return [h1, h2], data_rows, color_map, dates


def build_format_requests(sid, header_rows, data_rows, color_map, n_dates):
    reqs = []
    FIXED = 4
    n_rows_total = 2 + len(data_rows)
    n_cols = FIXED + n_dates * 2

    # ── Заморозить первые 2 строки и первые 2 столбца ──
    reqs.append({'updateSheetProperties': {
        'properties': {'sheetId': sid, 'gridProperties': {
            'frozenRowCount': 2, 'frozenColumnCount': 2
        }},
        'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'
    }})

    # ── Базовый шрифт для всего листа ──
    reqs.append({'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': n_rows_total,
                  'startColumnIndex': 0, 'endColumnIndex': n_cols},
        'cell': {'userEnteredFormat': {
            'textFormat': {'fontFamily': SHEETS_FONT, 'fontSize': SHEETS_SIZE_BODY}
        }},
        'fields': 'userEnteredFormat.textFormat'
    }})

    # ── Строка 1 (даты) — тёмно-синий фон, белый текст, жирный ──
    reqs.append({'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1,
                  'startColumnIndex': 0, 'endColumnIndex': n_cols},
        'cell': {'userEnteredFormat': {
            'textFormat': {'fontFamily': SHEETS_FONT, 'fontSize': 11,
                           'bold': True, 'foregroundColor': CLR_WHITE_C},
            'backgroundColor': CLR_HDR_DATE,
            'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE',
        }},
        'fields': 'userEnteredFormat(textFormat,backgroundColor,horizontalAlignment,verticalAlignment)'
    }})

    # Первые 4 ячейки строки 1 — тёмно-зелёный
    reqs.append({'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1,
                  'startColumnIndex': 0, 'endColumnIndex': FIXED},
        'cell': {'userEnteredFormat': {
            'textFormat': {'fontFamily': SHEETS_FONT, 'fontSize': SHEETS_SIZE_HEADING,
                           'bold': True, 'foregroundColor': CLR_WHITE_C},
            'backgroundColor': CLR_SECTION,
            'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE',
        }},
        'fields': 'userEnteredFormat(textFormat,backgroundColor,horizontalAlignment,verticalAlignment)'
    }})

    # ── Строка 2 (Факт / Расх.) — светлый фон, жирный ──
    reqs.append({'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': 2,
                  'startColumnIndex': 0, 'endColumnIndex': n_cols},
        'cell': {'userEnteredFormat': {
            'textFormat': {'fontFamily': SHEETS_FONT, 'fontSize': 10,
                           'bold': True, 'foregroundColor': CLR_WHITE_C},
            'backgroundColor': CLR_HDR_DATE,
            'horizontalAlignment': 'CENTER',
        }},
        'fields': 'userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)'
    }})
    reqs.append({'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': 2,
                  'startColumnIndex': 0, 'endColumnIndex': FIXED},
        'cell': {'userEnteredFormat': {
            'backgroundColor': CLR_SECTION,
        }},
        'fields': 'userEnteredFormat.backgroundColor'
    }})

    # ── Слияние ячеек для дат в строке 1 ──
    for i in range(n_dates):
        col_start = FIXED + i * 2
        reqs.append({'mergeCells': {
            'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1,
                      'startColumnIndex': col_start, 'endColumnIndex': col_start + 2},
            'mergeType': 'MERGE_ALL'
        }})

    # ── Ширины столбцов ──
    col_widths = [80, 220, 50, 70] + [65, 70] * n_dates
    for i, w in enumerate(col_widths):
        reqs.append({'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                      'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})

    # ── Цвет строк данных ──
    for row_i, info in color_map.items():
        abs_row = row_i  # row_i уже абсолютный с учётом 0=h1, 1=h2

        if info == 'section':
            # Заголовок категории — тёмно-зелёный
            reqs.append({'repeatCell': {
                'range': {'sheetId': sid, 'startRowIndex': abs_row,
                          'endRowIndex': abs_row + 1,
                          'startColumnIndex': 0, 'endColumnIndex': n_cols},
                'cell': {'userEnteredFormat': {
                    'textFormat': {'fontFamily': SHEETS_FONT, 'fontSize': 11,
                                   'bold': True, 'foregroundColor': CLR_WHITE_C},
                    'backgroundColor': CLR_SECTION,
                }},
                'fields': 'userEnteredFormat(textFormat,backgroundColor)'
            }})
        elif isinstance(info, tuple):
            _, cell_colors, is_even = info
            # Фиксированные колонки — чередующийся серый
            bg = CLR_LIGHT if is_even else CLR_WHITE_C
            reqs.append({'repeatCell': {
                'range': {'sheetId': sid, 'startRowIndex': abs_row,
                          'endRowIndex': abs_row + 1,
                          'startColumnIndex': 0, 'endColumnIndex': FIXED},
                'cell': {'userEnteredFormat': {'backgroundColor': bg}},
                'fields': 'userEnteredFormat.backgroundColor'
            }})
            # Ячейки по датам — цвет по расхождению
            for j, clr_key in enumerate(cell_colors):
                col_start = FIXED + j * 2
                if clr_key == 'red':    clr = CLR_RED
                elif clr_key == 'yellow': clr = CLR_YELLOW
                elif clr_key == 'zero':   clr = CLR_ZERO
                else:                     clr = bg
                reqs.append({'repeatCell': {
                    'range': {'sheetId': sid, 'startRowIndex': abs_row,
                              'endRowIndex': abs_row + 1,
                              'startColumnIndex': col_start,
                              'endColumnIndex': col_start + 2},
                    'cell': {'userEnteredFormat': {'backgroundColor': clr}},
                    'fields': 'userEnteredFormat.backgroundColor'
                }})

    # ── Выравнивание числовых ячеек ──
    reqs.append({'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': 2, 'endRowIndex': n_rows_total,
                  'startColumnIndex': FIXED, 'endColumnIndex': n_cols},
        'cell': {'userEnteredFormat': {'horizontalAlignment': 'RIGHT'}},
        'fields': 'userEnteredFormat.horizontalAlignment'
    }})

    return reqs


# ─── ЛИСТ СВОДКА ─────────────────────────────────────────────────────────────
HDR_SVOD = ['Дата', 'Точка', 'Инв.#', 'Позиций', 'С расхожд.',
            '%% с расх.', 'Расхожд.(с)', 'Списания(с)', 'Нач.остаток(с)', 'Статус']

def build_svod(all_invs_by_loc):
    rows = []
    for loc, invs in all_invs_by_loc.items():
        for inv in invs:
            items = list(inv['items'].values())
            total_diff_c  = sum(safe_float(it.get('diffcurrency')) for it in items)
            total_spis_c  = sum(safe_float(it.get('writeoffcurrency')) for it in items)
            total_start_c = sum(safe_float(it.get('startrestcurrency')) for it in items)
            n_diff        = sum(1 for it in items if abs(safe_float(it.get('difference'))) > 0.01)
            n_total       = len(items)
            pct_items     = round(n_diff / n_total * 100, 1) if n_total else 0

            if total_start_c > 0:
                pct_tot = abs(total_diff_c) / total_start_c * 100
            else:
                pct_tot = 0
            status = 'Норма' if pct_tot < 5 else ('Проверить' if pct_tot < 15 else 'Критично')

            rows.append([
                inv['date'], loc, inv['inv_id'],
                n_total, n_diff, f'{pct_items}%',
                round(total_diff_c, 2), round(total_spis_c, 2),
                round(total_start_c, 2), status
            ])
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows


def fmt_svod(s, ss_id, sid, n_rows):
    reqs = []
    n_cols = len(HDR_SVOD)
    # Заголовок
    reqs.append({'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1,
                  'startColumnIndex': 0, 'endColumnIndex': n_cols},
        'cell': {'userEnteredFormat': {
            'textFormat': {'fontFamily': SHEETS_FONT, 'fontSize': SHEETS_SIZE_HEADING,
                           'bold': True, 'foregroundColor': CLR_WHITE_C},
            'backgroundColor': CLR_SECTION,
            'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE',
            'wrapStrategy': 'WRAP',
        }},
        'fields': 'userEnteredFormat(textFormat,backgroundColor,horizontalAlignment,verticalAlignment,wrapStrategy)'
    }})
    reqs.append({'updateSheetProperties': {
        'properties': {'sheetId': sid, 'gridProperties': {'frozenRowCount': 1}},
        'fields': 'gridProperties.frozenRowCount'
    }})
    # Тело
    if n_rows:
        reqs.append({'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': n_rows + 1,
                      'startColumnIndex': 0, 'endColumnIndex': n_cols},
            'cell': {'userEnteredFormat': {
                'textFormat': {'fontFamily': SHEETS_FONT, 'fontSize': SHEETS_SIZE_BODY}
            }},
            'fields': 'userEnteredFormat.textFormat'
        }})
    # Ширины
    for i, w in enumerate([85, 60, 55, 65, 80, 75, 100, 100, 120, 80]):
        reqs.append({'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                      'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})
    return reqs


# ─── ЛИСТ СПИСАНИЯ ───────────────────────────────────────────────────────────
HDR_SPIS = ['Период (от→до)', 'Точка', 'Наименование',
            'Ед.', 'Кол-во', 'Сумма(с)', 'Себ-ть ед.']

def build_spis(all_invs_by_loc):
    """Списания per период (между двумя соседними инвентаризациями)."""
    rows = []
    for loc, invs in all_invs_by_loc.items():
        # invs отсортированы от новой к старой
        for i, inv in enumerate(invs):
            date_curr = inv['date']
            date_prev = invs[i + 1]['date'] if i + 1 < len(invs) else '—'
            period    = f'{date_prev} → {date_curr}'

            for it in sorted(inv['items'].values(), key=lambda x: x.get('item', '')):
                wo = safe_float(it.get('writeoff'))
                wo_c = safe_float(it.get('writeoffcurrency'))
                if wo < 0.001:
                    continue
                rows.append([
                    period, loc,
                    it.get('item', ''),
                    UNIT_MAP.get(it.get('unit', it.get('db_unit', '')),
                                 it.get('unit', '')),
                    round(wo, 3),
                    round(wo_c, 2),
                    round(safe_float(it.get('primecost')), 2),
                ])
    return rows


def fmt_spis(s, ss_id, sid, n_rows):
    reqs = []
    n_cols = len(HDR_SPIS)
    reqs.append({'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1,
                  'startColumnIndex': 0, 'endColumnIndex': n_cols},
        'cell': {'userEnteredFormat': {
            'textFormat': {'fontFamily': SHEETS_FONT, 'fontSize': SHEETS_SIZE_HEADING,
                           'bold': True, 'foregroundColor': CLR_WHITE_C},
            'backgroundColor': CLR_HDR_DATE,
            'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE',
        }},
        'fields': 'userEnteredFormat(textFormat,backgroundColor,horizontalAlignment,verticalAlignment)'
    }})
    reqs.append({'updateSheetProperties': {
        'properties': {'sheetId': sid, 'gridProperties': {'frozenRowCount': 1}},
        'fields': 'gridProperties.frozenRowCount'
    }})
    if n_rows:
        reqs.append({'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': n_rows + 1,
                      'startColumnIndex': 0, 'endColumnIndex': n_cols},
            'cell': {'userEnteredFormat': {
                'textFormat': {'fontFamily': SHEETS_FONT, 'fontSize': SHEETS_SIZE_BODY}
            }},
            'fields': 'userEnteredFormat.textFormat'
        }})
    for i, w in enumerate([160, 60, 200, 50, 70, 90, 80]):
        reqs.append({'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                      'startIndex': i, 'endIndex': i + 1},
            'properties': {'pixelSize': w}, 'fields': 'pixelSize'
        }})
    return reqs


# ─── ГЛАВНАЯ ФУНКЦИЯ ──────────────────────────────────────────────────────────
def main(ss_id=None):
    s = get_session()

    # 1. Загрузка данных из Poster
    all_invs_by_loc = {}
    for loc in LOCATIONS:
        print(f'  {loc["name"]}: загружаю инвентаризации...')
        invs = fetch_location_data(loc['token'], loc['name'])
        print(f'    → {len(invs)} инвентаризаций (последние {N_DATES})')
        all_invs_by_loc[loc['name']] = invs

    # Мастер-список позиций
    master = build_master_list(all_invs_by_loc)
    print(f'  Уникальных позиций: {len(master)}')

    # 2. Создать / получить таблицу
    sheet_names = ['ЗБ', 'ОВИР', 'Сводка', 'Списания по периодам']
    if not ss_id:
        print('Создаю таблицу...')
        ss_id = create_spreadsheet(s, 'Ромашка — Трекер инвентаризаций v2')
    sids = ensure_sheets(s, ss_id, sheet_names)
    print(f'  https://docs.google.com/spreadsheets/d/{ss_id}/edit\n')

    # 3. Заполнить пивот для каждой локации
    for loc_name in ['ЗБ', 'ОВИР']:
        invs = all_invs_by_loc[loc_name]
        if not invs:
            print(f'{loc_name}: нет данных, пропускаю.')
            continue
        print(f'Строю пивот {loc_name}...')

        # Мастер только с позициями этой локации
        loc_master = {}
        for inv in invs:
            for item_id, it in inv['items'].items():
                if item_id not in loc_master:
                    name = it.get('item', '')
                    unit = UNIT_MAP.get(it.get('unit', it.get('db_unit', '')),
                                       it.get('unit', ''))
                    loc_master[item_id] = {
                        'name': name, 'unit': unit,
                        'cost': safe_float(it.get('primecost')),
                        'cat':  categorize(name)
                    }

        headers, data_rows, color_map, dates = pivot_rows(invs, loc_master, N_DATES)
        n_dates_actual = len(dates)

        # Записать значения
        all_values = headers + data_rows
        values_write(s, ss_id, loc_name, all_values)

        # Форматирование
        sid = sids[loc_name]
        fmt_reqs = build_format_requests(sid, headers, data_rows, color_map, n_dates_actual)
        if fmt_reqs:
            sheets_batch(s, ss_id, fmt_reqs)
        print(f'  ✅ {loc_name}: {len(data_rows)} строк, {n_dates_actual} дат')

    # 4. Сводка
    print('Строю Сводку...')
    svod_rows = build_svod(all_invs_by_loc)
    values_write(s, ss_id, 'Сводка', [HDR_SVOD] + svod_rows)
    fmt_reqs = fmt_svod(s, ss_id, sids['Сводка'], len(svod_rows))
    if fmt_reqs:
        sheets_batch(s, ss_id, fmt_reqs)
    print(f'  ✅ Сводка: {len(svod_rows)} строк')

    # 5. Списания по периодам
    print('Строю Списания...')
    spis_rows = build_spis(all_invs_by_loc)
    values_write(s, ss_id, 'Списания по периодам', [HDR_SPIS] + spis_rows)
    fmt_reqs = fmt_spis(s, ss_id, sids['Списания по периодам'], len(spis_rows))
    if fmt_reqs:
        sheets_batch(s, ss_id, fmt_reqs)
    print(f'  ✅ Списания: {len(spis_rows)} строк')

    print(f'\n✅ Готово: https://docs.google.com/spreadsheets/d/{ss_id}/edit')
    return ss_id


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--ss-id', default='', help='ID существующей таблицы (иначе создаст новую)')
    args = ap.parse_args()
    main(ss_id=args.ss_id or None)
