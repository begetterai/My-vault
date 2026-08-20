#!/usr/bin/env python3
"""Дашборд — один лист таблицы, где видно всё сразу.

Тридцать листов с данными — это склад, а не обзор. Дашборд собирает из них
одну страницу и перезаписывает её раз в час. Значениями, а не формулами:
формула на тридцать листов ломается от любого переименования, а значения
переживают всё и читаются с телефона.

Дашборд ничего не считает сам — он показывает то, что посчитали kpi.py
и reports.py. Одна логика на телеграм, приложение и таблицу: цифры
не могут разойтись.
"""
import datetime
from collections import Counter, defaultdict

from . import config as C
from . import storage as S
from . import reports as R
from . import kpi as K

TAB = 'Дашборд'
W = 9                      # колонок на листе


def _rows_period(kind, ref=None):
    """Блок строк по одному периоду: индекс, составляющие, флаги."""
    since, until, label = K.period(kind, ref)
    out = [[f'{label.upper()}', '', '', '', '', '', '', '', '']]
    out.append(['Точка', 'Индекс'] + list(K.PARTS) + ['Сдано', 'Подтв.'])
    for p in S.points():
        ix = K.point_index(p, since, until)
        out.append([S.point_label(p),
                    '' if ix['total'] is None else ix['total']]
                   + ['' if ix['parts'].get(n) is None else ix['parts'][n]
                      for n in K.PARTS]
                   + [f'{ix["fills"]} из {ix["expect"]}', ix['checked']])
    return out, since, until


