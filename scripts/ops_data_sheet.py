#!/usr/bin/env python3
"""Склад операционных данных.

Заполняет бот (ops_checklist.py). Таблица нужна человеку для ЧТЕНИЯ,
поэтому она сводная, а не в 34 колонки галочек.

Листы:
  Открытие смены — одна строка на смену: кто, сколько выполнено, что не сделано
  Невыполнено    — по одной строке на каждый проваленный пункт (для аналитики:
                   какой пункт валят чаще всего)
  Пункты         — справочник 34 пунктов, тянется из документа 03-CL-01
  Команда        — кто может заполнять через бота; Азиз правит сам

Скрипт идемпотентный.
"""
import sys
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session, find
import checklists as CL

ROOT = '1cSLEkOXikhTv0g6lPxZ31xJca1Yu-q43'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'
NAME = 'ОПЕРАЦИОННЫЕ ДАННЫЕ (заполняет смена)'
FOLDER = '00.2 Данные — заполняет смена'

BLACK = {'red': 0, 'green': 0, 'blue': 0}
WHITE = {'red': 1, 'green': 1, 'blue': 1}
LINE = {'style': 'SOLID', 'width': 1, 'color': BLACK}

TABS = {
    'Открытие смены': (
        ['Дата', 'Точка', 'Старший смены', 'Заполнил в', 'Открыли в',
         'Выполнено', 'Всего', '%', 'Не выполнены пункты', 'Комментарий',
         'Замеры', 'Фото', 'Минут на заполнение',
         'Проверил управляющий', 'Когда проверил', 'Расхождение при проверке'],
        [96, 74, 140, 96, 90, 96, 70, 62, 170, 320, 280, 150, 110,
         170, 130, 320]),
    'Закрытие смены': (
        ['Дата', 'Точка', 'Старший смены', 'Заполнил в', 'Закрыли в',
         'Выполнено', 'Всего', '%', 'Не выполнены пункты', 'Комментарий',
         'Замеры', 'Фото', 'Минут на заполнение',
         'Проверил управляющий', 'Когда проверил', 'Расхождение при проверке'],
        [96, 74, 140, 96, 90, 96, 70, 62, 170, 320, 280, 150, 110,
         170, 130, 320]),
    'Невыполнено': (
        ['Дата', 'Точка', 'Старший смены', 'Документ', '№', 'Блок', 'Пункт'],
        [96, 74, 140, 150, 50, 190, 420]),
    'Идеи и задачи': (
        ['Дата', 'Кто', 'Точка', 'Откуда', 'Текст', 'Статус', 'Решение'],
        [96, 140, 74, 200, 460, 110, 320]),
    'Пункты': (['Документ', '№', 'Блок', 'Пункт'], [150, 50, 190, 460]),
    'Команда': (['chat_id', 'Имя', 'Точка', 'Роль', 'Активен'],
                [130, 150, 90, 170, 90]),
}

EXAMPLE = 'Пример — как это выглядит'

