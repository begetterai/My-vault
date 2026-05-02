#!/usr/bin/env python3
"""Перезаписывает колонку N (Расходы нал.) — только расходы с физической кассы.
ЗБ: account_id=3, ОВИР: account_id=4.
Перезаписывает всё (даже заполненные), т.к. старые данные были с учётом всех счетов.
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
    {'sheet': 'ЗБ',   'token': '398711:8746917c4a23ea897774040e039dfb76', 'cash_account': '3'},
    {'sheet': 'ОВИР', 'token': '935215:79675564e3d086d7e03d5fd56b50c8df', 'cash_account': '4'},
]

DATE_FROM = datetime.date(2026, 1, 1)
DATE_TO   = datetime.date(2026, 4, 30)

SKIP_CATEGORIES = {'Переводы', 'Внесения в кассу', 'Открытие ФС'}

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

def get_cash_expenses(token, date, cash_account):
    ds = de = date.strftime("%Y%m%d")
    rt = poster_get(token, 'finance.getTransactions', {'dateFrom': ds, 'dateTo': de})
    total = sum(abs(int(t.get('amount', 0))) / 100
                for t in rt.get('response', [])
                if t.get('type') == '0'
                and str(t.get('account_id', '')) == cash_account
                and t.get('category_name', '') not in SKIP_CATEGORIES)
    return total if total > 0 else None

def main():
    s = get_session()

    for loc in LOCATIONS:
        sheet        = loc['sheet']
        token        = loc['token']
        cash_account = loc['cash_account']
        print(f"\n{'='*50}")
        print(f"  {sheet} (касса account_id={cash_account}) — перезаписываю N...")

        updates = []
        filled = empty = 0
        current = DATE_FROM

        while current <= DATE_TO:
            row = date_to_row(current)
            expenses = get_cash_expenses(token, current, cash_account)
            if expenses is not None:
                updates.append({
                    'range': f"'{sheet}'!N{row}",
                    'values': [[expenses]]
                })
                filled += 1
                print(f"    {current.strftime('%d.%m')} → {expenses:,.0f}с")
            else:
                empty += 1

            time.sleep(0.15)
            current += datetime.timedelta(days=1)

        print(f"\n  Итого: заполнено {filled}, пустых дней {empty}")

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