def build():
    """Собрать все строки дашборда."""
    now = C.now()
    rows = [[f'{C.COMPANY} · операционный дашборд', '', '', '', '', '', '', '', ''],
            [f'обновлено {now.strftime("%d.%m.%Y %H:%M")} · пересобирается каждый час',
             '', '', '', '', '', '', '', ''],
            [''] * W]

    # ── индекс по периодам ───────────────────────────────────────────────
    for kind in ('week', 'month'):
        block, since, until = _rows_period(kind)
        rows += block + [[''] * W]

    # ── флаги внимания ───────────────────────────────────────────────────
    since, until, label = K.period('week')
    rows.append(['ФЛАГИ ВНИМАНИЯ · неделя', '', '', '', '', '', '', '', ''])
    rows.append(['Точка', 'Флаг', 'Подробности', '', '', '', '', '', ''])
    any_flag = False
    for p in S.points():
        for title, _n, why in K.flags(p, since, until):
            rows.append([p, title, why, '', '', '', '', '', ''])
            any_flag = True
    if not any_flag:
        rows.append(['', 'нет', 'ни одного признака формального заполнения',
                     '', '', '', '', '', ''])
    rows.append([''] * W)

    # ── что чаще всего не выполняется ────────────────────────────────────
    m_since, m_until, m_label = K.period('month')
    fl = [r for r in S.get(C.TABS['fails'], 'A2:G')
          if len(r) > 6 and R._d(r[0]) and m_since <= R._d(r[0]) <= m_until]
    cnt = Counter((r[1].strip(), r[6].strip()) for r in fl)
    rows.append([f'ЧАЩЕ ВСЕГО НЕ ВЫПОЛНЯЕТСЯ · {m_label}', '', '', '',
                 '', '', '', '', ''])
    rows.append(['Точка', 'Раз', 'Пункт', '', '', '', '', '', ''])
    if cnt:
        for (pt, text), c in cnt.most_common(10):
            rows.append([pt, c, text[:90], '', '', '', '', '', ''])
    else:
        rows.append(['', '', 'невыполненных пунктов нет', '', '', '', '', '', ''])
    rows.append([''] * W)

    # ── журналы: происшествия, поломки, нарушения, жалобы ────────────────
    jr = K.journals(m_since, m_until)
    rows.append([f'СОБЫТИЯ · {m_label}', '', '', '', '', '', '', '', ''])
    rows.append(['Дата', 'Точка', 'Что', 'Кто', 'Важность', 'Статус',
                 '', '', ''])
    if jr:
        for j in sorted(jr, key=lambda x: x['date'], reverse=True)[:15]:
            rows.append([j['date'].strftime('%d.%m'), j['point'], j['kind'],
                         j['who'], j['severity'], j['status'] or 'Новая',
                         '', '', ''])
    else:
        rows.append(['', '', 'записей нет', '', '', '', '', '', ''])
    rows.append([''] * W)

    # ── деньги: списания, приёмка, инвентаризация ────────────────────────
    rows.append([f'ДВИЖЕНИЕ ТОВАРА · {m_label}', '', '', '', '', '', '', '', ''])
    rows.append(['Бланк', 'Точка', 'Записей', 'Позиций', 'Сумма кол-ва',
                 '', '', '', ''])
    money_any = False
    for cl in C.by_type('form').values():
        agg = defaultdict(lambda: {'docs': set(), 'lines': 0, 'qty': 0.0})
        for r in S.get(cl['tab'], 'A2:N'):
            r = list(r) + [''] * 14
            d = R._d(r[0])
            if not d or not (m_since <= d <= m_until):
                continue
            a = agg[r[2].strip()]
            a['docs'].add((r[0], r[1], r[3]))
            a['lines'] += 1
            a['qty'] += R._n(r[7]) or 0
        for pt, a in agg.items():
            rows.append([cl['title'], pt, len(a['docs']), a['lines'],
                         round(a['qty'], 2), '', '', '', ''])
            money_any = True
    if not money_any:
        rows.append(['', '', 'записей нет', '', '', '', '', '', ''])
    rows.append([''] * W)

    # ── люди ─────────────────────────────────────────────────────────────
    rows.append([f'ЛЮДИ · {m_label}', '', '', '', '', '', '', '', ''])
    rows.append(['Кто', 'Точка', 'Заполнений', 'Нашёл проблемы',
                 'Ср. минут', 'Быстрее нормы', 'Опозданий', 'Часов', 'Баллы'])
    fills = R.fills(m_since, m_until)
    by = defaultdict(lambda: {'n': 0, 'found': 0, 'min': [], 'fast': 0,
                              'point': '', 'late': 0, 'hours': 0.0})
    for x in fills:
        d = by[x['who']]
        d['n'] += 1
        d['point'] = x['point']
        if x['ok'] < x['tot']:
            d['found'] += 1
        if x['min'] is not None:
            d['min'].append(x['min'])
            if x['min'] * 60 < C.MIN_SECONDS:
                d['fast'] += 1
    for sh in K.shifts(m_since, m_until):
        d = by[sh['who']]
        d['point'] = d['point'] or sh['point']
        if sh['late'] > 0:
            d['late'] += 1
    for r in S.get(C.TABS['shift'], 'A2:J'):
        r = list(r) + [''] * 10
        dd = R._d(r[0])
        if dd and m_since <= dd <= m_until:
            by[r[2].strip()]['hours'] += R._n(r[5]) or 0
    try:
        from . import score as SC
        pts = SC.totals(since=m_since, until=m_until)
    except Exception:
        pts = {}
    if by:
        for who, d in sorted(by.items(), key=lambda kv: -kv[1]['n']):
            rows.append([who, d['point'], d['n'], d['found'],
                         round(sum(d['min']) / len(d['min'])) if d['min'] else '',
                         d['fast'] or '', d['late'] or '',
                         round(d['hours'], 1) or '', pts.get(who, '')])
    else:
        rows.append(['', '', 'заполнений нет', '', '', '', '', '', ''])
    rows.append([''] * W)

    # ── идеи с точек ─────────────────────────────────────────────────────
    ideas = [r for r in S.get(C.TABS['ideas'], 'A2:G')
             if len(r) > 4 and R._d(r[0]) and m_since <= R._d(r[0]) <= m_until]
    rows.append([f'ИДЕИ И ЗАДАЧИ С ТОЧЕК · {m_label}', '', '', '',
                 '', '', '', '', ''])
    rows.append(['Дата', 'Кто', 'Точка', 'Текст', 'Статус', '', '', '', ''])
    if ideas:
        for r in ideas[-12:][::-1]:
            r = list(r) + [''] * 7
            rows.append([r[0], r[1], r[2], r[4][:110], r[5] or 'Новая',
                         '', '', '', ''])
    else:
        rows.append(['', '', '', 'новых нет', '', '', '', '', ''])
    rows.append([''] * W)
    rows.append(['Индекс измеряет исполнение: сроки, подтверждение вторым '
                 'человеком, замеры, явку. Флаги ловят имитацию и в индекс '
                 'НЕ входят.', '', '', '', '', '', '', '', ''])
    return rows


