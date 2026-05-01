#!/usr/bin/env python3
"""Ромашка — Super P&L 2026 | ЗБ + ОВИР + Свод + KPI + Cash Flow"""
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
C_WHITE  = rgb(255,255, 255)

def pad(lst):
    return list(lst) + [''] * (12 - len(lst))

ZB = {
    'revenue':    pad([332680,    292349.27, 287813.84]),
    'delivery':   pad([24092,     0,         0]),
    'work_days':  pad([31,        28,        31]),
    'cash':       pad([191043,    188694,    0]),
    'noncash':    pad([162425,    118729,    0]),
    'alif':       pad([69894,     0,         0]),
    'dushcity':   pad([54816,     0,         0]),
    'card':       pad([1129,      0,         0]),
    'cogs_k':     pad([107863.78, 116660.24, 118376.30]),
    'cogs_b':     pad([17267.33,  15059.66,  11744.21]),
    'cogs_staff': pad([0,         0,         0]),
    'cogs_mat':   pad([0,         0,         0]),
    'pay_prod':   pad([49134,     36627,     41833]),
    'pay_adm':    pad([15800,     15300,     15100]),
    'rent':       pad([26522,     13530,     27060]),
    'util':       pad([12558.52,  11344.25,  11485.27]),
    'pack':       pad([3630,      1759,      1270]),
    'logi':       pad([2806,      1530,      1210]),
    'crm':        pad([730.08,    739,       750]),
    'house':      pad([1540,      400,       1940]),
    'mkt':        pad([0,         0,         0]),
    'legal':      pad([2900,      4900,      800]),
    'other':      pad([3924,      1246.50,   3594.75]),
    'force':      pad([13000,     8100,      500]),
    'taxes':      pad([14982,     5178,      6112]),
    'divid':      pad([4600,      5150,      2100]),
    'tx':         pad([4212,      2970,      2799]),
    'vis':        pad([4442,      3083,      2849]),
    'avg_chk':    pad([85.68,     104.56,    108.08]),
}

OVIR = {
    'revenue':    pad([50563,     209027.40, 241169.80]),
    'delivery':   pad([0,         0,         0]),
    'work_days':  pad([8,         28,        31]),
    'cash':       pad([27688,     36788,     32592]),
    'noncash':    pad([22875,     28888,     35873]),
    'alif':       pad([15534,     0,         0]),
    'dushcity':   pad([6971,      0,         0]),
    'card':       pad([370,       0,         0]),
    'cogs_k':     pad([20421.56,  67706.46,  79078.48]),
    'cogs_b':     pad([15265.70,  11581.56,  14005.17]),
    'cogs_staff': pad([0,         0,         0]),
    'cogs_mat':   pad([0,         0,         0]),
    'pay_prod':   pad([10236,     32650,     35719]),
    'pay_adm':    pad([6880,      16800,     16900]),
    'rent':       pad([32500,     20000,     32500]),
    'util':       pad([1345.27,   3755.03,   4134.57]),
    'pack':       pad([0,         2319,      4720]),
    'logi':       pad([450,       1740,      1336]),
    'crm':        pad([816.06,    843.04,    840]),
    'house':      pad([7886,      1174,      1740.76]),
    'mkt':        pad([0,         300,       200]),
    'legal':      pad([600,       1500,      1823]),
    'other':      pad([1181,      2221,      558]),
    'force':      pad([0,         8000,      303]),
    'taxes':      pad([882,       0,         0]),
    'divid':      pad([0,         0,         0]),
    'tx':         pad([0,         0,         0]),
    'vis':        pad([0,         0,         0]),
    'avg_chk':    pad([0,         0,         0]),
}

MONTHS = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']


