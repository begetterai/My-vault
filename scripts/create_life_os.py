#!/usr/bin/env python3
"""
Life OS — трекер привычек (недельный вид + обзор) + личные финансы (доходы/расходы + графики).
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
ACCENT_PUR  = {'red': 0.60, 'green': 0.40, 'blue': 0.95}
WHITE       = {'red': 1.0,  'green': 1.0,  'blue': 1.0}
GRAY        = {'red': 0.55, 'green': 0.55, 'blue': 0.60}
LIGHT_GRAY  = {'red': 0.80, 'green': 0.80, 'blue': 0.85}

MONTHS_RU = ['', 'ЯНВАРЬ','ФЕВРАЛЬ','МАРТ','АПРЕЛЬ','МАЙ','ИЮНЬ',
             'ИЮЛЬ','АВГУСТ','СЕНТЯБРЬ','ОКТЯБРЬ','НОЯБРЬ','ДЕКАБРЬ']
MONTHS_SHORT = ['Январь','Февраль','Март','Апрель','Май','Июнь',
                'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
DAY_NAMES = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']


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

def col_letter(c):
    """0-indexed col -> A1 letter (поддержка >25)."""
    s = ''
    c += 1
    while c > 0:
        c, r = divmod(c - 1, 26)
        s = chr(65 + r) + s
    return s

def a1(row, col):
    return f'{col_letter(col)}{row+1}'


# ────────────────────────────────────────────────────────────────
# ЛИСТ ПРИВЫЧЕК — недельный вид + sidebar "Прогресс за месяц" +
# секция "Еженедельный обзор" с мини-графиками (SPARKLINE)
# ────────────────────────────────────────────────────────────────

HABITS = [
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
N_HABIT_ROWS = sum(len(h) for _, _, h in HABITS)  # без строк-заголовков групп


def week_chunks(days_in_month):
    """Разбивает дни месяца на недели по 7 (последняя — ДОП., может быть короче)."""
    chunks = []
    d = 1
    while d <= days_in_month:
        end = min(d + 6, days_in_month)
        chunks.append(list(range(d, end + 1)))
        d = end + 1
    return chunks


def build_habits_sheet(sid, year, month):
    reqs, vals = [], {}
    days_in_month = calendar.monthrange(year, month)[1]
    month_name = MONTHS_RU[month]
    weeks = week_chunks(days_in_month)  # список списков дней

    HABIT_COL = 0
    DAY_START = 1
    DAYS_END  = DAY_START + days_in_month          # колонка сразу после дней
    GAP_COL   = DAYS_END                            # узкий разделитель
    SIDE_COL  = GAP_COL + 1                         # начало "Прогресс за месяц"
    SIDE_W    = 4                                   # ширина sidebar в колонках
    TOTAL_COLS = SIDE_COL + SIDE_W

    # ── Фон + размеры ──
    reqs.append(repeat_cell(sid, 0, 0, 200, TOTAL_COLS + 2, cell_fmt(bg=DARK_BG)))
    reqs.append(col_width(sid, HABIT_COL, HABIT_COL + 1, 190))
    for d in range(days_in_month):
        reqs.append(col_width(sid, DAY_START + d, DAY_START + d + 1, 26))
    reqs.append(col_width(sid, GAP_COL, GAP_COL + 1, 16))
    reqs.append(col_width(sid, SIDE_COL, SIDE_COL + 1, 130))
    reqs.append(col_width(sid, SIDE_COL + 1, SIDE_COL + 2, 80))
    reqs.append(col_width(sid, SIDE_COL + 2, SIDE_COL + 3, 90))
    reqs.append(col_width(sid, SIDE_COL + 3, SIDE_COL + 4, 14))

    # ── Заголовок: "Помни о целях" + дата (строка 0) ──
    reqs.append(row_height(sid, 0, 1, 46))
    reqs.append(merge(sid, 0, HABIT_COL, 1, DAY_START))
    vals[(0, HABIT_COL)] = '🎯 Помни о целях'
    reqs.append(repeat_cell(sid, 0, HABIT_COL, 1, DAY_START,
        cell_fmt(bg=CARD_BG, bold=True, size=13, halign='LEFT')))

    # Над днями — название месяца, по недельным группам
    col_cursor = DAY_START
    for wi, week in enumerate(weeks):
        w_start, w_end = col_cursor, col_cursor + len(week)
        label = 'ДОП.' if len(week) < 7 and wi == len(weeks) - 1 else f'НЕДЕЛЯ {wi+1}'
        reqs.append(merge(sid, 0, w_start, 1, w_end))
        vals[(0, w_start)] = label
        reqs.append(repeat_cell(sid, 0, w_start, 1, w_end,
            cell_fmt(bg=CARD_BG, bold=True, size=10, halign='CENTER',
                     fg=ACCENT_RED if label == 'ДОП.' else WHITE)))
        col_cursor = w_end

    reqs.append(merge(sid, 0, SIDE_COL, 1, SIDE_COL + SIDE_W))
    vals[(0, SIDE_COL)] = f'📊 {month_name} {year}'
    reqs.append(repeat_cell(sid, 0, SIDE_COL, 1, SIDE_COL + SIDE_W,
        cell_fmt(bg=CARD_BG, bold=True, size=11, halign='CENTER')))

    # ── Строка дней недели Пн..Вс + номер дня (строка 1) ──
    reqs.append(row_height(sid, 1, 2, 30))
    vals[(1, HABIT_COL)] = 'ПРИВЫЧКА'
    reqs.append(repeat_cell(sid, 1, HABIT_COL, 2, DAY_START,
        cell_fmt(bg=HEADER_BG, bold=True, size=9, halign='LEFT', fg=LIGHT_GRAY)))
    col_cursor = DAY_START
    for week in weeks:
        for i, d in enumerate(week):
            dow = datetime.date(year, month, d).weekday()
            vals[(1, col_cursor)] = DAY_NAMES[dow]
            fg = ACCENT_ORG if dow >= 5 else LIGHT_GRAY
            reqs.append(repeat_cell(sid, 1, col_cursor, 2, col_cursor + 1,
                cell_fmt(bg=HEADER_BG, bold=True, size=8, halign='CENTER', fg=fg)))
            col_cursor += 1
    vals[(1, SIDE_COL)] = 'ОБЩИЙ ПРОГРЕСС'
    reqs.append(merge(sid, 1, SIDE_COL, 2, SIDE_COL + SIDE_W))
    reqs.append(repeat_cell(sid, 1, SIDE_COL, 2, SIDE_COL + SIDE_W,
        cell_fmt(bg=HEADER_BG, bold=True, size=8, halign='CENTER', fg=LIGHT_GRAY)))

    # ── Строка номеров дней (строка 2) ──
    reqs.append(row_height(sid, 2, 3, 26))
    col_cursor = DAY_START
    for week in weeks:
        for d in week:
            dow = datetime.date(year, month, d).weekday()
            fg = ACCENT_ORG if dow >= 5 else GRAY
            vals[(2, col_cursor)] = d
            reqs.append(repeat_cell(sid, 2, col_cursor, 3, col_cursor + 1,
                cell_fmt(bg=CARD_BG, size=8, halign='CENTER', fg=fg)))
            col_cursor += 1

    # ── Привычки по группам ──
    row = 3
    habit_rows = []  # (row)
    for group_name, group_color, group_habits in HABITS:
        reqs.append(row_height(sid, row, row + 1, 26))
        vals[(row, HABIT_COL)] = f'  {group_name}'
        reqs.append(repeat_cell(sid, row, HABIT_COL, row + 1, DAYS_END,
            cell_fmt(bg=group_color, bold=True, size=9, fg={'red':0.08,'green':0.08,'blue':0.08})))
        reqs.append(repeat_cell(sid, row, SIDE_COL, row + 1, SIDE_COL + SIDE_W, cell_fmt(bg=CARD_BG)))
        row += 1

        for habit_name, freq in group_habits:
            reqs.append(row_height(sid, row, row + 1, 28))
            vals[(row, HABIT_COL)] = f'  {habit_name}'
            reqs.append(repeat_cell(sid, row, HABIT_COL, row + 1, DAY_START,
                cell_fmt(bg=CARD_BG, size=9)))

            col_cursor = DAY_START
            for week in weeks:
                for d in week:
                    dow = datetime.date(year, month, d).weekday()
                    bg = {'red':0.10,'green':0.11,'blue':0.15} if dow >= 5 else CARD_BG
                    reqs.append(repeat_cell(sid, row, col_cursor, row + 1, col_cursor + 1,
                        cell_fmt(bg=bg, halign='CENTER')))
                    col_cursor += 1
            reqs.append({'setDataValidation': {
                'range': rng(sid, row, DAY_START, row + 1, DAYS_END),
                'rule': {'condition': {'type': 'BOOLEAN'}, 'strict': True, 'showCustomUi': True}
            }})

            day_rng = f'{a1(row, DAY_START)}:{a1(row, DAYS_END - 1)}'
            pct_formula = f'=IFERROR(COUNTIF({day_rng},TRUE)/COUNTA({day_rng}),0)'
            bar_formula = (f'=SPARKLINE(COUNTIF({day_rng},TRUE)/MAX(COUNTA({day_rng}),1),'
                           f'{{"charttype","bar";"max",1;"color1","#33C873";"empty",0}})')

            vals[(row, SIDE_COL)] = pct_formula
            vals[(row, SIDE_COL + 1)] = bar_formula
            vals[(row, SIDE_COL + 2)] = f'=COUNTIF({day_rng},TRUE)&"/"&COUNTA({day_rng})'

            reqs.append({'repeatCell': {
                'range': rng(sid, row, SIDE_COL, row + 1, SIDE_COL + 1),
                'cell': {'userEnteredFormat': {
                    'numberFormat': {'type': 'PERCENT', 'pattern': '0%'},
                    'backgroundColor': CARD_BG,
                    'textFormat': {'bold': True, 'fontSize': 9, 'foregroundColor': ACCENT_GRN},
                    'horizontalAlignment': 'CENTER'}},
                'fields': 'userEnteredFormat'}})
            reqs.append(repeat_cell(sid, row, SIDE_COL + 1, row + 1, SIDE_COL + 2, cell_fmt(bg=CARD_BG)))
            reqs.append(repeat_cell(sid, row, SIDE_COL + 2, row + 1, SIDE_COL + 3,
                cell_fmt(bg=CARD_BG, size=8, halign='CENTER', fg=GRAY)))
            reqs.append(repeat_cell(sid, row, SIDE_COL + 3, row + 1, SIDE_COL + 4, cell_fmt(bg=CARD_BG)))

            habit_rows.append(row)
            row += 1

    last_habit_row = row - 1

    # ОБЩИЙ ПРОГРЕСС (под заголовком sidebar, строка 2) — считаем по всем привычкам сразу
    all_day_ranges = '+'.join(f'COUNTIF({a1(r, DAY_START)}:{a1(r, DAYS_END-1)},TRUE)' for r in habit_rows)
    all_day_totals = '+'.join(f'COUNTA({a1(r, DAY_START)}:{a1(r, DAYS_END-1)})' for r in habit_rows)
    vals[(2, SIDE_COL)] = f'=({all_day_ranges})&"/"&({all_day_totals})'
    reqs.append(merge(sid, 2, SIDE_COL, 3, SIDE_COL + 2))
    reqs.append(repeat_cell(sid, 2, SIDE_COL, 3, SIDE_COL + 2,
        cell_fmt(bg=CARD_BG, bold=True, size=12, halign='CENTER', fg=ACCENT_ORG)))
    vals[(2, SIDE_COL + 2)] = f'=ROUND(({all_day_ranges})/({all_day_totals})*100,0)&"%"'
    reqs.append(merge(sid, 2, SIDE_COL + 2, 3, SIDE_COL + 4))
    reqs.append(repeat_cell(sid, 2, SIDE_COL + 2, 3, SIDE_COL + 4,
        cell_fmt(bg=CARD_BG, bold=True, size=12, halign='CENTER', fg=ACCENT_GRN)))

    # Донат-чарт "Задач выполнено" под sidebar
    donut_row = last_habit_row + 2
    reqs.append(merge(sid, donut_row, SIDE_COL, donut_row + 1, SIDE_COL + SIDE_W))
    vals[(donut_row, SIDE_COL)] = '🍩 Задач выполнено'
    reqs.append(repeat_cell(sid, donut_row, SIDE_COL, donut_row + 1, SIDE_COL + SIDE_W,
        cell_fmt(bg=CARD_BG, bold=True, size=9, halign='CENTER', fg=LIGHT_GRAY)))
    done_num_row = donut_row + 1
    vals[(done_num_row, SIDE_COL)] = 'Выполнено'
    vals[(done_num_row, SIDE_COL + 2)] = f'=({all_day_ranges})'
    vals[(done_num_row + 1, SIDE_COL)] = 'Осталось'
    vals[(done_num_row + 1, SIDE_COL + 2)] = f'=({all_day_totals})-({all_day_ranges})'
    for rr in (done_num_row, done_num_row + 1):
        reqs.append(repeat_cell(sid, rr, SIDE_COL, rr + 1, SIDE_COL + 2,
            cell_fmt(bg=CARD_BG, size=8, fg=GRAY)))
        reqs.append(repeat_cell(sid, rr, SIDE_COL + 2, rr + 1, SIDE_COL + 3,
            cell_fmt(bg=CARD_BG, size=8, halign='CENTER', bold=True)))

    donut_chart_row = done_num_row + 3
    reqs.append({'addChart': {'chart': {
        'spec': {
            'title': 'Задач выполнено',
            'pieChart': {
                'legendPosition': 'RIGHT_LEGEND',
                'domain': {'sourceRange': {'sources': [rng(sid, done_num_row, SIDE_COL, done_num_row + 2, SIDE_COL + 1)]}},
                'series': {'sourceRange': {'sources': [rng(sid, done_num_row, SIDE_COL + 2, done_num_row + 2, SIDE_COL + 3)]}},
                'pieHole': 0.5,
            },
            'backgroundColor': CARD_BG,
        },
        'position': {'overlayPosition': {
            'anchorCell': {'sheetId': sid, 'rowIndex': donut_chart_row, 'columnIndex': SIDE_COL},
            'widthPixels': 280, 'heightPixels': 170}}
    }}})

    # ── ЕЖЕНЕДЕЛЬНЫЙ ОБЗОР ──
    review_row = last_habit_row + 2
    reqs.append(row_height(sid, review_row, review_row + 1, 32))
    vals[(review_row, HABIT_COL)] = '📅 ЕЖЕНЕДЕЛЬНЫЙ ОБЗОР'
    reqs.append(repeat_cell(sid, review_row, HABIT_COL, review_row + 1, DAYS_END,
        cell_fmt(bg=HEADER_BG, bold=True, size=12, halign='LEFT')))

    week_header_row = review_row + 1
    dow_row = review_row + 2
    daynum_row = review_row + 3
    reqs.append(row_height(sid, week_header_row, dow_row, 24))
    reqs.append(row_height(sid, dow_row, daynum_row, 22))
    reqs.append(row_height(sid, daynum_row, daynum_row + 1, 22))

    week_colors = [ACCENT_RED, ACCENT_PUR, ACCENT_BLUE, ACCENT_ORG, ACCENT_GRN]
    col_cursor = DAY_START
    week_ranges = []  # (start_col, end_col, label, color)
    for wi, week in enumerate(weeks):
        w_start = col_cursor
        w_end = col_cursor + len(week)
        label = 'ДОП.' if len(week) < 7 and wi == len(weeks) - 1 else f'НЕДЕЛЯ {wi+1}'
        wcolor = week_colors[wi % len(week_colors)]
        reqs.append(merge(sid, week_header_row, w_start, week_header_row + 1, w_end))
        vals[(week_header_row, w_start)] = label
        reqs.append(repeat_cell(sid, week_header_row, w_start, week_header_row + 1, w_end,
            cell_fmt(bg=CARD_BG, bold=True, size=9, halign='CENTER', fg=wcolor)))
        for i, d in enumerate(week):
            dow = datetime.date(year, month, d).weekday()
            vals[(dow_row, w_start + i)] = DAY_NAMES[dow]
            vals[(daynum_row, w_start + i)] = d
            reqs.append(repeat_cell(sid, dow_row, w_start + i, dow_row + 1, w_start + i + 1,
                cell_fmt(bg=CARD_BG, size=7, halign='CENTER', fg=LIGHT_GRAY)))
            reqs.append(repeat_cell(sid, daynum_row, w_start + i, daynum_row + 1, w_start + i + 1,
                cell_fmt(bg=CARD_BG, size=7, halign='CENTER', fg=GRAY)))
        week_ranges.append((w_start, w_end, label, wcolor))
        col_cursor = w_end

    # Строка с количеством выполненных привычек в день (для каждой недели)
    daycount_row = daynum_row + 1
    reqs.append(row_height(sid, daycount_row, daycount_row + 1, 22))
    for w_start, w_end, label, wcolor in week_ranges:
        for c in range(w_start, w_end):
            day_col_letter = col_letter(c)
            formula = f'=COUNTIF({day_col_letter}{habit_rows[0]+1}:{day_col_letter}{last_habit_row+1},TRUE)'
            vals[(daycount_row, c)] = formula
            reqs.append(repeat_cell(sid, daycount_row, c, daycount_row + 1, c + 1,
                cell_fmt(bg=CARD_BG, size=7, halign='CENTER', bold=True, fg=wcolor)))

    # Мини bar-chart (SPARKLINE) на неделю
    chart_row = daycount_row + 1
    reqs.append(row_height(sid, chart_row, chart_row + 1, 60))
    for w_start, w_end, label, wcolor in week_ranges:
        rgb_hex = '#%02X%02X%02X' % (round(wcolor['red']*255), round(wcolor['green']*255), round(wcolor['blue']*255))
        day_rng_row = f'{col_letter(w_start)}{daycount_row+1}:{col_letter(w_end-1)}{daycount_row+1}'
        formula = (f'=SPARKLINE({day_rng_row},'
                   f'{{"charttype","column";"color1","{rgb_hex}";"ymin",0}})')
        reqs.append(merge(sid, chart_row, w_start, chart_row + 1, w_end))
        vals[(chart_row, w_start)] = formula
        reqs.append(repeat_cell(sid, chart_row, w_start, chart_row + 1, w_end, cell_fmt(bg=CARD_BG)))

    # ВЫПОЛНЕНЫ / ОСТАЛОСЬ / ИТОГО / % / ФИНАЛЬНЫЙ ПРОГРЕСС за каждую неделю
    n_habits_total = len(habit_rows)
    done_row = chart_row + 1
    left_row = done_row + 1
    xy_row = left_row + 1
    pct_row = xy_row + 1
    final_row = pct_row + 1

    for label_row, label_text, fg in (
        (done_row, 'ВЫПОЛНЕНЫ', LIGHT_GRAY),
        (left_row, 'ОСТАЛОСЬ', LIGHT_GRAY),
    ):
        vals[(label_row, HABIT_COL)] = label_text
        reqs.append(repeat_cell(sid, label_row, HABIT_COL, label_row + 1, DAY_START,
            cell_fmt(bg=CARD_BG, size=8, fg=fg)))
    vals[(xy_row, HABIT_COL)] = 'ИТОГО'
    vals[(pct_row, HABIT_COL)] = '%'
    vals[(final_row, HABIT_COL)] = 'ФИНАЛЬНЫЙ ПРОГРЕСС'
    for r in (xy_row, pct_row, final_row):
        reqs.append(repeat_cell(sid, r, HABIT_COL, r + 1, DAY_START, cell_fmt(bg=CARD_BG, size=8, fg=LIGHT_GRAY)))

    for w_start, w_end, label, wcolor in week_ranges:
        rgb_hex = '#%02X%02X%02X' % (round(wcolor['red']*255), round(wcolor['green']*255), round(wcolor['blue']*255))
        n_days = w_end - w_start
        total_possible = n_days * n_habits_total
        done_sum = f'SUM({col_letter(w_start)}{daycount_row+1}:{col_letter(w_end-1)}{daycount_row+1})'

        reqs.append(merge(sid, done_row, w_start, done_row + 1, w_end))
        vals[(done_row, w_start)] = f'={done_sum}'
        reqs.append(repeat_cell(sid, done_row, w_start, done_row + 1, w_end,
            cell_fmt(bg=CARD_BG, size=9, bold=True, halign='CENTER', fg=ACCENT_GRN)))

        reqs.append(merge(sid, left_row, w_start, left_row + 1, w_end))
        vals[(left_row, w_start)] = f'={total_possible}-({done_sum})'
        reqs.append(repeat_cell(sid, left_row, w_start, left_row + 1, w_end,
            cell_fmt(bg=CARD_BG, size=9, bold=True, halign='CENTER', fg=ACCENT_RED)))

        reqs.append(merge(sid, xy_row, w_start, xy_row + 1, w_end))
        vals[(xy_row, w_start)] = f'=({done_sum})&"/"&{total_possible}'
        reqs.append(repeat_cell(sid, xy_row, w_start, xy_row + 1, w_end,
            cell_fmt(bg=CARD_BG, size=9, halign='CENTER', fg=LIGHT_GRAY)))

        reqs.append(merge(sid, pct_row, w_start, pct_row + 1, w_end))
        vals[(pct_row, w_start)] = f'=ROUND(({done_sum})/{total_possible}*100,0)&"%"'
        reqs.append(repeat_cell(sid, pct_row, w_start, pct_row + 1, w_end,
            cell_fmt(bg=CARD_BG, size=10, bold=True, halign='CENTER', fg=wcolor)))

        reqs.append(merge(sid, final_row, w_start, final_row + 1, w_end))
        vals[(final_row, w_start)] = (f'=SPARKLINE(({done_sum})/{total_possible},'
                                       f'{{"charttype","bar";"max",1;"color1","{rgb_hex}"}})')
        reqs.append(repeat_cell(sid, final_row, w_start, final_row + 1, w_end, cell_fmt(bg=CARD_BG)))

    reqs.append(freeze(sid, rows=3, cols=1))
    return reqs, vals


# ────────────────────────────────────────────────────────────────
# ЛИСТ ФИНАНСОВ (помесячный) — ОБЩИЙ ДОХОД/РАСХОД, таблицы Доходы/Расходы,
# pie-чарт по доходам, bar-чарты План vs Факт
# ────────────────────────────────────────────────────────────────

INCOME_ITEMS = [
    ('💼 Зарплата Ромашка', 12000),
    ('📊 Бухгалтерия',        5000),
    ('💵 Фриланс',               0),
    ('📈 Бизнес / Дивиденды',    0),
    ('🎁 Подарки / переводы',    0),
    ('➕ Прочие поступления',    0),
]
EXPENSE_ITEMS = [
    ('🏠 Жильё',              5200),
    ('💡 Коммуналка + интернет', 490),
    ('⛽ Транспорт / топливо', 1000),
    ('📱 Телефон + подписки',   750),
    ('🥗 Еда',                 1500),
    ('🏋️ Здоровье / спортпит', 1000),
    ('🚬 Стики',                600),
    ('🛍️ Покупки и вещи',        0),
    ('📦 Другое',                300),
]


def build_finance_month_sheet(sid, month_idx):
    """month_idx: 0=Январь..11=Декабрь."""
    reqs, vals = [], {}
    month_name = MONTHS_SHORT[month_idx]

    CAT_COL, PLAN_COL, FACT_COL = 0, 1, 2
    GAP_COL = 3
    CAT2_COL, PLAN2_COL, FACT2_COL = 4, 5, 6
    TOTAL_COLS = 8

    reqs.append(repeat_cell(sid, 0, 0, 80, TOTAL_COLS, cell_fmt(bg=DARK_BG)))
    reqs.append(col_width(sid, CAT_COL, CAT_COL + 1, 190))
    reqs.append(col_width(sid, PLAN_COL, PLAN_COL + 1, 100))
    reqs.append(col_width(sid, FACT_COL, FACT_COL + 1, 100))
    reqs.append(col_width(sid, GAP_COL, GAP_COL + 1, 20))
    reqs.append(col_width(sid, CAT2_COL, CAT2_COL + 1, 190))
    reqs.append(col_width(sid, PLAN2_COL, PLAN2_COL + 1, 100))
    reqs.append(col_width(sid, FACT2_COL, FACT2_COL + 1, 100))

    # Заголовок месяца + "месячное накопление"
    reqs.append(row_height(sid, 0, 1, 40))
    reqs.append(merge(sid, 0, CAT_COL, 1, GAP_COL))
    vals[(0, CAT_COL)] = f'📅 {month_name.upper()}'
    reqs.append(repeat_cell(sid, 0, CAT_COL, 1, GAP_COL,
        cell_fmt(bg=CARD_BG, bold=True, size=14, halign='LEFT')))
    reqs.append(merge(sid, 0, CAT2_COL, 1, TOTAL_COLS))
    vals[(0, CAT2_COL)] = 'МЕСЯЧНОЕ НАКОПЛЕНИЕ'
    reqs.append(repeat_cell(sid, 0, CAT2_COL, 1, TOTAL_COLS,
        cell_fmt(bg=CARD_BG, bold=True, size=10, halign='RIGHT', fg=LIGHT_GRAY)))

    # ОБЩИЙ ДОХОД / ОБЩИЙ РАСХОД
    reqs.append(row_height(sid, 1, 2, 36))
    reqs.append(merge(sid, 1, CAT_COL, 2, GAP_COL))
    vals[(1, CAT_COL)] = 'ОБЩИЙ ДОХОД'
    reqs.append(merge(sid, 1, CAT2_COL, 2, TOTAL_COLS))
    vals[(1, CAT2_COL)] = 'ОБЩИЙ РАСХОД'

    # ── Таблица ДОХОДЫ (слева) ──
    row = 3
    reqs.append(row_height(sid, row, row + 1, 26))
    reqs.append(merge(sid, row, CAT_COL, row + 1, FACT_COL + 1))
    vals[(row, CAT_COL)] = '  ДОХОДЫ'
    reqs.append(repeat_cell(sid, row, CAT_COL, row + 1, FACT_COL + 1,
        cell_fmt(bg=ACCENT_GRN, bold=True, size=10, fg={'red':0.05,'green':0.05,'blue':0.05})))
    row += 1
    vals[(row, CAT_COL)] = 'Категория'
    vals[(row, PLAN_COL)] = 'Планируемый'
    vals[(row, FACT_COL)] = 'Фактический'
    reqs.append(repeat_cell(sid, row, CAT_COL, row + 1, FACT_COL + 1,
        cell_fmt(bg=HEADER_BG, bold=True, size=8, halign='CENTER', fg=LIGHT_GRAY)))
    row += 1
    income_start_row = row
    for name, plan in INCOME_ITEMS:
        vals[(row, CAT_COL)] = f'  {name}'
        vals[(row, PLAN_COL)] = plan
        reqs.append(repeat_cell(sid, row, CAT_COL, row + 1, PLAN_COL,
            cell_fmt(bg=CARD_BG, size=9)))
        reqs.append(repeat_cell(sid, row, PLAN_COL, row + 1, FACT_COL + 1,
            cell_fmt(bg=CARD_BG, size=9, halign='RIGHT')))
        row += 1
    income_end_row = row
    vals[(row, CAT_COL)] = '  Итого'
    vals[(row, PLAN_COL)] = f'=SUM({a1(income_start_row, PLAN_COL)}:{a1(income_end_row-1, PLAN_COL)})'
    vals[(row, FACT_COL)] = f'=SUM({a1(income_start_row, FACT_COL)}:{a1(income_end_row-1, FACT_COL)})'
    reqs.append(repeat_cell(sid, row, CAT_COL, row + 1, FACT_COL + 1,
        cell_fmt(bg=HEADER_BG, bold=True, size=9, halign='RIGHT', fg=ACCENT_GRN)))
    income_total_row = row

    # ── Таблица РАСХОДЫ (справа) ──
    row2 = 3
    reqs.append(merge(sid, row2, CAT2_COL, row2 + 1, FACT2_COL + 1))
    vals[(row2, CAT2_COL)] = '  РАСХОДЫ'
    reqs.append(repeat_cell(sid, row2, CAT2_COL, row2 + 1, FACT2_COL + 1,
        cell_fmt(bg=ACCENT_RED, bold=True, size=10, fg={'red':0.05,'green':0.05,'blue':0.05})))
    row2 += 1
    vals[(row2, CAT2_COL)] = 'Категория'
    vals[(row2, PLAN2_COL)] = 'Планируемый'
    vals[(row2, FACT2_COL)] = 'Фактический'
    reqs.append(repeat_cell(sid, row2, CAT2_COL, row2 + 1, FACT2_COL + 1,
        cell_fmt(bg=HEADER_BG, bold=True, size=8, halign='CENTER', fg=LIGHT_GRAY)))
    row2 += 1
    expense_start_row = row2
    for name, plan in EXPENSE_ITEMS:
        vals[(row2, CAT2_COL)] = f'  {name}'
        vals[(row2, PLAN2_COL)] = plan
        reqs.append(repeat_cell(sid, row2, CAT2_COL, row2 + 1, PLAN2_COL,
            cell_fmt(bg=CARD_BG, size=9)))
        reqs.append(repeat_cell(sid, row2, PLAN2_COL, row2 + 1, FACT2_COL + 1,
            cell_fmt(bg=CARD_BG, size=9, halign='RIGHT')))
        row2 += 1
    expense_end_row = row2
    vals[(row2, CAT2_COL)] = '  Итого'
    vals[(row2, PLAN2_COL)] = f'=SUM({a1(expense_start_row, PLAN2_COL)}:{a1(expense_end_row-1, PLAN2_COL)})'
    vals[(row2, FACT2_COL)] = f'=SUM({a1(expense_start_row, FACT2_COL)}:{a1(expense_end_row-1, FACT2_COL)})'
    reqs.append(repeat_cell(sid, row2, CAT2_COL, row2 + 1, FACT2_COL + 1,
        cell_fmt(bg=HEADER_BG, bold=True, size=9, halign='RIGHT', fg=ACCENT_RED)))
    expense_total_row = row2

    # ОБЩИЙ ДОХОД / ОБЩИЙ РАСХОД — значения (после того как известны итоговые строки)
    vals[(1, PLAN_COL)] = f'={a1(income_total_row, PLAN_COL)}'
    reqs.append({'repeatCell': {
        'range': rng(sid, 1, CAT_COL, 2, GAP_COL),
        'cell': {'userEnteredFormat': {
            'backgroundColor': {'red':0.10,'green':0.20,'blue':0.13},
            'textFormat': {'bold': True, 'fontSize': 14, 'foregroundColor': ACCENT_GRN},
            'horizontalAlignment': 'CENTER', 'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0"с"'}}},
        'fields': 'userEnteredFormat'}})
    vals[(1, PLAN2_COL)] = f'={a1(expense_total_row, PLAN2_COL)}'
    reqs.append({'repeatCell': {
        'range': rng(sid, 1, CAT2_COL, 2, TOTAL_COLS),
        'cell': {'userEnteredFormat': {
            'backgroundColor': {'red':0.22,'green':0.10,'blue':0.10},
            'textFormat': {'bold': True, 'fontSize': 14, 'foregroundColor': ACCENT_RED},
            'horizontalAlignment': 'CENTER', 'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0"с"'}}},
        'fields': 'userEnteredFormat'}})

    bottom = max(income_total_row, expense_total_row) + 2

    # ── Месячное накопление = доход - расход (рядом с заголовком, строка 0) ──
    vals[(0, TOTAL_COLS - 1)] = f'={a1(income_total_row, PLAN_COL)}-{a1(expense_total_row, PLAN2_COL)}'
    reqs.append({'repeatCell': {
        'range': rng(sid, 0, CAT2_COL, 1, TOTAL_COLS),
        'cell': {'userEnteredFormat': {
            'backgroundColor': CARD_BG, 'textFormat': {'bold': True, 'fontSize': 10, 'foregroundColor': ACCENT_BLUE},
            'horizontalAlignment': 'RIGHT', 'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0"с"'}}},
        'fields': 'userEnteredFormat'}})

    # ── Pie-чарт: структура доходов ──
    reqs.append({'addChart': {'chart': {
        'spec': {
            'title': 'Структура доходов',
            'pieChart': {
                'legendPosition': 'RIGHT_LEGEND', 'pieHole': 0,
                'domain': {'sourceRange': {'sources': [rng(sid, income_start_row, CAT_COL, income_end_row, CAT_COL + 1)]}},
                'series': {'sourceRange': {'sources': [rng(sid, income_start_row, PLAN_COL, income_end_row, PLAN_COL + 1)]}},
            },
            'backgroundColor': CARD_BG,
        },
        'position': {'overlayPosition': {
            'anchorCell': {'sheetId': sid, 'rowIndex': bottom, 'columnIndex': CAT_COL},
            'widthPixels': 360, 'heightPixels': 230}}
    }}})

    # ── Bar-чарт: Доход План vs Факт ──
    reqs.append({'addChart': {'chart': {
        'spec': {
            'title': 'Доход: план vs факт',
            'basicChart': {
                'chartType': 'COLUMN', 'legendPosition': 'TOP_LEGEND',
                'axis': [{'position': 'BOTTOM_AXIS'}, {'position': 'LEFT_AXIS'}],
                'domains': [{'domain': {'sourceRange': {'sources': [rng(sid, income_start_row, CAT_COL, income_end_row, CAT_COL + 1)]}}}],
                'series': [
                    {'series': {'sourceRange': {'sources': [rng(sid, income_start_row, PLAN_COL, income_end_row, PLAN_COL + 1)]}}, 'targetAxis': 'LEFT_AXIS'},
                    {'series': {'sourceRange': {'sources': [rng(sid, income_start_row, FACT_COL, income_end_row, FACT_COL + 1)]}}, 'targetAxis': 'LEFT_AXIS'},
                ],
            },
            'backgroundColor': CARD_BG,
        },
        'position': {'overlayPosition': {
            'anchorCell': {'sheetId': sid, 'rowIndex': bottom, 'columnIndex': CAT2_COL},
            'widthPixels': 420, 'heightPixels': 230}}
    }}})

    bottom2 = bottom + 13

    # ── Bar-чарт: Расход План vs Факт ──
    reqs.append({'addChart': {'chart': {
        'spec': {
            'title': 'Расход: план vs факт',
            'basicChart': {
                'chartType': 'COLUMN', 'legendPosition': 'TOP_LEGEND',
                'axis': [{'position': 'BOTTOM_AXIS'}, {'position': 'LEFT_AXIS'}],
                'domains': [{'domain': {'sourceRange': {'sources': [rng(sid, expense_start_row, CAT2_COL, expense_end_row, CAT2_COL + 1)]}}}],
                'series': [
                    {'series': {'sourceRange': {'sources': [rng(sid, expense_start_row, PLAN2_COL, expense_end_row, PLAN2_COL + 1)]}}, 'targetAxis': 'LEFT_AXIS'},
                    {'series': {'sourceRange': {'sources': [rng(sid, expense_start_row, FACT2_COL, expense_end_row, FACT2_COL + 1)]}}, 'targetAxis': 'LEFT_AXIS'},
                ],
            },
            'backgroundColor': CARD_BG,
        },
        'position': {'overlayPosition': {
            'anchorCell': {'sheetId': sid, 'rowIndex': bottom2, 'columnIndex': CAT_COL},
            'widthPixels': 420, 'heightPixels': 230}}
    }}})

    reqs.append(freeze(sid, rows=2, cols=0))
    return reqs, vals


def main():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    session = AuthorizedSession(creds)

    today = datetime.date.today()
    month_sheet_name = f'Привычки {MONTHS_SHORT[today.month-1]} {today.year}'

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

    sheet_defs = [
        {'sheetId': 1, 'title': month_sheet_name,
         'tabColor': ACCENT_GRN, 'gridProperties': {'rowCount': 80, 'columnCount': 45}},
    ]
    finance_sheet_ids = {}
    next_id = 10
    for mi in range(12):
        sid = next_id
        next_id += 1
        finance_sheet_ids[mi] = sid
        sheet_defs.append({'sheetId': sid, 'title': f'Финансы {MONTHS_SHORT[mi]}',
                            'tabColor': ACCENT_ORG if mi == today.month - 1 else ACCENT_BLUE,
                            'gridProperties': {'rowCount': 60, 'columnCount': 10}})

    r = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
        json={'requests': [{'addSheet': {'properties': sd}} for sd in sheet_defs]}, timeout=30)
    print(f'📋 Листы добавлены: {r.status_code}')
    if r.status_code != 200:
        print(r.text[:2000])

    # удалить дефолтный Sheet1 (sheetId=0), если есть
    session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
        json={'requests': [{'deleteSheet': {'sheetId': 0}}]}, timeout=30)

    all_reqs, all_updates = [], []

    h_reqs, h_vals = build_habits_sheet(1, today.year, today.month)
    all_reqs.extend(h_reqs)
    all_updates.extend([
        {'range': f"'{month_sheet_name}'!{a1(r, c)}", 'values': [[v]]}
        for (r, c), v in h_vals.items()
    ])

    for mi in range(12):
        sid = finance_sheet_ids[mi]
        f_reqs, f_vals = build_finance_month_sheet(sid, mi)
        all_reqs.extend(f_reqs)
        sheet_title = f'Финансы {MONTHS_SHORT[mi]}'
        all_updates.extend([
            {'range': f"'{sheet_title}'!{a1(r, c)}", 'values': [[v]]}
            for (r, c), v in f_vals.items()
        ])

    # Применяем форматирование пачками (лимит размера запроса)
    BATCH = 400
    for i in range(0, len(all_reqs), BATCH):
        chunk = all_reqs[i:i+BATCH]
        rr = session.post(
            f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
            json={'requests': chunk}, timeout=90)
        print(f'🎨 Формат [{i}:{i+len(chunk)}]: {rr.status_code}')
        if rr.status_code != 200:
            print(rr.text[:1500])

    r4 = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/values:batchUpdate',
        json={'valueInputOption': 'USER_ENTERED', 'data': all_updates},
        timeout=90)
    print(f'📝 Данные: {r4.status_code}')
    if r4.status_code != 200:
        print(r4.text[:1500])

    print(f'\n🔗 https://docs.google.com/spreadsheets/d/{ss_id}')
    return ss_id


if __name__ == '__main__':
    main()