# Лист с примерами. Реальные данные не трогает, отчёт его не читает.
EX_ROWS = [
    ['ПРИМЕР. Этот лист — только образец. Реальные данные пишет бот '
     'на листы «Открытие смены» и «Невыполнено».'],
    [],
    ['1. Как заполняет старший смены — диалог с ботом'],
    [],
    ['Старший смены пишет:', 'открытие'],
    ['Бот отвечает:', 'Открытие смены · ЗБ · 17.08.2026'],
    ['', 'Блок 1 из 6 — Персонал'],
    ['', '1. Смена вышла в полном составе, опозданий нет'],
    ['', '2. Форма чистая, целая, по стандарту; бейдж на месте'],
    ['', '3. Волосы убраны, головной убор надет, ногти короткие'],
    ['', '…'],
    ['', 'Ответь «ок», если всё выполнено.'],
    ['', 'Если нет — номера невыполненных через пробел: 2 5'],
    ['Старший смены:', 'ок'],
    ['Бот:', 'Блок 2 из 6 — Помещение и зал …'],
    ['Старший смены:', '2 4'],
    ['', '(так шесть блоков — меньше минуты)'],
    ['Бот:', 'Во сколько открылись?'],
    ['Старший смены:', '10:05'],
    ['Бот:', 'Не выполнено: 8. Вывеска и подсветка; 10. Туалет…'],
    ['', 'Напиши коротко, почему.'],
    ['Старший смены:', 'Одна лампа не горит, вызвал электрика'],
    ['Бот:', '✅ Записал. 31 из 34 (91%). Хорошей смены.'],
    [],
    ['2. Что попадает на лист «Открытие смены»'],
    [],
    ['Дата', 'Точка', 'Старший смены', 'Заполнил в', 'Открыли в',
     'Выполнено', 'Всего', '%', 'Не выполнены пункты', 'Комментарий'],
    ['17.08.2026', 'ЗБ', 'Владимир', '9:12', '10:05', 31, 34, '91%',
     '8, 10, 15', 'Одна лампа не горит, вызвал электрика'],
    ['17.08.2026', 'ОВИР', 'Дилчу', '9:30', '10:00', 34, 34, '100%', '—', ''],
    ['16.08.2026', 'ЗБ', 'Владимир', '9:05', '10:00', 34, 34, '100%', '—', ''],
    ['16.08.2026', 'ОВИР', 'Дилчу', '9:40', '10:20', 29, 34, '85%',
     '1, 12, 19, 26, 34', 'Один повар не вышел, открылись позже'],
    [],
    ['3. Что попадает на лист «Невыполнено» — расшифровка'],
    [],
    ['Дата', 'Точка', 'Старший смены', '№', 'Блок', 'Пункт'],
    ['17.08.2026', 'ЗБ', 'Владимир', 8, '2. Помещение и зал',
     'Вывеска и подсветка работают'],
    ['17.08.2026', 'ЗБ', 'Владимир', 10, '2. Помещение и зал',
     'Туалет: чисто, есть мыло, бумага, сушилка работает'],
    ['17.08.2026', 'ЗБ', 'Владимир', 15, '3. Оборудование',
     'Морозильники: температура −18 °C и ниже — записать в журнал'],
    [],
    ['4. Что приходит Азизу в телеграм сразу после заполнения'],
    [],
    ['', '🧾 ЗБ · открытие 17.08.2026 · Владимир'],
    ['', '31/34 (91%)'],
    ['', '✗ 8. Вывеска и подсветка работают'],
    ['', '✗ 10. Туалет: чисто, есть мыло, бумага, сушилка работает'],
    ['', '✗ 15. Морозильники: температура −18 °C и ниже'],
    ['', '💬 Одна лампа не горит, вызвал электрика'],
    [],
    ['5. Зачем нужен лист «Невыполнено»'],
    [],
    ['', 'Через месяц по нему видно, какой пункт валят чаще всего. '
         'Если «Туалет» проваливается 12 раз за месяц — это не забывчивость, '
         'а сломанный процесс уборки. Проценты этого не показывают.'],
]
EX_BOLD = {0, 2, 24, 26, 33, 35, 40, 48}      # строки-заголовки, 0-based


def items():
    """Справочник пунктов обоих чек-листов."""
    out = []
    for kind in ('open', 'close'):
        title = CL.KINDS[kind]['title']
        for n, b, t in CL.flat(kind):
            out.append((title, n, b, t))
    return out


def ensure_folder(s, name, parent):
    fid = find(s, name, parent)
    if fid:
        return fid, 'уже была'
    r = s.post('https://www.googleapis.com/drive/v3/files',
               params={'supportsAllDrives': 'true', 'fields': 'id'},
               json={'name': name, 'parents': [parent],
                     'mimeType': 'application/vnd.google-apps.folder'}, timeout=60)
    r.raise_for_status()
    return r.json()['id'], 'создана'


def ensure_file(s, name, parent):
    fid = find(s, name, parent)
    if fid:
        return fid, 'уже был'
    r = s.post('https://www.googleapis.com/drive/v3/files',
               params={'supportsAllDrives': 'true', 'fields': 'id'},
               json={'name': name, 'parents': [parent],
                     'mimeType': 'application/vnd.google-apps.spreadsheet'}, timeout=60)
    r.raise_for_status()
    return r.json()['id'], 'создан'


