#!/usr/bin/env python3
"""Разбор личных расходов: свод по группам и все транзакции построчно.

Зачем отдельная таблица, когда есть журнал. В журнале строки лежат как
записывались — по дате, без групп и без счёта операций. Смотреть, куда
уходят деньги, по нему нельзя: категорий два десятка, и глаз в них тонет.
Здесь то же самое, но сведено — по группам смысла, с числом операций
и средним чеком, и рядом полный список, чтобы любую цифру можно было
раскрыть до конкретной покупки.

Источник задаётся ключом: по умолчанию копия журнала до очистки 04.09.2026,
где лежат июль и август. Для сентября и дальше — боевая таблица.

Оформление по правилу Азиза: Times New Roman 13, без заливок, жирным
только заголовки и итоги.

Запуск: python3 scripts/build_budget_review.py [id-таблицы-источника]
"""
import datetime
import sys

sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session

SRC = sys.argv[1] if len(sys.argv) > 1 else '1BVPX5rbBp-opmbkbpK3eTLRM465nUI4W33Hl-swQ-FE'
FOLDER = '1MpzfxZVhLUVUwo6p2QcoCMoqxxYEdMjm'          # папка личного бюджета
NAME = 'Личный бюджет — разбор расходов'
A = 'https://sheets.googleapis.com/v4/spreadsheets/'
D = 'https://www.googleapis.com/drive/v3/files'

# Группы — те же, что в заметке «Личный бюджет — как всё работает».
# Категория без группы попадает в «Прочее»: лучше честная свалка, чем
# тихо потерянная строка.
GROUPS = [
    ('Обязательное / Быт', ['Дом', 'Машина', 'Подписки', 'Рассрочка',
                            'Семья', 'Связь']),
    ('Еда', ['Продукты', 'Кафе']),
    ('Здоровье / Тело', ['Лечение / Медикаменты', 'Спортивное питание',
                         'Абонемент в зал', 'БАДы', 'Массаж / Сауна',
                         'Уход за собой']),
    ('Хотелки / Досуг', ['Одежда/Обувь', 'Гаджеты', 'Подарки', 'Развлечение',
                         'Путешествие', 'Обучение', 'Курение', 'Свидания']),
    ('Прочее', ['Прочее']),
]
GROUP_OF = {c: g for g, cs in GROUPS for c in cs}
RU_MONTH = ['', 'январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль',
            'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']


def as_date(x):
    t = str(x).strip()
    for f in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.datetime.strptime(t[:10], f).date()
        except ValueError:
            pass
    try:
        return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(t)))
    except (ValueError, TypeError):
        return None


def read_ops(s):
    """[(дата, тип, категория, сумма, комментарий)] — только разобранные строки."""
    r = s.get(A + SRC + '/values/Operations!A2:E1000',
              params={'valueRenderOption': 'UNFORMATTED_VALUE'}, timeout=60)
    out = []
    for x in r.json().get('values', []):
        x = list(x) + [''] * 5
        d = as_date(x[0])
        try:
            amount = float(str(x[3]).replace(',', '.'))
        except (ValueError, TypeError):
            continue
        if d:
            out.append((d, str(x[1]).strip(), str(x[2]).strip(), amount,
                        str(x[4]).strip()))
    return sorted(out)


def sheet_id(s, ss, title, cols, rows):
    """Лист с таким именем: создать или очистить. → sheetId."""
    meta = s.get(A + ss, params={'fields': 'sheets.properties'}, timeout=60).json()
    have = {x['properties']['title']: x['properties'] for x in meta['sheets']}
    if title in have:
        s.post(A + ss + '/values/' + title + '!A1:Z5000:clear', json={}, timeout=60)
        return have[title]['sheetId']
    r = s.post(A + ss + ':batchUpdate', json={'requests': [{'addSheet': {
        'properties': {'title': title, 'gridProperties': {
            'rowCount': rows, 'columnCount': cols, 'frozenRowCount': 1}}}}]},
        timeout=60).json()
    return r['replies'][0]['addSheet']['properties']['sheetId']


