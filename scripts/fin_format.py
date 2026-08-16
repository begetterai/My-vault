#!/usr/bin/env python3
"""Финмодель — приведение к стандарту оформления Азиза.

Times New Roman 13, белый фон без цветовой кодировки, чёрный текст.
Структура держится жирным и рамками (это не цвет), а не заливкой.
Минусы — в скобках чёрным, а не красным.
Ширина колонок и высота строк считаются под содержимое: ничего не обрезается.

Меняет ТОЛЬКО оформление. Значения и формулы не трогаются.
Скрипт идемпотентный — можно гонять повторно.
"""
import sys, math
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session
import pymupdf

# Liberation Serif метрически совпадает с Times New Roman — меряем ширину текста
# по-настоящему, а не на глаз. Берём жирное начертание: оно шире, значит запас.
_FONT = pymupdf.Font(fontfile='/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf')
PT2PX = 96 / 72


def text_px(t):
    return _FONT.text_length(str(t), SIZE) * PT2PX

SID = '10UksdwNaWYedzgExEnMBLwHFms9ybHmyZu-5ZECLw7s'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'

FONT, SIZE = 'Times New Roman', 13
WHITE = {'red': 1, 'green': 1, 'blue': 1}
BLACK = {'red': 0, 'green': 0, 'blue': 0}
LINE = {'style': 'SOLID', 'width': 1, 'color': BLACK}

PAD, WMIN, WMAX, SPACER = 22, 66, 400, 24
LINEH, VPAD, HMIN = 21, 8, 26
RED_NF = '#,##0;[RED]\\(#,##0\\)'
NEW_NF = '#,##0;(#,##0)'

# Поля ввода из оригинала (были жёлтой заливкой): лист → строки и колонки, 1-based
INPUT = {
    'ДАННЫЕ':    (13, 205, 2, 25),
    'Активы':    (132, 252, 2, 8),
    'Дивиденды': (109, 231, 3, 7),
    'Остатки':   (5, 19, 3, 3),
}

# Текст, который ссылался на цвета, которых больше нет
RECOLOR_TEXT = {
    'Инструкция!B2': 'Заполняете только ячейки в пунктирной рамке на листах ввода. '
                     'Все отчёты пересчитываются сами.',
    'Инструкция!B4': 'Листы, куда вы вписываете данные (ячейки в пунктирной рамке)',
    'ДАННЫЕ!B2':     'Одна строка = одна точка за один период. Расходы вписывайте со '
                     'знаком минус. История за 2023–2026 уже заполнена — строки выше '
                     'рамки, их не трогаем.',
    'Остатки!B2':    'Вписывайте в ячейки в пунктирной рамке. Отсюда строится Баланс. Сомони.',
}


def dark(bc):
    if not bc:
        return False
    r, g, b = bc.get('red', 1), bc.get('green', 1), bc.get('blue', 1)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.6


def post(s, req, label):
    for i in range(0, len(req), 300):
        r = s.post(B + SID + ':batchUpdate', json={'requests': req[i:i + 300]})
        r.raise_for_status()
    print('%-34s %4d правок' % (label, len(req)))


def rng(sid, r0, r1, c0, c1):
    return {'sheetId': sid, 'startRowIndex': r0, 'endRowIndex': r1,
            'startColumnIndex': c0, 'endColumnIndex': c1}


def scan(s):
    """Снимок до правок: шапки (тёмная заливка), красные форматы, границы данных."""
    r = s.get(B + SID, params={'fields':
        'sheets(properties,merges,data(rowData(values(effectiveValue,'
        'effectiveFormat(backgroundColor,numberFormat)))))'}).json()
    out = []
    for sh in r['sheets']:
        p = sh['properties']
        rows = sh.get('data', [{}])[0].get('rowData', [])
        heads, red, last_row, last_col = [], [], 0, 0
        for i, rd in enumerate(rows):
            vals = rd.get('values', [])
            filled = [j for j, c in enumerate(vals) if c.get('effectiveValue') is not None]
            if filled:
                last_row, last_col = i + 1, max(last_col, filled[-1] + 1)
            nd = 0
            for j, c in enumerate(vals):
                f = c.get('effectiveFormat', {})
                if dark(f.get('backgroundColor')):
                    nd += 1
                if (f.get('numberFormat') or {}).get('pattern') == RED_NF:
                    red.append((i, j))
            if nd >= 2:
                heads.append(i)
        out.append({'id': p['sheetId'], 'title': p['title'],
                    'rows': p['gridProperties']['rowCount'],
                    'cols': p['gridProperties']['columnCount'],
                    'merges': sh.get('merges', []),
                    'heads': heads, 'red': red,
                    'last_row': last_row, 'last_col': last_col})
    return out


def red_ranges(sh):
    """Красные числа — сжимаем в вертикальные полосы, чтобы не слать 5 000 запросов."""
    bycol = {}
    for i, j in sh['red']:
        bycol.setdefault(j, []).append(i)
    out = []
    for j, rows in bycol.items():
        rows.sort()
        a = p = rows[0]
        for i in rows[1:]:
            if i == p + 1:
                p = i
                continue
            out.append((a, p + 1, j))
            a = p = i
        out.append((a, p + 1, j))
    return out


