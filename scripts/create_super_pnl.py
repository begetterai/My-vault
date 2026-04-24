#!/usr/bin/env python3
"""Ромашка — Super P&L 2026 | ЗБ + ОВИР + Свод + KPI"""
import json, os, time
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')
FOLDER_ID = '14NnVXa9k1h0dyS-vNch61A3-aSpJG_Jn'
FONT = 'Times New Roman'

def rgb(r, g, b): return {"red": r/255, "green": g/255, "blue": b/255}

C_DARK   = rgb(20,  43,  75)
C_SEC    = rgb(31,  73, 125)
C_SUB    = rgb(65, 105, 185)
C_CALC   = rgb(219,229, 241)
C_GOLD   = rgb(255,242, 204)
C_GREEN  = rgb(198,239, 206)
C_RED    = rgb(255,199, 206)
C_POSTER = rgb(232,244, 253)
C_GRAY   = rgb(242,242, 242)
C_WHITE  = rgb(255,255, 255)

def pad(lst):
    return list(lst) + [''] * (12 - len(lst))

ZB = {
    'revenue':  pad([332680,    292349.27, 287813.84]),
    'delivery': pad([24092,     0,         0]),
    'work_days':pad([31,        28,        31]),
    'cash':     pad([191043,    188694,    0]),
    'noncash':  pad([162425,    118729,    0]),
    'alif':     pad([69894,     0,         0]),
    'dushcity': pad([54816,     0,         0]),
    'card':     pad([1129,      0,         0]),
    'cogs_k':   pad([107863.78, 116660.24, 118376.30]),
    'cogs_b':   pad([17267.33,  15059.66,  11744.21]),
    'pay_prod': pad([49134,     36627,     41833]),
    'pay_adm':  pad([15800,     15300,     15100]),
    'rent':     pad([26522,     13530,     27060]),
    'util':     pad([12558.52,  11344.25,  11485.27]),
    'pack':     pad([3630,      1759,      1270]),
    'logi':     pad([2806,      1530,      1210]),
    'crm':      pad([730.08,    739,       750]),
    'house':    pad([1540,      400,       1940]),
    'mkt':      pad([0,         0,         0]),
    'legal':    pad([2900,      4900,      800]),
    'other':    pad([3924,      1246.50,   3594.75]),
    'force':    pad([13000,     8100,      500]),
    'taxes':    pad([14982,     5178,      6112]),
    'divid':    pad([4600,      5150,      2100]),
    'tx':       pad([4212,      2970,      2799]),
    'vis':      pad([4442,      3083,      2849]),
    'avg_chk':  pad([85.68,     104.56,    108.08]),
}

OVIR = {
    'revenue':  pad([50563,     209027.40, 241169.80]),
    'delivery': pad([0,         0,         0]),
    'work_days':pad([8,         28,        31]),
    'cash':     pad([27688,     36788,     32592]),
    'noncash':  pad([22875,     28888,     35873]),
    'alif':     pad([15534,     0,         0]),
    'dushcity': pad([6971,      0,         0]),
    'card':     pad([370,       0,         0]),
    'cogs_k':   pad([20421.56,  67706.46,  79078.48]),
    'cogs_b':   pad([15265.70,  11581.56,  14005.17]),
    'pay_prod': pad([10236,     32650,     35719]),
    'pay_adm':  pad([6880,      16800,     16900]),
    'rent':     pad([32500,     20000,     32500]),
    'util':     pad([1345.27,   3755.03,   4134.57]),
    'pack':     pad([0,         2319,      4720]),
    'logi':     pad([450,       1740,      1336]),
    'crm':      pad([816.06,    843.04,    840]),
    'house':    pad([7886,      1174,      1740.76]),
    'mkt':      pad([0,         300,       200]),
    'legal':    pad([600,       1500,      1823]),
    'other':    pad([1181,      2221,      558]),
    'force':    pad([0,         8000,      303]),
    'taxes':    pad([882,       0,         0]),
    'divid':    pad([0,         0,         0]),
    'tx':       pad([0,         0,         0]),
    'vis':      pad([0,         0,         0]),
    'avg_chk':  pad([0,         0,         0]),
}

MONTHS = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']

