#!/usr/bin/env python3
"""
Создаёт Google Sheet «Система — Подписки» в папке Трекеры.
Источник данных для 1-Projects/sistema/подписки.md (Drive = данные, Obsidian = структура).
"""
import os
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'romashka-drive.json')
TRACKERS_FOLDER = '1JmYk1Vp1sazmcL_uIrDmaxr7UA-2sqXx'
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

HEADER_BG = {'red': 0.15, 'green': 0.16, 'blue': 0.22}
WHITE = {'red': 1.0, 'green': 1.0, 'blue': 1.0}

# Статус/решение (🟢🔴🟡) — это архитектура/решение, живёт в Obsidian, не здесь.
ACTIVE_HEADERS = ['Сервис', 'Сумма', 'Валюта', 'Периодичность', 'Дата списания', 'Способ оплаты']
ACTIVE_ROWS = [
    ['Claude (Anthropic)', 22.00, 'USD', 'Ежемесячно', '4 число', 'Mastercard Алиф'],
    ['iCloud+', 0.99, 'USD', 'Ежемесячно', '6 число', 'Mastercard Алиф'],
    ['Telegram Premium', 3.99, 'USD', 'Ежемесячно', '28 число', 'Mastercard Алиф'],
    ['Google Workspace Business Plus', 25.30, 'EUR', 'Ежемесячно', '1 число', 'уточнить'],
]

CANCELLED_HEADERS = ['Сервис', 'Дата отключения', 'Комментарий']
CANCELLED_ROWS = [
    ['AI Expanded Access (Google Workspace)', '2026-06-28', 'Дополнение отключено'],
    ['Gemini / Google One', '2026-06-28', 'Отключено на всех личных аккаунтах'],
]


def header_format(sid, n_cols):
    return {'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': n_cols},
        'cell': {'userEnteredFormat': {
            'backgroundColor': HEADER_BG,
            'textFormat': {'foregroundColor': WHITE, 'bold': True},
        }},
        'fields': 'userEnteredFormat(backgroundColor,textFormat)',
    }}


def freeze(sid):
    return {'updateSheetProperties': {
        'properties': {'sheetId': sid, 'gridProperties': {'frozenRowCount': 1}},
        'fields': 'gridProperties.frozenRowCount',
    }}


def main():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    session = AuthorizedSession(creds)

    r_create = session.post(
        'https://www.googleapis.com/drive/v3/files',
        params={'supportsAllDrives': 'true'},
        json={
            'name': 'Система — Подписки',
            'mimeType': 'application/vnd.google-apps.spreadsheet',
            'parents': [TRACKERS_FOLDER],
        }, timeout=30)
    ss_id = r_create.json()['id']
    print(f'✅ Spreadsheet создан: {ss_id}')

    r = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
        json={'requests': [
            {'addSheet': {'properties': {'sheetId': 1, 'title': 'Подписки'}}},
            {'addSheet': {'properties': {'sheetId': 2, 'title': 'Отменённые'}}},
        ]}, timeout=30)
    print(f'📋 Листы добавлены: {r.status_code}')
    if r.status_code != 200:
        print(r.text[:1500])

    session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
        json={'requests': [{'deleteSheet': {'sheetId': 0}}]}, timeout=30)

    fmt_reqs = [
        header_format(1, len(ACTIVE_HEADERS)),
        freeze(1),
        header_format(2, len(CANCELLED_HEADERS)),
        freeze(2),
    ]
    rf = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
        json={'requests': fmt_reqs}, timeout=30)
    print(f'🎨 Формат: {rf.status_code}')
    if rf.status_code != 200:
        print(rf.text[:1500])

    values_data = [
        {'range': "'Подписки'!A1", 'values': [ACTIVE_HEADERS] + ACTIVE_ROWS},
        {'range': "'Отменённые'!A1", 'values': [CANCELLED_HEADERS] + CANCELLED_ROWS},
    ]
    rv = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/values:batchUpdate',
        json={'valueInputOption': 'USER_ENTERED', 'data': values_data}, timeout=30)
    print(f'📝 Данные: {rv.status_code}')
    if rv.status_code != 200:
        print(rv.text[:1500])

    print(f'\n🔗 https://docs.google.com/spreadsheets/d/{ss_id}')
    return ss_id


if __name__ == '__main__':
    main()
