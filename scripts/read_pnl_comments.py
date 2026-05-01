#!/usr/bin/env python3
"""Читает комментарии из обоих P&L файлов с деталями по ячейкам."""
import json, os
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')

# Все известные файлы P&L
FILE_IDS = [
    ('Новый',  '1MbiWUKK6iMTs13MifUi22tsWS1oLAmZT1Cg9Aa07CNU'),
    ('Старый1','14xH6Xcw6-8YJmOd4Fy-fzN0gOCNi7-UqOqhNuL-ndSI'),
    ('Старый2','1UfHb5RJhLMsOkk_xVTNtI-jqxTpQfSJq_SXOkWJDhyE'),
    ('Старый3','1bTuRnNVGR078qg4ZvODoFoxYYRW2qWh3TKf-3mrJ2IM'),
]

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/drive',
                       'https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def read_comments(s, label, fid):
    url = (f'https://www.googleapis.com/drive/v3/files/{fid}/comments'
           f'?fields=comments(id,content,anchor,quotedFileContent,resolved)&pageSize=100')
    r = s.get(url, timeout=20)
    if r.status_code != 200:
        print(f'  {label}: ошибка {r.status_code}')
        return
    comments = r.json().get('comments', [])
    if not comments:
        print(f'  {label}: комментариев нет')
        return
    print(f'\n{"="*60}')
    print(f'  {label} ({fid}): {len(comments)} комментариев')
    for c in comments:
        print(f'\n  [{"✅" if c.get("resolved") else "❗"}] {c.get("content","")[:300]}')
        qfc = c.get('quotedFileContent', {})
        if qfc:
            print(f'  Ячейка: {qfc.get("value","")[:200]}')
        print(f'  Anchor: {c.get("anchor","")[:300]}')

def read_zb_revenue(s, label, fid):
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{fid}/values/ЗБ!A1:O15'
    r = s.get(url, timeout=20)
    if r.status_code != 200:
        print(f'  {label} ЗБ!A1:O15: ошибка {r.status_code}')
        return
    print(f'\n  {label} — ЗБ строки 1-15:')
    for i, row in enumerate(r.json().get('values', []), 1):
        if row:
            print(f'    {i:2}: {row[0][:60]}')

def main():
    s = get_session()
    for label, fid in FILE_IDS:
        read_comments(s, label, fid)
    print('\n' + '='*60)
    for label, fid in FILE_IDS:
        read_zb_revenue(s, label, fid)

if __name__ == '__main__':
    main()
