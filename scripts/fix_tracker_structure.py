#!/usr/bin/env python3
"""
Приводит оба листа трекера к единой структуре:

A  Дата             — ручной ввод
B  День             — формула =TEXT(A,"ДДД")
C  Заметки/События  — ручной ввод
D  Выручка          — Poster dash.getAnalytics (авто)
E  Наличные         — Poster getCashShifts.amount_sell_cash (авто)
F  Alif             — Poster getTransactions, включает Beeyor Алиф (авто)
G  DC               — Poster getTransactions, включает Beeyor ДС (авто)
H  Карта            — Poster getTransactions, безнал касса (авто)
I  Beeygor/Teztar   — Poster getTransactions, все Beeyor+Teztar (авто, инфо)
J  Итого оплат      — формула =E+F+G+H (без I — уже в F и G)
K  Расхождение      — формула =D-J (выручка vs оплаты, д.б. ~0)
L  Инкасс. нал.     — Poster getCashShifts.amount_collection (авто)
M  Ост. откр.       — Poster getCashShifts.amount_start (авто)
N  Расходы нал.     — Poster getTransactions type=0, account_id=касса (авто)
O  Ост. закр.       — Poster getCashShifts.amount_end (авто)
P  Расхожд.кассы    — формула =E+M-L-N-O (д.б. ~0)
Q  Нарастающий итог — формула =Q_prev+D (сбрасывается каждый месяц)
R  % плана          — формула =Q/ПЛАН
S  Нужно/день       — формула =(ПЛАН-Q)/оставшиеся_дни

ЗБ:  ПЛАН=390,000с/мес
ОВИР: ПЛАН=330,000с/мес
"""
import json, os, time, urllib.parse
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')
SS_ID = '1_KFsr5IRXMb9_5IJiuJOD8OD29b793La8TH5n7nIJE4'

DATA_ROWS = 365   # строки 3–367 (весь 2026 год)
FIRST_ROW = 3

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def get_sheet_ids(s):
    r = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}?fields=sheets.properties', timeout=20)
    return {sh['properties']['title']: sh['properties']['sheetId']
            for sh in r.json().get('sheets', [])}

def sheets_batch_update(s, requests):
    body = {'requests': requests}
    r = s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}:batchUpdate',
               headers={'Content-Type': 'application/json'},
               data=json.dumps(body), timeout=30)
    if r.status_code != 200:
        print(f"  ❌ batchUpdate error: {r.text[:300]}")
    return r.status_code == 200

def values_batch_update(s, data):
    body = {'valueInputOption': 'USER_ENTERED', 'data': data}
    r = s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values:batchUpdate',
               headers={'Content-Type': 'application/json'},
               data=json.dumps(body), timeout=30)
    if r.status_code != 200:
        print(f"  ❌ values error: {r.text[:300]}")
    return r.status_code == 200

def col_formula_range(sheet, col, start, count, formula_fn):
    """Генерирует список значений для колонки с формулой, зависящей от номера строки."""
    return {
        'range': f"'{sheet}'!{col}{start}:{col}{start+count-1}",
        'values': [[formula_fn(start + i)] for i in range(count)]
    }

# ─── ЗБ ────────────────────────────────────────────────────────────────────

def fix_zb(s):
    sheet = 'ЗБ'
    PLAN = 390000
    print(f"\n{'='*55}\n  Обновляю {sheet} (план {PLAN:,}с)...")

    updates = []

    # P2: добавить название
    updates.append({'range': f"'{sheet}'!P2", 'values': [['Расхожд.кассы']]})

    # S3:S367 — исправить 300000 → 390000
    def s_formula(row):
        return f'=IFERROR(IF(EOMONTH(A{row},0)<TODAY(),"",' \
               f'({PLAN}-Q{row})/MAX(1,DAY(EOMONTH(A{row},0))-DAY(A{row})+1)),"")'
    updates.append(col_formula_range(sheet, 'S', FIRST_ROW, DATA_ROWS, s_formula))

    ok = values_batch_update(s, updates)
    print(f"  {'✅' if ok else '❌'} ЗБ: заголовок P + формула S ({PLAN:,})")

