#!/usr/bin/env python3
"""Читает колонки K и P из трекера и показывает проблемные дни."""
import os, urllib.parse, datetime
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS         = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'credentials', 'romashka-drive.json')
TRACKER_SS_ID = '1_KFsr5IRXMb9_5IJiuJOD8OD29b793La8TH5n7nIJE4'

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def read_range(s, sheet, rng):
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{TRACKER_SS_ID}/values/{urllib.parse.quote(rng)}'
    return s.get(url, timeout=20).json().get('values', [])

def main():
    s = get_session()
    for sheet in ['ЗБ', 'ОВИР']:
        print(f"\n{'='*60}")
        print(f"  {sheet}")
        # Читаем B (дата), E (нал), K (?), L (инкасс), M (ост.откр), N (расх), O (ост.закр), P (расхождение)
        data = read_range(s, sheet, f"'{sheet}'!B3:P123")
        print(f"  {'Дата':<8} {'E нал':>8} {'K':>10} {'L инкасс':>10} {'M откр':>8} {'N расх':>8} {'O закр':>8} {'P разн':>10}")
        print(f"  {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")
        for row in data:
            def c(i): return row[i] if i < len(row) else ''
            date_val = c(0)
            e = c(3)   # E = col index 3 (B=0,C=1,D=2,E=3)
            k = c(9)   # K = col index 9
            l = c(10)  # L = col index 10
            m = c(11)  # M = col index 11
            n = c(12)  # N = col index 12
            o = c(13)  # O = col index 13
            p = c(14)  # P = col index 14

            if not date_val:
                continue

            # Показываем только строки где P большое или K необычное
            try:
                p_val = float(str(p).replace(',', '.').replace(' ', '')) if p else 0
                flag = abs(p_val) > 1000
            except:
                p_val = 0
                flag = False

            marker = ' ⚠️' if flag else ''
            print(f"  {date_val:<8} {e:>8} {k:>10} {l:>10} {m:>8} {n:>8} {o:>8} {str(p):>10}{marker}")

if __name__ == '__main__':
    main()
