#!/usr/bin/env python3
"""
Фикс листа Месяцы — исправляет формулы с двойным = (=IFERROR(='ЗБ'!O33/...)).
Проблема: zr содержал = внутри себя, вставлялся в другие формулы → невалидный синтаксис.
"""
import json, os, time
from calendar import monthrange
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')
TRACKER_SS_ID = '1_KFsr5IRXMb9_5IJiuJOD8OD29b793La8TH5n7nIJE4'
MONTHS_SHEET  = 'Месяцы'
PLAN_ZB, PLAN_OVIR = 300_000, 360_000
MONTHS_RU = ['','Январь','Февраль','Март','Апрель','Май','Июнь',
             'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']


def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)


def build_months_data():
    """Строки данных для листа Месяцы (строки 3–14, колонки A–I)."""
    rows = []
    day_offset = 2
    for m in range(1, 13):
        _, last = monthrange(2026, m)
        lr = day_offset + last
        zb = f"'ЗБ'!O{lr}"       # ссылка без = — вставляется внутрь формул
        ov = f"'ОВИР'!O{lr}"
        rows.append([
            MONTHS_RU[m],
            PLAN_ZB,
            f"=IFERROR({zb},\"\")",                      # C: Выручка ЗБ
            f"=IFERROR({zb}/{PLAN_ZB},\"\")",            # D: % ЗБ
            PLAN_OVIR,
            f"=IFERROR({ov},\"\")",                      # F: Выручка ОВИР
            f"=IFERROR({ov}/{PLAN_OVIR},\"\")",          # G: % ОВИР
            f"=IFERROR({zb}+{ov},\"\")",                 # H: СВОД
            f"=IFERROR(({zb}+{ov})/660000,\"\")",        # I: % СВОД
        ])
        day_offset += last
    return rows


def main():
    s = get_session()
    rows = build_months_data()

    # Строки 3–14 в листе Месяцы (1-based: row 3 = index 2)
    data = []
    for i, row in enumerate(rows):
        row_num = i + 3
        for j, val in enumerate(row):
            col = chr(ord('A') + j)
            data.append({
                'range': f"'{MONTHS_SHEET}'!{col}{row_num}",
                'values': [[val]]
            })

    body = {
        'valueInputOption': 'USER_ENTERED',
        'data': data
    }
    r = s.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{TRACKER_SS_ID}/values:batchUpdate',
        headers={'Content-Type': 'application/json'},
        data=json.dumps(body), timeout=60
    )
    if r.status_code == 200:
        print(f'✅ Месяцы исправлены ({len(data)} ячеек)')
    else:
        print(f'❌ Ошибка {r.status_code}: {r.text[:400]}')


if __name__ == '__main__':
    main()
