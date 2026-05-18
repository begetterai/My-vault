#!/usr/bin/env python3
"""Создаёт Google Sheets таблицу учёта барбершопа (Выручка / Расходы / Косметика / P&L)."""
import json, os, calendar
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive']

YEAR, MONTH = 2026, 5
DAYS = calendar.monthrange(YEAR, MONTH)[1]

MONTHS_RU = ['','Январь','Февраль','Март','Апрель','Май','Июнь',
             'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
MONTH_NAME = MONTHS_RU[MONTH]

BARBERS      = ['Барбер 1', 'Барбер 2', 'Барбер 3', 'Барбер 4']
EXPENSE_CATS = ['Аренда', 'Электричество', 'Вода', 'Налог', 'Хоз расходы', 'Расходники']
SUPPLIERS    = ['Рынок', 'Нишман']


# ── cell value helpers ─────────────────────────────────────────────────────
def sv(s):  return {'userEnteredValue': {'stringValue': str(s)}}
def nv(n):  return {'userEnteredValue': {'numberValue': n}}
def fv(f):  return {'userEnteredValue': {'formulaValue': f}}
def MT():   return {'userEnteredValue': {}}

# ── colours ────────────────────────────────────────────────────────────────
def rgb(r, g, b): return {'red': r/255, 'green': g/255, 'blue': b/255}

DARK  = rgb(26,  26,  26)
GOLD  = rgb(212, 175, 55)
MID   = rgb(60,  60,  60)
LGRAY = rgb(248, 248, 248)
WHITE = {'red': 1, 'green': 1, 'blue': 1}
GREEN = rgb(27,  94,  32)
LGRN  = rgb(232, 245, 233)
AMBE  = rgb(255, 243, 205)
ORANG = rgb(255, 224, 178)
LBLU  = rgb(227, 242, 253)
BLUE  = rgb(13,  71,  161)
RED   = rgb(183, 28,  28)


# ── format / layout helpers ────────────────────────────────────────────────
def fmt(bg=None, fg=None, bold=False, size=10, ha=None, num_pat=None, pct=False):
    f = {'verticalAlignment': 'MIDDLE'}
    if bg: f['backgroundColor'] = bg
    if ha: f['horizontalAlignment'] = ha
    tf = {}
    if fg:   tf['foregroundColor'] = fg
    if bold: tf['bold'] = True
    if size != 10: tf['fontSize'] = size
    if tf: f['textFormat'] = tf
    if num_pat: f['numberFormat'] = {'type': 'NUMBER',  'pattern': num_pat}
    if pct:     f['numberFormat'] = {'type': 'PERCENT', 'pattern': '0%'}
    return f

def rc(sid, r1, r2, c1, c2, f, fields='userEnteredFormat'):
    return {'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': r1, 'endRowIndex': r2,
                  'startColumnIndex': c1, 'endColumnIndex': c2},
        'cell': {'userEnteredFormat': f}, 'fields': fields}}

def mg(sid, r1, r2, c1, c2):
    return {'mergeCells': {
        'range': {'sheetId': sid, 'startRowIndex': r1, 'endRowIndex': r2,
                  'startColumnIndex': c1, 'endColumnIndex': c2},
        'mergeType': 'MERGE_ALL'}}

def cw(sid, c1, c2, px):
    return {'updateDimensionProperties': {
        'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                  'startIndex': c1, 'endIndex': c2},
        'properties': {'pixelSize': px}, 'fields': 'pixelSize'}}

def rh(sid, r1, r2, px):
    return {'updateDimensionProperties': {
        'range': {'sheetId': sid, 'dimension': 'ROWS',
                  'startIndex': r1, 'endIndex': r2},
        'properties': {'pixelSize': px}, 'fields': 'pixelSize'}}