# ── ROW BUILDER ──────────────────────────────────────────────────────────────
def build_rows(d, title, is_svod=False, ref_rows=None):
    rows = []

    def data(label, key):
        r = len(rows) + 1
        if is_svod and ref_rows:
            rr = ref_rows[key]
            vals = [f"='ЗБ'!{chr(66+i)}{rr}+'ОВИР'!{chr(66+i)}{rr}" for i in range(12)]
        else:
            vals = list(d[key])
        row = [label] + vals + [f'=SUM(B{r}:M{r})', '']
        rows.append(row)
        return r

    def calc(label, fml, ytd_fml):
        r = len(rows) + 1
        cols = [fml(chr(66+i)) for i in range(12)]
        rows.append([label] + cols + [ytd_fml, ''])
        return r

    def sect(label):
        rows.append([label])
        return len(rows)

    rows.append([title])
    rows.append(['Янв–Мар заполнены (Poster API + PnL). Апр–Дек — вводить вручную.'])
    rows.append([])
    rows.append(['Показатель'] + MONTHS + ['YTD', 'Бюджет'])

    sect('📊 ВЫРУЧКА')
    Rv  = data('Чистая выручка (Poster)', 'revenue')
    Rdl = data('  └ в т.ч. доставка',    'delivery')
    Rdy = data('Рабочих дней',            'work_days')
    Rrpd= calc('Выручка в день (с)',
               lambda c: f'=IFERROR({c}{Rv}/{c}{Rdy},"")',
               f'=IFERROR(N{Rv}/N{Rdy},"")')

    sect('💳 ОПЛАТЫ')
    Rca = data('Наличные (с)',          'cash')
    Rnc = data('Безналичные (с)',        'noncash')
    Ral = data('  └ Alif',              'alif')
    Rdc = data('  └ Dushanbe City',     'dushcity')
    Rcd = data('  └ Банковская карта',  'card')
    Rcp = calc('% наличных',
               lambda c: f'=IFERROR({c}{Rca}/({c}{Rca}+{c}{Rnc}),"")',
               f'=IFERROR(N{Rca}/(N{Rca}+N{Rnc}),"")')

    sect('🛒 СЕБЕСТОИМОСТЬ')
    Rck = data('Закупки кухня (с)',  'cogs_k')
    Rcb = data('Закупки бар (с)',    'cogs_b')
    Rct = calc('ИТОГО COGS',
               lambda c: f'={c}{Rck}+{c}{Rcb}',
               f'=N{Rck}+N{Rcb}')
    Rfk = calc('Food Cost кухня %  [цель: <30%]',
               lambda c: f'=IFERROR({c}{Rck}/{c}{Rv},"")',
               f'=IFERROR(N{Rck}/N{Rv},"")')
    Rft = calc('Food Cost общий %  [цель: <30%]',
               lambda c: f'=IFERROR({c}{Rct}/{c}{Rv},"")',
               f'=IFERROR(N{Rct}/N{Rv},"")')

    sect('ВАЛОВАЯ ПРИБЫЛЬ')
    Rgp = calc('Валовая прибыль',
               lambda c: f'={c}{Rv}-{c}{Rct}',
               f'=N{Rv}-N{Rct}')
    Rgpp= calc('Маржа %  [цель: >60%]',
               lambda c: f'=IFERROR({c}{Rgp}/{c}{Rv},"")',
               f'=IFERROR(N{Rgp}/N{Rv},"")')

    sect('👥 ФОТ')
    Rpp = data('ФОТ — производство',   'pay_prod')
    Rpa = data('ФОТ — администрация',  'pay_adm')
    Rpt = calc('ИТОГО ФОТ',
               lambda c: f'={c}{Rpp}+{c}{Rpa}',
               f'=N{Rpp}+N{Rpa}')
    Rlc = calc('Labor Cost %  [цель: <25%]',
               lambda c: f'=IFERROR({c}{Rpt}/{c}{Rv},"")',
               f'=IFERROR(N{Rpt}/N{Rv},"")')
    Rpc = calc('Prime Cost (еда + труд) %  [цель: <55%]',
               lambda c: f'=IFERROR(({c}{Rct}+{c}{Rpt})/{c}{Rv},"")',
               f'=IFERROR((N{Rct}+N{Rpt})/N{Rv},"")')

    sect('📋 ОПЕРАЦИОННЫЕ РАСХОДЫ')
    Rre = data('Аренда',               'rent')
    Rrp = calc('  % аренды',
               lambda c: f'=IFERROR({c}{Rre}/{c}{Rv},"")',
               f'=IFERROR(N{Rre}/N{Rv},"")')
    Rut = data('Коммунальные',          'util')
    Rpk = data('Упаковка',              'pack')
    Rlg = data('Логистика',             'logi')
    Rcm = data('CRM / Poster',          'crm')
    Rho = data('Хозтовары',             'house')
    Rmk = data('Маркетинг',             'mkt')
    Rle = data('Юридические расходы',   'legal')
    Rot = data('Прочие расходы',        'other')
    Rfo = data('Форс-мажор',            'force')
    Rox = calc('ИТОГО OpEx',
               lambda c: (f'=SUM({c}{Rre},{c}{Rut},{c}{Rpk},{c}{Rlg},'
                          f'{c}{Rcm},{c}{Rho},{c}{Rmk},{c}{Rle},{c}{Rot},{c}{Rfo})'),
               (f'=SUM(N{Rre},N{Rut},N{Rpk},N{Rlg},'
                f'N{Rcm},N{Rho},N{Rmk},N{Rle},N{Rot},N{Rfo})'))

    sect('EBITDA')
    Reb = calc('EBITDA',
               lambda c: f'={c}{Rgp}-{c}{Rpt}-{c}{Rox}',
               f'=N{Rgp}-N{Rpt}-N{Rox}')
    Rebp= calc('EBITDA %  [цель: 15–22%]',
               lambda c: f'=IFERROR({c}{Reb}/{c}{Rv},"")',
               f'=IFERROR(N{Reb}/N{Rv},"")')

    sect('💰 ИТОГ')
    Rtx = data('Налоги',               'taxes')
    Rnet= calc('Чистая прибыль',
               lambda c: f'={c}{Reb}-{c}{Rtx}',
               f'=N{Reb}-N{Rtx}')
    Rnp = calc('Чистая маржа %  [цель: 10–15%]',
               lambda c: f'=IFERROR({c}{Rnet}/{c}{Rv},"")',
               f'=IFERROR(N{Rnet}/N{Rv},"")')
    Rdv = data('Дивиденды',            'divid')
    Rfc = calc('Свободный кэш',
               lambda c: f'={c}{Rnet}-{c}{Rdv}',
               f'=N{Rnet}-N{Rdv}')

    rows.append([])

    sect('📱 POSTER МЕТРИКИ')
    if is_svod:
        Rtr = data('Транзакции (чеки)', 'tx')
        Rvi = data('Гости',             'vis')
        Rac = calc('Средний чек (с)',
                   lambda c: f'=IFERROR({c}{Rv}/{c}{Rtr},"")',
                   f'=IFERROR(N{Rv}/N{Rtr},"")')
    else:
        Rtr = data('Транзакции (чеки)', 'tx')
        Rvi = data('Гости',             'vis')
        Rac = data('Средний чек (с)',    'avg_chk')
    Rgpd= calc('Гостей в день',
               lambda c: f'=IFERROR({c}{Rvi}/{c}{Rdy},"")',
               f'=IFERROR(N{Rvi}/N{Rdy},"")')

    ref = {
        'revenue': Rv, 'delivery': Rdl, 'work_days': Rdy,
        'cash': Rca, 'noncash': Rnc, 'alif': Ral, 'dushcity': Rdc, 'card': Rcd,
        'cogs_k': Rck, 'cogs_b': Rcb,
        'pay_prod': Rpp, 'pay_adm': Rpa,
        'rent': Rre, 'util': Rut, 'pack': Rpk, 'logi': Rlg,
        'crm': Rcm, 'house': Rho, 'mkt': Rmk, 'legal': Rle,
        'other': Rot, 'force': Rfo,
        'taxes': Rtx, 'divid': Rdv,
        'tx': Rtr, 'vis': Rvi, 'avg_chk': Rac,
        'R_REV': Rv, 'R_GP': Rgp, 'R_GPP': Rgpp,
        'R_EBIT': Reb, 'R_EBITP': Rebp,
        'R_NET': Rnet, 'R_NP': Rnp, 'R_FC': Rft, 'R_LC': Rlc,
        'R_PC': Rpc, 'R_FREE': Rfc, 'R_GPD': Rgpd, 'R_AVG': Rac,
        'R_VIS': Rvi, 'R_TX': Rtr, 'R_DAYS': Rdy,
    }
    return rows, ref

