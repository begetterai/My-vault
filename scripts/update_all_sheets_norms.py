#!/usr/bin/env python3
"""
Обновляет все листы дневного трекера по новым нормам:
  ЗБ:   390,000с/мес
  ОВИР: 330,000с/мес
  Свод: 720,000с/мес (390+330)

Изменения:
  ЗБ/ОВИР:
    R  — % выполнения дня (0–100%), формула =ROUND(D/S*100,0)
    S  — Нужно/день фиксированный = ROUND(ПЛАН/дней_в_месяце, 0)
  Свод:
    A1 — план 660k→720k
    P  — % плана: /660k→/720k
    Q  — Норма/день: 660k→720k
    R  — % выполнения (вместо "Откл. от нормы")
    T  — Нужно/день: 660k→720k
  Месяцы:
    B3:B14 — план ЗБ: 300k→390k
    E3:E14 — план ОВИР: 360k→330k
    D3:D14 — % ЗБ формула: /300k→/390k
    G3:G14 — % ОВИР формула: /360k→/330k
    H3:H14 — Свод план: остаётся сумма из ЗБ+ОВИР
    I3:I14 — % Свод: /660k→/720k
"""
import json, os
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')
SS_ID = '1_KFsr5IRXMb9_5IJiuJOD8OD29b793La8TH5n7nIJE4'

ROWS   = 365   # дней в 2026
START  = 3     # первая строка данных

ZB_PLAN   = 390000
OVIR_PLAN = 330000
SVOD_PLAN = ZB_PLAN + OVIR_PLAN  # 720000

# Последние строки каждого месяца (row = 3 + day_of_year - 1)
# 2026 не високосный: Jan31 Mar31 Apr30 May31 Jun30 Jul31 Aug31 Sep30 Oct31 Nov30 Dec31
MONTH_END_ROWS = [33, 61, 92, 122, 153, 183, 214, 245, 275, 306, 336, 367]

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def vbu(s, data):
    """values:batchUpdate"""
    body = {'valueInputOption': 'USER_ENTERED', 'data': data}
    r = s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values:batchUpdate',
               headers={'Content-Type': 'application/json'},
               data=json.dumps(body), timeout=60)
    if r.status_code != 200:
        print(f"  ❌ {r.text[:300]}")
    return r.status_code == 200

def col_range(sheet, col, start, n, fn):
    return {'range': f"'{sheet}'!{col}{start}:{col}{start+n-1}",
            'values': [[fn(start + i)] for i in range(n)]}

# Дата в листах хранится как текст "DD.MM.YYYY".
# EOMONTH не работает с текстом, поэтому парсим вручную:
# RIGHT(A,4)=год, MID(A,4,2)=месяц → DATE(год, месяц+1, 0) = последний день месяца
def days_in_month_formula(a_cell):
    return f'DAY(DATE(VALUE(RIGHT({a_cell},4)),VALUE(MID({a_cell},4,2))+1,0))'

# ─── ЗБ ────────────────────────────────────────────────────────────────────

def update_zb(s):
    plan = ZB_PLAN
    sheet = 'ЗБ'
    print(f"\n  {sheet}…")

    updates = [
        # R: % выполнения дня (0–100)
        col_range(sheet, 'R', START, ROWS,
                  lambda r: f'=IFERROR(ROUND(D{r}/S{r}*100,0),"")'),
        # R2: header
        {'range': f"'{sheet}'!R2", 'values': [['% выполнения']]},
        # S: фиксированная норма в день (текстовая дата → парсим вручную)
        col_range(sheet, 'S', START, ROWS,
                  lambda r: f'=IFERROR(ROUND({plan}/{days_in_month_formula(f"A{r}")},0),"")'),
        {'range': f"'{sheet}'!S2", 'values': [['Нужно/день']]},
    ]
    ok = vbu(s, updates)
    print(f"  {'✅' if ok else '❌'} ЗБ R/S обновлены ({plan:,})")

# ─── ОВИР ──────────────────────────────────────────────────────────────────

def update_ovir(s):
    plan = OVIR_PLAN
    sheet = 'ОВИР'
    print(f"\n  {sheet}…")

    updates = [
        col_range(sheet, 'R', START, ROWS,
                  lambda r: f'=IFERROR(ROUND(D{r}/S{r}*100,0),"")'),
        {'range': f"'{sheet}'!R2", 'values': [['% выполнения']]},
        col_range(sheet, 'S', START, ROWS,
                  lambda r: f'=IFERROR(ROUND({plan}/{days_in_month_formula(f"A{r}")},0),"")'),
        {'range': f"'{sheet}'!S2", 'values': [['Нужно/день']]},
    ]
    ok = vbu(s, updates)
    print(f"  {'✅' if ok else '❌'} ОВИР R/S обновлены ({plan:,})")

