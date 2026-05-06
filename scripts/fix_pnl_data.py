#!/usr/bin/env python3
"""Обновляет P&L: COGS из складов Poster, ФОТ из файла пользователя, коммунальные из транзакций.
Охватывает все 12 месяцев 2026. ФОТ вручную только для Янв–Апр (известные данные).
"""
import os, sys, json, time, calendar
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests
from collections import defaultdict
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'romashka-drive.json')
SS_ID  = '16aX_684tTXpRuuK1bR37DswcJMWdSixhmq-0zxhXFp8'
BASE   = 'https://joinposter.com/api'
YEAR   = 2026

# Все 12 месяцев
MONTHS = []
MON_NAMES = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']
for m in range(1, 13):
    last = calendar.monthrange(YEAR, m)[1]
    MONTHS.append((f'{YEAR}{m:02d}01', f'{YEAR}{m:02d}{last:02d}'))

LOCATIONS = [
    {
        'sheet': 'ЗБ',
        'token': '398711:8746917c4a23ea897774040e039dfb76',
        # ФОТ Янв–Апр из файла пользователя; Май–Дек = None (вводить вручную)
        'fot_prod': [49134, 36627, 41833, 47350, None, None, None, None, None, None, None, None],
        'fot_adm':  [15800, 15300, 15100, 15800, None, None, None, None, None, None, None, None],
        # Электричество Апр = из файла пользователя (в Poster не записано)
        'elec_overrides': {3: 13582.71},   # индекс месяца → значение
    },
    {
        'sheet': 'ОВИР',
        'token': '935215:79675564e3d086d7e03d5fd56b50c8df',
        'fot_prod': [10236, 32650, 35719, 40928, None, None, None, None, None, None, None, None],
        'fot_adm':  [6880,  16800, 16900, 17300, None, None, None, None, None, None, None, None],
        'elec_overrides': {3: 4082.97},
    },
]

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def get_supplies(token, d_from, d_to):
    r = requests.get(f'{BASE}/storage.getSupplies',
        params={'token': token, 'dateFrom': d_from, 'dateTo': d_to}, timeout=20)
    items = r.json().get('response', [])
    by_storage = defaultdict(float)
    for s in items:
        name = s.get('storage_name', '').strip()
        amt  = float(s.get('supply_sum', 0)) / 100
        by_storage[name] += amt
    return by_storage

def get_utilities(token, d_from, d_to):
    r = requests.get(f'{BASE}/finance.getTransactions',
        params={'token': token, 'dateFrom': d_from, 'dateTo': d_to}, timeout=20)
    txs = r.json().get('response', [])
    elec    = sum(abs(int(t.get('amount',0)))/100 for t in txs
                  if t.get('type')=='0' and str(t.get('category_id'))=='10')
    water   = sum(abs(int(t.get('amount',0)))/100 for t in txs
                  if t.get('type')=='0' and str(t.get('category_id'))=='11')
    garbage = sum(abs(int(t.get('amount',0)))/100 for t in txs
                  if t.get('type')=='0' and str(t.get('category_id'))=='12')
    return elec, water, garbage

def col(month_idx):
    return chr(66 + month_idx)  # B=Янв … M=Дек

def main():
    s = get_session()
    all_updates = []

    for loc in LOCATIONS:
        sheet    = loc['sheet']
        token    = loc['token']
        overrides = loc.get('elec_overrides', {})
        updates  = []
        print(f"\n{'='*65}\n  {sheet}\n{'='*65}")

        for m_idx, (d_from, d_to) in enumerate(MONTHS):
            mon = MON_NAMES[m_idx]
            c   = col(m_idx)

            # ── COGS из складов ──
            sup     = get_supplies(token, d_from, d_to)
            kitchen = sup.get('Кухня', 0)
            bar     = sup.get('Бар', 0)
            staff   = sup.get('Персоналка', 0)
            mats    = sup.get('Расходные материалы', 0) or sup.get('Расходные материалы ', 0)

            if any([kitchen, bar, staff, mats]):
                updates += [
                    {f'{sheet}!{c}19': round(kitchen, 2)},
                    {f'{sheet}!{c}20': round(bar, 2)},
                    {f'{sheet}!{c}21': round(staff, 2)},
                    {f'{sheet}!{c}22': round(mats, 2)},
                ]
                print(f"  {mon} COGS: Кухня={kitchen:,.2f} | Бар={bar:,.2f} | Персон={staff:,.2f} | РасхМат={mats:,.2f}")
            else:
                print(f"  {mon} COGS: нет данных — пропуск")

            # ── ФОТ (только если задан вручную) ──
            fp = loc['fot_prod'][m_idx]
            fa = loc['fot_adm'][m_idx]
            if fp is not None:
                updates += [
                    {f'{sheet}!{c}30': fp},
                    {f'{sheet}!{c}31': fa},
                ]
                print(f"  {mon} ФОТ: Произв={fp:,} | Адм={fa:,}")

            # ── Коммунальные ──
            elec, water, garbage = get_utilities(token, d_from, d_to)
            if m_idx in overrides and elec == 0:
                elec = overrides[m_idx]

            if any([elec, water, garbage]):
                util_total = round(elec + water + garbage, 2)
                updates += [
                    {f'{sheet}!{c}38': util_total},
                    {f'{sheet}!{c}39': round(elec, 2)},
                    {f'{sheet}!{c}40': round(water, 2)},
                    {f'{sheet}!{c}41': round(garbage, 2)},
                ]
                print(f"  {mon} Коммун: Электр={elec:,.2f} | Вода={water:,.2f} | Мусор={garbage:,.2f}")

            time.sleep(0.2)

        all_updates.append((sheet, updates))

    # ── Запись в Sheets ──
    for sheet, updates in all_updates:
        data = []
        for d in updates:
            for rng, val in d.items():
                data.append({'range': rng, 'values': [[val]]})

        body = {'valueInputOption': 'USER_ENTERED', 'data': data}
        r = s.post(
            f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values:batchUpdate',
            json=body, timeout=30)
        status = '✅' if r.status_code == 200 else f'❌ {r.status_code}'
        print(f"\n  {status} {sheet}: записано {len(data)} ячеек")
        if r.status_code != 200:
            print(f"  {r.text[:200]}")

    print('\n✅ Готово')

if __name__ == '__main__':
    main()