def _sheet_id(s):
    meta = s.get(S.B + C.DATA_SHEET, params={'fields': 'sheets.properties'},
                 timeout=60).json()
    for sh in meta.get('sheets', []):
        if sh['properties']['title'] == TAB:
            return sh['properties']['sheetId']
    r = s.post(S.B + C.DATA_SHEET + ':batchUpdate', json={'requests': [
        {'addSheet': {'properties': {'title': TAB, 'index': 0, 'gridProperties': {
            'rowCount': 400, 'columnCount': W, 'frozenRowCount': 2}}}}]},
        timeout=60)
    r.raise_for_status()
    return r.json()['replies'][0]['addSheet']['properties']['sheetId']


def refresh():
    """Пересобрать лист «Дашборд». Идемпотентно."""
    s = S.session()
    gid = _sheet_id(s)
    rows = build()
    # чистим старое, пишем новое
    s.post(S.B + C.DATA_SHEET + '/values/' + S._rng(TAB, f'A1:I400') + ':clear',
           timeout=60)
    s.put(S.B + C.DATA_SHEET + '/values/' + S._rng(TAB, 'A1'),
          params={'valueInputOption': 'RAW'}, json={'values': rows},
          timeout=60).raise_for_status()

    # Оформление: без заливок, Times New Roman 13 — по правилу Азиза.
    heads = [i for i, r in enumerate(rows)
             if r[0] and r[0] == r[0].upper() and len(r[0]) > 8 and not r[1]]
    reqs = [
        {'repeatCell': {'range': {'sheetId': gid},
                        'cell': {'userEnteredFormat': {
                            'textFormat': {'fontFamily': 'Times New Roman',
                                           'fontSize': 13},
                            'verticalAlignment': 'TOP',
                            'wrapStrategy': 'WRAP'}},
                        'fields': 'userEnteredFormat(textFormat,verticalAlignment,'
                                  'wrapStrategy)'}},
        {'repeatCell': {'range': {'sheetId': gid, 'startRowIndex': 0,
                                  'endRowIndex': 1},
                        'cell': {'userEnteredFormat': {'textFormat': {
                            'fontFamily': 'Times New Roman', 'fontSize': 16,
                            'bold': True}}},
                        'fields': 'userEnteredFormat.textFormat'}},
        {'updateDimensionProperties': {
            'range': {'sheetId': gid, 'dimension': 'COLUMNS',
                      'startIndex': 0, 'endIndex': 1},
            'properties': {'pixelSize': 210}, 'fields': 'pixelSize'}},
        {'updateDimensionProperties': {
            'range': {'sheetId': gid, 'dimension': 'COLUMNS',
                      'startIndex': 2, 'endIndex': 3},
            'properties': {'pixelSize': 330}, 'fields': 'pixelSize'}},
    ]
    for i in heads:
        reqs.append({'repeatCell': {
            'range': {'sheetId': gid, 'startRowIndex': i, 'endRowIndex': i + 1},
            'cell': {'userEnteredFormat': {'textFormat': {
                'fontFamily': 'Times New Roman', 'fontSize': 13, 'bold': True}}},
            'fields': 'userEnteredFormat.textFormat'}})
    s.post(S.B + C.DATA_SHEET + ':batchUpdate', json={'requests': reqs}, timeout=60)
    return len(rows)


def url():
    return (f'https://docs.google.com/spreadsheets/d/{C.DATA_SHEET}'
            f'/edit#gid=0')