# ── ROW BUILDER ───────────────────────────────────────────────────────────────
def build_rows(d, title, is_svod=False, ref_rows=None):
    rows = []

    def data(label, key):
        r = len(rows) + 1
        if is_svod and ref_rows:
            rr = ref_rows[key]
            vals = [f"='ЗБ'!{chr(66+i)}{rr}+'ОВИР'!{chr(66+i)}{rr}" for i in range(12)]
        else:
            vals = list(d[key])
        rows.append([label] + vals + [f'=SUM(B{r}:M{r})', ''])
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

    s_rev   = sect('📊 ВЫРУЧКА')
    Rv      = data('Чистая выручка (Poster)',  'revenue')
    Rdl     = data('  └ в т.ч. доставка',      'delivery')
    Rdy     = data('Рабочих дней',              'work_days')
    Rrpd    = calc('Выручка в день (с)',
                   lambda c: f'=IFERROR({c}{Rv}/{c}{Rdy},"")',
                   f'=IFERROR(N{Rv}/N{Rdy},"")')

    s_opl   = sect('💳 ОПЛАТЫ')
    Rca     = data('Наличные (с)',              'cash')
    Rnc     = data('Безналичные (с)',           'noncash')
    Ral     = data('  └ Alif',                  'alif')
    Rdc     = data('  └ Dushanbe City',         'dushcity')
    Rcd     = data('  └ Банковская карта',      'card')
    Rcp     = calc('% наличных',
                   lambda c: f'=IFERROR({c}{Rca}/({c}{Rca}+{c}{Rnc}),"")',
                   f'=IFERROR(N{Rca}/(N{Rca}+N{Rnc}),"")')
    Rncp2   = calc('% безналичных',
                   lambda c: f'=IFERROR({c}{Rnc}/({c}{Rca}+{c}{Rnc}),"")',
                   f'=IFERROR(N{Rnc}/(N{Rca}+N{Rnc}),"")')

    s_cogs  = sect('🛒 СЕБЕСТОИМОСТЬ')
    Rck     = data('Закупки кухня (с)',         'cogs_k')
    Rcb     = data('Закупки бар (с)',           'cogs_b')
    Rcs     = data('Закуп персонал (с)',        'cogs_staff')
    Rcm2    = data('Расходные материалы (с)',   'cogs_mat')
    Rct     = calc('ИТОГО COGS',
                   lambda c: f'={c}{Rck}+{c}{Rcb}+{c}{Rcs}+{c}{Rcm2}',
                   f'=N{Rck}+N{Rcb}+N{Rcs}+N{Rcm2}')
    Rfk     = calc('Food Cost кухня %  [цель: <30%]',
                   lambda c: f'=IFERROR({c}{Rck}/{c}{Rv},"")',
                   f'=IFERROR(N{Rck}/N{Rv},"")')
    Rft     = calc('Food Cost общий %  [цель: <30%]',
                   lambda c: f'=IFERROR({c}{Rct}/{c}{Rv},"")',
                   f'=IFERROR(N{Rct}/N{Rv},"")')

    s_gp    = sect('ВАЛОВАЯ ПРИБЫЛЬ')
    Rgp     = calc('Валовая прибыль',
                   lambda c: f'={c}{Rv}-{c}{Rct}',
                   f'=N{Rv}-N{Rct}')
    Rgpp    = calc('Маржа %  [цель: >60%]',
                   lambda c: f'=IFERROR({c}{Rgp}/{c}{Rv},"")',
                   f'=IFERROR(N{Rgp}/N{Rv},"")')

    s_pay   = sect('👥 ФОТ')
    Rpp     = data('ФОТ — производство',       'pay_prod')
    Rpa     = data('ФОТ — администрация',      'pay_adm')
    Rpt     = calc('ИТОГО ФОТ',
                   lambda c: f'={c}{Rpp}+{c}{Rpa}',
                   f'=N{Rpp}+N{Rpa}')
    Rlc     = calc('Labor Cost %  [цель: <25%]',
                   lambda c: f'=IFERROR({c}{Rpt}/{c}{Rv},"")',
                   f'=IFERROR(N{Rpt}/N{Rv},"")')
    Rpc     = calc('Prime Cost (еда + труд) %  [цель: <55%]',
                   lambda c: f'=IFERROR(({c}{Rct}+{c}{Rpt})/{c}{Rv},"")',
                   f'=IFERROR((N{Rct}+N{Rpt})/N{Rv},"")')

    s_opex  = sect('📋 ОПЕРАЦИОННЫЕ РАСХОДЫ')
    Rre     = data('Аренда',                   'rent')
    Rrp     = calc('  % аренды',
                   lambda c: f'=IFERROR({c}{Rre}/{c}{Rv},"")',
                   f'=IFERROR(N{Rre}/N{Rv},"")')
    Rut     = data('Коммунальные',             'util')
    Rpk     = data('Упаковка',                 'pack')
    Rlg     = data('Логистика',                'logi')
    Rcm     = data('CRM / Poster',             'crm')
    Rho     = data('Хозтовары',               'house')
    Rmk     = data('Маркетинг',                'mkt')
    Rle     = data('Юридические расходы',      'legal')
    Rot     = data('Прочие расходы',           'other')
    Rfo     = data('Форс-мажор',               'force')
    Rox     = calc('ИТОГО OpEx',
                   lambda c: (f'=SUM({c}{Rre},{c}{Rut},{c}{Rpk},{c}{Rlg},'
                              f'{c}{Rcm},{c}{Rho},{c}{Rmk},{c}{Rle},{c}{Rot},{c}{Rfo})'),
                   (f'=SUM(N{Rre},N{Rut},N{Rpk},N{Rlg},'
                    f'N{Rcm},N{Rho},N{Rmk},N{Rle},N{Rot},N{Rfo})'))

    s_ebit  = sect('🔶 EBITDA')
    Reb     = calc('EBITDA',
                   lambda c: f'={c}{Rgp}-{c}{Rpt}-{c}{Rox}',
                   f'=N{Rgp}-N{Rpt}-N{Rox}')
    Rebp    = calc('EBITDA %  [цель: 15–22%]',
                   lambda c: f'=IFERROR({c}{Reb}/{c}{Rv},"")',
                   f'=IFERROR(N{Reb}/N{Rv},"")')

    s_itog  = sect('💰 ИТОГ')
    Rtx     = data('Налоги',                   'taxes')
    Rnet    = calc('Чистая прибыль',
                   lambda c: f'={c}{Reb}-{c}{Rtx}',
                   f'=N{Reb}-N{Rtx}')
    Rnp     = calc('Чистая маржа %  [цель: 10–15%]',
                   lambda c: f'=IFERROR({c}{Rnet}/{c}{Rv},"")',
                   f'=IFERROR(N{Rnet}/N{Rv},"")')
    Rdv     = data('Дивиденды',                'divid')
    Rfc     = calc('Свободный кэш',
                   lambda c: f'={c}{Rnet}-{c}{Rdv}',
                   f'=N{Rnet}-N{Rdv}')

    rows.append([])

    s_post  = sect('📱 POSTER МЕТРИКИ')
    if is_svod:
        Rtr = data('Транзакции (чеки)',        'tx')
        Rvi = data('Гости',                    'vis')
        Rac = calc('Средний чек (с)',
                   lambda c: f'=IFERROR({c}{Rv}/{c}{Rtr},"")',
                   f'=IFERROR(N{Rv}/N{Rtr},"")')
    else:
        Rtr = data('Транзакции (чеки)',        'tx')
        Rvi = data('Гости',                    'vis')
        Rac = data('Средний чек (с)',           'avg_chk')
    Rgpd    = calc('Гостей в день',
                   lambda c: f'=IFERROR({c}{Rvi}/{c}{Rdy},"")',
                   f'=IFERROR(N{Rvi}/N{Rdy},"")')

    ref = {
        'revenue': Rv,   'delivery': Rdl,   'work_days': Rdy,
        'cash': Rca,     'noncash': Rnc,    'alif': Ral,
        'dushcity': Rdc, 'card': Rcd,
        'cogs_k': Rck,   'cogs_b': Rcb,     'cogs_staff': Rcs,  'cogs_mat': Rcm2,
        'pay_prod': Rpp, 'pay_adm': Rpa,
        'rent': Rre,     'util': Rut,        'pack': Rpk,        'logi': Rlg,
        'crm': Rcm,      'house': Rho,       'mkt': Rmk,         'legal': Rle,
        'other': Rot,    'force': Rfo,
        'taxes': Rtx,    'divid': Rdv,
        'tx': Rtr,       'vis': Rvi,         'avg_chk': Rac,
        # section rows
        'S_REV': s_rev,  'S_OPL': s_opl,    'S_COGS': s_cogs,   'S_GP': s_gp,
        'S_PAY': s_pay,  'S_OPEX': s_opex,  'S_EBIT': s_ebit,   'S_ITOG': s_itog,
        'S_POST': s_post,
        # calc rows
        'R_RPD':   Rrpd,   'R_CASH_PCT': Rcp,  'R_NC_PCT': Rncp2,
        'R_COGS_TOT': Rct, 'R_FC_K': Rfk,      'R_FC': Rft,
        'R_GP': Rgp,       'R_GPP': Rgpp,
        'R_PAY_TOT': Rpt,  'R_LC': Rlc,        'R_PC': Rpc,
        'R_RENT_PCT': Rrp, 'R_OPEX_TOT': Rox,
        'R_EBIT': Reb,     'R_EBITP': Rebp,
        'R_NET': Rnet,     'R_NP': Rnp,        'R_FREE': Rfc,
        'R_GPD': Rgpd,     'R_AVG': Rac,       'R_VIS': Rvi,
        'R_TX': Rtr,       'R_DAYS': Rdy,      'R_REV': Rv,
    }
    return rows, ref