# ─── Свод ───────────────────────────────────────────────────────────────────

def update_svod(s):
    plan = SVOD_PLAN
    sheet = 'Свод'
    print(f"\n  {sheet}…")

    updates = [
        # A1: заголовок
        {'range': f"'{sheet}'!A1",
         'values': [[f'РОМАШКА — Дневной трекер 2026 | СВОД (ЗБ + ОВИР) | ПЛАН {plan:,} с/мес']]},
        # P: % плана нарастающий
        col_range(sheet, 'P', START, ROWS,
                  lambda r: f'=IFERROR(O{r}/{plan},"")'),
        # Q: Норма/день (фиксированная, текстовая дата → парсим)
        col_range(sheet, 'Q', START, ROWS,
                  lambda r: f'=IFERROR(ROUND({plan}/{days_in_month_formula(f"A{r}")},0),"")'),
        {'range': f"'{sheet}'!Q2", 'values': [['Нужно/день']]},
        # R: % выполнения дня
        col_range(sheet, 'R', START, ROWS,
                  lambda r: f'=IFERROR(ROUND(C{r}/Q{r}*100,0),"")'),
        {'range': f"'{sheet}'!R2", 'values': [['% выполнения']]},
        # T: Осталось/день (для текущего месяца: сколько нужно в оставшиеся дни)
        col_range(sheet, 'T', START, ROWS,
                  lambda r: (
                      f'=IFERROR(IF(VALUE(MID(A{r},4,2))<MONTH(TODAY()),"",'
                      f'({plan}-O{r})/MAX(1,{days_in_month_formula(f"A{r}")}'
                      f'-VALUE(LEFT(A{r},2))+1)),"")'
                  )),
        {'range': f"'{sheet}'!T2", 'values': [['Осталось/день']]},
    ]
    ok = vbu(s, updates)
    print(f"  {'✅' if ok else '❌'} Свод обновлён ({plan:,})")

# ─── Месяцы ─────────────────────────────────────────────────────────────────

def update_mesyacy(s):
    sheet = 'Месяцы'
    print(f"\n  {sheet}…")

    # Значения планов для 12 строк (row 3–14)
    plan_zb   = [[ZB_PLAN]]   * 12
    plan_ovir = [[OVIR_PLAN]] * 12

    # Формулы % для каждого месяца (ссылки на конец месяца в листах)
    d_formulas = [[f"=IFERROR('ЗБ'!Q{row}/{ZB_PLAN},\"\")"]
                  for row in MONTH_END_ROWS]
    g_formulas = [[f"=IFERROR('ОВИР'!Q{row}/{OVIR_PLAN},\"\")"]
                  for row in MONTH_END_ROWS]
    i_formulas = [[f"=IFERROR(('ЗБ'!Q{row}+'ОВИР'!Q{row})/{SVOD_PLAN},\"\")"]
                  for row in MONTH_END_ROWS]
    h_formulas = [[f"=IFERROR('ЗБ'!Q{row}+'ОВИР'!Q{row},\"\")"]
                  for row in MONTH_END_ROWS]

    updates = [
        # Плановые значения (вручную)
        {'range': f"'{sheet}'!B3:B14", 'values': plan_zb},
        {'range': f"'{sheet}'!E3:E14", 'values': plan_ovir},
        # Формулы % выполнения
        {'range': f"'{sheet}'!D3:D14", 'values': d_formulas},
        {'range': f"'{sheet}'!G3:G14", 'values': g_formulas},
        {'range': f"'{sheet}'!H3:H14", 'values': h_formulas},
        {'range': f"'{sheet}'!I3:I14", 'values': i_formulas},
    ]
    ok = vbu(s, updates)
    print(f"  {'✅' if ok else '❌'} Месяцы обновлены (ЗБ {ZB_PLAN:,} / ОВИР {OVIR_PLAN:,} / Свод {SVOD_PLAN:,})")

# ─── main ────────────────────────────────────────────────────────────────────

def main():
    s = get_session()
    print('Обновляю все листы трекера...')
    update_zb(s)
    update_ovir(s)
    update_svod(s)
    update_mesyacy(s)
    print('\n✅ Готово')

if __name__ == '__main__':
    main()
