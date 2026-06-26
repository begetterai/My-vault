#!/usr/bin/env python3
"""Добавляет лист «30 Дней — Цикл 1» (трекер чек-листов по блокам) в Life OS."""
import os
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from create_life_os import (
    CREDS, SCOPES, DARK_BG, CARD_BG, HEADER_BG, ACCENT_RED, ACCENT_BLUE,
    ACCENT_GRN, ACCENT_ORG, ACCENT_PUR, WHITE, GRAY, LIGHT_GRAY,
    cell_fmt, rng, repeat_cell, merge, col_width, row_height, freeze, a1,
)

SPREADSHEET_ID = '1-MuD4j9HLwltld6w0GObUtpuyUMKLIY9z3dh5wkMW3o'
SHEET_ID = 2
SHEET_TITLE = '30 Дней — Цикл 1'

A, B, C = 0, 1, 2  # Действие | Неделя | Готово

BLOCKS = [
    ('🟥 РОМАШКА', ACCENT_RED,
     'Закрыть 5 флагов ФОТ, оплатить Poster ОВИР и написать 3 базовых SOP — '
     'операционная нагрузка падает, сеть управляема без постоянного контроля Азиза.',
     '5/5 флагов · Poster оплачен · 3/3 SOP готовы',
     [
        ('Разобрать 5 флагов ФОТ апрель (Нигина, Махмуд×3, Азиз-дубль, Владимир-калькулятор)', 'Неделя 1'),
        ('Оплатить Poster ОВИР (просрочено с 01.05)', 'Неделя 1'),
        ('Заполнить 2-ю половину ФОТ (16–30) — ЗБ и ОВИР', 'Неделя 2'),
        ('SOP — Кассовая дисциплина (V.0)', 'Неделя 2'),
        ('SOP — Onboarding (V.0)', 'Неделя 3'),
        ('SOP — Старший повар (V.0)', 'Неделя 4'),
     ]),
    ('🟩 ЗДОРОВЬЕ', ACCENT_GRN,
     'Держать ≥80% выполнения привычек и не пропускать стоматолога — растёт энергия, '
     'дисциплина переносится на остальные блоки.',
     '≥80% привычек · 0 пропущенных визитов · ЛОР начат',
     [
        ('Трекать привычки в Life OS каждый день (зал, сон, и т.д.)', 'Все 4 недели'),
        ('Не пропускать ни одного приёма у стоматолога по графику', 'Все 4 недели'),
        ('Записаться и пройти первичную диагностику у ЛОРа', 'Неделя 2'),
     ]),
    ('🟦 ФИНАНСЫ', ACCENT_BLUE,
     'Фиксировать факт по доходам/расходам каждую неделю и сверять с планом — '
     'накопление выходит в плюс, долг 5000с гасится по графику.',
     'факт ≤ план · накопление ≥ 0 · −5000с долга',
     [
        ('Вносить факт по категориям (Life OS → Финансы Июль)', 'Неделя 1–3'),
        ('Сверка план vs факт в конце недели, корректировка', 'Неделя 1–4'),
        ('Перевод 5000с в счёт долга', 'Неделя 4'),
        ('Итоговая сверка месяца', 'Неделя 4'),
     ]),
    ('🟪 ОБУЧЕНИЕ / ПРАЙМ', ACCENT_PUR,
     'Выстроить процесс оцифровки уроков Маркаряна и читать системно — за 30 дней '
     'появляется структурированная база знаний, а не разрозненные файлы.',
     '≥80% привычка «чтение» · 4 урока Маркаряна оцифрованы',
     [
        ('Собрать материалы Маркаряна + выбрать инструмент транскрибации', 'Неделя 1'),
        ('Транскрибировать и оцифровать урок 1', 'Неделя 2'),
        ('Урок 2 + выбрать источник по рынкам/крипто и начать изучение', 'Неделя 3'),
        ('Уроки 3–4', 'Неделя 4'),
     ]),
]