# ── CASH FLOW BUILDER ─────────────────────────────────────────────────────────
def build_cf_rows(sv_ref):
    rows = []

    def sv(key, i):
        return f"='Свод'!{chr(66+i)}{sv_ref[key]}"

    def neg(key, i):
        return f"=0-'Свод'!{chr(66+i)}{sv_ref[key]}"

    rows.append(['РОМАШКА — CASH FLOW 2026 (Прямой метод)'])
    rows.append(['Операционная деятельность = данные из Свода P&L. Инвестиции и займы — ручной ввод.'])
    rows.append([])
    rows.append(['Показатель'] + MONTHS + ['YTD', ''])

    rows.append(['🔵 ОПЕРАЦИОННАЯ ДЕЯТЕЛЬНОСТЬ'])

    r_rev  = len(rows) + 1
    rows.append(['+  Поступления от клиентов (выручка)'] +
                [sv('R_REV', i) for i in range(12)] +
                [f"='Свод'!N{sv_ref['R_REV']}", ''])

    r_cogs = len(rows) + 1
    rows.append(['−  Себестоимость (закупки)'] +
                [neg('R_COGS_TOT', i) for i in range(12)] +
                [f"=0-'Свод'!N{sv_ref['R_COGS_TOT']}", ''])

    r_pay  = len(rows) + 1
    rows.append(['−  ФОТ (производство + администрация)'] +
                [neg('R_PAY_TOT', i) for i in range(12)] +
                [f"=0-'Свод'!N{sv_ref['R_PAY_TOT']}", ''])

    r_opex = len(rows) + 1
    rows.append(['−  Операционные расходы (аренда, ком., прочее)'] +
                [neg('R_OPEX_TOT', i) for i in range(12)] +
                [f"=0-'Свод'!N{sv_ref['R_OPEX_TOT']}", ''])

    r_tax  = len(rows) + 1
    rows.append(['−  Налоги'] +
                [neg('taxes', i) for i in range(12)] +
                [f"=0-'Свод'!N{sv_ref['taxes']}", ''])

    r_oper = len(rows) + 1
    rows.append(['= ОПЕРАЦИОННЫЙ ДЕНЕЖНЫЙ ПОТОК'] +
                [f'={chr(66+i)}{r_rev}+{chr(66+i)}{r_cogs}+{chr(66+i)}{r_pay}+'
                 f'{chr(66+i)}{r_opex}+{chr(66+i)}{r_tax}' for i in range(12)] +
                [f'=N{r_rev}+N{r_cogs}+N{r_pay}+N{r_opex}+N{r_tax}', ''])

    rows.append([])
    rows.append(['🟡 ИНВЕСТИЦИОННАЯ ДЕЯТЕЛЬНОСТЬ'])

    r_capex    = len(rows) + 1
    rows.append(['−  Покупка оборудования / ОС'] + [''] * 12 + ['=SUM(B{0}:M{0})'.format(r_capex), ''])

    r_inv_oth  = len(rows) + 1
    rows.append(['−  Прочие капитальные вложения'] + [''] * 12 + ['=SUM(B{0}:M{0})'.format(r_inv_oth), ''])

    r_inv  = len(rows) + 1
    rows.append(['= ИНВЕСТИЦИОННЫЙ ДЕНЕЖНЫЙ ПОТОК'] +
                [f'=0-{chr(66+i)}{r_capex}-{chr(66+i)}{r_inv_oth}' for i in range(12)] +
                [f'=0-N{r_capex}-N{r_inv_oth}', ''])

    rows.append([])
    rows.append(['🟠 ФИНАНСОВАЯ ДЕЯТЕЛЬНОСТЬ'])

    r_div  = len(rows) + 1
    rows.append(['−  Дивиденды выплаченные'] +
                [neg('divid', i) for i in range(12)] +
                [f"=0-'Свод'!N{sv_ref['divid']}", ''])

    r_ln_in  = len(rows) + 1
    rows.append(['+  Займы полученные'] + [''] * 12 + ['=SUM(B{0}:M{0})'.format(r_ln_in), ''])

    r_ln_out = len(rows) + 1
    rows.append(['−  Погашение займов'] + [''] * 12 + ['=SUM(B{0}:M{0})'.format(r_ln_out), ''])

    r_fin  = len(rows) + 1
    rows.append(['= ФИНАНСОВЫЙ ДЕНЕЖНЫЙ ПОТОК'] +
                [f'={chr(66+i)}{r_div}+{chr(66+i)}{r_ln_in}-{chr(66+i)}{r_ln_out}'
                 for i in range(12)] +
                [f'=N{r_div}+N{r_ln_in}-N{r_ln_out}', ''])

    rows.append([])
    rows.append(['📊 ИТОГО ДЕНЕЖНЫЙ ПОТОК'])

    r_net  = len(rows) + 1
    rows.append(['ИТОГО изменение кэша'] +
                [f'={chr(66+i)}{r_oper}+{chr(66+i)}{r_inv}+{chr(66+i)}{r_fin}'
                 for i in range(12)] +
                [f'=N{r_oper}+N{r_inv}+N{r_fin}', ''])

    r_open = len(rows) + 1
    rows.append(['+ Остаток кэша на начало периода (ручной ввод)'] +
                [''] * 12 + ['', ''])

    r_close = len(rows) + 1
    rows.append(['= Остаток кэша на конец периода'] +
                [f'={chr(66+i)}{r_open}+{chr(66+i)}{r_net}' for i in range(12)] +
                [f'=N{r_open}+N{r_net}', ''])

    cf_ref = {
        'r_rev': r_rev, 'r_cogs': r_cogs, 'r_pay': r_pay,
        'r_opex': r_opex, 'r_tax': r_tax, 'R_OPER': r_oper,
        'r_capex': r_capex, 'r_inv_oth': r_inv_oth, 'R_INV': r_inv,
        'r_div': r_div, 'r_ln_in': r_ln_in, 'r_ln_out': r_ln_out, 'R_FIN': r_fin,
        'R_NET': r_net, 'r_open': r_open, 'r_close': r_close,
        'S_OPER': 5, 'S_INV': r_capex - 1, 'S_FIN': r_div - 1, 'S_TOT': r_net - 1,
    }
    return rows, cf_ref