def main():
    s = session()
    sheets = scan(s)

    # ── 1. шрифт, белый фон, чёрный текст, перенос, выравнивание ─────────────
    req = []
    for sh in sheets:
        req.append({'repeatCell': {
            'range': rng(sh['id'], 0, sh['rows'], 0, sh['cols']),
            'cell': {'userEnteredFormat': {
                'backgroundColor': WHITE, 'verticalAlignment': 'MIDDLE',
                'wrapStrategy': 'WRAP',
                'textFormat': {'fontFamily': FONT, 'fontSize': SIZE,
                               'foregroundColor': BLACK}}},
            'fields': 'userEnteredFormat(backgroundColor,verticalAlignment,'
                      'wrapStrategy,textFormat.fontFamily,textFormat.fontSize,'
                      'textFormat.foregroundColor)'}})
        for r0, r1, j in red_ranges(sh):
            req.append({'repeatCell': {
                'range': rng(sh['id'], r0, r1, j, j + 1),
                'cell': {'userEnteredFormat': {
                    'numberFormat': {'type': 'NUMBER', 'pattern': NEW_NF}}},
                'fields': 'userEnteredFormat.numberFormat'}})
        for i in sh['heads']:
            w = sh['last_col'] or sh['cols']
            req.append({'repeatCell': {
                'range': rng(sh['id'], i, i + 1, 0, w),
                'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
                'fields': 'userEnteredFormat.textFormat.bold'}})
            req.append({'updateBorders': {
                'range': rng(sh['id'], i, i + 1, 0, w), 'top': LINE, 'bottom': LINE}})
    post(s, req, 'шрифт, фон, минусы, шапки')

    # ── 2. ширина колонок — считаем сами ────────────────────────────────────
    # autoResize нельзя: он тянет колонку под объединённый заголовок во всю
    # ширину таблицы и раздувает первую колонку.
    vals = s.get(B + SID + '/values:batchGet', params={
        'ranges': [sh['title'] for sh in sheets],
        'valueRenderOption': 'FORMATTED_VALUE'}).json().get('valueRanges', [])
    width, req = {}, []
    for sh, vr in zip(sheets, vals):
        merged = {(m['startRowIndex'], m['startColumnIndex'])
                  for m in sh['merges'] if m['endColumnIndex'] - m['startColumnIndex'] > 1}
        w = [SPACER] + [WMIN] * (sh['cols'] - 1)
        for i, row in enumerate(vr.get('values', [])):
            for j, c in enumerate(row):
                if j == 0 or (i, j) in merged or not str(c):
                    continue
                w[j] = max(w[j], min(int(text_px(c)) + PAD, WMAX))
        width[sh['id']] = w
        for j, px in enumerate(w):
            req.append({'updateDimensionProperties': {
                'range': {'sheetId': sh['id'], 'dimension': 'COLUMNS',
                          'startIndex': j, 'endIndex': j + 1},
                'properties': {'pixelSize': px}, 'fields': 'pixelSize'}})
    post(s, req, 'ширина колонок по содержимому')

    # ── 3. высота строк — считаем сами, autoResize врёт на переносе ──────────
    req = []
    for sh, vr in zip(sheets, vals):
        w = width[sh['id']]
        span = {}
        for m in sh['merges']:
            span[(m['startRowIndex'], m['startColumnIndex'])] = \
                sum(w[c] for c in range(m['startColumnIndex'], m['endColumnIndex']) if c < len(w))
        for i, row in enumerate(vr.get('values', [])):
            lines = 1
            for j, c in enumerate(row):
                t = str(c)
                if not t:
                    continue
                cw = span.get((i, j), w[j] if j < len(w) else 100)
                lines = max(lines, math.ceil(text_px(t) / max(20, cw - 12)))
            h = max(HMIN, lines * LINEH + VPAD)
            req.append({'updateDimensionProperties': {
                'range': {'sheetId': sh['id'], 'dimension': 'ROWS',
                          'startIndex': i, 'endIndex': i + 1},
                'properties': {'pixelSize': h}, 'fields': 'pixelSize'}})
        n = len(vr.get('values', []))
        req.append({'updateDimensionProperties': {
            'range': {'sheetId': sh['id'], 'dimension': 'ROWS',
                      'startIndex': n, 'endIndex': max(n + 1, sh['rows'])},
            'properties': {'pixelSize': HMIN}, 'fields': 'pixelSize'}})
    post(s, req, 'высота строк под содержимое')

    # ── 4. поля ввода: пунктирная рамка вместо жёлтой заливки ───────────────
    # В оригинале ячейки для ввода были жёлтыми. Заливки по стандарту нет —
    # значит помечаем их рамкой: цветом не пользуемся, а видно всё так же.
    by_title = {sh['title']: sh for sh in sheets}
    DOT = {'style': 'DOTTED', 'width': 1, 'color': BLACK}
    req = []
    for title, (r0, r1, c0, c1) in INPUT.items():
        sh = by_title[title]
        req.append({'updateBorders': {
            'range': rng(sh['id'], r0 - 1, r1, c0 - 1, c1),
            'top': LINE, 'bottom': LINE, 'left': LINE, 'right': LINE,
            'innerHorizontal': DOT, 'innerVertical': DOT}})
    post(s, req, 'поля ввода: пунктирная рамка')

    # ── 5. текст, который ссылался на цвет, — переписываем ──────────────────
    data = [{'range': k, 'values': [[v]]} for k, v in RECOLOR_TEXT.items()]
    s.post(B + SID + '/values:batchUpdate',
           json={'valueInputOption': 'USER_ENTERED', 'data': data}).raise_for_status()
    print('%-34s %4d правок' % ('текст про цвета переписан', len(data)))

    print()
    for sh in sheets:
        print('  %-20s данные %3d×%-3d  шапок %2d  красных чисел %d'
              % (sh['title'], sh['last_row'], sh['last_col'],
                 len(sh['heads']), len(sh['red'])))
    print('\nhttps://docs.google.com/spreadsheets/d/' + SID)


if __name__ == '__main__':
    main()