def build():
    reqs, vals = [], {}
    reqs.append(repeat_cell(SHEET_ID, 0, 0, 120, 4, cell_fmt(bg=DARK_BG)))
    reqs.append(col_width(SHEET_ID, A, A + 1, 360))
    reqs.append(col_width(SHEET_ID, B, B + 1, 110))
    reqs.append(col_width(SHEET_ID, C, C + 1, 90))

    row = 0
    reqs.append(row_height(SHEET_ID, row, row + 1, 40))
    reqs.append(merge(SHEET_ID, row, A, row + 1, C + 1))
    vals[(row, A)] = '30 ДНЕЙ — ЦИКЛ 1 · 26.06–25.07.2026'
    reqs.append(repeat_cell(SHEET_ID, row, A, row + 1, C + 1,
        cell_fmt(bg=CARD_BG, bold=True, size=14, halign='LEFT')))
    row += 1

    reqs.append(row_height(SHEET_ID, row, row + 1, 26))
    reqs.append(merge(SHEET_ID, row, A, row + 1, C + 1))
    vals[(row, A)] = 'Гипотеза → Действие → Анализ → Доработка гипотезы → Повтор'
    reqs.append(repeat_cell(SHEET_ID, row, A, row + 1, C + 1,
        cell_fmt(bg=CARD_BG, size=9, halign='LEFT', fg=LIGHT_GRAY)))
    row += 1

    progress_row = row
    reqs.append(row_height(SHEET_ID, row, row + 1, 30))
    reqs.append(merge(SHEET_ID, row, A, row + 1, B))
    vals[(row, A)] = 'ОБЩИЙ ПРОГРЕСС ЦИКЛА'
    reqs.append(repeat_cell(SHEET_ID, row, A, row + 1, B,
        cell_fmt(bg=HEADER_BG, bold=True, size=10, fg=WHITE)))
    reqs.append(repeat_cell(SHEET_ID, row, B, row + 1, C + 1,
        cell_fmt(bg=HEADER_BG, bold=True, size=11, halign='CENTER', fg=ACCENT_ORG)))
    row += 1

    reqs.append(row_height(SHEET_ID, row, row + 1, 10))
    row += 1

    block_ranges = []  # (start_action_row, end_action_row) per block, for overall progress

    for name, color, hypothesis, metric, actions in BLOCKS:
        reqs.append(row_height(SHEET_ID, row, row + 1, 28))
        reqs.append(merge(SHEET_ID, row, A, row + 1, C + 1))
        vals[(row, A)] = name
        reqs.append(repeat_cell(SHEET_ID, row, A, row + 1, C + 1,
            cell_fmt(bg=color, bold=True, size=11, fg={'red': 0.07, 'green': 0.07, 'blue': 0.07})))
        row += 1

        reqs.append(row_height(SHEET_ID, row, row + 1, 40))
        reqs.append(merge(SHEET_ID, row, A, row + 1, C + 1))
        vals[(row, A)] = f'Гипотеза: {hypothesis}'
        reqs.append({'repeatCell': {
            'range': rng(SHEET_ID, row, A, row + 1, C + 1),
            'cell': {'userEnteredFormat': {
                'backgroundColor': CARD_BG,
                'textFormat': {'fontSize': 9, 'foregroundColor': LIGHT_GRAY},
                'wrapStrategy': 'WRAP', 'verticalAlignment': 'MIDDLE'}},
            'fields': 'userEnteredFormat'}})
        row += 1

        reqs.append(row_height(SHEET_ID, row, row + 1, 24))
        reqs.append(merge(SHEET_ID, row, A, row + 1, C + 1))
        vals[(row, A)] = f'Метрика: {metric}'
        reqs.append(repeat_cell(SHEET_ID, row, A, row + 1, C + 1,
            cell_fmt(bg=CARD_BG, bold=True, size=9, fg=color)))
        row += 1

        reqs.append(row_height(SHEET_ID, row, row + 1, 22))
        vals[(row, A)] = 'Действие'
        vals[(row, B)] = 'Срок'
        vals[(row, C)] = 'Готово'
        reqs.append(repeat_cell(SHEET_ID, row, A, row + 1, C + 1,
            cell_fmt(bg=HEADER_BG, bold=True, size=8, halign='CENTER', fg=LIGHT_GRAY)))
        row += 1

        action_start = row
        for text, week in actions:
            reqs.append(row_height(SHEET_ID, row, row + 1, 30))
            vals[(row, A)] = text
            vals[(row, B)] = week
            reqs.append({'repeatCell': {
                'range': rng(SHEET_ID, row, A, row + 1, B),
                'cell': {'userEnteredFormat': {
                    'backgroundColor': CARD_BG,
                    'textFormat': {'fontSize': 9, 'foregroundColor': WHITE},
                    'wrapStrategy': 'WRAP', 'verticalAlignment': 'MIDDLE'}},
                'fields': 'userEnteredFormat'}})
            reqs.append(repeat_cell(SHEET_ID, row, B, row + 1, C,
                cell_fmt(bg=CARD_BG, size=8, halign='CENTER', fg=GRAY)))
            reqs.append(repeat_cell(SHEET_ID, row, C, row + 1, C + 1,
                cell_fmt(bg=CARD_BG, halign='CENTER')))
            reqs.append({'setDataValidation': {
                'range': rng(SHEET_ID, row, C, row + 1, C + 1),
                'rule': {'condition': {'type': 'BOOLEAN'}, 'strict': True, 'showCustomUi': True}
            }})
            row += 1
        action_end = row
        block_ranges.append((action_start, action_end))

        reqs.append(row_height(SHEET_ID, row, row + 1, 26))
        reqs.append(merge(SHEET_ID, row, A, row + 1, B))
        vals[(row, A)] = 'Прогресс блока'
        reqs.append(repeat_cell(SHEET_ID, row, A, row + 1, B,
            cell_fmt(bg=CARD_BG, size=9, fg=LIGHT_GRAY)))
        done_rng = f'{a1(action_start, C)}:{a1(action_end - 1, C)}'
        vals[(row, C)] = (f'=COUNTIF({done_rng},TRUE)&"/"&COUNTA({done_rng})&"  ("&'
                           f'ROUND(COUNTIF({done_rng},TRUE)/COUNTA({done_rng})*100,0)&"%)"')
        reqs.append(repeat_cell(SHEET_ID, row, C, row + 1, C + 1,
            cell_fmt(bg=CARD_BG, bold=True, size=9, halign='CENTER', fg=color)))
        row += 1

        reqs.append(row_height(SHEET_ID, row, row + 1, 12))
        row += 1

    reqs.append(row_height(SHEET_ID, row, row + 1, 30))
    reqs.append(merge(SHEET_ID, row, A, row + 1, C + 1))
    vals[(row, A)] = ('🌙 Не в фокусе этого цикла: Отношения, Отдых, Окружение, Вклад. '
                       'Бар закрыт — см. ретроспективу в Vault.')
    reqs.append({'repeatCell': {
        'range': rng(SHEET_ID, row, A, row + 1, C + 1),
        'cell': {'userEnteredFormat': {
            'backgroundColor': CARD_BG,
            'textFormat': {'fontSize': 9, 'foregroundColor': GRAY, 'italic': True},
            'wrapStrategy': 'WRAP'}},
        'fields': 'userEnteredFormat'}})
    row += 1

    overall_done = '+'.join(f'COUNTIF({a1(s, C)}:{a1(e - 1, C)},TRUE)' for s, e in block_ranges)
    overall_total = '+'.join(f'COUNTA({a1(s, C)}:{a1(e - 1, C)})' for s, e in block_ranges)
    vals[(progress_row, B)] = (f'=({overall_done})&"/"&({overall_total})&"  ("&'
                                f'ROUND(({overall_done})/({overall_total})*100,0)&"%)"')

    reqs.append(freeze(SHEET_ID, rows=3, cols=0))
    return reqs, vals


