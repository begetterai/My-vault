#!/usr/bin/env python3
"""
Ромашка — ежедневное обновление трекера.
Cron: 0 23 * * * python3 /home/user/My-vault/scripts/update_daily_tracker.py
Обновляет колонку C (выручка) в листах ЗБ и ОВИР из Poster API.
Свод обновляется автоматически через формулы.
"""
import json, os, time, datetime, urllib.request, urllib.parse
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')
TRACKER_SS_ID = '1_KFsr5IRXMb9_5IJiuJOD8OD29b793La8TH5n7nIJE4'
POSTER_BASE   = 'https://joinposter.com/api'

LOCATIONS = [
    {'sheet': 'ЗБ',   'token': '398711:8746917c4a23ea897774040e039dfb76'},
    {'sheet': 'ОВИР', 'token': '935215:79675564e3d086d7e03d5fd56b50c8df'},
]

def poster_get(token, method, params=None):
    p = {'token': token}
    if params: p.update(params)
    url = f"{POSTER_BASE}/{method}?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers={'User-Agent': 'RomashkaBot/1.0'}),
                timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  ⚠️  {e}")
        return {}

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def date_to_row(d):
    return 3 + (d - datetime.date(2026, 1, 1)).days

def main():
    today = datetime.date.today()
    print(f'Обновление трекера за {today.strftime("%d.%m.%Y")}...')

    s = get_session()
    ds = de = today.strftime("%Y%m%d")
    row = date_to_row(today)
    updates = []

    for loc in LOCATIONS:
        r = poster_get(loc['token'], 'dash.getAnalytics', {'dateFrom': ds, 'dateTo': de})
        counters = r.get('response', {}).get('counters', {})
        rev = float(counters.get('revenue', 0))
        print(f"  Poster {loc['sheet']}: {rev:,.0f}с")
        if rev > 0:
            updates.append({'range': f"'{loc['sheet']}'!C{row}", 'values': [[rev]]})

    if not updates:
        print('  ⚠️  Нет данных. Обновление пропущено.')
        return

    body = {'valueInputOption': 'USER_ENTERED', 'data': updates}
    r2 = s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{TRACKER_SS_ID}/values:batchUpdate',
                headers={'Content-Type': 'application/json'},
                data=json.dumps(body), timeout=30)
    ok = r2.status_code == 200
    print(f"  {'✅' if ok else '❌'} строка {row} обновлена")

if __name__ == '__main__':
    main()
