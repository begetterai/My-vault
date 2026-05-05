#!/usr/bin/env python3
"""
Создаёт Google Sheets «Ромашка — Трекер контроля управляющих».
Листы: ЗБ (Владимир), ОВИР (Дилчу), Свод.
"""
import json, os, sys, time, datetime, urllib.request, urllib.parse
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from doc_styles import CLR_HEADER, CLR_WHITE, SHEETS_FONT, SHEETS_SIZE_BODY, SHEETS_SIZE_HEADING

CREDS       = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'romashka-drive.json')
FOLDER_ID   = '14NnVXa9k1h0dyS-vNch61A3-aSpJG_Jn'
TRELLO_CREDS= os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'trello.json')
TRELLO_BOARD= '68b331d46b2eb8ddb94bcc72'
MEMBER_VL   = '695d2ace7d0ed18e4ed17dd7'   # Владимир
MEMBER_DL   = '6969f00f3ed7a6c2b8f02b1c'   # Дилчу
DONE_LISTS  = {'Сделано ✅'}

# ─── Цвета ────────────────────────────────────────────────────────────────────
C_DARK_GREEN  = {'red': 0.18, 'green': 0.31, 'blue': 0.18}
C_BLUE        = {'red': 0.16, 'green': 0.32, 'blue': 0.55}
C_TEAL        = {'red': 0.13, 'green': 0.45, 'blue': 0.50}
C_PURPLE      = {'red': 0.34, 'green': 0.20, 'blue': 0.54}
C_BROWN       = {'red': 0.45, 'green': 0.28, 'blue': 0.12}
C_WHITE       = {'red': 1.0, 'green': 1.0, 'blue': 1.0}
C_LIGHT       = {'red': 0.96, 'green': 0.96, 'blue': 0.96}
C_LIGHT_GREEN = {'red': 0.85, 'green': 0.93, 'blue': 0.83}
C_LIGHT_BLUE  = {'red': 0.87, 'green': 0.92, 'blue': 0.98}
C_LIGHT_YELL  = {'red': 1.00, 'green': 0.95, 'blue': 0.70}
C_LIGHT_RED   = {'red': 0.96, 'green': 0.80, 'blue': 0.80}
C_LIGHT_TEAL  = {'red': 0.85, 'green': 0.94, 'blue': 0.95}
C_LIGHT_PURP  = {'red': 0.93, 'green': 0.87, 'blue': 0.98}

WEEKDAYS_RU = {0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт', 4: 'Пт', 5: 'Сб', 6: 'Вс'}
WEEKEND     = {5, 6}

# Текущий месяц
TODAY = datetime.date.today()
MONTH = TODAY.replace(day=1)
MONTH_DAYS = [MONTH.replace(day=d) for d in range(1, 32)
              if (MONTH.replace(day=d)).month == MONTH.month]
MONTH_RU   = {1:'Январь',2:'Февраль',3:'Март',4:'Апрель',5:'Май',6:'Июнь',
              7:'Июль',8:'Август',9:'Сентябрь',10:'Октябрь',11:'Ноябрь',12:'Декабрь'}

# Финансовые нормы (настроить)
FIN_NORMS = {
    'ЗБ':   [
        ('Выручка в день', 'с', '', '', ''),
        ('Выручка за месяц', 'с', '', '', ''),
        ('Средний чек', 'с', '', '', ''),
        ('Кол-во чеков / день', 'шт', '', '', ''),
        ('FoodCost %', '%', '≤ 35%', '', ''),
        ('Расходы / Выручка %', '%', '≤ 25%', '', ''),
        ('Списания / Выручка %', '%', '≤ 3%', '', ''),
        ('ФОТ / Выручка %', '%', '≤ 30%', '', ''),
    ],
    'ОВИР': [
        ('Выручка в день', 'с', '', '', ''),
        ('Выручка за месяц', 'с', '', '', ''),
        ('Средний чек', 'с', '', '', ''),
        ('Кол-во чеков / день', 'шт', '', '', ''),
        ('FoodCost %', '%', '≤ 35%', '', ''),
        ('Расходы / Выручка %', '%', '≤ 25%', '', ''),
        ('Списания / Выручка %', '%', '≤ 3%', '', ''),
        ('ФОТ / Выручка %', '%', '≤ 30%', '', ''),
    ],
}

# ─── Trello ───────────────────────────────────────────────────────────────────

def get_trello_tasks(member_id):
    creds = json.load(open(TRELLO_CREDS))
    key, token = creds['api_key'], creds['token']
    url = f'https://api.trello.com/1/boards/{TRELLO_BOARD}/lists?key={key}&token={token}'
    with urllib.request.urlopen(url, timeout=15) as r:
        lists = json.loads(r.read().decode())
    list_map = {l['id']: l['name'] for l in lists}
    url2 = (f'https://api.trello.com/1/boards/{TRELLO_BOARD}/cards'
            f'?key={key}&token={token}&fields=name,idList,due,idMembers')
    with urllib.request.urlopen(url2, timeout=15) as r:
        cards = json.loads(r.read().decode())
    result = []
    for c in cards:
        if member_id not in c.get('idMembers', []):
            continue
        lst = list_map.get(c['idList'], '?')
        if lst in DONE_LISTS:
            continue
        due = (c.get('due') or '')[:10]
        result.append({'name': c['name'], 'list': lst, 'due': due})
    return result


# ─── Sheets API ───────────────────────────────────────────────────────────────

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/drive',
                       'https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)


def sheets_post(s, ss_id, method, body):
    if method == 'batchUpdate':
        url = f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate'
    else:
        url = f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/{method}'
    r = s.post(url, json=body, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f'{method} → {r.status_code}: {r.text[:300]}')
    return r.json()


def get_sheet_ids(s, ss_id):
    r = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}', timeout=20)
    return {sh['properties']['title']: sh['properties']['sheetId']
            for sh in r.json().get('sheets', [])}


