#!/usr/bin/env python3
"""
Ромашка — ежедневное обновление трекера.
Запускать через cron: 0 23 * * * python3 /home/user/My-vault/scripts/update_daily_tracker.py

Обновляет строку с сегодняшней датой в листе ЗБ:
- Колонка C: выручка из Poster API
- Также обновляет строку в Свод (данные берутся формулой из ЗБ автоматически)

ОВИР обновляется вручную до подключения ОВИР Poster.
"""
import json, os, time, datetime, urllib.request, urllib.parse
from calendar import monthrange

os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS        = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'credentials', 'romashka-drive.json')
POSTER_TOKEN = '398711:8746917c4a23ea897774040e039dfb76'
POSTER_BASE  = 'https://joinposter.com/api'

TRACKER_SS_ID = '1_KFsr5IRXMb9_5IJiuJOD8OD29b793La8TH5n7nIJE4'

def poster_get(method, params=None):
    p = {'token': POSTER_TOKEN}
    if params: p.update(params)
    url = f"{POSTER_BASE}/{method}?{urllib.parse.urlencode(p)}"
    req = urllib.request.Request(url, headers={'User-Agent': 'RomashkaBot/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  ⚠️  Poster {method}: {e}")
        return {}

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def get_today_revenue():
    """Возвращает выручку ЗБ за сегодня из Poster."""
    today = datetime.date.today()
    ds = de = today.strftime("%Y%m%d")
    r = poster_get('dash.getAnalytics', {'dateFrom': ds, 'dateTo': de})
    counters = r.get('response', {}).get('counters', {})
    rev = float(counters.get('revenue', 0))
    tx  = int(float(counters.get('transactions', 0)))
    vis = int(float(counters.get('visitors', 0)))
    avg = float(counters.get('average_receipt', 0))
    return rev, tx, vis, avg

def date_to_row(target_date):
    """
    Вычисляет номер строки в таблице для заданной даты.
    Строки 1-2 = заголовки. Строка 3 = 01.01.2026.
    """
    jan1 = datetime.date(2026, 1, 1)
    delta = (target_date - jan1).days
    return delta + 3   # +3 because rows 1,2 are headers, row 3 = Jan 1

def update_row(s, ss_id, sheet_name, row_num, revenue, transactions, visitors, avg_check):
    """Записывает данные в строку row_num листа sheet_name."""
    range_c = f"'{sheet_name}'!C{row_num}"
    body = {
        'valueInputOption': 'USER_ENTERED',
        'data': [
            {'range': range_c, 'values': [[revenue]]}
        ]
    }
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/values:batchUpdate'
    r = s.post(url, headers={'Content-Type': 'application/json'},
               data=json.dumps(body), timeout=30)
    return r.status_code == 200

def main():
    if not TRACKER_SS_ID:
        print('❌ Укажи TRACKER_SS_ID в скрипте (ID файла из create_daily_tracker.py)')
        return

    today = datetime.date.today()
    print(f'Обновление трекера за {today.strftime("%d.%m.%Y")}...')

    rev, tx, vis, avg = get_today_revenue()
    print(f'  Poster ЗБ: выручка={rev:,.0f}с | чеки={tx} | гости={vis} | ср.чек={avg:.0f}с')

    if rev == 0:
        print('  ⚠️  Выручка = 0. Обновление пропущено (возможно, день ещё не начался).')
        return

    row = date_to_row(today)
    print(f'  Строка в таблице: {row}')

    s = get_session()
    ok = update_row(s, TRACKER_SS_ID, 'ЗБ', row, rev, tx, vis, avg)
    print(f'  {"✅" if ok else "❌"} ЗБ строка {row} обновлена: {rev:,.0f}с')

    print('\n✅ Готово.')

if __name__ == '__main__':
    main()
