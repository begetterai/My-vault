#!/usr/bin/env python3
"""Разметка реестра: колонки «ВВОД» и «ОТЧЁТ».

Правило системы: отчёт рождается не из документа, а из ввода. Поэтому по каждому
документу заранее решаем — порождает он данные или его только читают, и в какой
отчёт эти данные идут. Проставляется ДО того, как документ написан.

ВВОД:    Форма · Бот · Sheets · Poster · Подпись · —
ОТЧЁТ:   День · Неделя · Месяц · —
"""
import sys
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session

REG = '1TzB9gjpJvj_ziBwKdVuOhfKezMVsdXzeLxQMJWz-cQk'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'

IN_VALUES = ['Форма', 'Бот', 'Sheets', 'Poster', 'Подпись', '—']
OUT_VALUES = ['День', 'Неделя', 'Месяц', '—']

# код → (ввод, отчёт)
MAP = {
    # 00 — управление системой: читают, кроме листа ознакомления
    '00-FRM-01': ('—', '—'), '00-FRM-02': ('—', '—'), '00-FRM-03': ('—', '—'),
    '00-FRM-04': ('Подпись', 'Месяц'),          # кто с чем ознакомлен
    '00-POL-01': ('—', '—'), '00-REF-01': ('Sheets', 'Месяц'),
    '00-REF-02': ('—', '—'), '00-REF-03': ('—', '—'),

    # 01 — организация и роли: читают; KPI считается из отчётов
    '01-DK-01': ('Подпись', '—'), '01-DK-02': ('Подпись', '—'),
    '01-DK-03': ('Подпись', '—'), '01-DK-04': ('Подпись', '—'),
    '01-DK-05': ('Подпись', '—'), '01-DK-06': ('Подпись', '—'),
    '01-DK-07': ('Подпись', '—'),
    '01-POL-01': ('—', 'Месяц'),                # премия считается по отчётам
    '01-REF-01': ('—', '—'), '01-REF-02': ('—', '—'),
    '01-SOP-01': ('Форма', 'Неделя'),           # протокол планёрки — форма

    # 02 — персонал
    '02-CL-01': ('Форма', 'Месяц'),
    '02-FRM-01': ('Подпись', '—'), '02-FRM-02': ('Подпись', '—'),
    '02-POL-01': ('—', '—'), '02-POL-02': ('—', '—'), '02-POL-03': ('—', '—'),
    '02-REF-01': ('—', '—'),
    '02-REF-02': ('Sheets', 'Месяц'),           # сроки медкнижек — контроль
    '02-SOP-01': ('—', 'Месяц'), '02-SOP-02': ('Форма', 'Месяц'),
    '02-SOP-03': ('Форма', 'Месяц'), '02-SOP-04': ('Форма', 'Месяц'),
    '02-SOP-05': ('Форма', 'Месяц'),
    '02-SOP-06': ('Sheets', 'Месяц'),           # график и табель
    '02-SOP-07': ('Подпись', 'Месяц'),

    # 03 — смена и обслуживание
    '03-CL-01': ('Форма', 'День'), '03-CL-02': ('Форма', 'День'),
    '03-LOG-01': ('Бот', 'День'),
    '03-POL-01': ('—', '—'),
    '03-SOP-01': ('Форма', 'День'),
    '03-SOP-02': ('—', '—'),
    '03-SOP-03': ('Poster', 'День'),            # касса и инкассация — из Poster
    '03-SOP-04': ('Бот', 'Неделя'),             # жалоба гостя
    '03-SOP-05': ('Poster', 'Неделя'),

    # 04 — кухня и производство
    '04-CL-01': ('Форма', 'День'),
    '04-DK-01': ('Подпись', '—'),
    '04-INS-01': ('—', '—'),
    '04-LOG-01': ('Форма', 'День'),             # температуры
    '04-POL-01': ('—', '—'), '04-POL-02': ('—', '—'), '04-POL-03': ('—', '—'),
    '04-POL-04': ('—', 'Месяц'),                # HACCP — сводка по ККТ
    '04-POL-05': ('—', '—'),
    '04-REF-01': ('—', '—'), '04-REF-02': ('—', 'Неделя'),
    '04-SOP-01': ('Форма', 'День'),             # план/факт заготовок
    '04-SOP-02': ('Форма', 'Неделя'), '04-SOP-03': ('Форма', 'Неделя'),
    '04-SOP-04': ('Форма', 'День'), '04-SOP-05': ('Форма', 'Неделя'),
    '04-TTK-*': ('—', '—'),

    # 05 — товародвижение и склад
    '05-EDU-01': ('—', '—'), '05-EDU-02': ('—', '—'),
    '05-FRM-01': ('Форма', 'Неделя'),           # акт списания
    '05-FRM-02': ('Форма', 'Месяц'),            # инвентаризация
    '05-REF-01': ('Sheets', '—'),
    '05-SOP-01': ('Форма', 'Неделя'),           # приём поставки
    '05-SOP-02': ('Бот', 'Неделя'),             # закупка на базаре
    '05-SOP-03': ('Форма', 'Месяц'),
    '05-SOP-04': ('Форма', 'Неделя'),
    '05-SOP-05': ('Форма', 'Месяц'),

    # 06 — деньги: данные уже в Poster, вводить нечего
    '06-REF-01': ('—', '—'), '06-REF-02': ('—', '—'), '06-REF-03': ('—', '—'),
    '06-REF-04': ('—', '—'),
    '06-REF-05': ('Sheets', 'Месяц'),           # реестр долгов
    '06-SOP-01': ('Poster', 'Месяц'),
    '06-SOP-02': ('Poster', 'День'),
    '06-SOP-03': ('Poster', 'Месяц'),

    # 07 — качество и контроль
    '07-CL-01': ('Форма', 'Неделя'),
    '07-FRM-01': ('Форма', 'Месяц'),
    '07-LOG-01': ('Бот', 'Неделя'),
    '07-SOP-01': ('Форма', 'Неделя'),
    '07-SOP-02': ('Бот', 'Неделя'),

    # 08 — безопасность
    '08-INS-01': ('—', '—'), '08-INS-02': ('—', '—'),
    '08-LOG-01': ('Подпись', 'Месяц'),          # инструктажи — подпись обязательна
    '08-SOP-01': ('Бот', 'Неделя'),
    '08-SOP-02': ('Бот', 'Неделя'),

    # 09 — оборудование
    '09-INS-*': ('—', '—'),
    '09-LOG-01': ('Бот', 'Неделя'),             # поломки и ремонты
    '09-POL-01': ('—', 'Месяц'),                # экономия электричества
    '09-REF-01': ('Sheets', 'Месяц'),           # реестр оборудования = база амортизации
    '09-SOP-01': ('Форма', 'Неделя'),

    # 10 — развитие сети
    '10-CL-01': ('Форма', '—'), '10-REF-01': ('—', '—'),
    '10-REF-02': ('Sheets', '—'), '10-SOP-01': ('—', '—'),
}