# ── KPI BUILDER ───────────────────────────────────────────────────────────────
def build_kpi_rows(zb_ref, ov_ref, sv_ref):
    # March = col D (index 2); last fully closed month
    def z(key): return f"='ЗБ'!D{zb_ref[key]}"
    def o(key): return f"='ОВИР'!D{ov_ref[key]}"
    def s(key): return f"='Свод'!D{sv_ref[key]}"

    return [
        ['РОМАШКА — KPI ДАШБОРД | Март 2026 (последний закрытый месяц)'],
        ['Данные из листов ЗБ, ОВИР, Свод — колонка «Мар»'],
        [],
        ['Показатель', 'ЗБ (Лохути)', 'ОВИР (Турсунзода)', 'СЕТЬ итого', 'Цель', 'Статус'],
        ['📊 ВЫРУЧКА'],
        ['Выручка месяц (с)',        z('R_REV'),   o('R_REV'),   s('R_REV'),   '—', ''],
        ['Выручка в день (с)',       z('R_RPD'),   o('R_RPD'),   s('R_RPD'),   '—', ''],
        [],
        ['💳 ОПЛАТЫ'],
        ['% наличных',              z('R_CASH_PCT'), o('R_CASH_PCT'), s('R_CASH_PCT'), '—', ''],
        ['% безналичных',           z('R_NC_PCT'),   o('R_NC_PCT'),   s('R_NC_PCT'),   '—', ''],
        [],
        ['🛒 СЕБЕСТОИМОСТЬ'],
        ['ИТОГО COGS (с)',           z('R_COGS_TOT'), o('R_COGS_TOT'), s('R_COGS_TOT'), '—', ''],
        ['Food Cost кухня %',        z('R_FC_K'),  o('R_FC_K'),  s('R_FC_K'),  '30%', ''],
        ['Food Cost общий %',        z('R_FC'),    o('R_FC'),    s('R_FC'),    '30%', ''],
        [],
        ['👥 ФОТ'],
        ['Labor Cost %',             z('R_LC'),    o('R_LC'),    s('R_LC'),    '25%', ''],
        ['Prime Cost %',             z('R_PC'),    o('R_PC'),    s('R_PC'),    '55%', ''],
        [],
        ['ПРИБЫЛЬНОСТЬ'],
        ['Валовая маржа %',          z('R_GPP'),   o('R_GPP'),   s('R_GPP'),   '60%', ''],
        ['EBITDA %',                 z('R_EBITP'), o('R_EBITP'), s('R_EBITP'), '17%', ''],
        ['Чистая маржа %',           z('R_NP'),    o('R_NP'),    s('R_NP'),    '12%', ''],
        ['Чистая прибыль (с)',       z('R_NET'),   o('R_NET'),   s('R_NET'),   '—', ''],
        ['Свободный кэш (с)',        z('R_FREE'),  o('R_FREE'),  s('R_FREE'),  '—', ''],
        [],
        ['📱 POSTER'],
        ['Гости в месяц',            z('R_VIS'),   o('R_VIS'),   s('R_VIS'),   '—', ''],
        ['Гостей в день',            z('R_GPD'),   o('R_GPD'),   s('R_GPD'),   '>100', ''],
        ['Средний чек (с)',          z('R_AVG'),   o('R_AVG'),   s('R_AVG'),   '>110', ''],
        ['Транзакции',               z('R_TX'),    o('R_TX'),    s('R_TX'),    '—', ''],
    ]