# ── KPI SHEET ─────────────────────────────────────────────────────────────────
def build_kpi_rows(zb_ref, ov_ref, sv_ref):
    m = 'D'   # March = col D (4th month = index 2 → col D)
    def z(key): return f"='ЗБ'!D{zb_ref[key]}"
    def o(key): return f"='ОВИР'!D{ov_ref[key]}"
    def s(key): return f"='Свод'!D{sv_ref[key]}"

    rows = [
        ['РОМАШКА — KPI ДАШБОРД | Март 2026 (последний полный месяц)'],
        ['Автоматически из листов ЗБ, ОВИР, Свод'],
        [],
        ['Показатель', 'ЗБ (Лохути)', 'ОВИР (ОВИР)', 'СЕТЬ итого', 'Цель', 'Статус'],
        ['📊 ВЫРУЧКА'],
        ['Выручка месяц (с)',         z('R_REV'),  o('R_REV'),  s('R_REV'),  '—', ''],
        ['Выручка в день (с)',        z('R_GPD'),  o('R_GPD'),  s('R_GPD'),  '—', ''],
        [],
        ['🛒 СЕБЕСТОИМОСТЬ'],
        ['Food Cost %',              z('R_FC'),   o('R_FC'),   s('R_FC'),   '30%', ''],
        [],
        ['👥 ФОТ'],
        ['Labor Cost %',             z('R_LC'),   o('R_LC'),   s('R_LC'),   '25%', ''],
        ['Prime Cost %',             z('R_PC'),   o('R_PC'),   s('R_PC'),   '55%', ''],
        [],
        ['ПРИБЫЛЬНОСТЬ'],
        ['Валовая маржа %',          z('R_GPP'),  o('R_GPP'),  s('R_GPP'),  '60%', ''],
        ['EBITDA %',                 z('R_EBITP'),o('R_EBITP'),s('R_EBITP'),'17%', ''],
        ['Чистая маржа %',           z('R_NP'),   o('R_NP'),   s('R_NP'),   '12%', ''],
        ['Чистая прибыль (с)',       z('R_NET'),  o('R_NET'),  s('R_NET'),  '—', ''],
        ['Свободный кэш (с)',        z('R_FREE'), o('R_FREE'), s('R_FREE'), '—', ''],
        [],
        ['📱 POSTER'],
        ['Гости в месяц',            z('R_VIS'),  o('R_VIS'),  s('R_VIS'),  '—', ''],
        ['Гостей в день',            z('R_GPD'),  o('R_GPD'),  s('R_GPD'),  '>100', ''],
        ['Средний чек (с)',          z('R_AVG'),  o('R_AVG'),  s('R_AVG'),  '>110', ''],
        ['Транзакции',               z('R_TX'),   o('R_TX'),   s('R_TX'),   '—', ''],
    ]
    return rows

