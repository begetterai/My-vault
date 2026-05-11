#!/usr/bin/env python3
"""
Создаёт новую Google Sheets таблицу с той же структурой, что и Main P&L.
Запуск: python3 scripts/create_pnl_sheet.py
Выводит ID созданной таблицы — нужно прописать в update_pnl.py.
"""
import json, os
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'romashka-drive.json')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

# Строки: (номер, русское название, формула или None)
# Формула использует {c} как плейсхолдер столбца
ROWS = [
    (1,  'Показатели',                       None),
    (2,  'Выручка (с)',                       None),
    (3,  'COGS (с)',                          '={c}4+{c}5+{c}6'),
    (4,  '  Закуп кухни (с)',                 None),
    (5,  '  Закуп бара (с)',                  None),
    (6,  '  Прочие расходы на произ-во (с)', '={c}7+{c}8'),
    (7,  '    Персоналка (с)',                None),
    (8,  '    Расходные материалы (с)',       None),
    (9,  'Валовая прибыль (с)',              '={c}2-{c}3'),
    (10, 'Маржинальность %',                 '=IFERROR({c}9/{c}2,"")'),
    (11, 'ФОТ общий (с)',                    '={c}13+{c}15'),
    (12, '  (% от выручки)',                 '=IFERROR({c}11/{c}2,"")'),
    (13, '  ФОТ производственный (с)',       None),
    (14, '    (% от общего ФОТ)',            '=IFERROR({c}13/{c}11,"")'),
    (15, '  ФОТ административный (с)',       None),
    (16, '    (% от общего ФОТ)',            '=IFERROR({c}15/{c}11,"")'),
    (17, 'ИТОГО OpEx (с)',                   '=SUM({c}18:{c}37)'),
    (18, 'Аренда (с)',                        None),
    (19, '  (% от выручки)',                 '=IFERROR({c}18/{c}2,"")'),
    (20, 'Коммунальные (с)',                 '={c}22+{c}23+{c}24'),
    (21, '  (% от выручки)',                 '=IFERROR({c}20/{c}2,"")'),
    (22, '  Электроэнергия (с)',              None),
    (23, '  Водоснабжение (с)',               None),
    (24, '  Вывоз мусора (с)',                None),
    (25, 'Расходы на заведение (с)',          None),
    (26, 'Расходы на оборудование (с)',       None),
    (27, 'Расходы на инвентарь (с)',          None),
    (28, 'Упаковка (с)',                      None),
    (29, 'Логистика (с)',                     None),
    (30, 'Агрегатор (с)',                     None),
    (31, 'Маркетинг (с)',                     None),
    (32, 'CRM / Poster (с)',                  None),
    (33, 'Интернет (с)',                      None),
    (34, 'Хозяйственные товары (с)',          None),
    (35, 'Прочие расходы (с)',                None),
    (36, 'Документы на заведение (с)',        None),
    (37, 'Форс-мажор (с)',                    None),
    (38, 'EBITDA (с)',                        '={c}9-{c}11-{c}17'),
    (39, 'EBITDA %',                          '=IFERROR({c}38/{c}2,"")'),
    (40, 'Налоги (с)',                        None),
    (41, '  (% от выручки)',                  '=IFERROR({c}40/{c}2,"")'),
    (42, 'Чистая прибыль (с)',               '={c}38-{c}40'),
    (43, 'Чистая маржа %',                   '=IFERROR({c}42/{c}2,"")'),
    (44, 'Погашение долгов (с)',              None),
    (45, 'Инвестиции (с)',                    None),
    (46, 'Дивиденды (с)',                     None),
    (47, 'Свободные средства (с)',            '={c}42-{c}44-{c}45-{c}46'),
]

MONTHS = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']
SHEETS = ['ЗБ', 'ОВИР']


def col_letter(month_idx):
    """1→B, 2→C, ..., 12→M"""
    return chr(ord('A') + month_idx)


def build_row_data(row_num, label, formula_tpl):
    """Строит запись для одной строки: метка + значения/формулы по 12 месяцам."""
    cells = []

    # Col A — метка
    cells.append({'userEnteredValue': {'stringValue': label}})

    # Col B–M — месяцы
    for m in range(1, 13):
        col = col_letter(m)
        if formula_tpl:
            f = formula_tpl.replace('{c}', col)
            cells.append({'userEnteredValue': {'formulaValue': f}})
        else:
            cells.append({'userEnteredValue': {}})  # пустая ячейка для ручного ввода

    return cells


def make_sheet_data(sheet_name):
    """Возвращает список updateCells requests для одного листа."""
    requests = []
    row_data = []

    # Заголовок: строка 1
    header = [{'userEnteredValue': {'stringValue': 'Показатели'}}]
    for m in MONTHS:
        header.append({'userEnteredValue': {'stringValue': m}})

    row_data.append({'values': header})

    # Данные: строки 2–47
    for row_num, label, formula_tpl in ROWS[1:]:
        row_data.append({'values': build_row_data(row_num, label, formula_tpl)})

    return row_data


def main():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    session = AuthorizedSession(creds)

    # 1. Создаём таблицу с двумя листами
    body = {
        'properties': {'title': 'PNL 2026 auto', 'locale': 'ru_RU'},
        'sheets': [
            {'properties': {'title': 'ЗБ',   'index': 0}},
            {'properties': {'title': 'ОВИР', 'index': 1}},
        ]
    }
    r = session.post('https://sheets.googleapis.com/v4/spreadsheets',
                     headers={'Content-Type': 'application/json'},
                     data=json.dumps(body), timeout=30)
    ss = r.json()
    ss_id = ss['spreadsheetId']
    sheet_ids = {s['properties']['title']: s['properties']['sheetId']
                 for s in ss['sheets']}
    print(f"Создана таблица: {ss_id}")
    print(f"Sheet IDs: {sheet_ids}")

    # 2. Заполняем оба листа
    updates = []
    for sheet_name in SHEETS:
        sid = sheet_ids[sheet_name]
        row_data_list = make_sheet_data(sheet_name)
        updates.append({
            'updateCells': {
                'range': {
                    'sheetId': sid,
                    'startRowIndex': 0,
                    'startColumnIndex': 0,
                },
                'rows': [{'values': rd['values']} for rd in row_data_list],
                'fields': 'userEnteredValue'
            }
        })

    # Ширина колонок
    for sheet_name in SHEETS:
        sid = sheet_ids[sheet_name]
        updates.append({
            'updateDimensionProperties': {
                'range': {'sheetId': sid, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 1},
                'properties': {'pixelSize': 280},
                'fields': 'pixelSize'
            }
        })
        for i in range(1, 13):
            updates.append({
                'updateDimensionProperties': {
                    'range': {'sheetId': sid, 'dimension': 'COLUMNS', 'startIndex': i, 'endIndex': i+1},
                    'properties': {'pixelSize': 110},
                    'fields': 'pixelSize'
                }
            })

    r2 = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
        headers={'Content-Type': 'application/json'},
        data=json.dumps({'requests': updates}), timeout=60)
    print(f"Структура: {r2.status_code}")

    print(f"\nНовый SS ID: {ss_id}")
    print(f"Пропиши в update_pnl.py: PNL_SS_ID = '{ss_id}'")


if __name__ == '__main__':
    main()