def frz(sid, rows=0, cols=0):
    return {'updateSheetProperties': {
        'properties': {'sheetId': sid,
                       'gridProperties': {'frozenRowCount': rows, 'frozenColumnCount': cols}},
        'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}}

def ddrop(sid, r1, r2, c1, c2, vals):
    return {'setDataValidation': {
        'range': {'sheetId': sid, 'startRowIndex': r1, 'endRowIndex': r2,
                  'startColumnIndex': c1, 'endColumnIndex': c2},
        'rule': {'condition': {'type': 'ONE_OF_LIST',
                               'values': [{'userEnteredValue': v} for v in vals]},
                 'showCustomUi': True, 'strict': False}}}

def uc(sid, row, col, rows_data):
    return {'updateCells': {
        'range': {'sheetId': sid, 'startRowIndex': row, 'startColumnIndex': col},
        'rows': rows_data, 'fields': 'userEnteredValue'}}

def numfmt(sid, r1, r2, c1, c2, pat):
    return rc(sid, r1, r2, c1, c2,
              {'numberFormat': {'type': 'NUMBER', 'pattern': pat}},
              'userEnteredFormat.numberFormat')

def pctfmt(sid, r1, r2, c1, c2):
    return rc(sid, r1, r2, c1, c2,
              {'numberFormat': {'type': 'PERCENT', 'pattern': '0%'}},
              'userEnteredFormat.numberFormat')


# ══════════════════════════════════════════════════════════════════════════════
# Лист «Выручка»
# Cols: A=День B-E=Барбер1-4выр F=ИтогоВыр G=sep H-K=Барбер1-4кл L=ИтогоКл M=Ср.чек
# ══════════════════════════════════════════════════════════════════════════════
def build_vyru(sid):
    N  = DAYS
    DS = 3               # DATA_START index (day 1)
    DE = DS + N          # DATA_END   index (exclusive)
    IT = DE              # ИТОГО      index
    SP = DE + 1          # spacer
    PC = DE + 2          # % ФОТ
    FT = DE + 3          # ФОТ суммы

    sr   = lambda i: i + 1          # index → sheet row (1-based) for formulas
    reqs = []

    # ── значения ──────────────────────────────────────────────────────────

    # Строка 0: заголовок
    reqs.append(uc(sid, 0, 0, [{'values':
        [sv(f'БАРБЕРШОП — {MONTH_NAME.upper()} {YEAR}')] + [MT()]*12}]))

    # Строка 1: секции
    reqs.append(uc(sid, 1, 0, [{'values':
        [MT(), sv('ВЫРУЧКА (нал)'), MT(), MT(), MT(), MT(),
         MT(), sv('КЛИЕНТЫ'), MT(), MT(), MT(), MT(), MT()]}]))

    # Строка 2: заголовки столбцов
    reqs.append(uc(sid, 2, 0, [{'values':
        [sv('День')] + [sv(b) for b in BARBERS] + [sv('Итого')] +
        [sv('')] +
        [sv(b) for b in BARBERS] + [sv('Итого')] + [sv('Ср. чек')]}]))

    # Строки 3..3+N-1: дни
    day_rows = []
    for d in range(1, N + 1):
        sr_d = sr(DS + d - 1)   # sheet row этого дня
        day_rows.append({'values': [
            nv(d),
            MT(), MT(), MT(), MT(),                          # B-E: выручка (ввод)
            fv(f'=SUM(B{sr_d}:E{sr_d})'),                   # F: итого выручка
            MT(),                                            # G: sep
            MT(), MT(), MT(), MT(),                          # H-K: клиенты (ввод)
            fv(f'=SUM(H{sr_d}:K{sr_d})'),                   # L: итого клиенты
            fv(f'=IF(L{sr_d}>0,F{sr_d}/L{sr_d},"")'),       # M: ср. чек
        ]})
    reqs.append(uc(sid, DS, 0, day_rows))

    # Строка ИТОГО
    s1, s2 = sr(DS), sr(DE - 1)          # первый и последний дни
    reqs.append(uc(sid, IT, 0, [{'values': [
        sv('ИТОГО'),
        fv(f'=SUM(B{s1}:B{s2})'), fv(f'=SUM(C{s1}:C{s2})'),
        fv(f'=SUM(D{s1}:D{s2})'), fv(f'=SUM(E{s1}:E{s2})'),
        fv(f'=SUM(F{s1}:F{s2})'),
        MT(),
        fv(f'=SUM(H{s1}:H{s2})'), fv(f'=SUM(I{s1}:I{s2})'),
        fv(f'=SUM(J{s1}:J{s2})'), fv(f'=SUM(K{s1}:K{s2})'),
        fv(f'=SUM(L{s1}:L{s2})'),
        fv(f'=IF(L{sr(IT)}>0,F{sr(IT)}/L{sr(IT)},"")'),
    ]}]))

    # % ФОТ (по умолчанию 50%)
    reqs.append(uc(sid, PC, 0, [{'values':
        [sv('% ФОТ'), nv(0.5), nv(0.5), nv(0.5), nv(0.5)] + [MT()]*8}]))

    # ФОТ суммы
    si = sr(IT); sp_row = sr(PC)
    reqs.append(uc(sid, FT, 0, [{'values': [
        sv('ФОТ'),
        fv(f'=B{si}*B{sp_row}'), fv(f'=C{si}*C{sp_row}'),
        fv(f'=D{si}*D{sp_row}'), fv(f'=E{si}*E{sp_row}'),
        fv(f'=SUM(B{sr(FT)}:E{sr(FT)})'),
    ] + [MT()]*7}]))

    # ── форматирование ─────────────────────────────────────────────────────

    # Заголовок
    reqs += [mg(sid, 0, 1, 0, 13),
             rc(sid, 0, 1, 0, 13, fmt(bg=DARK, fg=GOLD, bold=True, size=13, ha='CENTER')),
             rh(sid, 0, 1, 42)]

    # Секции
    reqs += [mg(sid, 1, 2, 1, 6), mg(sid, 1, 2, 7, 13),
             rc(sid, 1, 2, 0, 13, fmt(bg=MID, fg=WHITE, bold=True, ha='CENTER'))]

    # Заголовки столбцов
    reqs += [rc(sid, 2, 3, 0, 13, fmt(bg=DARK, fg=WHITE, bold=True, ha='CENTER')),
             rh(sid, 2, 3, 30)]

    # Дни: чередование фона
    for d in range(N):
        bg = WHITE if d % 2 == 0 else LGRAY
        reqs.append(rc(sid, DS + d, DS + d + 1, 0, 13, fmt(bg=bg, ha='CENTER')))

    # ИТОГО
    reqs += [rc(sid, IT, IT + 1, 0, 13, fmt(bg=DARK, fg=WHITE, bold=True, ha='CENTER'))]

    # % ФОТ
    reqs += [rc(sid, PC, PC + 1, 0, 13, fmt(bg=AMBE, ha='CENTER')),
             pctfmt(sid, PC, PC + 1, 1, 5)]

    # ФОТ суммы
    reqs += [rc(sid, FT, FT + 1, 0, 13, fmt(bg=ORANG, bold=True, ha='CENTER'))]

    # Разделитель G
    reqs += [rc(sid, 0, FT + 1, 6, 7, fmt(bg=DARK)), cw(sid, 6, 7, 12)]

    # Числовые форматы
    reqs += [numfmt(sid, DS, FT + 1, 1, 6,  '#,##0'),   # выручка
             numfmt(sid, DS, FT + 1, 11, 13, '#,##0')]  # итого кл + ср.чек

    # Ширина столбцов
    reqs += [cw(sid, 0, 1, 52), cw(sid, 1, 5, 90), cw(sid, 5, 6, 110),
             cw(sid, 7, 11, 72), cw(sid, 11, 12, 90), cw(sid, 12, 13, 100)]

    reqs.append(frz(sid, rows=3, cols=1))

    return reqs, {'IT': IT, 'PC': PC, 'FT': FT, 'sr_IT': sr(IT), 'sr_FT': sr(FT)}


# ══════════════════════════════════════════════════════════════════════════════
# Лист «Расходы»
# Cols: A=Дата B=Категория C=Сумма D=Комментарий | F=Категория G=Итого
# ══════════════════════════════════════════════════════════════════════════════
def build_rasx(sid):
    DATA_ROWS = 60
    DS = 3; DE = DS + DATA_ROWS; IT = DE
    reqs = []

    # Заголовок
    reqs.append(uc(sid, 0, 0, [{'values': [sv(f'РАСХОДЫ — {MONTH_NAME.upper()} {YEAR}')] + [MT()]*6}]))

    # Заголовки столбцов
    reqs.append(uc(sid, 2, 0, [{'values': [
        sv('Дата'), sv('Категория'), sv('Сумма'), sv('Комментарий'),
        MT(), sv('Категория'), sv('Итого'),
    ]}]))

    # Пустые строки данных (только даты для удобства не ставим)
    reqs.append(uc(sid, DS, 0, [{'values': [MT(), MT(), MT(), MT()]} for _ in range(DATA_ROWS)]))

    # ИТОГО по всем расходам
    reqs.append(uc(sid, IT, 0, [{'values': [
        sv('ИТОГО'), MT(), fv(f'=SUM(C{DS+1}:C{IT})'), MT()
    ]}]))

    # Сводка по категориям (F-G, строки 3..3+N)
    cat_rows = []
    for cat in EXPENSE_CATS:
        cat_rows.append({'values': [sv(cat), fv(f'=SUMIF(B:B,"{cat}",C:C)')]})
    cat_rows.append({'values': [sv('ИТОГО'), fv(f'=SUM(G{DS+1}:G{DS+len(EXPENSE_CATS)})')]})
    reqs.append(uc(sid, DS, 5, cat_rows))

    # ── форматирование ─────────────────────────────────────────────────────
    reqs += [mg(sid, 0, 1, 0, 7),
             rc(sid, 0, 1, 0, 7, fmt(bg=DARK, fg=GOLD, bold=True, size=13, ha='CENTER')),
             rh(sid, 0, 1, 42),
             rc(sid, 2, 3, 0, 7, fmt(bg=DARK, fg=WHITE, bold=True, ha='CENTER'))]

    # Чередование строк данных
    for i in range(DATA_ROWS):
        bg = WHITE if i % 2 == 0 else LGRAY
        reqs.append(rc(sid, DS + i, DS + i + 1, 0, 4, fmt(bg=bg)))

    # ИТОГО
    reqs += [rc(sid, IT, IT + 1, 0, 4, fmt(bg=DARK, fg=WHITE, bold=True))]

    # Сводка (F-G)
    reqs += [rc(sid, DS, DS + len(EXPENSE_CATS), 5, 7, fmt(bg=LBLU, ha='CENTER')),
             rc(sid, DS + len(EXPENSE_CATS), DS + len(EXPENSE_CATS) + 1, 5, 7,
                fmt(bg=BLUE, fg=WHITE, bold=True, ha='CENTER'))]

    # Числовой формат C и G
    reqs += [numfmt(sid, DS, IT + 1, 2, 3, '#,##0'),
             numfmt(sid, DS, DS + len(EXPENSE_CATS) + 1, 6, 7, '#,##0')]

    # Выпадающий список категорий
    reqs.append(ddrop(sid, DS, DE, 1, 2, EXPENSE_CATS))

    # Ширина
    reqs += [cw(sid, 0, 1, 90), cw(sid, 1, 2, 160), cw(sid, 2, 3, 110),
             cw(sid, 3, 4, 220), cw(sid, 4, 5, 20), cw(sid, 5, 6, 160), cw(sid, 6, 7, 120)]

    reqs.append(frz(sid, rows=3, cols=0))

    return reqs


# ══════════════════════════════════════════════════════════════════════════════
# Лист «Косметика»
# ПОСТАВКИ: A=Дата B=Поставщик C=Товар D=Кол D=Цена F=Сумма
# ПРОДАЖИ:  H=Дата I=Товар J=Кол K=Цена L=Сумма
# ══════════════════════════════════════════════════════════════════════════════
def build_kosm(sid):
    DATA_ROWS = 50
    DS = 3; DE = DS + DATA_ROWS; IT = DE
    reqs = []

    # Заголовок
    reqs.append(uc(sid, 0, 0, [{'values':
        [sv(f'КОСМЕТИКА — {MONTH_NAME.upper()} {YEAR}')] + [MT()]*11}]))

    # Секции
    reqs.append(uc(sid, 1, 0, [{'values':
        [sv('ПОСТАВКИ'), MT(), MT(), MT(), MT(), MT(),
         MT(), sv('ПРОДАЖИ'), MT(), MT(), MT(), MT()]}]))

    # Заголовки
    reqs.append(uc(sid, 2, 0, [{'values': [
        sv('Дата'), sv('Поставщик'), sv('Товар'), sv('Кол-во'), sv('Цена'), sv('Сумма'),
        MT(),
        sv('Дата'), sv('Товар'), sv('Кол-во'), sv('Цена продажи'), sv('Сумма'),
    ]}]))

    # Данные: формулы Сумма для каждой строки
    rows_data = []
    for i in range(DATA_ROWS):
        sr = DS + i + 1      # sheet row (1-based)
        rows_data.append({'values': [
            MT(), MT(), MT(), MT(), MT(),
            fv(f'=IF(D{sr}="","",D{sr}*E{sr})'),   # F: сумма поставки
            MT(),
            MT(), MT(), MT(), MT(),
            fv(f'=IF(J{sr}="","",J{sr}*K{sr})'),   # L: сумма продажи
        ]})
    reqs.append(uc(sid, DS, 0, rows_data))

    # ИТОГО
    s1 = DS + 1; s2 = IT
    reqs.append(uc(sid, IT, 0, [{'values': [
        sv('ИТОГО'), MT(), MT(), MT(), MT(), fv(f'=SUM(F{s1}:F{s2})'),
        MT(),
        sv('ИТОГО'), MT(), MT(), MT(), fv(f'=SUM(L{s1}:L{s2})'),
    ]}]))

    # Сводка (строки IT+2 .. IT+5)
    si = IT + 1     # sheet row ИТОГО
    reqs.append(uc(sid, IT + 2, 0, [
        {'values': [sv('Закупки Рынок'),
                    fv(f'=SUMIF(B{s1}:B{s2},"Рынок",F{s1}:F{s2})')]},
        {'values': [sv('Закупки Нишман'),
                    fv(f'=SUMIF(B{s1}:B{s2},"Нишман",F{s1}:F{s2})')]},
        {'values': [sv('Итого продажи'),  fv(f'=L{si}')]},
        {'values': [sv('Прибыль (продажи − закупки)'),
                    fv(f'=L{si}-F{si}')]},
    ]))

    # ── форматирование ─────────────────────────────────────────────────────
    reqs += [mg(sid, 0, 1, 0, 12),
             rc(sid, 0, 1, 0, 12, fmt(bg=DARK, fg=GOLD, bold=True, size=13, ha='CENTER')),
             rh(sid, 0, 1, 42),
             mg(sid, 1, 2, 0, 6), mg(sid, 1, 2, 7, 12),
             rc(sid, 1, 2, 0, 12, fmt(bg=MID, fg=WHITE, bold=True, ha='CENTER')),
             rc(sid, 2, 3, 0, 12, fmt(bg=DARK, fg=WHITE, bold=True, ha='CENTER'))]

    for i in range(DATA_ROWS):
        bg = WHITE if i % 2 == 0 else LGRAY
        reqs.append(rc(sid, DS + i, DS + i + 1, 0, 12, fmt(bg=bg)))

    reqs += [rc(sid, IT, IT + 1, 0, 12, fmt(bg=DARK, fg=WHITE, bold=True))]

    # Сводка
    reqs += [rc(sid, IT + 2, IT + 5, 0, 2, fmt(bg=LBLU)),
             rc(sid, IT + 5, IT + 6, 0, 2, fmt(bg=GREEN, fg=WHITE, bold=True))]

    # Разделитель G
    reqs += [rc(sid, 0, IT + 6, 6, 7, fmt(bg=DARK)), cw(sid, 6, 7, 12)]

    # Числовые форматы
    reqs += [numfmt(sid, DS, IT + 1, 5, 6, '#,##0'),   # сумма поставок
             numfmt(sid, DS, IT + 1, 11, 12, '#,##0'), # сумма продаж
             numfmt(sid, IT + 2, IT + 6, 1, 2, '#,##0')]  # сводка

    # Выпадающий список поставщиков
    reqs.append(ddrop(sid, DS, DE, 1, 2, SUPPLIERS))

    # Ширина
    reqs += [cw(sid, 0, 1, 90), cw(sid, 1, 2, 110), cw(sid, 2, 3, 160),
             cw(sid, 3, 4, 70), cw(sid, 4, 5, 90), cw(sid, 5, 6, 110),
             cw(sid, 7, 8, 90), cw(sid, 8, 9, 160), cw(sid, 9, 10, 70),
             cw(sid, 10, 11, 110), cw(sid, 11, 12, 110)]

    reqs.append(frz(sid, rows=3, cols=0))

    return reqs


# ══════════════════════════════════════════════════════════════════════════════
# Лист «P&L»
# ══════════════════════════════════════════════════════════════════════════════
def build_pnl(sid, vyru_info):
    sr_IT = vyru_info['sr_IT']   # sheet row ИТОГО в Выручке
    sr_FT = vyru_info['sr_FT']   # sheet row ФОТ в Выручке
    KOSM_DS = 4; KOSM_DE = 54    # диапазон данных в Косметике (sheet rows)
    RASX_DATA = 'C:C'

    def sumif(cat): return f'=SUMIF(\'Расходы\'!B:B,"{cat}",\'Расходы\'!C:C)'

    rows = [
        # 0: заголовок
        [sv(f'P&L — {MONTH_NAME.upper()} {YEAR}'), MT(), MT()],
        # 1: пусто
        [],
        # 2: секция ВЫРУЧКА
        [sv('ВЫРУЧКА'), MT(), MT()],
        # 3
        [sv('Услуги (барберы)'),
         fv(f'=\'Выручка\'!F{sr_IT}'),
         fv(f'=IFERROR(B4/B6,"")')],
        # 4
        [sv('Косметика (продажи)'),
         fv(f'=SUM(\'Косметика\'!L{KOSM_DS}:L{KOSM_DE})'),
         fv(f'=IFERROR(B5/B6,"")')],
        # 5: ИТОГО ВЫРУЧКА
        [sv('ИТОГО ВЫРУЧКА'), fv('=SUM(B4:B5)'), sv('')],
        # 6: пусто
        [],
        # 7: секция РАСХОДЫ
        [sv('РАСХОДЫ'), MT(), MT()],
        # 8: ФОТ
        [sv('ФОТ барберов'),
         fv(f'=\'Выручка\'!F{sr_FT}'),
         fv('=IFERROR(B9/B6,"")') ],
    ]

    # Строки расходов по категориям (9..14 = индексы 9..14)
    for cat in EXPENSE_CATS:
        pct_row = len(rows) + 1   # sheet row этой строки
        rows.append([sv(cat), fv(sumif(cat)), fv(f'=IFERROR(B{pct_row}/B6,"")')])

    # ИТОГО РАСХОДЫ
    expense_start = 9; expense_end = expense_start + 1 + len(EXPENSE_CATS)  # ФОТ + категории
    rows.append([sv('Себестоимость косметики'),
                 fv(f'=SUM(\'Косметика\'!F{KOSM_DS}:F{KOSM_DE})'),
                 fv(f'=IFERROR(B{len(rows)+1}/B6,"")')])

    it_exp_row  = len(rows) + 1
    exp_s       = expense_start + 1   # sheet row ФОТ
    exp_e       = it_exp_row - 1      # sheet row последней строки расхода
    rows.append([sv('ИТОГО РАСХОДЫ'), fv(f'=SUM(B{exp_s}:B{exp_e})'), sv('')])

    # Разделитель
    rows.append([])

    # ПРИБЫЛЬ
    profit_row = len(rows) + 1
    rows.append([sv('ПРИБЫЛЬ'), fv(f'=B6-B{it_exp_row}'), fv('=IFERROR(B{pr}/B6,"")'.replace('{pr}', str(profit_row)))])
    rows.append([sv('Маржа'), fv(f'=IFERROR(B{profit_row}/B6,"")'), sv('')])

    reqs = []
    cell_rows = [{'values': [sv(v) if isinstance(v, str) else v for v in r] if r else [MT()]}
                 for r in rows]
    # Пересобираем правильно
    cell_rows2 = []
    for r in rows:
        if not r:
            cell_rows2.append({'values': [MT()]})
        else:
            cell_rows2.append({'values': r})
    reqs.append(uc(sid, 0, 0, cell_rows2))

    # ── форматирование ─────────────────────────────────────────────────────
    TOTAL_ROWS = len(rows)

    # Заголовок
    reqs += [mg(sid, 0, 1, 0, 3),
             rc(sid, 0, 1, 0, 3, fmt(bg=DARK, fg=GOLD, bold=True, size=13, ha='CENTER')),
             rh(sid, 0, 1, 42)]

    # Секции ВЫРУЧКА / РАСХОДЫ
    for row_idx, label in [(2, 'В'), (7, 'Р')]:
        reqs += [mg(sid, row_idx, row_idx + 1, 0, 3),
                 rc(sid, row_idx, row_idx + 1, 0, 3,
                    fmt(bg=MID, fg=WHITE, bold=True, ha='CENTER'))]

    # ИТОГО ВЫРУЧКА (строка 5, индекс 5)
    reqs += [rc(sid, 5, 6, 0, 3, fmt(bg=DARK, fg=GOLD, bold=True))]

    # ИТОГО РАСХОДЫ
    it_exp_idx = it_exp_row - 1
    reqs += [rc(sid, it_exp_idx, it_exp_idx + 1, 0, 3,
                fmt(bg=DARK, fg=WHITE, bold=True))]

    # ПРИБЫЛЬ
    pr_idx = profit_row - 1
    reqs += [rc(sid, pr_idx, pr_idx + 1, 0, 3, fmt(bg=GREEN, fg=WHITE, bold=True, size=12)),
             rh(sid, pr_idx, pr_idx + 1, 36)]

    # Маржа
    mg_idx = pr_idx + 1
    reqs += [rc(sid, mg_idx, mg_idx + 1, 0, 3, fmt(bg=LGRN, bold=True)),
             pctfmt(sid, mg_idx, mg_idx + 1, 1, 3)]

    # Строки расходов
    for i in range(expense_start - 1, it_exp_idx):
        bg = WHITE if i % 2 == 0 else LGRAY
        reqs.append(rc(sid, i, i + 1, 0, 3, fmt(bg=bg)))

    # Числовые форматы B
    reqs += [numfmt(sid, 3, TOTAL_ROWS, 1, 2, '#,##0'),
             pctfmt(sid, 3, TOTAL_ROWS, 2, 3)]

    # Ширина
    reqs += [cw(sid, 0, 1, 240), cw(sid, 1, 2, 130), cw(sid, 2, 3, 90)]

    reqs.append(frz(sid, rows=1, cols=0))

    return reqs


# ══════════════════════════════════════════════════════════════════════════════
# Главная функция
# ══════════════════════════════════════════════════════════════════════════════
def main():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    session = AuthorizedSession(creds)

    print("Создаю таблицу...")
    body = {
        'properties': {'title': f'Барбершоп — {MONTH_NAME} {YEAR}', 'locale': 'ru_RU'},
        'sheets': [
            {'properties': {'title': 'Выручка',   'sheetId': 10, 'index': 0}},
            {'properties': {'title': 'Расходы',   'sheetId': 11, 'index': 1}},
            {'properties': {'title': 'Косметика', 'sheetId': 12, 'index': 2}},
            {'properties': {'title': 'P&L',       'sheetId': 13, 'index': 3}},
        ]
    }
    r = session.post('https://sheets.googleapis.com/v4/spreadsheets',
                     headers={'Content-Type': 'application/json'},
                     data=json.dumps(body), timeout=30)
    if r.status_code != 200:
        print(f"❌ Ошибка создания: {r.text[:500]}")
        return

    data  = r.json()
    ss_id = data['spreadsheetId']
    ids   = {s['properties']['title']: s['properties']['sheetId']
             for s in data['sheets']}
    print(f"   ID: {ss_id}")

    # Строим запросы для всех листов
    reqs = []
    vyru_reqs, vyru_info = build_vyru(ids['Выручка'])
    reqs += vyru_reqs
    reqs += build_rasx(ids['Расходы'])
    reqs += build_kosm(ids['Косметика'])
    reqs += build_pnl(ids['P&L'], vyru_info)

    print(f"Применяю форматирование ({len(reqs)} запросов)...")
    r2 = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
        headers={'Content-Type': 'application/json'},
        data=json.dumps({'requests': reqs}), timeout=120)

    if r2.status_code != 200:
        print(f"❌ Ошибка форматирования: {r2.text[:1000]}")
        return

    # Открываем доступ (anyone with link — editor)
    r3 = session.post(
        f'https://www.googleapis.com/drive/v3/files/{ss_id}/permissions',
        headers={'Content-Type': 'application/json'},
        data=json.dumps({'role': 'writer', 'type': 'anyone'}), timeout=30)

    url = f'https://docs.google.com/spreadsheets/d/{ss_id}'
    print(f"\n✅ Таблица создана!")
    print(f"   {url}")


if __name__ == '__main__':
    main()
