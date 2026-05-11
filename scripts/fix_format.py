#!/usr/bin/env python3
"""
Исправляет форматирование Super P&L:
- Локаль → ru_RU (запятые вместо точек)
- % строки → формат 0,00%
"""
import json, os
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SUPER_PNL_ID = '1l8Lau8K9997pyqJj-zjlILAkLoOHlQmPo6BAwqc5FBU'

SHEET_IDS = {'ЗБ': 0, 'ОВИР': 189519852}

# Строки с процентами (1-indexed) → 0-indexed для API
PCT_ROWS = [11, 13, 15, 17, 20, 22, 40, 42, 44]

# Строки с числами (данные + итоги)
NUM_ROWS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 19, 21,
            23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35,
            36, 37, 38, 39, 41, 43, 45, 46, 47, 48]


def pct_fmt():
    return {'numberFormat': {'type': 'PERCENT', 'pattern': '0.00%'}}


def num_fmt():
    return {'numberFormat': {'type': 'NUMBER', 'pattern': '0'}}


def main():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    session = AuthorizedSession(creds)

    reqs = []

    # 1. Локаль — оставляем en_US, иначе формулы ломаются
    # (Google Sheets ломает SUM/IFERROR при ru_RU locale)
    reqs.append({
        'updateSpreadsheetProperties': {
            'properties': {'locale': 'en_US'},
            'fields': 'locale'
        }
    })

    # 2. Форматы ячеек по листам
    for sheet_name, sheet_id in SHEET_IDS.items():
        # % строки: col C–N (indices 2–13)
        for row in PCT_ROWS:
            reqs.append({
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': row - 1, 'endRowIndex': row,
                        'startColumnIndex': 2, 'endColumnIndex': 14
                    },
                    'cell': {'userEnteredFormat': pct_fmt()},
                    'fields': 'userEnteredFormat.numberFormat'
                }
            })

        # Числовые строки: col C–N
        for row in NUM_ROWS:
            reqs.append({
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': row - 1, 'endRowIndex': row,
                        'startColumnIndex': 2, 'endColumnIndex': 14
                    },
                    'cell': {'userEnteredFormat': num_fmt()},
                    'fields': 'userEnteredFormat.numberFormat'
                }
            })

    r = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{SUPER_PNL_ID}:batchUpdate',
        headers={'Content-Type': 'application/json'},
        data=json.dumps({'requests': reqs}),
        timeout=60
    )
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        print(r.text[:500])
    else:
        print("✅ Локаль ru_RU, форматы % и числа применены")


if __name__ == '__main__':
    main()
