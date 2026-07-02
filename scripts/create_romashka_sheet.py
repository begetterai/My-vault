#!/usr/bin/env python3
"""
Создаёт Google Sheet «Ромашка — Финансы» с полной МСФО-структурой.
Запускается один раз. Выводит ID созданного листа.
"""
import os, json
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

VAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDS_FILE = os.path.join(VAULT_ROOT, 'scripts', 'credentials', 'romashka-drive.json')
TRACKERS_FOLDER = '1JmYk1Vp1sazmcL_uIrDmaxr7UA-2sqXx'
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

def get_session():
    creds = service_account.Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return AuthorizedSession(creds)

def create_spreadsheet(session, title):
    r = session.post('https://sheets.googleapis.com/v4/spreadsheets', json={
        'properties': {'title': title},
        'sheets': [
            {'properties': {'title': 'Настройки'}},
            {'properties': {'title': 'П&У_Структура'}},
            {'properties': {'title': 'ДДС_Структура'}},
            {'properties': {'title': 'Данные_Poster'}},
            {'properties': {'title': 'Данные_ручные'}},
            {'properties': {'title': 'Расчёты'}},
        ]
    }, timeout=30)
    r.raise_for_status()
    ss = r.json()
    ss_id = ss['spreadsheetId']
    print(f'Created: {ss_id}')
    return ss_id

def move_to_folder(session, file_id, folder_id):
    r = session.get(
        f'https://www.googleapis.com/drive/v3/files/{file_id}?fields=parents',
        timeout=30)
    r.raise_for_status()
    parents = r.json().get('parents', [])
    r2 = session.patch(
        f'https://www.googleapis.com/drive/v3/files/{file_id}'
        f'?addParents={folder_id}&removeParents={",".join(parents)}&fields=id',
        timeout=30)
    r2.raise_for_status()
    print(f'Moved to folder {folder_id}')

def batch_update(session, ss_id, requests):
    r = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
        json={'requests': requests}, timeout=30)
    r.raise_for_status()

def write_values(session, ss_id, range_, values):
    r = session.put(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/values/{range_}'
        '?valueInputOption=RAW',
        json={'values': values}, timeout=30)
    r.raise_for_status()

# ── Данные листов ─────────────────────────────────────────────────────────────

SETTINGS = [
    ['Параметр', 'Значение'],
    ['Точки', 'ЗБ,ОВИР'],
    ['Валюта', 'сомони'],
    ['Poster_token_ZB', 'ВСТАВИТЬ_ТОКЕН_ЗБ'],
    ['Poster_token_OVIR', 'ВСТАВИТЬ_ТОКЕН_ОВИР'],
    ['Plan_ZB_monthly', '354000'],
    ['Plan_OVIR_monthly', '277000'],
    ['Food_cost_target_%', '30'],
    ['Labor_cost_target_%', '25'],
]

