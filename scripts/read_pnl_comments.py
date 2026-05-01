#!/usr/bin/env python3
"""Читает комментарии из файла Super P&L и данные Cash Flow для диагностики."""
import json, os
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')
PNL_ID = '14xH6Xcw6-8YJmOd4Fy-fzN0gOCNi7-UqOqhNuL-ndSI'

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/drive',
                       'https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def read_comments(s):
    print('=== КОММЕНТАРИИ ===')
    url = f'https://www.googleapis.com/drive/v3/files/{PNL_ID}/comments?fields=comments(id,content,anchor,replies,resolved)&pageSize=100'
    r = s.get(url, timeout=30)
    comments = r.json().get('comments', [])
    print(f'Всего комментариев: {len(comments)}')
    for c in comments:
        print(f'\n[{"✅ решён" if c.get("resolved") else "❗ открыт"}]')
        print(f'  Контент: {c.get("content","")[:500]}')
        print(f'  Anchor: {c.get("anchor","")[:200]}')
        for rep in c.get('replies', []):
            print(f'  → Ответ: {rep.get("content","")[:200]}')

def read_cf_sheet(s):
    print('\n=== CASH FLOW — значения ===')
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{PNL_ID}/values/Cash Flow!A1:O35'
    r = s.get(url, timeout=30)
    rows = r.json().get('values', [])
    for i, row in enumerate(rows, 1):
        if row:
            print(f'  {i:2}: {row}')

def read_zb_sheet(s):
    print('\n=== ЗБ — первые 70 строк (колонка A) ===')
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{PNL_ID}/values/ЗБ!A1:A70'
    r = s.get(url, timeout=30)
    rows = r.json().get('values', [])
    for i, row in enumerate(rows, 1):
        if row:
            print(f'  {i:2}: {row[0]}')

def main():
    s = get_session()
    read_comments(s)
    read_zb_sheet(s)
    read_cf_sheet(s)

if __name__ == '__main__':
    main()