# ── FORMATTING HELPER ─────────────────────────────────────────────────────────
def fmt_cell(sid, r, c, bold=False, bg=None, fg=None, fs=12,
             align='LEFT', fmt_type=None, italic=False, borders=False):
    fields = []
    tf = {'fontFamily': FONT, 'fontSize': fs, 'bold': bold, 'italic': italic}
    if fg: tf['foregroundColor'] = fg
    cell_fmt = {'textFormat': tf, 'horizontalAlignment': align}
    if bg: cell_fmt['backgroundColor'] = bg
    if fmt_type == 'pct':
        cell_fmt['numberFormat'] = {'type': 'NUMBER', 'pattern': '0.0%'}
    elif fmt_type == 'num':
        cell_fmt['numberFormat'] = {'type': 'NUMBER', 'pattern': '#,##0'}
    elif fmt_type == 'num1':
        cell_fmt['numberFormat'] = {'type': 'NUMBER', 'pattern': '#,##0.0'}
    fields = ['textFormat','horizontalAlignment','backgroundColor','numberFormat']
    return {
        'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': r,
                      'endRowIndex': r+1, 'startColumnIndex': c, 'endColumnIndex': c+1},
            'cell': {'userEnteredFormat': cell_fmt},
            'fields': ','.join(f'userEnteredFormat.{f}' for f in fields)
        }
    }

