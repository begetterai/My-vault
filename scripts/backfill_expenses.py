#!/usr/bin/env python3
"""Backfill колонки M (Расходы) в дневном трекере за Jan–Apr 2026.
Использует type=0 (исправленный фильтр Poster).
Пропускает дни где M уже заполнено (не перезаписывает).
"""
import json, os, time, datetime, urllib.request, urllib.parse
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS         = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'credentials', 'romashka-drive.json')
TRACKER_SS_ID = '1_KFsr5IRXMb9_5IJiuJOD8OD29b793La8TH5n7nIJE4'
POSTER_BASE   = 'https://joinposter.com/api'

LOCATIONS = [
    {'sheet': 'ЗБ',   'token': '398711:8746917c4a23ea897774040e039dfb76'},
    {'sheet': 'ОВИР', 'token': '935215:79675564e3d086d7e03d5fd56b50c8df'},
]

DATE_FROM = datetime.date(2026, 1, 1)
DATE_TO   = datetime.date(2026, 4, 30)

def date_to_row(d):
    return 3 + (d - datetime.date(2026, 1, 1)).days

def poster_get(token, method, params=None):
    p = {'token': token}
    if params: p.update(params)
    url = f"{POSTER_BASE}/{method}?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers={'User-Agent': 'RomashkaBot/1.0'}),
                timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"    ⚠️  {e}")
        return {}

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def read_existing_m(s, sheet, row_from, row_to):
    """Читает текущие значения колонки M чтобы не перезаписывать заполненные."""
    rng = f"'{sheet}'!M{row_from}:M{row_to}"
    r = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{TRACKER_SS_ID}/values/{urllib.parse.quote(rng)}',
              timeout=20)
    vals = r.json().get('values', [])
    result = {}
    for i, row in enumerate(vals):
        row_num = row_from + i
        if row and row[0] not in ('', '0', 0):
            result[row_num] = row[0]
    return result

SKIP_CATEGORIES = {'Переводы', 'Внесения в кассу', 'Открытие ФС'}

def get_daily_expenses(token, date):
    ds = de = date.strftime("%Y%m%d")
    rt = poster_get(token, 'finance.getTransactions', {'dateFrom': ds, 'dateTo': de})
    total = sum(abs(int(t.get('amount', 0))) / 100
                for t in rt.get('response', [])
                if t.get('type') == '0'
                and t.get('category_name', '') not in SKIP_CATEGORIES)
    return total if total > 0 else None

def main():
    s = get_session()
    row_from = date_to_row(DATE_FROM)
    row_to   = date_to_row(DATE_TO)

    for loc in LOCATIONS:
        sheet = loc['sheet']
        token = loc['token']
        print(f"\n{'='*50}")
        print(f"  {sheet} — читаю текущие данные M...")

        existing = read_existing_m(s, sheet, row_from, row_to)
        print(f"  Уже заполнено: {len(existing)} дней — пропускаю")

        updates = []
        current = DATE_FROM
        filled = skipped = empty = 0

        while current <= DATE_TO:
            row = date_to_row(current)
            if row in existing:
                skipped += 1
                current += datetime.timedelta(days=1)
                continue

            expenses = get_daily_expenses(token, current)
            if expenses is not None:
                updates.append({
                    'range': f"'{sheet}'!M{row}",
                    'values': [[expenses]]
                })
                filled += 1
                print(f"    {current.strftime('%d.%m')} → {expenses:,.0f}с")
            else:
                empty += 1

            time.sleep(0.15)
            current += datetime.timedelta(days=1)

        print(f"\n  Итого: заполнено {filled}, пропущено (уже было) {skipped}, пустых дней {empty}")

        if not updates:
            print("  Нечего обновлять.")
            continue

        body = {'valueInputOption': 'USER_ENTERED', 'data': updates}
        r = s.post(
            f'https://sheets.googleapis.com/v4/spreadsheets/{TRACKER_SS_ID}/values:batchUpdate',
            headers={'Content-Type': 'application/json'},
            data=json.dumps(body), timeout=30)
        print(f"  {'✅' if r.status_code == 200 else '❌'} Записано {len(updates)} ячеек в {sheet}")

    print(f"\n✅ Готово")

if __name__ == '__main__':
    main()
