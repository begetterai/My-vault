#!/usr/bin/env python3
"""
Life OS — трекер привычек + личные финансы.
Создаёт Google Sheet в Private/Трекеры.
"""
import os, json, calendar, datetime
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'romashka-drive.json')
TRACKERS_FOLDER = '1JmYk1Vp1sazmcL_uIrDmaxr7UA-2sqXx'

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Цвета
DARK_BG     = {'red': 0.08, 'green': 0.08, 'blue': 0.12}
CARD_BG     = {'red': 0.12, 'green': 0.13, 'blue': 0.18}
HEADER_BG   = {'red': 0.15, 'green': 0.16, 'blue': 0.22}
ACCENT_RED  = {'red': 0.90, 'green': 0.22, 'blue': 0.22}
ACCENT_BLUE = {'red': 0.25, 'green': 0.55, 'blue': 0.95}
ACCENT_GRN  = {'red': 0.20, 'green': 0.78, 'blue': 0.45}
ACCENT_ORG  = {'red': 0.95, 'green': 0.60, 'blue': 0.10}
WHITE       = {'red': 1.0,  'green': 1.0,  'blue': 1.0}
GRAY        = {'red': 0.55, 'green': 0.55, 'blue': 0.60}
LIGHT_GRAY  = {'red': 0.80, 'green': 0.80, 'blue': 0.85}

def cell_fmt(bg=None, fg=None, bold=False, size=10, halign='LEFT', valign='MIDDLE'):
    fmt = {
        'textFormat': {'bold': bold, 'fontSize': size,
                       'foregroundColor': fg or WHITE},
        'horizontalAlignment': halign,
        'verticalAlignment': valign,
    }
    if bg:
        fmt['backgroundColor'] = bg
    return fmt

def rng(sid, r1, c1, r2=None, c2=None):
    d = {'sheetId': sid, 'startRowIndex': r1, 'startColumnIndex': c1}
    if r2 is not None: d['endRowIndex'] = r2
    if c2 is not None: d['endColumnIndex'] = c2
    return d

def repeat_cell(sid, r1, c1, r2, c2, fmt):
    return {'repeatCell': {'range': rng(sid, r1, c1, r2, c2),
                           'cell': {'userEnteredFormat': fmt},
                           'fields': 'userEnteredFormat'}}

def merge(sid, r1, c1, r2, c2):
    return {'mergeCells': {'range': rng(sid, r1, c1, r2, c2), 'mergeType': 'MERGE_ALL'}}

def col_width(sid, c1, c2, px):
    return {'updateDimensionProperties': {
        'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                  'startIndex': c1, 'endIndex': c2},
        'properties': {'pixelSize': px}, 'fields': 'pixelSize'}}

def row_height(sid, r1, r2, px):
    return {'updateDimensionProperties': {
        'range': {'sheetId': sid, 'dimension': 'ROWS',
                  'startIndex': r1, 'endIndex': r2},
        'properties': {'pixelSize': px}, 'fields': 'pixelSize'}}

