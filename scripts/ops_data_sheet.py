#!/usr/bin/env python3
"""Склад операционных данных — лист, который заполняет смена с телефона.

Первая петля: 03-CL-01 «Открытие смены» → таблица → утренний отчёт в телеграм.

Пункты берутся НАПРЯМУЮ из doc_03_CL_01.BLOCKS — то есть форма и документ
всегда совпадают по составу. Изменил документ — перезапустил скрипт,
колонки обновились.

Скрипт идемпотентный.
"""
import sys, json, datetime
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session, find, DRIVE_ID
from doc_03_CL_01 import BLOCKS

ROOT = '1cSLEkOXikhTv0g6lPxZ31xJca1Yu-q43'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'
NAME = 'ОПЕРАЦИОННЫЕ ДАННЫЕ (заполняет смена)'
TAB = 'Открытие смены'
FOLDER = '00.2 Данные — заполняет смена'

BLACK = {'red': 0, 'green': 0, 'blue': 0}
WHITE = {'red': 1, 'green': 1, 'blue': 1}
LINE = {'style': 'SOLID', 'width': 1, 'color': BLACK}
FIXED = ['Дата', 'Точка', 'Старший смены', 'Время заполнения']
TAIL = ['Точка открыта в', 'Комментарий к невыполненным']


def items():
    """[(номер, блок, текст пункта)] — сквозная нумерация как в документе."""
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


def ensure_sheet(s, name, parent):
    fid = find(s, name, parent)
    if fid:
        return fid, 'уже был'
    r = s.post('https://www.googleapis.com/drive/v3/files',
               params={'supportsAllDrives': 'true', 'fields': 'id'},
               json={'name': name, 'parents': [parent],
                     'mimeType': 'application/vnd.google-apps.spreadsheet'}, timeout=60)
    r.raise_for_status()
    return r.json()['id'], 'создан'