# ── FORMATTING HELPERS ────────────────────────────────────────────────────────
def fmt_row(sid, r, c0, c1, bold=False, bg=None, fg=None, fs=12,
            align='LEFT', fmt_type=None):
    tf = {'fontFamily': FONT, 'fontSize': fs, 'bold': bold}
    if fg: tf['foregroundColor'] = fg
    cell_fmt = {'textFormat': tf, 'horizontalAlignment': align}
    if bg: cell_fmt['backgroundColor'] = bg
    if fmt_type == 'pct':
        cell_fmt['numberFormat'] = {'type': 'NUMBER', 'pattern': '0.0%'}
    elif fmt_type == 'num':
        cell_fmt['numberFormat'] = {'type': 'NUMBER', 'pattern': '#,##0'}
    fields = ['textFormat', 'horizontalAlignment', 'backgroundColor', 'numberFormat']
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
        'properties': {'pixelSize': px}, 'fields': 'pixelSize'}}

def freeze(sid, rows=4, cols=0):
    return {'updateSheetProperties': {
        'properties': {'sheetId': sid,
                       'gridProperties': {'frozenRowCount': rows, 'frozenColumnCount': cols}},
        'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}}


# ── P&L SHEET FORMATTING ──────────────────────────────────────────────────────
def format_pnl_sheet(sid, ref):
    R = ref
    reqs = [freeze(sid, rows=4, cols=0)]
    NCOLS = 15

    reqs.append(col_width(sid, 0, 255))
    for c in range(1, 13): reqs.append(col_width(sid, c, 78))
    reqs += [col_width(sid, 13, 90), col_width(sid, 14, 90)]

    reqs += [
        fmt_row(sid, 0, 0, NCOLS, bold=True, bg=C_DARK, fg=C_WHITE, fs=14, align='CENTER'),
        merge(sid, 0, 1, 0, NCOLS),
        fmt_row(sid, 1, 0, NCOLS, bg=C_SEC, fg=C_WHITE, fs=11, align='CENTER'),
        merge(sid, 1, 2, 0, NCOLS),
        fmt_row(sid, 3, 0, NCOLS, bold=True, bg=C_SUB, fg=C_WHITE, fs=12, align='CENTER'),
    ]

    def sec(r):
        reqs.append(fmt_row(sid, r-1, 0, NCOLS, bold=True, bg=C_SEC, fg=C_WHITE, fs=12))
        reqs.append(merge(sid, r-1, r, 0, NCOLS))

    def dr(r, pct=False):
        reqs.append(fmt_row(sid, r-1, 0, 1, bg=C_WHITE, fs=12))
        reqs.append(fmt_row(sid, r-1, 1, NCOLS, bg=C_WHITE, fs=12, align='RIGHT',
                            fmt_type='pct' if pct else 'num'))

    def cr(r, pct=False):
        reqs.append(fmt_row(sid, r-1, 0, 1, bg=C_CALC, fs=12))
        reqs.append(fmt_row(sid, r-1, 1, NCOLS, bg=C_CALC, fs=12, align='RIGHT',
                            fmt_type='pct' if pct else 'num'))

    def kr(r, pct=False, bg=None):
        b = bg or C_GOLD
        reqs.append(fmt_row(sid, r-1, 0, 1, bold=True, bg=b, fs=12))
        reqs.append(fmt_row(sid, r-1, 1, NCOLS, bold=True, bg=b, fs=12, align='RIGHT',
                            fmt_type='pct' if pct else 'num'))

    sec(R['S_REV']);  kr(R['R_REV']); dr(R['delivery']); dr(R['work_days']); cr(R['R_RPD'])
    sec(R['S_OPL']);  dr(R['cash']); dr(R['noncash']); dr(R['alif']); dr(R['dushcity'])
    dr(R['card']); cr(R['R_CASH_PCT'], pct=True); cr(R['R_NC_PCT'], pct=True)
    sec(R['S_COGS']); dr(R['cogs_k']); dr(R['cogs_b']); dr(R['cogs_staff']); dr(R['cogs_mat'])
    kr(R['R_COGS_TOT']); cr(R['R_FC_K'], pct=True); cr(R['R_FC'], pct=True)
    sec(R['S_GP']);   kr(R['R_GP']); cr(R['R_GPP'], pct=True)
    sec(R['S_PAY']);  dr(R['pay_prod']); dr(R['pay_adm'])
    kr(R['R_PAY_TOT']); cr(R['R_LC'], pct=True); cr(R['R_PC'], pct=True)
    sec(R['S_OPEX']); dr(R['rent']); cr(R['R_RENT_PCT'], pct=True)
    dr(R['util']); dr(R['pack']); dr(R['logi']); dr(R['crm'])
    dr(R['house']); dr(R['mkt']); dr(R['legal']); dr(R['other']); dr(R['force'])
    kr(R['R_OPEX_TOT'])
    sec(R['S_EBIT']); kr(R['R_EBIT']); cr(R['R_EBITP'], pct=True)
    sec(R['S_ITOG']); dr(R['taxes']); kr(R['R_NET']); cr(R['R_NP'], pct=True)
    dr(R['divid']); kr(R['R_FREE'])
    sec(R['S_POST']); dr(R['tx']); dr(R['vis']); dr(R['avg_chk']); cr(R['R_GPD'])

    return reqs


# ── CASH FLOW FORMATTING ──────────────────────────────────────────────────────
def format_cf_sheet(cf_sid, cf_ref):
    R = cf_ref
    reqs = [freeze(cf_sid, rows=4, cols=0)]
    NCOLS = 15

    reqs.append(col_width(cf_sid, 0, 285))
    for c in range(1, 13): reqs.append(col_width(cf_sid, c, 78))
    reqs += [col_width(cf_sid, 13, 90), col_width(cf_sid, 14, 90)]

    reqs += [
        fmt_row(cf_sid, 0, 0, NCOLS, bold=True, bg=C_DARK, fg=C_WHITE, fs=14, align='CENTER'),
        merge(cf_sid, 0, 1, 0, NCOLS),
        fmt_row(cf_sid, 1, 0, NCOLS, bg=C_SEC, fg=C_WHITE, fs=11, align='CENTER'),
        merge(cf_sid, 1, 2, 0, NCOLS),
        fmt_row(cf_sid, 3, 0, NCOLS, bold=True, bg=C_SUB, fg=C_WHITE, fs=12, align='CENTER'),
    ]

    def sec(r):
        reqs.append(fmt_row(cf_sid, r-1, 0, NCOLS, bold=True, bg=C_SEC, fg=C_WHITE, fs=12))
        reqs.append(merge(cf_sid, r-1, r, 0, NCOLS))

    def inf(r):  # inflow — green
        reqs.append(fmt_row(cf_sid, r-1, 0, 1, bg=C_GREEN, fs=12))
        reqs.append(fmt_row(cf_sid, r-1, 1, NCOLS, bg=C_GREEN, fs=12, align='RIGHT', fmt_type='num'))

    def out(r):  # outflow — red
        reqs.append(fmt_row(cf_sid, r-1, 0, 1, bg=C_RED, fs=12))
        reqs.append(fmt_row(cf_sid, r-1, 1, NCOLS, bg=C_RED, fs=12, align='RIGHT', fmt_type='num'))

    def man(r):  # manual input
        reqs.append(fmt_row(cf_sid, r-1, 0, 1, bg=C_WHITE, fs=12))
        reqs.append(fmt_row(cf_sid, r-1, 1, NCOLS, bg=C_WHITE, fs=12, align='RIGHT', fmt_type='num'))

    def tot(r):  # total
        reqs.append(fmt_row(cf_sid, r-1, 0, 1, bold=True, bg=C_GOLD, fs=12))
        reqs.append(fmt_row(cf_sid, r-1, 1, NCOLS, bold=True, bg=C_GOLD, fs=12,
                            align='RIGHT', fmt_type='num'))

    sec(R['S_OPER']); inf(R['r_rev']); out(R['r_cogs']); out(R['r_pay'])
    out(R['r_opex']); out(R['r_tax']); tot(R['R_OPER'])
    sec(R['S_INV']);  man(R['r_capex']); man(R['r_inv_oth']); tot(R['R_INV'])
    sec(R['S_FIN']);  out(R['r_div']); man(R['r_ln_in']); man(R['r_ln_out']); tot(R['R_FIN'])
    sec(R['S_TOT']);  tot(R['R_NET']); man(R['r_open']); tot(R['r_close'])

    return reqs


# ── API HELPERS ───────────────────────────────────────────────────────────────
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
                time.sleep(2 ** attempt); continue
            return r
        except Exception as e:
            print(f'  retry {attempt+1} ({e})...')
            time.sleep(2 ** attempt)
    return None

def write_values(s, fid, sheet_name, rows):
    body = {'valueInputOption': 'USER_ENTERED',
            'data': [{'range': f"'{sheet_name}'!A1",
                      'values': [[str(c) if c != '' else '' for c in row] for row in rows]}]}
    r = api_post(s, f'https://sheets.googleapis.com/v4/spreadsheets/{fid}/values:batchUpdate', body)
    ok = r and r.status_code == 200
    print(f'  {"✅" if ok else "❌"} Values: {sheet_name}' + ('' if ok else f' — {r.status_code if r else "no resp"}'))
    if not ok and r: print(r.text[:300])

def apply_fmt(s, fid, reqs):
    if not reqs: return
    r = api_post(s, f'https://sheets.googleapis.com/v4/spreadsheets/{fid}:batchUpdate',
                 {'requests': reqs})
    ok = r and r.status_code == 200
    print(f'  {"✅" if ok else "❌"} Format ({len(reqs)} reqs)' + ('' if ok else f' — {r.status_code if r else "no resp"}'))
    if not ok and r: print(r.text[:300])

def delete_old_pnl(s):
    name = 'Ромашка — Super P&L 2026'
    q = f"name='{name}' and '{FOLDER_ID}' in parents and trashed=false"
    url = (f'https://www.googleapis.com/drive/v3/files'
           f'?q={urllib_quote(q)}&fields=files(id,name)'
           f'&supportsAllDrives=true&includeItemsFromAllDrives=true')
    r = s.get(url, timeout=30)
    for f in r.json().get('files', []):
        dr = s.delete(f"https://www.googleapis.com/drive/v3/files/{f['id']}?supportsAllDrives=true",
                      timeout=30)
        print(f'  Удалён {f["id"]}: {dr.status_code}')


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    from urllib.parse import quote as urllib_quote
    s = get_session()

    # Delete old file
    print('Удаляю старый файл...')
    name = 'Ромашка — Super P&L 2026'
    q = f"name='{name}' and '{FOLDER_ID}' in parents and trashed=false"
    from urllib.parse import urlencode
    url = ('https://www.googleapis.com/drive/v3/files?'
           + urlencode({'q': q, 'fields': 'files(id,name)',
                        'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true'}))
    rlist = s.get(url, timeout=30)
    for f in rlist.json().get('files', []):
        dr = s.delete(f"https://www.googleapis.com/drive/v3/files/{f['id']}?supportsAllDrives=true",
                      timeout=30)
        print(f'  Удалён {f["id"]}: {dr.status_code}')

    # Create new file
    print('Создаю новый файл...')
    r = api_post(s, 'https://www.googleapis.com/drive/v3/files?supportsAllDrives=true',
                 {'name': name, 'mimeType': 'application/vnd.google-apps.spreadsheet',
                  'parents': [FOLDER_ID]})
    fid = r.json()['id']
    print(f'ID: {fid}')

    # Get default sheet ID
    r2 = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{fid}?fields=sheets.properties',
               timeout=30)
    default_sid = r2.json()['sheets'][0]['properties']['sheetId']

    # Add sheets
    r3 = api_post(s, f'https://sheets.googleapis.com/v4/spreadsheets/{fid}:batchUpdate', {
        'requests': [
            {'updateSheetProperties': {'properties': {'sheetId': default_sid, 'title': 'ЗБ'},
                                       'fields': 'title'}},
            {'addSheet': {'properties': {'title': 'ОВИР',      'index': 1}}},
            {'addSheet': {'properties': {'title': 'Свод',      'index': 2}}},
            {'addSheet': {'properties': {'title': 'KPI',       'index': 3}}},
            {'addSheet': {'properties': {'title': 'Cash Flow', 'index': 4}}},
        ]
    })
    replies = r3.json()['replies']
    ovir_sid = replies[1]['addSheet']['properties']['sheetId']
    svod_sid = replies[2]['addSheet']['properties']['sheetId']
    kpi_sid  = replies[3]['addSheet']['properties']['sheetId']
    cf_sid   = replies[4]['addSheet']['properties']['sheetId']
    print(f'Sheets: ЗБ={default_sid} ОВИР={ovir_sid} Свод={svod_sid} KPI={kpi_sid} CF={cf_sid}')

    # ── ЗБ ──
    print('\n── ЗБ ──')
    zb_rows, zb_ref = build_rows(ZB, 'РОМАШКА — P&L 2026 | ЗБ (Лохути 11)')
    write_values(s, fid, 'ЗБ', zb_rows)
    time.sleep(1)
    apply_fmt(s, fid, format_pnl_sheet(default_sid, zb_ref))

    # ── ОВИР ──
    print('\n── ОВИР ──')
    ov_rows, ov_ref = build_rows(OVIR, 'РОМАШКА — P&L 2026 | ОВИР (Турсунзода)')
    write_values(s, fid, 'ОВИР', ov_rows)
    time.sleep(1)
    apply_fmt(s, fid, format_pnl_sheet(ovir_sid, ov_ref))

    # ── Свод ──
    print('\n── Свод ──')
    sv_rows, sv_ref = build_rows(ZB, 'РОМАШКА — P&L 2026 | СВОД (ЗБ + ОВИР)',
                                  is_svod=True, ref_rows=zb_ref)
    write_values(s, fid, 'Свод', sv_rows)
    time.sleep(1)
    apply_fmt(s, fid, format_pnl_sheet(svod_sid, sv_ref))

    # ── KPI ──
    print('\n── KPI ──')
    kpi_rows = build_kpi_rows(zb_ref, ov_ref, sv_ref)
    write_values(s, fid, 'KPI', kpi_rows)
    kpi_fmt = [
        freeze(kpi_sid, rows=4, cols=0),
        col_width(kpi_sid, 0, 230), col_width(kpi_sid, 1, 130),
        col_width(kpi_sid, 2, 140), col_width(kpi_sid, 3, 130),
        col_width(kpi_sid, 4, 80),  col_width(kpi_sid, 5, 80),
        fmt_row(kpi_sid, 0, 0, 6, bold=True, bg=C_DARK, fg=C_WHITE, fs=14, align='CENTER'),
        merge(kpi_sid, 0, 1, 0, 6),
        fmt_row(kpi_sid, 1, 0, 6, bg=C_SEC, fg=C_WHITE, fs=11, align='CENTER'),
        merge(kpi_sid, 1, 2, 0, 6),
        fmt_row(kpi_sid, 3, 0, 6, bold=True, bg=C_SUB, fg=C_WHITE, fs=12, align='CENTER'),
    ]
    apply_fmt(s, fid, kpi_fmt)

    # ── Cash Flow ──
    print('\n── Cash Flow ──')
    cf_rows, cf_ref = build_cf_rows(sv_ref)
    write_values(s, fid, 'Cash Flow', cf_rows)
    time.sleep(1)
    apply_fmt(s, fid, format_cf_sheet(cf_sid, cf_ref))

    print(f'\n✅ https://docs.google.com/spreadsheets/d/{fid}/edit')


if __name__ == '__main__':
    main()
