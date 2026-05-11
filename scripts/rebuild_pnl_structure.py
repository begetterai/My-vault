#!/usr/bin/env python3
"""Пересоздаёт структуру листов ЗБ и ОВИР в Super P&L."""
import json, os
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'romashka-drive.json')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
PNL_SS_ID = '1l8Lau8K9997pyqJj-zjlILAkLoOHlQmPo6BAwqc5FBU'

MONTHS_RU = ['Январь','Февраль','Март','Апрель','Май','Июнь',
             'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']

def mc(m): return chr(ord('B') + m)  # 1→C, 2→D, ..., 12→N

# (row_num, english_col_A, russian_col_B_zb, russian_col_B_ovir_or_None, formula_tpl)
ROWS = [
    (1,  'Метрики',                    'Показатели',                 None,                    None),
    (2,  'REVENUE',                    'Выручка',                    None,                    None),
    (3,  'COGS',                       'Расходы на производство',    None,                    '={c}4+{c}5+{c}6'),
    (4,  '',                           'Закуп кухни',                None,                    None),
    (5,  '',                           'Закуп бара',                 None,                    None),
    (6,  'В административные расходы', 'Прочие расходы на произ-во', None,                    '={c}7+{c}8'),
    (7,  '',                           'Закуп персоналка',           None,                    None),
    (8,  '',                           'Расходные материалы',        None,                    None),
    (9,  'GROSS PROFIT',               'Валовая прибыль',            None,                    '={c}2-{c}3'),
    (10, 'GROSS MARGIN',               'Маржинальность %',           None,                    '=IFERROR({c}9/{c}2,"")'),
    (11, 'PAYROLL',                    'ФОТ общий',                  None,                    '={c}13+{c}15'),
    (12, 'PAYROLL MARGIN',             '(% от выручки)',             None,                    '=IFERROR({c}11/{c}2,"")'),
    (13, 'DIRECT LABOR',               'ФОТ (Производственный)',     None,                    None),
    (14, '% OF PAYROLL',               '(% от общего ФОТ)',          None,                    '=IFERROR({c}13/{c}11,"")'),
    (15, 'ADMIN LABOR',                'ФОТ (Административный)',     None,                    None),
    (16, '% OF PAYROLL',               '(% от общего ФОТ)',          None,                    '=IFERROR({c}15/{c}11,"")'),
    (17, 'OPEX',                       'Административные расходы',   None,                    '=SUM({c}18:{c}37)'),
    (18, 'RENT',                       'Аренда',                     None,                    None),
    (19, 'RENT MARGIN',                '(% от выручки)',             None,                    '=IFERROR({c}18/{c}2,"")'),
    (20, 'UTILITIES',                  'Коммунальные платежи',       None,                    '={c}22+{c}23+{c}24'),
    (21, 'UTILITIES MARGIN',           '(% от выручки)',             None,                    '=IFERROR({c}20/{c}2,"")'),
    (22, '',                           'Электроэнергия',             None,                    None),
    (23, '',                           'Водоснабжение',              None,                    None),
    (24, '',                           'Вывоз мусора',               None,                    None),
    (25, '',                           'Расходы на заведение',       None,                    None),
    (26, '',                           'Расходы на оборудование',    None,                    None),
    (27, '',                           'Покупка инвентаря',          None,                    None),
    (28, '',                           'Упаковка',                   None,                    None),
    (29, '',                           'Логистика',                  None,                    None),
    (30, '',                           'Агрегатор',                  None,                    None),
    (31, '',                           'Маркетинг',                  None,                    None),
    (32, '',                           'CRM / Poster',               None,                    None),
    (33, '',                           'Интернет',                   None,                    None),
    (34, '',                           'Хозяйственные товары',       None,                    None),
    (35, '',                           'Прочие расходы',             None,                    None),
    (36, '',                           'Документы на заведение',     'Юридические расходы',   None),
    (37, '',                           'Форс-мажор',                 None,                    None),
    (38, 'EBITDA',                     'Операционная прибыль',       None,                    '={c}9-{c}11-{c}17'),
    (39, 'EBITDA MARGIN',              '(% от выручки)',             None,                    '=IFERROR({c}38/{c}2,"")'),
    (40, 'TAX',                        'Налоги',                     None,                    None),
    (41, '% OF REVENUE',               '(% от выручки)',             None,                    '=IFERROR({c}40/{c}2,"")'),
    (42, 'NET PROFIT',                 'Чистая прибыль',             None,                    '={c}38-{c}40'),
    (43, 'NET MARGIN',                 '(% от выручки)',             None,                    '=IFERROR({c}42/{c}2,"")'),
    (44, '',                           'Погашение долгов',           None,                    None),
    (45, '',                           'Инвестиции',                 None,                    None),
    (46, 'DIVIDENDS',                  'Выплаты дивидендов',         None,                    None),
    (47, '',                           'Свободные средства',         None,                    '={c}42-{c}44-{c}45-{c}46'),
]

SHEET_IDS = {'ЗБ': 0, 'ОВИР': 189519852}

def sv(s): return {'userEnteredValue': {'stringValue': s}}
def fv(f): return {'userEnteredValue': {'formulaValue': f}}
def empty(): return {'userEnteredValue': {}}


def build_requests():
    reqs = []
    for sheet_name, sheet_id in SHEET_IDS.items():
        rows_data = []
        for row_num, eng, ru_zb, ru_ovir, formula_tpl in ROWS:
            ru = (ru_ovir if ru_ovir else ru_zb) if sheet_name == 'ОВИР' else ru_zb

            if row_num == 1:
                cells = [sv(eng), sv(ru)] + [sv(m) for m in MONTHS_RU]
            else:
                cells = [sv(eng), sv(ru)]
                for m in range(1, 13):
                    col = mc(m)
                    if formula_tpl:
                        cells.append(fv(formula_tpl.replace('{c}', col)))
                    else:
                        cells.append(empty())
            rows_data.append({'values': cells})

        reqs.append({
            'updateCells': {
                'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'startColumnIndex': 0},
                'rows': rows_data,
                'fields': 'userEnteredValue'
            }
        })

        # Ширина столбцов: A=180, B=240, C-N=100
        reqs.append({'updateDimensionProperties': {
            'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 1},
            'properties': {'pixelSize': 180}, 'fields': 'pixelSize'}})
        reqs.append({'updateDimensionProperties': {
            'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 1, 'endIndex': 2},
            'properties': {'pixelSize': 240}, 'fields': 'pixelSize'}})
        reqs.append({'updateDimensionProperties': {
            'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 2, 'endIndex': 14},
            'properties': {'pixelSize': 100}, 'fields': 'pixelSize'}})

    return reqs


def main():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    session = AuthorizedSession(creds)

    reqs = build_requests()
    r = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{PNL_SS_ID}:batchUpdate',
        headers={'Content-Type': 'application/json'},
        data=json.dumps({'requests': reqs}),
        timeout=60
    )
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        print(r.text[:2000])
    else:
        print("✅ Структура ЗБ и ОВИР восстановлена")


if __name__ == '__main__':
    main()