def create_spreadsheet(s):
    r = s.post(
        'https://www.googleapis.com/drive/v3/files?supportsAllDrives=true',
        headers={'Content-Type': 'application/json'},
        data=json.dumps({
            'name': 'Ромашка — Трекер контроля управляющих',
            'mimeType': 'application/vnd.google-apps.spreadsheet',
            'parents': [FOLDER_ID],
        }), timeout=30)
    resp = r.json()
    if 'id' not in resp:
        raise RuntimeError(f'Drive create failed: {resp}')
    ss_id = resp['id']
    time.sleep(2)

    ri = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}', timeout=20)
    existing_id = ri.json()['sheets'][0]['properties']['sheetId']

    sheets_post(s, ss_id, 'batchUpdate', {'requests': [
        {'updateSheetProperties': {
            'properties': {'sheetId': existing_id, 'title': 'ЗБ', 'index': 0},
            'fields': 'title,index'}},
        {'addSheet': {'properties': {'title': 'ОВИР',  'index': 1}}},
        {'addSheet': {'properties': {'title': 'Свод',  'index': 2}}},
    ]})
    print(f'  Создан: https://docs.google.com/spreadsheets/d/{ss_id}/edit')
    return ss_id


# ─── Форматирование ───────────────────────────────────────────────────────────

NCOLS = 10  # A–J

def r_bg(sid, r0, r1, c0, c1, color):
    return {'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': r0, 'endRowIndex': r1,
                  'startColumnIndex': c0, 'endColumnIndex': c1},
        'cell': {'userEnteredFormat': {'backgroundColor': color}},
        'fields': 'userEnteredFormat.backgroundColor'}}


def r_fmt(sid, r0, r1, c0, c1, bold=False, color=None, size=None,
           halign=None, valign=None, wrap=False, fg=None):
    tf = {'fontFamily': SHEETS_FONT, 'fontSize': size or SHEETS_SIZE_BODY}
    if bold: tf['bold'] = True
    if fg:   tf['foregroundColor'] = fg
    uf = {'textFormat': tf}
    if color:  uf['backgroundColor'] = color
    if halign: uf['horizontalAlignment'] = halign
    if valign: uf['verticalAlignment']   = valign
    if wrap:   uf['wrapStrategy'] = 'WRAP'
    fields = 'userEnteredFormat(textFormat'
    if color:  fields += ',backgroundColor'
    if halign: fields += ',horizontalAlignment'
    if valign: fields += ',verticalAlignment'
    if wrap:   fields += ',wrapStrategy'
    fields += ')'
    return {'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': r0, 'endRowIndex': r1,
                  'startColumnIndex': c0, 'endColumnIndex': c1},
        'cell': {'userEnteredFormat': uf},
        'fields': fields}}