def example(s, fid):
    """Лист с примерами: диалог с ботом, как ложатся данные, что видит Азиз."""
    meta = s.get(B + fid, params={'fields': 'sheets.properties'}).json()
    have = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}
    if EXAMPLE not in have:
        s.post(B + fid + ':batchUpdate', json={'requests': [{'addSheet': {
            'properties': {'title': EXAMPLE,
                           'gridProperties': {'rowCount': 80, 'columnCount': 10}}}}]}
        ).raise_for_status()
        meta = s.get(B + fid, params={'fields': 'sheets.properties'}).json()
        have = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}
    sid = have[EXAMPLE]['sheetId']

    rows = [r + [''] * (10 - len(r)) for r in EX_ROWS]
    s.put(B + fid + '/values/' + EXAMPLE.replace(' ', '%20') + '!A1',
          params={'valueInputOption': 'RAW'}, json={'values': rows}).raise_for_status()

    # где таблица (много заполненных ячеек), а где текст — считаем из содержимого,
    # чтобы номера строк не разъезжались при правках
    table = {i for i, r in enumerate(EX_ROWS) if len([c for c in r if c != '']) >= 5}
    head = {i for i, r in enumerate(EX_ROWS)
            if r and str(r[0]).startswith(('ПРИМЕР', '1.', '2.', '3.', '4.', '5.'))
            and len([c for c in r if c != '']) == 1}

    req = [
        # текст перетекает вправо через пустые ячейки — иначе всё обрезается
        {'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 80,
                      'startColumnIndex': 0, 'endColumnIndex': 10},
            'cell': {'userEnteredFormat': {
                'backgroundColor': WHITE, 'verticalAlignment': 'MIDDLE',
                'wrapStrategy': 'OVERFLOW_CELL', 'horizontalAlignment': 'LEFT',
                'textFormat': {'fontFamily': 'Times New Roman', 'fontSize': 13,
                               'bold': False, 'foregroundColor': BLACK}}},
            'fields': 'userEnteredFormat(backgroundColor,verticalAlignment,wrapStrategy,'
                      'horizontalAlignment,textFormat)'}},
        {'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                      'startIndex': 0, 'endIndex': 1},
            'properties': {'pixelSize': 196}, 'fields': 'pixelSize'}},
        {'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                      'startIndex': 1, 'endIndex': 10},
            'properties': {'pixelSize': 118}, 'fields': 'pixelSize'}},
        {'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'ROWS',
                      'startIndex': 0, 'endIndex': 80},
            'properties': {'pixelSize': 26}, 'fields': 'pixelSize'}},
    ]
    for i in head:
        req.append({'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': i, 'endRowIndex': i + 1,
                      'startColumnIndex': 0, 'endColumnIndex': 10},
            'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
            'fields': 'userEnteredFormat.textFormat.bold'}})
    for i in sorted(table):
        # в таблицах перетекать некуда — обрезаем, кроме последней колонки
        req.append({'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': i, 'endRowIndex': i + 1,
                      'startColumnIndex': 0, 'endColumnIndex': 9},
            'cell': {'userEnteredFormat': {'wrapStrategy': 'CLIP'}},
            'fields': 'userEnteredFormat.wrapStrategy'}})
        # строка-шапка таблицы: жирная, с рамкой
        if EX_ROWS[i] and EX_ROWS[i][0] == 'Дата':
            req += [
                {'repeatCell': {
                    'range': {'sheetId': sid, 'startRowIndex': i, 'endRowIndex': i + 1,
                              'startColumnIndex': 0, 'endColumnIndex': 10},
                    'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
                    'fields': 'userEnteredFormat.textFormat.bold'}},
                {'updateBorders': {
                    'range': {'sheetId': sid, 'startRowIndex': i, 'endRowIndex': i + 1,
                              'startColumnIndex': 0, 'endColumnIndex': 10},
                    'top': LINE, 'bottom': LINE}},
            ]
    s.post(B + fid + ':batchUpdate', json={'requests': req}).raise_for_status()


