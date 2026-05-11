#!/usr/bin/env python3
"""Пересоздаёт структуру листов ЗБ и ОВИР в Super P&L (48 строк, как Main P&L)."""
import json, os
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'romashka-drive.json')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
PNL_SS_ID = '1l8Lau8K9997pyqJj-zjlILAkLoOHlQmPo6BAwqc5FBU'

MONTHS_RU = ['Январь','Февраль','Март','Апрель','Май','Июнь',
             'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']

def mc(m): return chr(ord('B') + m)  # 1→C, 2→D, ..., 12→N

# (row_num, english_A, russian_B_zb, russian_B_ovir_or_None, formula_zb, formula_ovir_or_None)
# formula_ovir_or_None: если отличается от ЗБ
ROWS = [
    (1,  'Метрики',                    'Показатели',                  None,                     None,                     None),
    (2,  'REVENUE',                    'Выручка',                     None,                     None,                     None),
    # R3 = итого закупки = Кухня+Бар+Персоналка+РМ
    (3,  '',                           '',                            None,                     '={c}5+{c}6+{c}7',        None),
    # R4 = COGS = только Кухня+Бар
    (4,  'COGS',                       'Расходы на производство',     None,                     '={c}5+{c}6',             None),
    (5,  '',                           'Закуп кухни',                 None,                     None,                     None),
    (6,  '',                           'Закуп бара',                  None,                     None,                     None),
    (7,  'В административные расходы', 'Прочие расходы на произ-во',  None,                     '={c}8+{c}9',             None),
    (8,  '',                           'Закуп персоналка',            None,                     None,                     None),
    (9,  '',                           'Расходные материалы',         None,                     None,                     None),
    # R10: ЗБ GP = R2-R3 (все закупки), ОВИР GP = R2-R4 (только Кухня+Бар)
    (10, 'GROSS PROFIT',               'Валовая прибыль',             None,                     '={c}2-{c}3',             '={c}2-{c}4'),
    (11, 'GROSS MARGIN',               'Маржинальность %',            None,                     '=IFERROR({c}10/{c}2,"")', None),
    (12, 'PAYROLL',                    'ФОТ общий',                   None,                     '={c}14+{c}16',           None),
    (13, 'PAYROLL MARGIN',             '(% от выручки)',              None,                     '=IFERROR({c}12/{c}2,"")', None),
    (14, 'DIRECT LABOR',               'ФОТ (Производственный)',      None,                     None,                     None),
    (15, '% OF PAYROLL',               '(% от общего ФОТ)',           None,                     '=IFERROR({c}14/{c}12,"")', None),
    (16, 'ADMIN LABOR',                'ФОТ (Административный)',      None,                     None,                     None),
    (17, '% OF PAYROLL',               '(% от общего ФОТ)',           None,                     '=IFERROR({c}16/{c}12,"")', None),
    (18, 'OPEX',                       'Административные расходы',    None,                     '=SUM({c}19:{c}38)',       None),
    (19, 'RENT',                       'Аренда',                      None,                     None,                     None),
    (20, 'RENT MARGIN',                '(% от выручки)',              None,                     '=IFERROR({c}19/{c}2,"")', None),
    (21, 'UTILITIES',                  'Коммунальные платежи',        None,                     '={c}23+{c}24+{c}25',     None),
    (22, 'UTILITIES MARGIN',           '(% от выручки)',              None,                     '=IFERROR({c}21/{c}2,"")', None),
    (23, '',                           'Электроэнергия',              None,                     None,                     None),
    (24, '',                           'Водоснабжение',               None,                     None,                     None),
    (25, '',                           'Вывоз мусора',                None,                     None,                     None),
    (26, '',                           'Расходы на заведение',        None,                     None,                     None),
    (27, '',                           'Расходы на оборудование',     None,                     None,                     None),
    (28, '',                           'Расходы на инвентарь',        None,                     None,                     None),
    (29, '',                           'Упаковка',                    None,                     None,                     None),
    (30, '',                           'Логистика',                   None,                     None,                     None),
    (31, '',                           'Агрегатор',                   None,                     None,                     None),
    (32, '',                           'Маркетинг',                   None,                     None,                     None),
    (33, '',                           'CRM',                         None,                     None,                     None),
    (34, '',                           'Интернет',                    None,                     None,                     None),
    (35, '',                           'Хозяйственные товары',        None,                     None,                     None),
    (36, '',                           'Прочие расходы',              None,                     None,                     None),
    (37, '',                           'Документы на заведение',      'Юридические расходы',    None,                     None),
    (38, '',                           'Форс-мажор',                  None,                     None,                     None),
    (39, 'EBITDA',                     'Операционная прибыль',        None,                     '={c}10-{c}12-{c}18',     None),
    (40, 'EBITDA MARGIN',              '(% от выручки)',              None,                     '=IFERROR({c}39/{c}2,"")', None),
    (41, 'TAX',                        'Налоги',                      None,                     None,                     None),
    (42, '% OF REVENUE',               '(% от выручки)',              None,                     '=IFERROR({c}41/{c}2,"")', None),
    (43, 'NET PROFIT',                 'Чистая прибыль',              None,                     '={c}39-{c}41',           None),
    (44, 'NET MARGIN',                 '(% от выручки)',              None,                     '=IFERROR({c}43/{c}2,"")', None),
    (45, '',                           'Погашение долгов',            None,                     None,                     None),
    (46, '',                           'Инвестиции',                  None,                     None,                     None),
    (47, 'DIVIDENDS',                  'Выплаты дивидендов',          None,                     None,                     None),
    (48, '',                           'Свободные средства',          None,                     '={c}43-{c}45-{c}46-{c}47', None),
]

SHEET_IDS = {'ЗБ': 0, 'ОВИР': 189519852}

def sv(s): return {'userEnteredValue': {'stringValue': s}} if s else {'userEnteredValue': {}}
def fv(f): return {'userEnteredValue': {'formulaValue': f}}
def empty(): return {'userEnteredValue': {}}


def build_requests():
    reqs = []
    for sheet_name, sheet_id in SHEET_IDS.items():
        rows_data = []
        for row_num, eng, ru_zb, ru_ovir, formula_zb, formula_ovir in ROWS:
            ru = (ru_ovir if ru_ovir else ru_zb) if sheet_name == 'ОВИР' else ru_zb
            formula = (formula_ovir if formula_ovir else formula_zb) if sheet_name == 'ОВИР' else formula_zb

            if row_num == 1:
                cells = [sv(eng), sv(ru)] + [sv(m) for m in MONTHS_RU]
            else:
                cells = [sv(eng), sv(ru)]
                for m in range(1, 13):
                    col = mc(m)
                    if formula:
                        cells.append(fv(formula.replace('{c}', col)))
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
        print("✅ Структура ЗБ и ОВИР восстановлена (48 строк)")


if __name__ == '__main__':
    main()