def r_merge(sid, r0, r1, c0, c1):
    return {'mergeCells': {
        'range': {'sheetId': sid, 'startRowIndex': r0, 'endRowIndex': r1,
                  'startColumnIndex': c0, 'endColumnIndex': c1},
        'mergeType': 'MERGE_ALL'}}


def r_border(sid, r0, r1, c0, c1, style='SOLID', width=1):
    line = {'style': style, 'width': width, 'color': {'red': 0.7, 'green': 0.7, 'blue': 0.7}}
    return {'updateBorders': {
        'range': {'sheetId': sid, 'startRowIndex': r0, 'endRowIndex': r1,
                  'startColumnIndex': c0, 'endColumnIndex': c1},
        'top': line, 'bottom': line, 'left': line, 'right': line,
        'innerHorizontal': line, 'innerVertical': line}}


def r_colwidth(sid, col, px):
    return {'updateDimensionProperties': {
        'range': {'sheetId': sid, 'dimension': 'COLUMNS', 'startIndex': col, 'endIndex': col+1},
        'properties': {'pixelSize': px}, 'fields': 'pixelSize'}}


def r_rowheight(sid, r0, r1, px):
    return {'updateDimensionProperties': {
        'range': {'sheetId': sid, 'dimension': 'ROWS', 'startIndex': r0, 'endIndex': r1},
        'properties': {'pixelSize': px}, 'fields': 'pixelSize'}}