def polish(s, fid):
    """Финальный проход по форматам — ПОСЛЕ записи значений.

    Раньше форматы шли одним батчем со структурой, и часть из них не доезжала:
    дата оставалась числом 46251, процент — 0,9118, данные жирными.
    """
    meta = s.get(B + fid, params={'fields': 'sheets.properties'}).json()
    p = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}
    req = []
    for t, pr in p.items():
        if t not in TABS:
            continue
        sid, last = pr['sheetId'], pr['gridProperties']['rowCount']
        ncol = len(TABS[t][0])
        req += [
            {'repeatCell': {
                'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': last,
                          'startColumnIndex': 0, 'endColumnIndex': ncol},
                'cell': {'userEnteredFormat': {'textFormat': {'bold': False}}},
                'fields': 'userEnteredFormat.textFormat.bold'}},
            {'repeatCell': {
                'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1,
                          'startColumnIndex': 0, 'endColumnIndex': ncol},
                'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
                'fields': 'userEnteredFormat.textFormat.bold'}},
        ]
        if t in ('Открытие смены', 'Закрытие смены', 'Невыполнено'):
            req.append({'repeatCell': {
                'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': last,
                          'startColumnIndex': 0, 'endColumnIndex': 1},
                'cell': {'userEnteredFormat': {'numberFormat': {
                    'type': 'DATE', 'pattern': 'dd.mm.yyyy'}}},
                'fields': 'userEnteredFormat.numberFormat'}})
        if t in ('Открытие смены', 'Закрытие смены'):
            req.append({'repeatCell': {
                'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': last,
                          'startColumnIndex': 7, 'endColumnIndex': 8},
                'cell': {'userEnteredFormat': {'numberFormat': {
                    'type': 'PERCENT', 'pattern': '0%'}}},
                'fields': 'userEnteredFormat.numberFormat'}})
    if req:
        s.post(B + fid + ':batchUpdate', json={'requests': req}).raise_for_status()