PNL_STRUCTURE = [
    ['Код', 'Название', 'Родитель', 'Тип', 'Знак', 'Источник', 'Порядок'],
    # Выручка
    ['REV', 'Выручка', '', 'group', '+', '', 1],
    ['REV.FOOD', 'Выручка от еды', 'REV', 'line', '+', 'Poster', 2],
    ['REV.BEV', 'Выручка от напитков', 'REV', 'line', '+', 'Poster', 3],
    ['REV.OTHER', 'Прочая выручка', 'REV', 'line', '+', 'Manual', 4],
    # Себестоимость
    ['COGS', 'Себестоимость продаж', '', 'group', '-', '', 5],
    ['COGS.FOOD', 'Food cost (продукты)', 'COGS', 'line', '-', 'Manual', 6],
    ['COGS.BEV', 'Beverage cost (напитки)', 'COGS', 'line', '-', 'Manual', 7],
    # Валовая прибыль
    ['GP', 'Валовая прибыль', '', 'calc', '=REV-COGS', '', 8],
    # OPEX
    ['OPEX', 'Операционные расходы', '', 'group', '-', '', 9],
    ['OPEX.LABOR', 'Фонд оплаты труда (ФОТ)', 'OPEX', 'group', '-', '', 10],
    ['OPEX.LABOR.KIT', 'ФОТ — Кухня', 'OPEX.LABOR', 'line', '-', 'Manual', 11],
    ['OPEX.LABOR.HALL', 'ФОТ — Зал', 'OPEX.LABOR', 'line', '-', 'Manual', 12],
    ['OPEX.LABOR.ADM', 'ФОТ — Администрация', 'OPEX.LABOR', 'line', '-', 'Manual', 13],
    ['OPEX.RENT', 'Аренда', 'OPEX', 'line', '-', 'Manual', 14],
    ['OPEX.UTIL', 'Коммунальные услуги', 'OPEX', 'line', '-', 'Manual', 15],
    ['OPEX.MKTG', 'Маркетинг и реклама', 'OPEX', 'line', '-', 'Manual', 16],
    ['OPEX.MAINT', 'Техническое обслуживание', 'OPEX', 'line', '-', 'Manual', 17],
    ['OPEX.SUPPLIES', 'Расходные материалы', 'OPEX', 'line', '-', 'Manual', 18],
    ['OPEX.OTHER', 'Прочие операционные расходы', 'OPEX', 'line', '-', 'Manual', 19],
    # EBITDA
    ['EBITDA', 'EBITDA', '', 'calc', '=GP-OPEX', '', 20],
    # DA
    ['DA', 'Амортизация (D&A)', '', 'group', '-', '', 21],
    ['DA.DEPR', 'Амортизация основных средств', 'DA', 'line', '-', 'Manual', 22],
    ['DA.AMORT', 'Амортизация нематериальных активов', 'DA', 'line', '-', 'Manual', 23],
    # EBIT
    ['EBIT', 'EBIT (Операционная прибыль)', '', 'calc', '=EBITDA-DA', '', 24],
    # Финансовые
    ['FIN', 'Финансовые расходы', '', 'group', '-', '', 25],
    ['FIN.INT', 'Проценты по кредитам', 'FIN', 'line', '-', 'Manual', 26],
    ['FIN.OTHER', 'Прочие финансовые расходы', 'FIN', 'line', '-', 'Manual', 27],
    # EBT
    ['EBT', 'Прибыль до налогообложения (EBT)', '', 'calc', '=EBIT-FIN', '', 28],
    # Налоги
    ['TAX', 'Налоги', '', 'line', '-', 'Manual', 29],
    # Чистая прибыль
    ['NET', 'Чистая прибыль', '', 'calc', '=EBT-TAX', '', 30],
]