def main():
    s = session()
    folder, fact = ensure_folder(s, FOLDER, ROOT)
    sid_file, sact = ensure_sheet(s, NAME, folder)
    print(f'папка — {fact}; таблица — {sact}')

    meta = s.get(B + sid_file, params={'fields': 'sheets.properties'}).json()
    tabs = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}

    req = []
    if TAB not in tabs:
        req.append({'addSheet': {'properties': {'title': TAB,
                    'gridProperties': {'rowCount': 2000, 'columnCount': 60,
                                       'frozenRowCount': 2, 'frozenColumnCount': 2}}}})
        s.post(B + sid_file + ':batchUpdate', json={'requests': req}).raise_for_status()
        meta = s.get(B + sid_file, params={'fields': 'sheets.properties'}).json()
        tabs = {sh['properties']['title']: sh['properties'] for sh in meta['sheets']}
    sid = tabs[TAB]['sheetId']

    # первый лист по умолчанию убираем, если он пустой и не наш
    for t, p in tabs.items():
        if t in ('Лист1', 'Sheet1') and t != TAB:
            s.post(B + sid_file + ':batchUpdate',
                   json={'requests': [{'deleteSheet': {'sheetId': p['sheetId']}}]})

    it = items()
    ncol = len(FIXED) + len(it) + len(TAIL)

    # две строки шапки: блок и текст пункта
    row1 = FIXED + [b for _, b, _ in it] + TAIL
    row2 = [''] * len(FIXED) + ['%d. %s' % (n, t) for n, _, t in it] + [''] * len(TAIL)
    s.put(B + sid_file + '/values/' + TAB + '!A1',
          params={'valueInputOption': 'RAW'},
          json={'values': [row1, row2]}).raise_for_status()

    c0 = len(FIXED)
    c1 = c0 + len(it)
    req = [
        # весь лист — стандарт оформления
        {'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 2000,
                      'startColumnIndex': 0, 'endColumnIndex': ncol},
            'cell': {'userEnteredFormat': {
                'backgroundColor': WHITE, 'verticalAlignment': 'MIDDLE',
                'wrapStrategy': 'WRAP',
                'textFormat': {'fontFamily': 'Times New Roman', 'fontSize': 13,
                               'foregroundColor': BLACK}}},
            'fields': 'userEnteredFormat(backgroundColor,verticalAlignment,wrapStrategy,'
                      'textFormat.fontFamily,textFormat.fontSize,textFormat.foregroundColor)'}},
        # шапка — жирная, вертикальная, с рамкой
        {'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 2,
                      'startColumnIndex': 0, 'endColumnIndex': ncol},
            'cell': {'userEnteredFormat': {
                'textFormat': {'bold': True},
                'horizontalAlignment': 'CENTER',
                'textRotation': {'angle': 90}}},
            'fields': 'userEnteredFormat(textFormat.bold,horizontalAlignment,textRotation)'}},
        # первые колонки — по-человечески, без поворота
        {'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 2,
                      'startColumnIndex': 0, 'endColumnIndex': len(FIXED)},
            'cell': {'userEnteredFormat': {
                'textRotation': {'angle': 0}, 'horizontalAlignment': 'LEFT'}},
            'fields': 'userEnteredFormat(textRotation,horizontalAlignment)'}},
        {'updateBorders': {
            'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 2,
                      'startColumnIndex': 0, 'endColumnIndex': ncol},
            'top': LINE, 'bottom': LINE}},
        # галочки по всем пунктам
        {'setDataValidation': {
            'range': {'sheetId': sid, 'startRowIndex': 2, 'endRowIndex': 2000,
                      'startColumnIndex': c0, 'endColumnIndex': c1},
            'rule': {'condition': {'type': 'BOOLEAN'}}}},
        # точка — выпадающий список
        {'setDataValidation': {
            'range': {'sheetId': sid, 'startRowIndex': 2, 'endRowIndex': 2000,
                      'startColumnIndex': 1, 'endColumnIndex': 2},
            'rule': {'condition': {'type': 'ONE_OF_LIST', 'values': [
                {'userEnteredValue': 'ЗБ'}, {'userEnteredValue': 'ОВИР'}]},
                'strict': True, 'showCustomUi': True}}},
        # дата — как дата
        {'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': 2, 'endRowIndex': 2000,
                      'startColumnIndex': 0, 'endColumnIndex': 1},
            'cell': {'userEnteredFormat': {'numberFormat': {
                'type': 'DATE', 'pattern': 'dd.mm.yyyy'}}},
            'fields': 'userEnteredFormat.numberFormat'}},
        # ширины: пункты узкие, первые колонки нормальные, хвост широкий
        {'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                      'startIndex': c0, 'endIndex': c1},
            'properties': {'pixelSize': 34}, 'fields': 'pixelSize'}},
        {'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                      'startIndex': 0, 'endIndex': len(FIXED)},
            'properties': {'pixelSize': 120}, 'fields': 'pixelSize'}},
        {'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                      'startIndex': c1, 'endIndex': ncol},
            'properties': {'pixelSize': 220}, 'fields': 'pixelSize'}},
        {'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'ROWS',
                      'startIndex': 0, 'endIndex': 2},
            'properties': {'pixelSize': 260}, 'fields': 'pixelSize'}},
        {'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'ROWS',
                      'startIndex': 2, 'endIndex': 2000},
            'properties': {'pixelSize': 30}, 'fields': 'pixelSize'}},
    ]
    s.post(B + sid_file + ':batchUpdate', json={'requests': req}).raise_for_status()

    # карта пунктов рядом — чтобы отчёт знал, что за колонкой
    m = [['№', 'Блок', 'Пункт']] + [[n, b, t] for n, b, t in it]
    if 'Пункты' not in tabs:
        s.post(B + sid_file + ':batchUpdate', json={'requests': [{'addSheet': {
            'properties': {'title': 'Пункты',
                           'gridProperties': {'rowCount': 200, 'columnCount': 4,
                                              'frozenRowCount': 1}}}}]}).raise_for_status()
    s.put(B + sid_file + '/values/Пункты!A1',
          params={'valueInputOption': 'RAW'}, json={'values': m}).raise_for_status()

    # кто может заполнять чек-лист через бота — Азиз правит этот лист сам
    if 'Команда' not in tabs:
        s.post(B + sid_file + ':batchUpdate', json={'requests': [{'addSheet': {
            'properties': {'title': 'Команда',
                           'gridProperties': {'rowCount': 100, 'columnCount': 6,
                                              'frozenRowCount': 1}}}}]}).raise_for_status()
        s.put(B + sid_file + '/values/Команда!A1',
              params={'valueInputOption': 'RAW'},
              json={'values': [
                  ['chat_id', 'Имя', 'Точка', 'Роль', 'Активен'],
                  ['', 'Владимир', 'ЗБ', 'Управляющий', 'да'],
                  ['', 'Дилчу', 'ОВИР', 'Управляющий', 'да'],
              ]}).raise_for_status()

    print(f'лист «{TAB}»: пунктов {len(it)}, колонок {ncol}')
    print('https://docs.google.com/spreadsheets/d/' + sid_file)
    return sid_file


if __name__ == '__main__':
    main()