def r_freeze(sid, rows=1, cols=0):
    return {'updateSheetProperties': {
        'properties': {'sheetId': sid, 'gridProperties': {
            'frozenRowCount': rows, 'frozenColumnCount': cols}},
        'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}}


# ─── Данные ───────────────────────────────────────────────────────────────────

HDR_OPS = [
    'Дата', 'День', 'Открытие\nпо регл.', 'Персонал\n(явка/план)',
    'Санитария', 'Poster\n(поставки)', 'Poster\n(расходы)',
    'Выручка (с)', 'Расходы (с)', 'Итог дня'
]

HDR_TASKS = ['#', 'Задача', 'Список (Trello)', 'Срок', 'Статус', '', '', '', '', '']

HDR_FIN = [
    'Показатель', 'Ед.', 'Норма', f'Факт ({MONTH_RU.get(TODAY.month-1 or 12, "—")})',
    'Отклонение', 'Статус', '', '', '', ''
]

HDR_NOTES = ['Дата', 'Тип нарушения', 'Описание', 'Реакция управляющего', 'Закрыто?',
             '', '', '', '', '']


def build_ops_rows():
    rows = []
    for d in MONTH_DAYS:
        wd = d.weekday()
        date_str = d.strftime('%d.%m.%Y')
        day_str  = WEEKDAYS_RU[wd]
        rows.append([date_str, day_str, '', '', '', '', '', '', '', ''])
    return rows


def build_tasks_rows(tasks):
    rows = []
    for i, t in enumerate(tasks, 1):
        due = t['due'] or '—'
        rows.append([str(i), t['name'], t['list'], due, 'В работе', '', '', '', '', ''])
    return rows


def build_fin_rows(loc):
    rows = []
    for norm in FIN_NORMS[loc]:
        rows.append([norm[0], norm[1], norm[2], norm[3], norm[4], '', '', '', '', ''])
    return rows


def build_notes_rows(n=5):
    return [['', '', '', '', '', '', '', '', '', ''] for _ in range(n)]


# ─── Запись листа ─────────────────────────────────────────────────────────────

def write_values(s, ss_id, sheet_name, values, start='A1'):
    body = {'valueInputOption': 'USER_ENTERED', 'data': [
        {'range': f"'{sheet_name}'!{start}", 'values': values}
    ]}
    sheets_post(s, ss_id, 'values:batchUpdate', body)


def format_location_sheet(s, ss_id, sid, loc_name, manager, tasks):
    ops_rows   = build_ops_rows()
    tasks_rows = build_tasks_rows(tasks)
    fin_rows   = build_fin_rows(loc_name)
    notes_rows = build_notes_rows(5)

    month_label = f"{MONTH_RU[MONTH.month]} {MONTH.year}"

    # Row positions (0-indexed)
    R_TITLE      = 0
    R_GAP1       = 1
    R_B1_HDR     = 2
    R_B1_COLS    = 3
    R_B1_DATA    = 4
    R_B1_END     = R_B1_DATA + len(ops_rows)   # exclusive
    R_GAP2       = R_B1_END
    R_B2_HDR     = R_GAP2 + 1
    R_B2_COLS    = R_B2_HDR + 1
    R_B2_DATA    = R_B2_COLS + 1
    R_B2_END     = R_B2_DATA + max(len(tasks_rows), 1)
    R_GAP3       = R_B2_END
    R_B3_HDR     = R_GAP3 + 1
    R_B3_COLS    = R_B3_HDR + 1
    R_B3_DATA    = R_B3_COLS + 1
    R_B3_END     = R_B3_DATA + len(fin_rows)
    R_GAP4       = R_B3_END
    R_B4_HDR     = R_GAP4 + 1
    R_B4_COLS    = R_B4_HDR + 1
    R_B4_DATA    = R_B4_COLS + 1
    R_B4_END     = R_B4_DATA + len(notes_rows)
    R_TOTAL      = R_B4_END + 2

    # ── Значения ──────────────────────────────────────────────────────────────
    title_row   = [f'{loc_name} — Контроль управляющего  •  {manager}  •  {month_label}']
    b1_hdr_row  = ['БЛОК 1: ЕЖЕДНЕВНАЯ ОПЕРАЦИОННАЯ РАБОТА НА ТОЧКЕ']
    b2_hdr_row  = ['БЛОК 2: ВХОДЯЩИЕ ЗАДАЧИ (TRELLO)']
    b3_hdr_row  = ['БЛОК 3: ФИНАНСОВЫЕ ПОКАЗАТЕЛИ — НОРМЫ vs ФАКТ']
    b4_hdr_row  = ['БЛОК 4: КОНТРОЛЬ И ЗАМЕЧАНИЯ']

    all_values = [title_row, ['']]
    all_values.append(b1_hdr_row)
    all_values.append(HDR_OPS)
    all_values += ops_rows
    all_values.append([''])
    all_values.append(b2_hdr_row)
    all_values.append(HDR_TASKS)
    all_values += (tasks_rows if tasks_rows else [['—', 'Нет активных задач', '', '', '', '', '', '', '', '']])
    all_values.append([''])
    all_values.append(b3_hdr_row)
    all_values.append(HDR_FIN)
    all_values += fin_rows
    all_values.append([''])
    all_values.append(b4_hdr_row)
    all_values.append(HDR_NOTES)
    all_values += notes_rows

    write_values(s, ss_id, loc_name, all_values)

    # ── Форматирование ────────────────────────────────────────────────────────
    reqs = []

    # Ширины столбцов A-J
    widths = [85, 55, 105, 110, 100, 100, 100, 110, 110, 95]
    for col, w in enumerate(widths):
        reqs.append(r_colwidth(sid, col, w))

    # Высота строки заголовка
    reqs.append(r_rowheight(sid, R_TITLE, R_TITLE+1, 40))

    # Заморозить первую строку
    reqs.append(r_freeze(sid, rows=1))

    # TITLE: merge + формат
    reqs.append(r_merge(sid, R_TITLE, R_TITLE+1, 0, NCOLS))
    reqs.append(r_fmt(sid, R_TITLE, R_TITLE+1, 0, NCOLS,
                      bold=True, color=C_DARK_GREEN, fg=C_WHITE,
                      size=SHEETS_SIZE_HEADING, halign='CENTER', valign='MIDDLE'))

    # БЛОК 1 — тёмно-зелёный
    reqs.append(r_merge(sid, R_B1_HDR, R_B1_HDR+1, 0, NCOLS))
    reqs.append(r_fmt(sid, R_B1_HDR, R_B1_HDR+1, 0, NCOLS,
                      bold=True, color=C_DARK_GREEN, fg=C_WHITE,
                      halign='LEFT', valign='MIDDLE', size=13))
    reqs.append(r_rowheight(sid, R_B1_HDR, R_B1_HDR+1, 28))
    # Заголовки столбцов блока 1
    reqs.append(r_fmt(sid, R_B1_COLS, R_B1_COLS+1, 0, NCOLS,
                      bold=True, color=C_LIGHT_GREEN, halign='CENTER',
                      valign='MIDDLE', wrap=True, size=12))
    reqs.append(r_rowheight(sid, R_B1_COLS, R_B1_COLS+1, 45))
    # Данные блока 1 — чередование строк + выходные дни
    for i, d in enumerate(MONTH_DAYS):
        r = R_B1_DATA + i
        wd = d.weekday()
        color = C_LIGHT_YELL if wd in WEEKEND else (C_LIGHT if i % 2 == 1 else C_WHITE)
        reqs.append(r_bg(sid, r, r+1, 0, NCOLS, color))
    reqs.append(r_fmt(sid, R_B1_DATA, R_B1_END, 0, NCOLS,
                      halign='CENTER', valign='MIDDLE', size=12))
    reqs.append(r_fmt(sid, R_B1_DATA, R_B1_END, 1, 2, bold=True, size=12))  # День — жирный
    reqs.append(r_border(sid, R_B1_COLS, R_B1_END, 0, NCOLS))

    # БЛОК 2 — синий
    reqs.append(r_merge(sid, R_B2_HDR, R_B2_HDR+1, 0, NCOLS))
    reqs.append(r_fmt(sid, R_B2_HDR, R_B2_HDR+1, 0, NCOLS,
                      bold=True, color=C_BLUE, fg=C_WHITE,
                      halign='LEFT', valign='MIDDLE', size=13))
    reqs.append(r_rowheight(sid, R_B2_HDR, R_B2_HDR+1, 28))
    reqs.append(r_fmt(sid, R_B2_COLS, R_B2_COLS+1, 0, NCOLS,
                      bold=True, color=C_LIGHT_BLUE, halign='CENTER',
                      valign='MIDDLE', wrap=True, size=12))
    reqs.append(r_rowheight(sid, R_B2_COLS, R_B2_COLS+1, 35))
    # Данные задач
    for i in range(max(len(tasks_rows), 1)):
        r = R_B2_DATA + i
        color = C_LIGHT if i % 2 == 1 else C_WHITE
        reqs.append(r_bg(sid, r, r+1, 0, NCOLS, color))
    reqs.append(r_fmt(sid, R_B2_DATA, R_B2_END, 0, 1, halign='CENTER', size=12))   # #
    reqs.append(r_fmt(sid, R_B2_DATA, R_B2_END, 1, 5, halign='LEFT', wrap=True, size=12))
    reqs.append(r_fmt(sid, R_B2_DATA, R_B2_END, 5, NCOLS, size=12))
    reqs.append(r_rowheight(sid, R_B2_DATA, R_B2_END, 36))
    reqs.append(r_border(sid, R_B2_COLS, R_B2_END, 0, 5))

    # БЛОК 3 — бирюзовый
    reqs.append(r_merge(sid, R_B3_HDR, R_B3_HDR+1, 0, NCOLS))
    reqs.append(r_fmt(sid, R_B3_HDR, R_B3_HDR+1, 0, NCOLS,
                      bold=True, color=C_TEAL, fg=C_WHITE,
                      halign='LEFT', valign='MIDDLE', size=13))
    reqs.append(r_rowheight(sid, R_B3_HDR, R_B3_HDR+1, 28))
    reqs.append(r_fmt(sid, R_B3_COLS, R_B3_COLS+1, 0, NCOLS,
                      bold=True, color=C_LIGHT_TEAL, halign='CENTER',
                      valign='MIDDLE', wrap=True, size=12))
    reqs.append(r_rowheight(sid, R_B3_COLS, R_B3_COLS+1, 35))
    for i in range(len(fin_rows)):
        r = R_B3_DATA + i
        color = C_LIGHT if i % 2 == 1 else C_WHITE
        reqs.append(r_bg(sid, r, r+1, 0, NCOLS, color))
    reqs.append(r_fmt(sid, R_B3_DATA, R_B3_END, 0, NCOLS, size=12))
    reqs.append(r_fmt(sid, R_B3_DATA, R_B3_END, 0, 1, halign='LEFT', size=12))
    reqs.append(r_fmt(sid, R_B3_DATA, R_B3_END, 1, NCOLS, halign='CENTER', size=12))
    reqs.append(r_border(sid, R_B3_COLS, R_B3_END, 0, 6))

    # БЛОК 4 — фиолетовый
    reqs.append(r_merge(sid, R_B4_HDR, R_B4_HDR+1, 0, NCOLS))
    reqs.append(r_fmt(sid, R_B4_HDR, R_B4_HDR+1, 0, NCOLS,
                      bold=True, color=C_PURPLE, fg=C_WHITE,
                      halign='LEFT', valign='MIDDLE', size=13))
    reqs.append(r_rowheight(sid, R_B4_HDR, R_B4_HDR+1, 28))
    reqs.append(r_fmt(sid, R_B4_COLS, R_B4_COLS+1, 0, NCOLS,
                      bold=True, color=C_LIGHT_PURP, halign='CENTER',
                      valign='MIDDLE', wrap=True, size=12))
    reqs.append(r_rowheight(sid, R_B4_COLS, R_B4_COLS+1, 35))
    for i in range(len(notes_rows)):
        r = R_B4_DATA + i
        reqs.append(r_rowheight(sid, r, r+1, 30))
    reqs.append(r_fmt(sid, R_B4_DATA, R_B4_END, 0, NCOLS, size=12))
    reqs.append(r_border(sid, R_B4_COLS, R_B4_END, 0, 5))

    sheets_post(s, ss_id, 'batchUpdate', {'requests': reqs})
    print(f'  Лист «{loc_name}» отформатирован ({R_TOTAL} строк).')


# ─── Лист «Свод» ──────────────────────────────────────────────────────────────

def write_svod(s, ss_id, sid, tasks_zb, tasks_ovir):
    month_label = f"{MONTH_RU[MONTH.month]} {MONTH.year}"

    zb_active  = [t for t in tasks_zb  if t['list'] not in DONE_LISTS]
    ov_active  = [t for t in tasks_ovir if t['list'] not in DONE_LISTS]
    zb_urgent  = sum(1 for t in zb_active  if t['list'] == 'ASAP')
    ov_urgent  = sum(1 for t in ov_active  if t['list'] == 'ASAP')
    zb_wip     = sum(1 for t in zb_active  if t['list'] == 'В процессе')
    ov_wip     = sum(1 for t in ov_active  if t['list'] == 'В процессе')

    values = [
        [f'СВОД — Контроль управляющих  •  {month_label}'],
        [''],
        ['ЗАДАЧИ — СВОДНАЯ СТАТИСТИКА'],
        ['Показатель', 'ЗБ (Владимир)', 'ОВИР (Дилчу)', 'Итого'],
        ['ASAP (срочные)',   zb_urgent, ov_urgent, zb_urgent + ov_urgent],
        ['В процессе',       zb_wip,    ov_wip,    zb_wip + ov_wip],
        ['Всего активных',   len(zb_active), len(ov_active), len(zb_active)+len(ov_active)],
        [''],
        ['ФИНАНСОВЫЕ НОРМЫ — ПЛАН vs ФАКТ'],
        ['Показатель', 'Ед.', 'Норма', 'ЗБ Факт', 'ОВИР Факт', 'ЗБ Статус', 'ОВИР Статус'],
        ['Выручка в день', 'с', '', '', '', '', ''],
        ['Выручка за месяц', 'с', '', '', '', '', ''],
        ['Средний чек', 'с', '', '', '', '', ''],
        ['Кол-во чеков / день', 'шт', '', '', '', '', ''],
        ['FoodCost %', '%', '≤ 35%', '', '', '', ''],
        ['Расходы / Выручка %', '%', '≤ 25%', '', '', '', ''],
        ['Списания / Выручка %', '%', '≤ 3%', '', '', '', ''],
        ['ФОТ / Выручка %', '%', '≤ 30%', '', '', '', ''],
        [''],
        ['ОПЕРАТИВНЫЙ КОНТРОЛЬ — ЭТОТ МЕСЯЦ'],
        ['Показатель', 'ЗБ', 'ОВИР', 'Норма'],
        ['Дней без нарушений', '', '', f'{len(MONTH_DAYS)} из {len(MONTH_DAYS)}'],
        ['Открытий по регламенту', '', '', f'{len(MONTH_DAYS)} из {len(MONTH_DAYS)}'],
        ['Poster заполнен ежедневно', '', '', 'Каждый день'],
        ['Еженедельных инвентаризаций', '', '', '4 из 4'],
        ['Отчётов сдано вовремя', '', '', 'Еженедельно'],
    ]

    write_values(s, ss_id, 'Свод', values)

    reqs = []
    # Ширины
    for col, w in enumerate([260, 150, 150, 130, 130, 120, 120]):
        reqs.append(r_colwidth(sid, col, w))

    # Заголовок
    reqs.append(r_merge(sid, 0, 1, 0, 7))
    reqs.append(r_fmt(sid, 0, 1, 0, 7, bold=True, color=C_DARK_GREEN, fg=C_WHITE,
                      halign='CENTER', valign='MIDDLE', size=SHEETS_SIZE_HEADING))
    reqs.append(r_rowheight(sid, 0, 1, 40))

    # Блок задач
    reqs.append(r_merge(sid, 2, 3, 0, 7))
    reqs.append(r_fmt(sid, 2, 3, 0, 7, bold=True, color=C_BLUE, fg=C_WHITE,
                      halign='LEFT', valign='MIDDLE', size=13))
    reqs.append(r_fmt(sid, 3, 4, 0, 4, bold=True, color=C_LIGHT_BLUE,
                      halign='CENTER', size=12))
    for i in range(3):
        clr = C_LIGHT if i % 2 == 0 else C_WHITE
        reqs.append(r_bg(sid, 4+i, 5+i, 0, 4, clr))
    reqs.append(r_fmt(sid, 4, 7, 0, 4, halign='CENTER', size=12))
    reqs.append(r_fmt(sid, 4, 7, 0, 1, halign='LEFT', size=12))
    reqs.append(r_border(sid, 3, 7, 0, 4))

    # Блок финансов
    reqs.append(r_merge(sid, 8, 9, 0, 7))
    reqs.append(r_fmt(sid, 8, 9, 0, 7, bold=True, color=C_TEAL, fg=C_WHITE,
                      halign='LEFT', valign='MIDDLE', size=13))
    reqs.append(r_fmt(sid, 9, 10, 0, 7, bold=True, color=C_LIGHT_TEAL,
                      halign='CENTER', size=12))
    for i in range(8):
        clr = C_LIGHT if i % 2 == 0 else C_WHITE
        reqs.append(r_bg(sid, 10+i, 11+i, 0, 7, clr))
    reqs.append(r_fmt(sid, 10, 18, 0, 7, halign='CENTER', size=12))
    reqs.append(r_fmt(sid, 10, 18, 0, 1, halign='LEFT', size=12))
    reqs.append(r_border(sid, 9, 18, 0, 7))

    # Блок оперативного контроля
    reqs.append(r_merge(sid, 19, 20, 0, 7))
    reqs.append(r_fmt(sid, 19, 20, 0, 7, bold=True, color=C_DARK_GREEN, fg=C_WHITE,
                      halign='LEFT', valign='MIDDLE', size=13))
    reqs.append(r_fmt(sid, 20, 21, 0, 4, bold=True, color=C_LIGHT_GREEN,
                      halign='CENTER', size=12))
    for i in range(5):
        clr = C_LIGHT if i % 2 == 0 else C_WHITE
        reqs.append(r_bg(sid, 21+i, 22+i, 0, 4, clr))
    reqs.append(r_fmt(sid, 21, 26, 0, 4, halign='CENTER', size=12))
    reqs.append(r_fmt(sid, 21, 26, 0, 1, halign='LEFT', size=12))
    reqs.append(r_border(sid, 20, 26, 0, 4))

    sheets_post(s, ss_id, 'batchUpdate', {'requests': reqs})
    print(f'  Лист «Свод» отформатирован.')


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    s = get_session()

    print('Загружаю задачи из Trello...')
    tasks_vl = get_trello_tasks(MEMBER_VL)
    tasks_dl = get_trello_tasks(MEMBER_DL)
    print(f'  Владимир: {len(tasks_vl)} активных задач')
    print(f'  Дилчу:    {len(tasks_dl)} активных задач')

    print('\nСоздаю таблицу...')
    ss_id = create_spreadsheet(s)

    sids = get_sheet_ids(s, ss_id)
    sid_zb   = sids['ЗБ']
    sid_ovir = sids['ОВИР']
    sid_svod = sids['Свод']

    print('\nЗаполняю лист ЗБ...')
    format_location_sheet(s, ss_id, sid_zb, 'ЗБ', 'Владимир Митюков', tasks_vl)

    print('Заполняю лист ОВИР...')
    format_location_sheet(s, ss_id, sid_ovir, 'ОВИР', 'Дилчу Шодибеков', tasks_dl)

    print('Заполняю лист Свод...')
    write_svod(s, ss_id, sid_svod, tasks_vl, tasks_dl)

    print(f'\nГотово! ID: {ss_id}')
    print(f'https://docs.google.com/spreadsheets/d/{ss_id}/edit')
    return ss_id


if __name__ == '__main__':
    main()
