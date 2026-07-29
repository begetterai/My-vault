#!/usr/bin/env python3
"""
sync_romashka.py — ежедневная синхронизация:
  Poster API (ЗБ + ОВИР) → Google Sheet «Ромашка — Финансы 2026»
  Лист Данные_Poster: дописывает строки за вчера (или указанный период)
  Лист Данные_ручные: не трогает (ручной ввод)
Запуск: python3 scripts/sync_romashka.py [YYYY-MM-DD] [YYYY-MM-DD]
"""
import os, sys, datetime, json, urllib.parse, time
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

# ── Config ────────────────────────────────────────────────────────────────────
VAULT_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDS_FILE      = os.path.join(VAULT_ROOT, 'scripts', 'credentials', 'romashka-drive.json')
CREDS_ENV_VAR   = 'ROMASHKA_SA_JSON'

ROMASHKA_SS_ID  = '1bTDELaAo8Ft9WIQqeWDFQQzp5rrDDHiRZ4VpFo-D4m8'
POSTER_BASE     = 'https://joinposter.com/api'

LOCATIONS = {
    'ЗБ':   '398711:8746917c4a23ea897774040e039dfb76',
    'ОВИР': '935215:79675564e3d086d7e03d5fd56b50c8df',
}

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

# ── Auth ──────────────────────────────────────────────────────────────────────
def load_creds():
    raw = os.environ.get(CREDS_ENV_VAR)
    if raw:
        return service_account.Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    return service_account.Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)

# ── Poster API ────────────────────────────────────────────────────────────────
def poster_get(token, method, params=None, retries=4):
    p = {'token': token}
    if params:
        p.update(params)
    url = f'{POSTER_BASE}/{method}?{urllib.parse.urlencode(p)}'
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)

def _tx_list(resp):
    if isinstance(resp, dict) and 'data' in resp: return resp['data']
    return resp if isinstance(resp, list) else []

def fetch_day(token, date_str):
    """Разбор по чекам: розничная выручка по каналам + СНБЖ отдельно.
    Каналы: 1=В заведении, 2=Навынос, 3=Доставка. СНБЖ = чек с меткой «Снбж» в комментарии."""
    d = date_str.replace('-', '')
    an = poster_get(token, 'dash.getAnalytics', {'dateFrom': d, 'dateTo': d}).get('response', {}).get('counters', {})
    rows = _tx_list(poster_get(token, 'dash.getTransactions', {'dateFrom': d, 'dateTo': d}).get('response'))

    ch = {'1': 0.0, '2': 0.0, '3': 0.0}
    snbzh = 0.0; retail = 0.0; retail_tx = 0
    for r in rows:
        amt = float(r.get('payed_sum', 0)) / 100
        if 'снбж' in str(r.get('transaction_comment', '')).lower():
            snbzh += amt
            continue
        sm = str(r.get('service_mode'))
        if sm in ch: ch[sm] += amt
        retail += amt; retail_tx += 1

    return {
        'revenue':      round(retail, 2),                       # розница = без СНБЖ
        'visitors':     int(an.get('visitors', 0)),
        'transactions': retail_tx,
        'avg_check':    round(retail / retail_tx, 2) if retail_tx else 0,
        'dine_in':      round(ch['1'], 2),                      # В заведении
        'takeaway':     round(ch['2'], 2),                      # Навынос
        'delivery':     round(ch['3'], 2),                      # Доставка
        'snbzh':        round(snbzh, 2),                        # СНБЖ (передачи п/ф)
    }

# ── Sheets helpers ────────────────────────────────────────────────────────────
def _with_retries(fn, retries=5):
    """Google API иногда отдаёт 5xx — повторяем с экспоненциальной паузой."""
    for attempt in range(retries):
        try:
            return fn()
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if code < 500 or attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)

def sheets_get(session, range_):
    def call():
        r = session.get(
            f'https://sheets.googleapis.com/v4/spreadsheets/{ROMASHKA_SS_ID}/values/{range_}',
            timeout=30)
        r.raise_for_status()
        return r.json().get('values', [])
    return _with_retries(call)

def sheets_append(session, range_, values):
    def call():
        r = session.post(
            f'https://sheets.googleapis.com/v4/spreadsheets/{ROMASHKA_SS_ID}/values/{range_}:append'
            '?valueInputOption=RAW&insertDataOption=INSERT_ROWS',
            json={'values': values}, timeout=30)
        r.raise_for_status()
        return r.json()
    return _with_retries(call)

def sheets_write(session, range_, values):
    r = session.put(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ROMASHKA_SS_ID}/values/{range_}'
        '?valueInputOption=RAW',
        json={'values': values}, timeout=30)
    r.raise_for_status()

# ── Date helpers ──────────────────────────────────────────────────────────────
def date_range(start, end):
    d = datetime.date.fromisoformat(start)
    e = datetime.date.fromisoformat(end)
    while d <= e:
        yield str(d)
        d += datetime.timedelta(days=1)

def existing_keys(session):
    """Return set of 'YYYY-MM-DD|Точка' already in Данные_Poster."""
    rows = sheets_get(session, 'Данные_Poster!A2:B')
    return {f'{r[0]}|{r[1]}' for r in rows if len(r) >= 2}

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    if len(sys.argv) >= 3:
        date_from, date_to = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 2:
        date_from = date_to = sys.argv[1]
    else:
        date_from = date_to = str(yesterday)

    print(f'Синхронизация: {date_from} → {date_to}')

    creds = load_creds()
    session = AuthorizedSession(creds)
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    seen = existing_keys(session)
    new_rows = []

    for date_str in date_range(date_from, date_to):
        for loc, token in LOCATIONS.items():
            key = f'{date_str}|{loc}'
            if key in seen:
                print(f'  Пропускаю {date_str} {loc} (уже есть)')
                continue
            try:
                d = fetch_day(token, date_str)
                row = [date_str, loc, d['revenue'], d['visitors'], d['transactions'], d['avg_check'], now_str,
                       d['dine_in'], d['takeaway'], d['delivery'], d['snbzh']]
                new_rows.append(row)
                print(f'  ✓ {date_str} {loc}: {d["revenue"]} с, {d["visitors"]} гостей')
            except Exception as e:
                print(f'  ✗ {date_str} {loc}: {e}')

    if new_rows:
        sheets_append(session, 'Данные_Poster!A:K', new_rows)
        print(f'\n✅ Добавлено {len(new_rows)} строк в Данные_Poster')
    else:
        print('\nНовых данных нет — всё актуально')

if __name__ == '__main__':
    main()