def freeze(sid, rows=0, cols=0):
    return {'updateSheetProperties': {
        'properties': {'sheetId': sid, 'gridProperties': {
            'frozenRowCount': rows, 'frozenColumnCount': cols}},
        'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}}


def build_habits_sheet(sid, year, month):
    """Строит лист трекера привычек."""
    reqs = []
    vals = {}  # (row, col): value

    days_in_month = calendar.monthrange(year, month)[1]
    month_name = ['', 'ЯНВАРЬ','ФЕВРАЛЬ','МАРТ','АПРЕЛЬ','МАЙ','ИЮНЬ',
                  'ИЮЛЬ','АВГУСТ','СЕНТЯБРЬ','ОКТЯБРЬ','НОЯБРЬ','ДЕКАБРЬ'][month]
    day_names = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']

    # Привычки по группам
    habits = [
        ('ЗДОРОВЬЕ', ACCENT_GRN, [
            ('🏋️ Зал',              '3-4x/нед'),
            ('🚿 Холодный душ',      'каждый день'),
            ('🧘 Медитация',         'каждый день'),
            ('💨 Дыхательная',       'каждый день'),
        ]),
        ('РАЗВИТИЕ', ACCENT_BLUE, [
            ('📚 Чтение',            'каждый день'),
        ]),
        ('ЛИЧНОЕ', ACCENT_ORG, [
            ('💰 Записать расходы',  'каждый день'),
            ('😴 Сон до 00:00',      'каждый день'),
        ]),
    ]

    # Размеры
    N_HABITS = sum(len(h) for _, _, h in habits) + len(habits)  # +1 заголовок группы
    HABIT_COL = 0   # колонка названий (A)
    FREQ_COL  = 1   # частота (B)
    DAY_START = 2   # дни начинаются с C
    STREAK_COL = DAY_START + days_in_month      # streak
    PCT_COL    = STREAK_COL + 1                 # %
    TOTAL_COLS = PCT_COL + 1

    # Фон всего листа
    reqs.append(repeat_cell(sid, 0, 0, 200, TOTAL_COLS + 5, cell_fmt(bg=DARK_BG)))

    # Ширины колонок
    reqs.append(col_width(sid, HABIT_COL, HABIT_COL+1, 200))
    reqs.append(col_width(sid, FREQ_COL,  FREQ_COL+1,  90))
    for d in range(days_in_month):
        reqs.append(col_width(sid, DAY_START+d, DAY_START+d+1, 28))
    reqs.append(col_width(sid, STREAK_COL, STREAK_COL+1, 65))
    reqs.append(col_width(sid, PCT_COL,    PCT_COL+1,    65))

    # Заголовок месяца (строка 0)
    reqs.append(row_height(sid, 0, 1, 50))
    reqs.append(merge(sid, 0, 0, 1, FREQ_COL+1))
    vals[(0, 0)] = f'{month_name} {year}'
    reqs.append(repeat_cell(sid, 0, 0, 1, FREQ_COL+1,
        cell_fmt(bg=CARD_BG, bold=True, size=16, halign='LEFT')))

    # Заголовок ПРОГРЕСС ЗА МЕСЯЦ
    reqs.append(merge(sid, 0, DAY_START, 1, PCT_COL+1))
    vals[(0, DAY_START)] = '📊 ПРОГРЕСС ЗА МЕСЯЦ'
    reqs.append(repeat_cell(sid, 0, DAY_START, 1, PCT_COL+1,
        cell_fmt(bg=CARD_BG, bold=True, size=11, halign='CENTER')))

    # Строка дней (строка 1)
    reqs.append(row_height(sid, 1, 2, 32))
    reqs.append(repeat_cell(sid, 1, 0, 2, TOTAL_COLS,
        cell_fmt(bg=HEADER_BG, bold=True, size=9, halign='CENTER', fg=LIGHT_GRAY)))
    vals[(1, HABIT_COL)] = 'ПРИВЫЧКА'
    vals[(1, FREQ_COL)]  = 'ЧАСТОТА'
    for d in range(days_in_month):
        col = DAY_START + d
        dow = datetime.date(year, month, d+1).weekday()
        vals[(1, col)] = str(d+1)
        # Выходные — другой цвет
        if dow >= 5:
            reqs.append(repeat_cell(sid, 1, col, 2, col+1,
                cell_fmt(bg=HEADER_BG, bold=True, size=8, halign='CENTER', fg=ACCENT_ORG)))
    vals[(1, STREAK_COL)] = '🔥'
    vals[(1, PCT_COL)]    = '%'

    # Привычки
    row = 2
    for group_name, group_color, group_habits in habits:
        reqs.append(row_height(sid, row, row+1, 28))
        reqs.append(merge(sid, row, 0, row+1, TOTAL_COLS))
        vals[(row, 0)] = f'  {group_name}'
        reqs.append(repeat_cell(sid, row, 0, row+1, TOTAL_COLS,
            cell_fmt(bg=group_color, bold=True, size=9, fg={'red':0.08,'green':0.08,'blue':0.08})))
        row += 1

        for habit_name, freq in group_habits:
            reqs.append(row_height(sid, row, row+1, 30))
            vals[(row, HABIT_COL)] = f'  {habit_name}'
            vals[(row, FREQ_COL)]  = freq
            reqs.append(repeat_cell(sid, row, HABIT_COL, row+1, FREQ_COL+1,
                cell_fmt(bg=CARD_BG, size=9)))
            reqs.append(repeat_cell(sid, row, FREQ_COL, row+1, FREQ_COL+1,
                cell_fmt(bg=CARD_BG, size=8, halign='CENTER', fg=GRAY)))

            # Чекбоксы
            for d in range(days_in_month):
                col = DAY_START + d
                dow = datetime.date(year, month, d+1).weekday()
                bg = {'red':0.10,'green':0.11,'blue':0.15} if dow >= 5 else CARD_BG
                reqs.append(repeat_cell(sid, row, col, row+1, col+1,
                    cell_fmt(bg=bg, halign='CENTER')))

            # Чекбоксы через data validation
            reqs.append({'setDataValidation': {
                'range': rng(sid, row, DAY_START, row+1, DAY_START+days_in_month),
                'rule': {'condition': {'type': 'BOOLEAN'}, 'strict': True, 'showCustomUi': True}
            }})

            # Streak формула
            day_range_start = chr(ord('A') + DAY_START)
            day_range_end   = chr(ord('A') + DAY_START + days_in_month - 1)
            r_num = row + 1
            streak_col_letter = chr(ord('A') + STREAK_COL)
            pct_col_letter    = chr(ord('A') + PCT_COL)

            vals[(row, STREAK_COL)] = f'=COUNTIF({day_range_start}{r_num}:{day_range_end}{r_num},TRUE)'
            vals[(row, PCT_COL)]    = f'=IFERROR({streak_col_letter}{r_num}/COUNTA({day_range_start}{r_num}:{day_range_end}{r_num}),0)'

            reqs.append(repeat_cell(sid, row, STREAK_COL, row+1, STREAK_COL+1,
                cell_fmt(bg=CARD_BG, bold=True, size=10, halign='CENTER', fg=ACCENT_ORG)))
            reqs.append(repeat_cell(sid, row, PCT_COL, row+1, PCT_COL+1,
                cell_fmt(bg=CARD_BG, bold=True, size=10, halign='CENTER', fg=ACCENT_GRN)))
            reqs.append({'repeatCell': {
                'range': rng(sid, row, PCT_COL, row+1, PCT_COL+1),
                'cell': {'userEnteredFormat': {
                    'numberFormat': {'type': 'PERCENT', 'pattern': '0%'},
                    'backgroundColor': CARD_BG,
                    'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': ACCENT_GRN},
                    'horizontalAlignment': 'CENTER'
                }},
                'fields': 'userEnteredFormat'
            }})

            row += 1

    reqs.append(freeze(sid, rows=2, cols=2))

    return reqs, vals, row


def build_finance_sheet(sid):
    """Строит лист личных финансов."""
    reqs = []
    vals = {}

    MONTHS = ['Январь','Февраль','Март','Апрель','Май','Июнь',
              'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']

    # Доходы
    income = [
        ('💼 Зарплата Ромашка',   12000),
        ('📊 Бухгалтерия',         5000),
    ]
    # Расходы
    expenses = [
        ('🏠 Аренда жилья',        5200),
        ('💡 Коммуналка',           250),
        ('🌐 Интернет',             240),
        ('📱 Телефон',              150),
        ('⛽ Топливо',             1000),
        ('🎮 Подписки',             600),
        ('🏋️ Спортпит',           1000),
        ('🥗 Еда',                 1500),
        ('🚬 Стики',                600),
        ('📦 Прочее',               500),
    ]
    # Накопления
    savings = [
        ('💳 На долг',             5000),
    ]

    total_income   = sum(v for _, v in income)
    total_expenses = sum(v for _, v in expenses)
    total_savings  = sum(v for _, v in savings)
    balance        = total_income - total_expenses - total_savings

    # Ширины
    reqs.append(repeat_cell(sid, 0, 0, 200, 30, cell_fmt(bg=DARK_BG)))
    reqs.append(col_width(sid, 0, 1, 220))   # Категория
    reqs.append(col_width(sid, 1, 2, 110))   # Плановый
    reqs.append(col_width(sid, 2, 3, 110))   # Фактический
    reqs.append(col_width(sid, 3, 4, 30))    # разделитель
    for m in range(12):
        reqs.append(col_width(sid, 4+m, 5+m, 95))

    # Заголовок
    reqs.append(row_height(sid, 0, 1, 50))
    reqs.append(merge(sid, 0, 0, 1, 3))
    vals[(0, 0)] = '💰 ЛИЧНЫЕ ФИНАНСЫ 2026'
    reqs.append(repeat_cell(sid, 0, 0, 1, 3,
        cell_fmt(bg=CARD_BG, bold=True, size=14, halign='LEFT')))

    # Заголовки месяцев
    reqs.append(row_height(sid, 1, 2, 30))
    vals[(1, 0)] = 'КАТЕГОРИЯ'
    vals[(1, 1)] = 'ПЛАН'
    vals[(1, 2)] = 'ФАКТ'
    reqs.append(repeat_cell(sid, 1, 0, 2, 3,
        cell_fmt(bg=HEADER_BG, bold=True, size=9, halign='CENTER', fg=LIGHT_GRAY)))
    for m, mn in enumerate(MONTHS):
        vals[(1, 4+m)] = mn
        reqs.append(repeat_cell(sid, 1, 4+m, 2, 5+m,
            cell_fmt(bg=HEADER_BG, bold=True, size=8, halign='CENTER', fg=LIGHT_GRAY)))

    row = 2

    def add_section(title, color, items, is_total=False):
        nonlocal row
        # Заголовок секции
        reqs.append(row_height(sid, row, row+1, 28))
        reqs.append(merge(sid, row, 0, row+1, 16))
        vals[(row, 0)] = f'  {title}'
        reqs.append(repeat_cell(sid, row, 0, row+1, 16,
            cell_fmt(bg=color, bold=True, size=9,
                     fg={'red':0.05,'green':0.05,'blue':0.05})))
        section_start = row + 1
        row += 1

        for name, plan in items:
            reqs.append(row_height(sid, row, row+1, 28))
            vals[(row, 0)] = f'   {name}'
            vals[(row, 1)] = plan
            reqs.append(repeat_cell(sid, row, 0, row+1, 1,
                cell_fmt(bg=CARD_BG, size=9)))
            reqs.append(repeat_cell(sid, row, 1, row+1, 3,
                cell_fmt(bg=CARD_BG, size=10, halign='RIGHT', bold=True)))
            for m in range(12):
                reqs.append(repeat_cell(sid, row, 4+m, row+1, 5+m,
                    cell_fmt(bg=CARD_BG, size=10, halign='RIGHT')))
            row += 1

        # Итого
        reqs.append(row_height(sid, row, row+1, 30))
        vals[(row, 0)] = f'   ИТОГО'
        vals[(row, 1)] = sum(v for _, v in items)
        reqs.append(repeat_cell(sid, row, 0, row+1, 3,
            cell_fmt(bg=HEADER_BG, bold=True, size=10, halign='RIGHT', fg=color)))
        row += 1
        return section_start

    add_section('ДОХОДЫ', ACCENT_GRN, income)
    add_section('РАСХОДЫ', ACCENT_RED, expenses)
    add_section('НАКОПЛЕНИЯ / ДОЛГ', ACCENT_BLUE, savings)

    # Баланс
    reqs.append(row_height(sid, row, row+1, 36))
    reqs.append(merge(sid, row, 0, row+1, 2))
    vals[(row, 0)] = '  💵 СВОБОДНЫЕ ДЕНЬГИ'
    vals[(row, 2)] = balance
    reqs.append(repeat_cell(sid, row, 0, row+1, 3,
        cell_fmt(bg=ACCENT_GRN if balance >= 0 else ACCENT_RED,
                 bold=True, size=12, halign='CENTER',
                 fg={'red':0.05,'green':0.05,'blue':0.05})))

    # Прогресс долга
    row += 2
    reqs.append(row_height(sid, row, row+1, 40))
    reqs.append(merge(sid, row, 0, row+1, 3))
    vals[(row, 0)] = '🎯 ДОЛГ: цель закрыть 80 000с → 5 000с/мес → 16 мес (октябрь 2027)'
    reqs.append(repeat_cell(sid, row, 0, row+1, 3,
        cell_fmt(bg=CARD_BG, bold=True, size=9, fg=ACCENT_ORG)))

    reqs.append(freeze(sid, rows=2, cols=1))
    return reqs, vals


def main():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    session = AuthorizedSession(creds)

    today = datetime.date.today()

    # Создать spreadsheet
    ss_body = {
        'properties': {'title': 'Life OS — Азиз 2026', 'locale': 'ru_RU'},
        'sheets': [
            {'properties': {'sheetId': 1, 'title': f'Привычки {today.strftime("%B %Y")}',
                            'tabColor': {'red':0.20,'green':0.78,'blue':0.45},
                            'gridProperties': {'rowCount': 100, 'columnCount': 50}}},
            {'properties': {'sheetId': 2, 'title': 'Финансы 2026',
                            'tabColor': {'red':0.25,'green':0.55,'blue':0.95},
                            'gridProperties': {'rowCount': 60, 'columnCount': 20}}},
        ]
    }
    # Создать файл через Drive API в нужной папке
    r_create = session.post(
        'https://www.googleapis.com/drive/v3/files',
        params={'supportsAllDrives': 'true'},
        json={
            'name': 'Life OS — Азиз 2026',
            'mimeType': 'application/vnd.google-apps.spreadsheet',
            'parents': [TRACKERS_FOLDER]
        }, timeout=30)
    ss_id = r_create.json()['id']
    print(f'✅ Spreadsheet создан: {ss_id}')

    # Добавить листы через Sheets API
    r = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
        json={'requests': [
            {'addSheet': {'properties': {'sheetId': 1,
                'title': f'Привычки {today.strftime("%B %Y")}',
                'tabColor': {'red':0.20,'green':0.78,'blue':0.45},
                'gridProperties': {'rowCount': 100, 'columnCount': 50}}}},
            {'addSheet': {'properties': {'sheetId': 2,
                'title': 'Финансы 2026',
                'tabColor': {'red':0.25,'green':0.55,'blue':0.95},
                'gridProperties': {'rowCount': 60, 'columnCount': 20}}}},
        ]}, timeout=30)
    print(f'📋 Листы добавлены: {r.status_code}')

    all_reqs = []
    all_updates = []

    # Лист привычек
    h_reqs, h_vals, _ = build_habits_sheet(1, today.year, today.month)
    all_reqs.extend(h_reqs)
    month_sheet = today.strftime("%B %Y")
    all_updates.extend([
        {'range': f"'Привычки {month_sheet}'!{chr(ord('A')+c)}{r+1}",
         'values': [[v]]}
        for (r, c), v in h_vals.items()
    ])

    # Лист финансов
    f_reqs, f_vals = build_finance_sheet(2)
    all_reqs.extend(f_reqs)
    all_updates.extend([
        {'range': f"'Финансы 2026'!{chr(ord('A')+c)}{r+1}", 'values': [[v]]}
        for (r, c), v in f_vals.items()
    ])

    # Применить форматирование
    r3 = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
        json={'requests': all_reqs}, timeout=60)
    print(f'🎨 Форматирование: {r3.status_code}')

    # Записать данные
    r4 = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/values:batchUpdate',
        json={'valueInputOption': 'USER_ENTERED', 'data': all_updates},
        timeout=60)
    print(f'📝 Данные: {r4.status_code}')

    print(f'\n🔗 https://docs.google.com/spreadsheets/d/{ss_id}')
    return ss_id


if __name__ == '__main__':
    main()