def fmt_row(sid, r, c0, c1, bold=False, bg=None, fg=None, fs=12,
            align='LEFT', fmt_type=None):
    fields = ['textFormat','horizontalAlignment','backgroundColor']
    if fmt_type: fields.append('numberFormat')
    tf = {'fontFamily': FONT, 'fontSize': fs, 'bold': bold}
    if fg: tf['foregroundColor'] = fg
    cell_fmt = {'textFormat': tf, 'horizontalAlignment': align}
    if bg: cell_fmt['backgroundColor'] = bg
    if fmt_type == 'pct':
        cell_fmt['numberFormat'] = {'type': 'NUMBER', 'pattern': '0.0%'}
    elif fmt_type == 'num':
        cell_fmt['numberFormat'] = {'type': 'NUMBER', 'pattern': '#,##0'}
    return {
        'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': r,
                      'endRowIndex': r+1, 'startColumnIndex': c0, 'endColumnIndex': c1},
            'cell': {'userEnteredFormat': cell_fmt},
            'fields': ','.join(f'userEnteredFormat.{f}' for f in fields)
        }
    }

def merge(sid, r0, r1, c0, c1):
    return {'mergeCells': {
        'range': {'sheetId': sid, 'startRowIndex': r0, 'endRowIndex': r1,
                  'startColumnIndex': c0, 'endColumnIndex': c1},
        'mergeType': 'MERGE_ALL'}}

def col_width(sid, c, px):
    return {'updateDimensionProperties': {
        'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                  'startIndex': c, 'endIndex': c+1},
        'properties': {'pixelSize': px},
        'fields': 'pixelSize'}}