BLACK = {'red': 0, 'green': 0, 'blue': 0}
LINE = {'style': 'SOLID', 'width': 1, 'color': BLACK}


def main():
    s = session()
    meta = s.get(B + REG, params={'fields': 'sheets(properties)'}).json()
    sh = meta['sheets'][0]['properties']
    sid, cols = sh['sheetId'], sh['gridProperties']['columnCount']

    if cols < 17:
        s.post(B + REG + ':batchUpdate', json={'requests': [{'appendDimension': {
            'sheetId': sid, 'dimension': 'COLUMNS', 'length': 17 - cols}}]}).raise_for_status()

    v = s.get(B + REG + '/values/A1:Q200').json().get('values', [])
    rows = [(i, r[0]) for i, r in enumerate(v[1:], 2) if r and r[0]]

    data = [{'range': 'P1', 'values': [['ВВОД']]},
            {'range': 'Q1', 'values': [['ОТЧЁТ']]}]
    miss = []
    for i, code in rows:
        m = MAP.get(code)
        if not m:
            miss.append(code)
            continue
        data.append({'range': f'P{i}:Q{i}', 'values': [list(m)]})
    s.post(B + REG + '/values:batchUpdate',
           json={'valueInputOption': 'USER_ENTERED', 'data': data}).raise_for_status()

    last = rows[-1][0]
    req = [
        # выпадающие списки — чтобы вручную не написали лишнего
        {'setDataValidation': {
            'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': last,
                      'startColumnIndex': 15, 'endColumnIndex': 16},
            'rule': {'condition': {'type': 'ONE_OF_LIST',
                     'values': [{'userEnteredValue': x} for x in IN_VALUES]},
                     'strict': True, 'showCustomUi': True}}},
        {'setDataValidation': {
            'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': last,
                      'startColumnIndex': 16, 'endColumnIndex': 17},
            'rule': {'condition': {'type': 'ONE_OF_LIST',
                     'values': [{'userEnteredValue': x} for x in OUT_VALUES]},
                     'strict': True, 'showCustomUi': True}}},
        # вид как у всей таблицы
        {'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': last,
                      'startColumnIndex': 15, 'endColumnIndex': 17},
            'cell': {'userEnteredFormat': {
                'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE',
                'textFormat': {'fontFamily': 'Times New Roman', 'fontSize': 13}}},
            'fields': 'userEnteredFormat(horizontalAlignment,verticalAlignment,'
                      'textFormat.fontFamily,textFormat.fontSize)'}},
        {'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1,
                      'startColumnIndex': 15, 'endColumnIndex': 17},
            'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
            'fields': 'userEnteredFormat.textFormat.bold'}},
        {'updateBorders': {
            'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1,
                      'startColumnIndex': 15, 'endColumnIndex': 17},
            'top': LINE, 'bottom': LINE}},
        {'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                      'startIndex': 15, 'endIndex': 17},
            'properties': {'pixelSize': 96}, 'fields': 'pixelSize'}},
    ]
    s.post(B + REG + ':batchUpdate', json={'requests': req}).raise_for_status()

    print(f'размечено строк: {len(data) - 2} из {len(rows)}')
    if miss:
        print('НЕ РАЗМЕЧЕНЫ (нет в MAP):', miss)

    # сводка — сколько чего
    from collections import Counter
    ci = Counter(MAP[c][0] for _, c in rows if c in MAP)
    co = Counter(MAP[c][1] for _, c in rows if c in MAP)
    print('\nввод: ', dict(ci))
    print('отчёт:', dict(co))
    print('\nдокументов, порождающих данные:',
          sum(n for k, n in ci.items() if k != '—'))
    print('https://docs.google.com/spreadsheets/d/' + REG)


if __name__ == '__main__':
    main()