CF_STRUCTURE = [
    ['Код', 'Название', 'Раздел', 'Знак', 'Источник', 'Порядок'],
    # CFO
    ['CFO', 'I. Операционная деятельность', '', '', '', 1],
    ['CFO.NET', 'Чистая прибыль', 'CFO', '+', 'П&У', 2],
    ['CFO.DA', 'Амортизация (добавить обратно)', 'CFO', '+', 'П&У', 3],
    ['CFO.WC', 'Изменение оборотного капитала', 'CFO', '', '', 4],
    ['CFO.WC.INV', 'Изменение запасов (инвентаря)', 'CFO.WC', '±', 'Manual', 5],
    ['CFO.WC.REC', 'Изменение дебиторской задолженности', 'CFO.WC', '±', 'Manual', 6],
    ['CFO.WC.PAY', 'Изменение кредиторской задолженности', 'CFO.WC', '±', 'Manual', 7],
    ['CFO.TOTAL', 'Итого: денежный поток от операций', 'CFO', '=', 'Расчёт', 8],
    # CFI
    ['CFI', 'II. Инвестиционная деятельность', '', '', '', 9],
    ['CFI.CAPEX', 'Покупка оборудования и ОС', 'CFI', '-', 'Manual', 10],
    ['CFI.RENOV', 'Ремонт и капитальные вложения', 'CFI', '-', 'Manual', 11],
    ['CFI.OTHER', 'Прочие инвестиции', 'CFI', '±', 'Manual', 12],
    ['CFI.TOTAL', 'Итого: денежный поток от инвестиций', 'CFI', '=', 'Расчёт', 13],
    # CFF
    ['CFF', 'III. Финансовая деятельность', '', '', '', 14],
    ['CFF.LOAN_IN', 'Получение кредитов', 'CFF', '+', 'Manual', 15],
    ['CFF.LOAN_OUT', 'Погашение кредитов', 'CFF', '-', 'Manual', 16],
    ['CFF.OWNER', 'Взносы / изъятия собственника', 'CFF', '±', 'Manual', 17],
    ['CFF.TOTAL', 'Итого: денежный поток от финансирования', 'CFF', '=', 'Расчёт', 18],
    # Итого
    ['NET_CF', 'Чистое изменение денежных средств', '', '=', 'Расчёт', 19],
    ['CASH_OPEN', 'Остаток на начало периода', '', '', 'Manual', 20],
    ['CASH_CLOSE', 'Остаток на конец периода', '', '=', 'Расчёт', 21],
]

MANUAL_DATA_HEADER = [
    ['Период', 'Точка', 'Код', 'Название', 'Сумма', 'Комментарий'],
    # Примеры для июня 2026
    ['2026-06', 'ЗБ', 'COGS.FOOD', 'Food cost', '', ''],
    ['2026-06', 'ЗБ', 'OPEX.LABOR.KIT', 'ФОТ Кухня', '', ''],
    ['2026-06', 'ЗБ', 'OPEX.LABOR.HALL', 'ФОТ Зал', '', ''],
    ['2026-06', 'ЗБ', 'OPEX.LABOR.ADM', 'ФОТ Администрация', '', ''],
    ['2026-06', 'ЗБ', 'OPEX.RENT', 'Аренда', '', ''],
    ['2026-06', 'ЗБ', 'OPEX.UTIL', 'Коммунальные', '', ''],
    ['2026-06', 'ОВИР', 'COGS.FOOD', 'Food cost', '', ''],
    ['2026-06', 'ОВИР', 'OPEX.LABOR.KIT', 'ФОТ Кухня', '', ''],
    ['2026-06', 'ОВИР', 'OPEX.LABOR.HALL', 'ФОТ Зал', '', ''],
    ['2026-06', 'ОВИР', 'OPEX.RENT', 'Аренда', '', ''],
    ['2026-06', 'ОВИР', 'OPEX.UTIL', 'Коммунальные', '', ''],
]

POSTER_DATA_HEADER = [
    ['Дата', 'Точка', 'Код', 'Выручка', 'Гостей', 'Чеков', 'Ср.чек'],
]

def main():
    session = get_session()
    ss_id = create_spreadsheet(session, 'Ромашка — Финансы')
    move_to_folder(session, ss_id, TRACKERS_FOLDER)

    write_values(session, ss_id, 'Настройки!A1', SETTINGS)
    write_values(session, ss_id, 'П&У_Структура!A1', PNL_STRUCTURE)
    write_values(session, ss_id, 'ДДС_Структура!A1', CF_STRUCTURE)
    write_values(session, ss_id, 'Данные_ручные!A1', MANUAL_DATA_HEADER)
    write_values(session, ss_id, 'Данные_Poster!A1', POSTER_DATA_HEADER)

    print(f'\n✅ Готово!')
    print(f'Sheet ID: {ss_id}')
    print(f'URL: https://docs.google.com/spreadsheets/d/{ss_id}')
    print(f'\nСледующий шаг: заполни токены Poster в листе "Настройки"')

if __name__ == '__main__':
    main()