def freeze(sid, rows=4, cols=1):
    return {'updateSheetProperties': {
        'properties': {'sheetId': sid,
                       'gridProperties': {'frozenRowCount': rows, 'frozenColumnCount': cols}},
        'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}}

# ── APPLY FORMAT FOR ONE PNL SHEET ───────────────────────────────────────────
def format_pnl_sheet(sid, ref):
    reqs = [freeze(sid, rows=4, cols=1)]
    NCOLS = 15  # A..O

    # Column widths
    reqs.append(col_width(sid, 0, 250))
    for c in range(1, 13): reqs.append(col_width(sid, c, 78))
    reqs.append(col_width(sid, 13, 90))  # YTD
    reqs.append(col_width(sid, 14, 90))  # Бюджет

    R = ref

    # Row 1: Title
    reqs.append(fmt_row(sid, 0, 0, NCOLS, bold=True, bg=C_DARK, fg=C_WHITE, fs=14, align='CENTER'))
    reqs.append(merge(sid, 0, 1, 0, NCOLS))

    # Row 2: Subtitle
    reqs.append(fmt_row(sid, 1, 0, NCOLS, bg=C_SEC, fg=C_WHITE, fs=11, align='CENTER'))
    reqs.append(merge(sid, 1, 2, 0, NCOLS))

    # Row 4: Headers
    reqs.append(fmt_row(sid, 3, 0, NCOLS, bold=True, bg=C_SUB, fg=C_WHITE, fs=12, align='CENTER'))

    def sec_row(r): # section header row
        reqs.append(fmt_row(sid, r-1, 0, NCOLS, bold=True, bg=C_SEC, fg=C_WHITE, fs=12))
        reqs.append(merge(sid, r-1, r, 0, NCOLS))

    def data_r(r, pct=False):
        reqs.append(fmt_row(sid, r-1, 0, 1, bg=C_WHITE, fs=12))
        t = 'pct' if pct else 'num'
        reqs.append(fmt_row(sid, r-1, 1, NCOLS, bg=C_WHITE, fs=12, align='RIGHT', fmt_type=t))

    def calc_r(r, pct=False):
        reqs.append(fmt_row(sid, r-1, 0, 1, bg=C_CALC, fs=12))
        t = 'pct' if pct else 'num'
        reqs.append(fmt_row(sid, r-1, 1, NCOLS, bg=C_CALC, fs=12, align='RIGHT', fmt_type=t))

    def key_r(r, pct=False, good_bg=None):
        bg = good_bg or C_GOLD
        reqs.append(fmt_row(sid, r-1, 0, 1, bold=True, bg=bg, fs=12))
        t = 'pct' if pct else 'num'
        reqs.append(fmt_row(sid, r-1, 1, NCOLS, bold=True, bg=bg, fs=12, align='RIGHT', fmt_type=t))

    # Section rows (each is 1-indexed row in the sheet):
    sec_row(5)   # ВЫРУЧКА
    key_r(R['R_REV'])               # Выручка
    data_r(R['delivery'])           # доставка
    data_r(R['work_days'])          # дни
    calc_r(R['R_GPD'], pct=False)   # выручка/день

    sec_row(R['R_GPD']+1)           # ОПЛАТЫ
    data_r(R['cash'])
    data_r(R['noncash'])
    data_r(R['alif'])
    data_r(R['dushcity'])
    data_r(R['card'])
    calc_r(R['R_LC']-10, pct=True)  # % наличных (approximate, adjust via ref)

    sec_row(R['cogs_k']-1)          # СЕБЕСТОИМОСТЬ
    data_r(R['cogs_k'])
    data_r(R['cogs_b'])
    key_r(R['cogs_k']+2)            # ИТОГО COGS
    calc_r(R['cogs_k']+3, pct=True) # FC кухня %
    calc_r(R['R_FC'], pct=True)     # FC общий %

    sec_row(R['R_GP']-1)            # ВАЛОВАЯ ПРИБЫЛЬ
    key_r(R['R_GP'])
    calc_r(R['R_GPP'], pct=True)

    sec_row(R['pay_prod']-1)        # ФОТ
    data_r(R['pay_prod'])
    data_r(R['pay_adm'])
    key_r(R['pay_prod']+2)          # ИТОГО ФОТ
    calc_r(R['R_LC'], pct=True)
    calc_r(R['R_PC'], pct=True)

    sec_row(R['rent']-1)            # ОПEX
    data_r(R['rent'])
    calc_r(R['rent']+1, pct=True)   # % аренды
    for k in ['util','pack','logi','crm','house','mkt','legal','other','force']:
        data_r(R[k])
    key_r(R['force']+1)             # ИТОГО OpEx

    sec_row(R['R_EBIT']-1)          # EBITDA
    key_r(R['R_EBIT'])
    calc_r(R['R_EBITP'], pct=True)

    sec_row(R['taxes']-1)           # ИТОГ
    data_r(R['taxes'])
    key_r(R['R_NET'])
    calc_r(R['R_NP'], pct=True)
    data_r(R['divid'])
    key_r(R['R_FREE'])

    sec_row(R['tx']-1)              # POSTER
    data_r(R['tx'])
    data_r(R['vis'])
    data_r(R['avg_chk'])
    calc_r(R['R_GPD'])

    return reqs

# ── MAIN ──────────────────────────────────────────────────────────────────────
def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/drive',
                       'https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def api_post(s, url, body, retries=6):
    for attempt in range(retries):
        try:
            r = s.post(url, headers={'Content-Type': 'application/json'},
                       data=json.dumps(body), timeout=90)
            if r.status_code == 503 or len(r.content) == 0:
                print(f'    retry {attempt+1} (503/empty)...')
                time.sleep(2 ** attempt); continue
            return r
        except Exception as e:
            print(f'    retry {attempt+1} ({e})...')
            time.sleep(2 ** attempt)
    return None

def api_put(s, url, body, params=None, retries=5):
    for attempt in range(retries):
        r = s.put(url, headers={'Content-Type': 'application/json'},
                  data=json.dumps(body), params=params or {}, timeout=45)
        if r.status_code == 503 or len(r.content) == 0:
            time.sleep(2 ** attempt); continue
        return r
    return None

def write_values(s, sid, sheet_name, rows):
    body = {'valueInputOption': 'USER_ENTERED',
            'data': [{'range': f"'{sheet_name}'!A1",
                      'values': [[str(c) if c != '' else '' for c in row] for row in rows]}]}
    r = api_post(s, f'https://sheets.googleapis.com/v4/spreadsheets/{sid}/values:batchUpdate',
                 body)
    if r and r.status_code == 200:
        print(f'  ✅ Values written: {sheet_name}')
    else:
        print(f'  ❌ Values failed: {sheet_name} — {r.status_code if r else "no response"}')
        if r: print(r.text[:300])

def apply_format(s, sid, reqs):
    if not reqs: return
    r = api_post(s, f'https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate',
                 {'requests': reqs})
    if r and r.status_code == 200:
        print(f'  ✅ Formatting applied ({len(reqs)} requests)')
    else:
        print(f'  ❌ Format failed — {r.status_code if r else "no response"}')
        if r: print(r.text[:300])

def main():
    s = get_session()
    print('Создаём файл...')

    # Create file
    r = api_post(s, 'https://www.googleapis.com/drive/v3/files?supportsAllDrives=true',
                 {'name': 'Ромашка — Super P&L 2026',
                  'mimeType': 'application/vnd.google-apps.spreadsheet',
                  'parents': [FOLDER_ID]})
    sid = r.json()['id']
    print(f'ID: {sid}')

    # Get default sheet ID
    r2 = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{sid}?fields=sheets.properties',
               timeout=30)
    sheets = r2.json()['sheets']
    default_sid = sheets[0]['properties']['sheetId']

    # Create sheets
    r3 = api_post(s, f'https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate', {
        'requests': [
            {'updateSheetProperties': {'properties': {'sheetId': default_sid, 'title': 'ЗБ'},
                                       'fields': 'title'}},
            {'addSheet': {'properties': {'title': 'ОВИР',  'index': 1}}},
            {'addSheet': {'properties': {'title': 'Свод',  'index': 2}}},
            {'addSheet': {'properties': {'title': 'KPI',   'index': 3}}},
        ]
    })
    new_sheets = r3.json()['replies']
    ovir_sid = new_sheets[1]['addSheet']['properties']['sheetId']
    svod_sid = new_sheets[2]['addSheet']['properties']['sheetId']
    kpi_sid  = new_sheets[3]['addSheet']['properties']['sheetId']
    print(f'Sheets: ЗБ={default_sid} ОВИР={ovir_sid} Свод={svod_sid} KPI={kpi_sid}')

    # ── Build ЗБ ──
    print('\n── ЗБ ──')
    zb_rows, zb_ref = build_rows(ZB, 'РОМАШКА — P&L 2026 | ЗБ (Лохути 11)')
    write_values(s, sid, 'ЗБ', zb_rows)
    time.sleep(1)
    apply_format(s, sid, format_pnl_sheet(default_sid, zb_ref))

    # ── Build ОВИР ──
    print('\n── ОВИР ──')
    ov_rows, ov_ref = build_rows(OVIR, 'РОМАШКА — P&L 2026 | ОВИР (Турсунзода)')
    write_values(s, sid, 'ОВИР', ov_rows)
    time.sleep(1)
    apply_format(s, sid, format_pnl_sheet(ovir_sid, ov_ref))

    # ── Build Свод ──
    print('\n── Свод ──')
    sv_rows, sv_ref = build_rows(ZB, 'РОМАШКА — P&L 2026 | СВОД (ЗБ + ОВИР)',
                                  is_svod=True, ref_rows=zb_ref)
    write_values(s, sid, 'Свод', sv_rows)
    time.sleep(1)
    apply_format(s, sid, format_pnl_sheet(svod_sid, sv_ref))

    # ── Build KPI ──
    print('\n── KPI ──')
    kpi_rows = build_kpi_rows(zb_ref, ov_ref, sv_ref)
    write_values(s, sid, 'KPI', kpi_rows)

    # KPI basic formatting
    kpi_fmt = [
        freeze(kpi_sid, rows=4, cols=1),
        col_width(kpi_sid, 0, 220),
        col_width(kpi_sid, 1, 130),
        col_width(kpi_sid, 2, 130),
        col_width(kpi_sid, 3, 130),
        col_width(kpi_sid, 4, 80),
        col_width(kpi_sid, 5, 80),
        fmt_row(kpi_sid, 0, 0, 6, bold=True, bg=C_DARK, fg=C_WHITE, fs=14, align='CENTER'),
        merge(kpi_sid, 0, 1, 0, 6),
        fmt_row(kpi_sid, 1, 0, 6, bg=C_SEC, fg=C_WHITE, fs=11, align='CENTER'),
        merge(kpi_sid, 1, 2, 0, 6),
        fmt_row(kpi_sid, 3, 0, 6, bold=True, bg=C_SUB, fg=C_WHITE, fs=12, align='CENTER'),
    ]
    apply_format(s, sid, kpi_fmt)

    print(f'\n✅ https://docs.google.com/spreadsheets/d/{sid}/edit')

if __name__ == '__main__':
    main()