def main():
    s = session()
    ops = read_ops(s)
    if not ops:
        raise SystemExit('в источнике нет операций')
    spend = [o for o in ops if o[1] == 'Расход']
    months = sorted({o[0].strftime('%Y-%m') for o in spend})
    print(f'операций: {len(ops)} · расходов: {len(spend)} · месяцев: {len(months)}')

    # ── файл ─────────────────────────────────────────────────────────────
    q = (f"name = '{NAME}' and '{FOLDER}' in parents and trashed = false")
    found = s.get(D, params={'q': q, 'fields': 'files(id)',
                             'supportsAllDrives': 'true',
                             'includeItemsFromAllDrives': 'true'},
                  timeout=60).json().get('files', [])
    if found:
        ss = found[0]['id']
    else:
        ss = s.post(A, json={'properties': {'title': NAME}}, timeout=60).json()['spreadsheetId']
        s.post(D + '/' + ss, params={'addParents': FOLDER, 'removeParents': 'root',
                                     'supportsAllDrives': 'true'}, timeout=60)
    print('таблица:', f'https://docs.google.com/spreadsheets/d/{ss}/edit')

    # ── свод ─────────────────────────────────────────────────────────────
    head = ['Группа / категория'] + [RU_MONTH[int(m[5:])] for m in months] \
           + ['Итого', 'Операций', 'Средний чек']
    rows = [head]
    total_by_month = {m: 0.0 for m in months}
    for gname, cats in GROUPS:
        here = [c for c in sorted(set(o[2] for o in spend))
                if GROUP_OF.get(c, 'Прочее') == gname]
        if not here:
            continue
        g_line = [gname]
        g_tot, g_num = 0.0, 0
        body = []
        for c in here:
            mine = [o for o in spend if o[2] == c]
            per = [sum(o[3] for o in mine if o[0].strftime('%Y-%m') == m)
                   for m in months]
            tot = sum(per)
            g_tot += tot
            g_num += len(mine)
            body.append([c] + [round(v, 2) for v in per] + [round(tot, 2),
                        len(mine), round(tot / len(mine), 2)])
        per_g = [sum(o[3] for o in spend
                     if GROUP_OF.get(o[2], 'Прочее') == gname
                     and o[0].strftime('%Y-%m') == m) for m in months]
        for m, v in zip(months, per_g):
            total_by_month[m] += v
        rows.append(g_line + [round(v, 2) for v in per_g]
                    + [round(g_tot, 2), g_num,
                       round(g_tot / g_num, 2) if g_num else 0])
        rows.extend(['  ' + b[0]] + b[1:] for b in body)
    grand = sum(total_by_month.values())
    rows.append(['ВСЕГО РАСХОДОВ']
                + [round(total_by_month[m], 2) for m in months]
                + [round(grand, 2), len(spend), round(grand / len(spend), 2)])

    # Доходы и прочие типы — отдельной строкой: без них месяц не читается.
    for typ in ('Доход', 'Накопление', 'Погашение'):
        mine = [o for o in ops if o[1] == typ]
        if not mine:
            continue
        per = [sum(o[3] for o in mine if o[0].strftime('%Y-%m') == m) for m in months]
        rows.append([typ] + [round(v, 2) for v in per]
                    + [round(sum(per), 2), len(mine),
                       round(sum(per) / len(mine), 2)])

    sid = sheet_id(s, ss, 'Свод', len(head), len(rows) + 10)
    s.put(A + ss + '/values/' + f'Свод!A1',
          params={'valueInputOption': 'USER_ENTERED'},
          json={'values': rows}, timeout=60).raise_for_status()

    # ── транзакции ───────────────────────────────────────────────────────
    thead = ['Дата', 'Месяц', 'Тип', 'Группа', 'Категория', 'Сумма',
             'Комментарий']
    trows = [thead] + [
        [o[0].strftime('%d.%m.%Y'), RU_MONTH[o[0].month], o[1],
         GROUP_OF.get(o[2], 'Прочее') if o[1] == 'Расход' else '—',
         o[2], round(o[3], 2), o[4]] for o in ops]
    tid = sheet_id(s, ss, 'Транзакции', len(thead), len(trows) + 50)
    s.put(A + ss + '/values/' + 'Транзакции!A1',
          params={'valueInputOption': 'USER_ENTERED'},
          json={'values': trows}, timeout=60).raise_for_status()

    # ── оформление ───────────────────────────────────────────────────────
    bold_rows = [i for i, r in enumerate(rows)
                 if r[0] in [g for g, _ in GROUPS]
                 or r[0] in ('ВСЕГО РАСХОДОВ', 'Доход', 'Накопление', 'Погашение')]
    req = []
    for s_id, ncol, nrow in ((sid, len(head), len(rows)), (tid, len(thead), len(trows))):
        req += [
            {'repeatCell': {
                'range': {'sheetId': s_id, 'startRowIndex': 0, 'endRowIndex': nrow,
                          'startColumnIndex': 0, 'endColumnIndex': ncol},
                'cell': {'userEnteredFormat': {'textFormat': {
                    'fontFamily': 'Times New Roman', 'fontSize': 13}}},
                'fields': 'userEnteredFormat.textFormat'}},
            {'repeatCell': {
                'range': {'sheetId': s_id, 'startRowIndex': 0, 'endRowIndex': 1},
                'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
                'fields': 'userEnteredFormat.textFormat.bold'}},
            {'updateSheetProperties': {
                'properties': {'sheetId': s_id,
                               'gridProperties': {'frozenRowCount': 1}},
                'fields': 'gridProperties.frozenRowCount'}},
            {'autoResizeDimensions': {'dimensions': {
                'sheetId': s_id, 'dimension': 'COLUMNS',
                'startIndex': 0, 'endIndex': ncol}}},
        ]
    for i in bold_rows:
        req.append({'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': i, 'endRowIndex': i + 1,
                      'startColumnIndex': 0, 'endColumnIndex': len(head)},
            'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
            'fields': 'userEnteredFormat.textFormat.bold'}})
    s.post(A + ss + ':batchUpdate', json={'requests': req}, timeout=120).raise_for_status()
    print(f'свод: {len(rows)} строк · транзакции: {len(trows) - 1}')


if __name__ == '__main__':
    main()