def main():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    session = AuthorizedSession(creds)

    r = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}:batchUpdate',
        json={'requests': [{'addSheet': {'properties': {
            'sheetId': SHEET_ID, 'title': SHEET_TITLE, 'index': 1,
            'tabColor': ACCENT_RED,
            'gridProperties': {'rowCount': 70, 'columnCount': 4},
        }}}]}, timeout=30)
    print(f'📋 Лист добавлен: {r.status_code}')
    if r.status_code != 200:
        print(r.text[:2000]); return

    reqs, vals = build()
    BATCH = 400
    for i in range(0, len(reqs), BATCH):
        chunk = reqs[i:i + BATCH]
        rr = session.post(
            f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}:batchUpdate',
            json={'requests': chunk}, timeout=90)
        print(f'🎨 Формат [{i}:{i+len(chunk)}]: {rr.status_code}')
        if rr.status_code != 200:
            print(rr.text[:1500])

    updates = [{'range': f"'{SHEET_TITLE}'!{a1(r_, c_)}", 'values': [[v]]} for (r_, c_), v in vals.items()]
    r4 = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values:batchUpdate',
        json={'valueInputOption': 'USER_ENTERED', 'data': updates}, timeout=90)
    print(f'📝 Данные: {r4.status_code}')
    if r4.status_code != 200:
        print(r4.text[:1500])

    print(f'\n🔗 https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit')


if __name__ == '__main__':
    main()
