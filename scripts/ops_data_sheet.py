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
from doc_03_CL_01 import BLOCKS

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
         'Выполнено', 'Всего', '%', 'Не выполнены пункты', 'Комментарий'],
        [96, 74, 140, 96, 90, 96, 70, 62, 200, 460]),
    'Невыполнено': (
        ['Дата', 'Точка', 'Старший смены', '№', 'Блок', 'Пункт'],
        [96, 74, 140, 50, 190, 420]),
    'Пункты': (['№', 'Блок', 'Пункт'], [50, 190, 460]),
    'Команда': (['chat_id', 'Имя', 'Точка', 'Роль', 'Активен'],
                [130, 150, 90, 150, 90]),
}


def items():
    out, n = [], 0
    for block, rows in BLOCKS:
        for text, norm, photo in rows:
            n += 1
            out.append((n, block, text))
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
        if t in ('Открытие смены', 'Невыполнено'):
            req.append({'repeatCell': {
                'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': last,
                          'startColumnIndex': 0, 'endColumnIndex': 1},
                'cell': {'userEnteredFormat': {'numberFormat': {
                    'type': 'DATE', 'pattern': 'dd.mm.yyyy'}}},
                'fields': 'userEnteredFormat.numberFormat'}})
        if t == 'Открытие смены':
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
    data.append({'range': "'Пункты'!A2", 'values': [[n, b, x] for n, b, x in it]})
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

    polish(s, fid)
    print('листы:', ' · '.join(TABS))
    print(f'пунктов в справочнике: {len(it)}')
    print('https://docs.google.com/spreadsheets/d/' + fid)
    return fid


if __name__ == '__main__':
    main()