def main():
    s = session()
    folder, fact = ensure_folder(s, FOLDER, ROOT)
    fid, fileact = ensure_file(s, NAME, folder)
    print(f'папка — {fact}; таблица — {fileact}')

    meta = s.get(B + fid, params={'fields': 'sheets.properties'}).json()
    have = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}

    # добавляем недостающие листы
    add = [{'addSheet': {'properties': {
        'title': t, 'gridProperties': {'rowCount': 1000, 'columnCount': len(h),
                                       'frozenRowCount': 1}}}}
        for t, (h, _) in TABS.items() if t not in have]
    if add:
        s.post(B + fid + ':batchUpdate', json={'requests': add}).raise_for_status()
        meta = s.get(B + fid, params={'fields': 'sheets.properties'}).json()
        have = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}

    # если колонок в листе меньше, чем нужно — сначала добавим, иначе 400
    grow = [{'appendDimension': {'sheetId': have[t]['sheetId'], 'dimension': 'COLUMNS',
                                 'length': len(h) - have[t]['gridProperties']['columnCount']}}
            for t, (h, _) in TABS.items()
            if have[t]['gridProperties']['columnCount'] < len(h)]
    if grow:
        s.post(B + fid + ':batchUpdate', json={'requests': grow}).raise_for_status()
        meta = s.get(B + fid, params={'fields': 'sheets.properties'}).json()
        have = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}

    req = []
    for t, (head, widths) in TABS.items():
        p = have[t]
        sid, ncol = p['sheetId'], len(head)
        # старая раскладка на 40 колонок галочек — вычищаем всё лишнее
        req += [
            {'updateSheetProperties': {
                'properties': {'sheetId': sid,
                               'gridProperties': {'frozenRowCount': 1, 'frozenColumnCount': 0}},
                'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}},
            {'setDataValidation': {'range': {'sheetId': sid, 'startRowIndex': 0,
                                             'endRowIndex': p['gridProperties']['rowCount'],
                                             'startColumnIndex': 0,
                                             'endColumnIndex': p['gridProperties']['columnCount']}}},
            {'repeatCell': {
                'range': {'sheetId': sid, 'startRowIndex': 0,
                          'endRowIndex': p['gridProperties']['rowCount'],
                          'startColumnIndex': 0,
                          'endColumnIndex': p['gridProperties']['columnCount']},
                'cell': {'userEnteredFormat': {
                    'backgroundColor': WHITE, 'verticalAlignment': 'MIDDLE',
                    'wrapStrategy': 'WRAP', 'horizontalAlignment': 'LEFT',
                    'textRotation': {'angle': 0},
                    'textFormat': {'fontFamily': 'Times New Roman', 'fontSize': 13,
                                   'bold': False, 'foregroundColor': BLACK}}},
                'fields': 'userEnteredFormat(backgroundColor,verticalAlignment,wrapStrategy,'
                          'horizontalAlignment,textRotation,textFormat)'}},
            # шапка
            {'repeatCell': {
                'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1,
                          'startColumnIndex': 0, 'endColumnIndex': ncol},
                'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
                'fields': 'userEnteredFormat.textFormat.bold'}},
            {'updateBorders': {
                'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1,
                          'startColumnIndex': 0, 'endColumnIndex': ncol},
                'top': LINE, 'bottom': LINE}},
            {'updateDimensionProperties': {
                'range': {'sheetId': sid, 'dimension': 'ROWS',
                          'startIndex': 0, 'endIndex': 1000},
                'properties': {'pixelSize': 30}, 'fields': 'pixelSize'}},
        ]
        for j, w in enumerate(widths):
            req.append({'updateDimensionProperties': {
                'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                          'startIndex': j, 'endIndex': j + 1},
                'properties': {'pixelSize': w}, 'fields': 'pixelSize'}})
        # лишние колонки от старой раскладки — отдельным проходом ниже,
        # иначе удаление сдвигает диапазоны форматов в этом же батче

    # дата — как дата, на обоих листах с датой
    for t in ('Открытие смены', 'Невыполнено'):
        req.append({'repeatCell': {
            'range': {'sheetId': have[t]['sheetId'], 'startRowIndex': 1,
                      'endRowIndex': 1000, 'startColumnIndex': 0, 'endColumnIndex': 1},
            'cell': {'userEnteredFormat': {'numberFormat': {
                'type': 'DATE', 'pattern': 'dd.mm.yyyy'}}},
            'fields': 'userEnteredFormat.numberFormat'}})
    # числа по центру, процент — процентом, а не 0,9118
    sid_o = have['Открытие смены']['sheetId']
    req += [
        {'repeatCell': {
            'range': {'sheetId': sid_o, 'startRowIndex': 1, 'endRowIndex': 1000,
                      'startColumnIndex': 5, 'endColumnIndex': 8},
            'cell': {'userEnteredFormat': {'horizontalAlignment': 'CENTER'}},
            'fields': 'userEnteredFormat.horizontalAlignment'}},
        {'repeatCell': {
            'range': {'sheetId': sid_o, 'startRowIndex': 1, 'endRowIndex': 1000,
                      'startColumnIndex': 7, 'endColumnIndex': 8},
            'cell': {'userEnteredFormat': {'numberFormat': {
                'type': 'PERCENT', 'pattern': '0%'}}},
            'fields': 'userEnteredFormat.numberFormat'}},
    ]
    s.post(B + fid + ':batchUpdate', json={'requests': req}).raise_for_status()

    # вторым проходом — обрезка лишних колонок от старой раскладки
    meta = s.get(B + fid, params={'fields': 'sheets.properties'}).json()
    cut = []
    for sh in meta['sheets']:
        p = sh['properties']
        want = TABS.get(p['title'])
        if want and p['gridProperties']['columnCount'] > len(want[0]):
            cut.append({'deleteDimension': {'range': {
                'sheetId': p['sheetId'], 'dimension': 'COLUMNS',
                'startIndex': len(want[0]),
                'endIndex': p['gridProperties']['columnCount']}}})
    if cut:
        s.post(B + fid + ':batchUpdate', json={'requests': cut}).raise_for_status()

    # шапки
    data = [{'range': f"'{t}'!A1", 'values': [h]} for t, (h, _) in TABS.items()]
    it = items()
    data.append({'range': "'Пункты'!A2", 'values': [list(x) for x in it]})
    s.post(B + fid + '/values:batchUpdate',
           json={'valueInputOption': 'RAW', 'data': data}).raise_for_status()

    # команда — заготовка, если лист пустой
    cur = s.get(B + fid + '/values/Команда!A2:E2').json().get('values', [])
    if not cur:
        s.put(B + fid + '/values/Команда!A2',
              params={'valueInputOption': 'RAW'},
              json={'values': [['', 'Владимир', 'ЗБ', 'Управляющий', 'да'],
                               ['', 'Дилчу', 'ОВИР', 'Управляющий', 'да']]}
              ).raise_for_status()

    example(s, fid)
    polish(s, fid)
    print('листы:', ' · '.join(TABS), '·', EXAMPLE)
    print(f'пунктов в справочнике: {len(it)}')
    print('https://docs.google.com/spreadsheets/d/' + fid)
    return fid


if __name__ == '__main__':
    main()