# ─── ОВИР ──────────────────────────────────────────────────────────────────

def fix_ovir(s, sheet_ids):
    sheet = 'ОВИР'
    PLAN = 330000
    sheet_id = sheet_ids[sheet]
    print(f"\n{'='*55}\n  Обновляю {sheet} (план {PLAN:,}с)...")

    # Шаг 1: вставить колонку P (индекс 15) — сдвигает P→Q, Q→R, R→S, S→T
    ok = sheets_batch_update(s, [{
        'insertDimension': {
            'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS',
                      'startIndex': 15, 'endIndex': 16},
            'inheritFromBefore': False
        }
    }])
    print(f"  {'✅' if ok else '❌'} Вставлена колонка P")
    if not ok:
        return
    time.sleep(0.5)

    # Шаг 2: удалить бывшую S (Прогноз), теперь она на позиции T (индекс 19)
    # После вставки: P=new, Q=нарастающий(был P), R=%(был Q), S=Прогноз(был R), T=нужно(был S)
    ok = sheets_batch_update(s, [{
        'deleteDimension': {
            'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS',
                      'startIndex': 18, 'endIndex': 19}  # S = индекс 18
        }
    }])
    print(f"  {'✅' if ok else '❌'} Удалена колонка Прогноз")
    time.sleep(0.5)

    # Теперь структура ОВИР совпадает с ЗБ:
    # P=новая(расхожд.кассы), Q=нарастающий, R=%, S=нужно/день

    updates = []

    # A1: обновить план
    updates.append({'range': f"'{sheet}'!A1",
                    'values': [[f'РОМАШКА — Дневной трекер 2026 | ОВИР (Турсунзода) | ПЛАН {PLAN:,} с/мес']]})

    # P2: заголовок
    updates.append({'range': f"'{sheet}'!P2", 'values': [['Расхожд.кассы']]})

    # P3:P367 — формула кассового расхождения
    def p_formula(row):
        return f'=IF(D{row}="","",E{row}+M{row}-L{row}-N{row}-O{row})'
    updates.append(col_formula_range(sheet, 'P', FIRST_ROW, DATA_ROWS, p_formula))

    # J3:J367 — убрать +I (Beeygor уже в F и G)
    def j_formula(row):
        return f'=IF(D{row}="","",E{row}+F{row}+G{row}+H{row})'
    updates.append(col_formula_range(sheet, 'J', FIRST_ROW, DATA_ROWS, j_formula))

    # R3:R367 — % плана: исправить 360000 → 330000
    def r_formula(row):
        return f'=IFERROR(Q{row}/{PLAN},"")'
    updates.append(col_formula_range(sheet, 'R', FIRST_ROW, DATA_ROWS, r_formula))

    # S3:S367 — нужно/день: исправить 360000 → 330000
    def s_formula(row):
        return f'=IFERROR(IF(EOMONTH(A{row},0)<TODAY(),"",' \
               f'({PLAN}-Q{row})/MAX(1,DAY(EOMONTH(A{row},0))-DAY(A{row})+1)),"")'
    updates.append(col_formula_range(sheet, 'S', FIRST_ROW, DATA_ROWS, s_formula))

    ok = values_batch_update(s, updates)
    print(f"  {'✅' if ok else '❌'} ОВИР: заголовки + формулы P/J/R/S ({PLAN:,})")

def main():
    s = get_session()
    sheet_ids = get_sheet_ids(s)
    print(f"Листы: {list(sheet_ids.keys())}")

    fix_zb(s)
    fix_ovir(s, sheet_ids)

    print(f"\n✅ Готово")

if __name__ == '__main__':
    main()
