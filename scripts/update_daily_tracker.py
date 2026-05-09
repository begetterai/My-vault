#!/usr/bin/env python3
"""
Ромашка — ежедневное обновление трекера.
Cron: 0 23 * * * python3 /home/user/My-vault/scripts/update_daily_tracker.py

Источники данных:
  D  Выручка (нетто)  — dash.getAnalytics → revenue (после скидок = реальные деньги)
  E  Наличные         — finance.getCashShifts → amount_sell_cash
  F  Alif             — finance.getTransactions (Алиф + Beeyor Алиф)
  G  DC               — finance.getTransactions (Душанбе Сити + Beeyor ДС)
  H  Карта            — finance.getTransactions (Карта)
  I  Beeygor          — finance.getTransactions (все Beeyor)
  L  Инкасс. нал.     — finance.getCashShifts → amount_collection
  M  Ост. откр.       — finance.getCashShifts → amount_start первой смены
  N  Расходы          — finance.getTransactions type=0, только кассовый счёт
                        (включая Открытие ФС — реальный расход 1–3 сомони)
  O  Ост. закр.       — finance.getCashShifts → amount_end последней смены
  T  Внесения         — finance.getCashShifts → amount_debit

Сверка кассы (P = E + M + T − L − N − O ≈ 0):
  Расходы только с кассового счёта — безналичные не влияют на физическую кассу.
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

# Системные категории — не считаем расходами кассы
# Открытие ФС включается (1–3 сомони реального расхода)
SKIP_EXPENSE_CAT = {'Переводы', 'Внесения в кассу', 'Кассовые смены'}

def poster_get(token, method, params=None):
    p = {'token': token}
    if params:
        p.update(params)
    url = f"{POSTER_BASE}/{method}?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers={'User-Agent': 'RomashkaBot/1.0'}),
                timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"    ⚠️  {e}")
        return {}

def parse_payments(transactions):
    """Разбирает транзакции (type=1, Кассовые смены) по типам оплаты.

    Poster записывает закрытие кассы так:
      'Алиф — Закрытие безналичной кассы'          → Alif
      'Душанбе Сити — Закрытие безналичной кассы'   → DC
      'Закрытие безналичной кассы'                   → Карта (обычный терминал)
      'Beeyor (Алиф/ДС/Наличные) — ...'             → Beeygor (доставка)
      'Teztar — ...'                                 → Beeygor (доставка)
    """
    alif = dc = card = beeygor = 0.0
    for t in transactions:
        if t.get('type') != '1' or t.get('category_name') != 'Кассовые смены':
            continue
        comment = (t.get('comment', '') or '').lower()
        amt = abs(int(t.get('amount', 0))) / 100

        is_beeygor = 'beeyor' in comment or 'teztar' in comment
        is_alif    = 'алиф' in comment or 'alif' in comment
        is_dc      = 'душанбе сити' in comment or 'dushanbe city' in comment

        if is_beeygor:
            beeygor += amt
            if is_alif:
                alif += amt
            elif is_dc:
                dc += amt
        elif is_alif:
            alif += amt
        elif is_dc:
            dc += amt
        elif 'безналичной' in comment:
            card += amt

    return alif, dc, card, beeygor

def get_day_data(token, date, cash_account='3'):
    ds = de = date.strftime("%Y%m%d")

    # Выручка — нетто после скидок (реальные деньги, пришедшие в кассу)
    ra = poster_get(token, 'dash.getAnalytics', {'dateFrom': ds, 'dateTo': de})
    revenue = float(ra.get('response', {}).get('counters', {}).get('revenue', 0))

    # Кассовые смены — наличные продажи, инкассация, остатки, внесения
    rs = poster_get(token, 'finance.getCashShifts', {'dateFrom': ds, 'dateTo': de})
    shifts = rs.get('response', [])
    cash       = sum(int(s.get('amount_sell_cash',  0)) / 100 for s in shifts)
    collection = sum(int(s.get('amount_collection', 0)) / 100 for s in shifts)
    deposits   = sum(int(s.get('amount_debit',      0)) / 100 for s in shifts)
    open_bal   = int(shifts[0].get('amount_start', 0))  / 100 if shifts else None
    close_bal  = int(shifts[-1].get('amount_end',  0))  / 100 if shifts else None

    # Транзакции — только кассовый счёт (физическая касса) + типы оплаты
    rt = poster_get(token, 'finance.getTransactions', {'dateFrom': ds, 'dateTo': de})
    txns = rt.get('response', [])

    # Расходы только с кассового счёта — включая Открытие ФС (1–3 сомони)
    expenses = sum(abs(int(t.get('amount', 0))) / 100
                   for t in txns
                   if t.get('type') == '0'
                   and str(t.get('account_id', '')) == cash_account
                   and t.get('category_name', '') not in SKIP_EXPENSE_CAT)

    alif, dc, card, beeygor = parse_payments(txns)

    return {
        'revenue':    revenue      if revenue    > 0 else None,
        'cash':       cash         if cash       > 0 else None,
        'alif':       alif         if alif       > 0 else None,
        'dc':         dc           if dc         > 0 else None,
        'card':       card         if card       > 0 else None,
        'beeygor':    beeygor      if beeygor    > 0 else None,
        'collection': collection   if collection > 0 else None,
        'open_bal':   open_bal,
        'expenses':   round(expenses, 2) if expenses > 0 else None,
        'close_bal':  close_bal,
        'deposits':   round(deposits, 2) if deposits > 0 else None,
    }

def date_to_row(d):
    return 3 + (d - datetime.date(2026, 1, 1)).days

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

COL = {
    'revenue':    'D',
    'cash':       'E',
    'alif':       'F',
    'dc':         'G',
    'card':       'H',
    'beeygor':    'I',
    'collection': 'L',
    'open_bal':   'M',
    'expenses':   'N',
    'close_bal':  'O',
    'deposits':   'T',
}

def build_updates(sheet, row, data):
    return [{'range': f"'{sheet}'!{col}{row}", 'values': [[data[field]]]}
            for field, col in COL.items() if data.get(field) is not None]

def run(target_date=None):
    if target_date is None:
        target_date = datetime.date.today()
    print(f'Обновление трекера за {target_date.strftime("%d.%m.%Y")}...')

    s = get_session()
    row = date_to_row(target_date)
    all_updates = []

    for loc in LOCATIONS:
        print(f"  {loc['sheet']}...")
        data = get_day_data(loc['token'], target_date, loc['cash_account'])
        print(f"    выручка={data.get('revenue') or 0:,.2f}с  "
              f"нал={data.get('cash') or 0:,.0f}с  "
              f"alif={data.get('alif') or 0:,.0f}с  "
              f"dc={data.get('dc') or 0:,.0f}с  "
              f"beeygor={data.get('beeygor') or 0:,.0f}с  "
              f"расх={data.get('expenses') or 0:,.0f}с  "
              f"внесения={data.get('deposits') or 0:,.0f}с")
        if data.get('revenue'):
            all_updates += build_updates(loc['sheet'], row, data)
        time.sleep(0.5)

    if not all_updates:
        print('  ⚠️  Нет данных.')
        return

    body = {'valueInputOption': 'USER_ENTERED', 'data': all_updates}
    r = s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{TRACKER_SS_ID}/values:batchUpdate',
               headers={'Content-Type': 'application/json'},
               data=json.dumps(body), timeout=30)
    print(f"  {'✅' if r.status_code == 200 else '❌'} строка {row} ({len(all_updates)} ячеек)")

if __name__ == '__main__':
    run()
