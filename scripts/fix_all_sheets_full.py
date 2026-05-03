#!/usr/bin/env python3
"""
Комплексное исправление всех листов дневного трекера.

1. Свод:  полная перестройка — теперь A-T, совпадает со структурой ЗБ/ОВИР (A-S) + T=% плана
2. ОВИР:  исправлена формула R (0→"" для пустых строк)
3. Все листы: CENTER выравнивание всех ячеек

Итоговая структура ЗБ / ОВИР / Свод (A-S идентичны):
  A  Дата                  — ручной ввод
  B  День                  — формула или ручной
  C  Заметки/События       — ручной ввод (Свод: пусто)
  D  Выручка               — Poster / агрегат
  E  Наличные              — Poster / агрегат
  F  Alif                  — Poster (включая Beeyor Алиф) / агрегат
  G  DC                    — Poster (включая Beeyor ДС) / агрегат
  H  Карта                 — Poster / агрегат
  I  Beeygor/Teztar        — Poster (инфо) / агрегат
  J  Итого оплат           — формула E+F+G+H
  K  Расхождение           — формула D-J (д.б. ~0)
  L  Инкасс. нал.          — Poster / агрегат
  M  Ост. откр.            — Poster / (пусто в Своде)
  N  Расходы нал.          — Poster cash account / агрегат
  O  Ост. закр.            — Poster / (пусто в Своде)
  P  Расхожд.кассы         — формула E+M-L-N-O / (пусто в Своде)
  Q  Нарастающий итог      — формула (сбрасывается каждый месяц)
  R  % выполнения          — формула D/S*100 (0–100)
  S  Нужно/день            — формула ПЛАН/дней_в_месяце

  Свод дополнительно:
  T  % плана               — формула Q/720000 (нарастающий % месячного плана)
"""
import json, os, time
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'credentials', 'romashka-drive.json')
SS_ID    = '1_KFsr5IRXMb9_5IJiuJOD8OD29b793La8TH5n7nIJE4'
ROWS     = 365
START    = 3
ZB_PLAN  = 390000
OVIR_PLAN = 330000
SVOD_PLAN = ZB_PLAN + OVIR_PLAN  # 720000

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def get_sheet_ids(s):
    r = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}?fields=sheets.properties', timeout=20)
    return {sh['properties']['title']: sh['properties']['sheetId']
            for sh in r.json().get('sheets', [])}

def vbu(s, data):
    body = {'valueInputOption': 'USER_ENTERED', 'data': data}
    r = s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values:batchUpdate',
               headers={'Content-Type': 'application/json'},
               data=json.dumps(body), timeout=60)
    if r.status_code != 200:
        print(f"  ❌ values error: {r.text[:200]}")
    return r.status_code == 200

def sbu(s, requests_list):
    body = {'requests': requests_list}
    r = s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}:batchUpdate',
               headers={'Content-Type': 'application/json'},
               data=json.dumps(body), timeout=60)
    if r.status_code != 200:
        print(f"  ❌ struct error: {r.text[:200]}")
    return r.status_code == 200

def cr(sheet, col, start, n, fn):
    return {'range': f"'{sheet}'!{col}{start}:{col}{start+n-1}",
            'values': [[fn(start + i)] for i in range(n)]}

def days_f(a):
    """Формула: количество дней в месяце для текстовой даты DD.MM.YYYY."""
    return f'DAY(DATE(VALUE(RIGHT({a},4)),VALUE(MID({a},4,2))+1,0))'

def norm_f(plan, a):
    return f'=IFERROR(ROUND({plan}/{days_f(a)},0),"")'

def pct_f(d, s):
    return f'=IF({d}="","",IFERROR(ROUND({d}/{s}*100,0),""))'

# ─── 1. ЦЕНТРИРОВАНИЕ ─────────────────────────────────────────────────────

def center_sheet(s, sheet_id, n_cols, label=''):
    """CENTER выравнивание всех строк (заголовки + данные)."""
    req = {
        'repeatCell': {
            'range': {
                'sheetId': sheet_id,
                'startRowIndex': 0, 'endRowIndex': START + ROWS,
                'startColumnIndex': 0, 'endColumnIndex': n_cols
            },
            'cell': {'userEnteredFormat': {'horizontalAlignment': 'CENTER'}},
            'fields': 'userEnteredFormat.horizontalAlignment'
        }
    }
    ok = sbu(s, [req])
    print(f"  {'✅' if ok else '❌'} CENTER: {label}")

# ─── 2. ОВИР — исправить R (0 → "" для пустых строк) ────────────────────

def fix_ovir_r(s):
    sheet = 'ОВИР'
    updates = [
        cr(sheet, 'R', START, ROWS,
           lambda r: pct_f(f'D{r}', f'S{r}'))
    ]
    ok = vbu(s, updates)
    print(f"  {'✅' if ok else '❌'} ОВИР: R формула исправлена")

# ─── 3. СВОД — полная перестройка под структуру ЗБ/ОВИР ──────────────────

SVOD_HEADERS = [
    'Заметки / События', 'Выручка (с)', 'Наличные', 'Alif', 'DC',
    'Карта', 'Beeygor/Teztar', 'Итого оплат', 'Расхождение',
    'Инкасс. нал.', 'Ост. откр.', 'Расходы', 'Ост. закр.',
    'Расхожд.кассы', 'Нарастающий итог', '% выполнения',
    'Нужно/день', '% плана'
]

def rebuild_svod(s):
    sheet = 'Свод'
    plan  = SVOD_PLAN
    updates = []

    # Заголовок строка 1
    updates.append({'range': f"'{sheet}'!A1",
                    'values': [[f'РОМАШКА — Дневной трекер 2026 | СВОД (ЗБ + ОВИР) | ПЛАН {plan:,} с/мес']]})

    # Заголовки строка 2 (C–T)
    updates.append({'range': f"'{sheet}'!C2:T2", 'values': [SVOD_HEADERS]})

    # C: Заметки — пусто (очищаем старые данные)
    updates.append({'range': f"'{sheet}'!C3:C{START+ROWS-1}", 'values': [['']] * ROWS})

    # D: Выручка
    updates.append(cr(sheet, 'D', START, ROWS,
        lambda r: f"=IF(AND('ЗБ'!D{r}=\"\",'ОВИР'!D{r}=\"\"),\"\","
                  f"IFERROR('ЗБ'!D{r},0)+IFERROR('ОВИР'!D{r},0))"))

    # E: Наличные
    updates.append(cr(sheet, 'E', START, ROWS,
        lambda r: f"=IFERROR('ЗБ'!E{r},0)+IFERROR('ОВИР'!E{r},0)"))

    # F: Alif
    updates.append(cr(sheet, 'F', START, ROWS,
        lambda r: f"=IFERROR('ЗБ'!F{r},0)+IFERROR('ОВИР'!F{r},0)"))

    # G: DC
    updates.append(cr(sheet, 'G', START, ROWS,
        lambda r: f"=IFERROR('ЗБ'!G{r},0)+IFERROR('ОВИР'!G{r},0)"))

    # H: Карта
    updates.append(cr(sheet, 'H', START, ROWS,
        lambda r: f"=IFERROR('ЗБ'!H{r},0)+IFERROR('ОВИР'!H{r},0)"))

    # I: Beeygor
    updates.append(cr(sheet, 'I', START, ROWS,
        lambda r: f"=IFERROR('ЗБ'!I{r},0)+IFERROR('ОВИР'!I{r},0)"))

    # J: Итого оплат = E+F+G+H (без I — Beeygor уже в F и G)
    updates.append(cr(sheet, 'J', START, ROWS,
        lambda r: f"=IF(D{r}=\"\",\"\",E{r}+F{r}+G{r}+H{r})"))

    # K: Расхождение = D-J
    updates.append(cr(sheet, 'K', START, ROWS,
        lambda r: f"=IF(D{r}=\"\",\"\",D{r}-J{r})"))

    # L: Инкасс
    updates.append(cr(sheet, 'L', START, ROWS,
        lambda r: f"=IFERROR('ЗБ'!L{r},0)+IFERROR('ОВИР'!L{r},0)"))

    # M: Ост. откр. — пусто в Своде (нельзя агрегировать)
    updates.append({'range': f"'{sheet}'!M3:M{START+ROWS-1}", 'values': [['']] * ROWS})

    # N: Расходы
    updates.append(cr(sheet, 'N', START, ROWS,
        lambda r: f"=IFERROR('ЗБ'!N{r},0)+IFERROR('ОВИР'!N{r},0)"))

    # O: Ост. закр. — пусто в Своде
    updates.append({'range': f"'{sheet}'!O3:O{START+ROWS-1}", 'values': [['']] * ROWS})

    # P: Расхожд.кассы — пусто в Своде
    updates.append({'range': f"'{sheet}'!P3:P{START+ROWS-1}", 'values': [['']] * ROWS})

    # Q: Нарастающий итог (сбрасывается каждый месяц)
    def q_f(r):
        if r == START:
            return f"=IF(D{r}=\"\",\"\",D{r})"
        return (f"=IF(D{r}=\"\",\"\","
                f"IF(MID(A{r},4,2)=MID(A{r-1},4,2),Q{r-1}+D{r},D{r}))")
    updates.append(cr(sheet, 'Q', START, ROWS, q_f))

    # R: % выполнения дня
    updates.append(cr(sheet, 'R', START, ROWS,
        lambda r: pct_f(f'D{r}', f'S{r}')))

    # S: Нужно/день (фиксированная норма)
    updates.append(cr(sheet, 'S', START, ROWS,
        lambda r: norm_f(plan, f'A{r}')))

    # T: % плана (нарастающий % от месячного плана)
    updates.append(cr(sheet, 'T', START, ROWS,
        lambda r: f"=IFERROR(Q{r}/{plan},\"\")"))

    # Очистить U и V (старые колонки если остались)
    for col in ['U', 'V']:
        updates.append({'range': f"'{sheet}'!{col}2:{col}{START+ROWS-1}",
                        'values': [['']] * (ROWS + 1)})

    ok = vbu(s, updates)
    print(f"  {'✅' if ok else '❌'} Свод: перестроен (A-S = ЗБ/ОВИР, T = % плана)")

# ─── 4. ЗБ — убедиться что формула R правильная ──────────────────────────

def fix_zb_r(s):
    sheet = 'ЗБ'
    updates = [
        cr(sheet, 'R', START, ROWS,
           lambda r: pct_f(f'D{r}', f'S{r}'))
    ]
    ok = vbu(s, updates)
    print(f"  {'✅' if ok else '❌'} ЗБ: R формула унифицирована")

# ─── main ──────────────────────────────────────────────────────────────────

def main():
    s = get_session()
    sheet_ids = get_sheet_ids(s)
    print(f"Листы: {list(sheet_ids.keys())}\n")

    # 1. Перестройка Свода
    print("━━ Свод ━━")
    rebuild_svod(s)
    time.sleep(0.5)

    # 2. Исправить формулы
    print("\n━━ Формулы ━━")
    fix_zb_r(s)
    fix_ovir_r(s)
    time.sleep(0.5)

    # 3. CENTER выравнивание всех листов
    print("\n━━ CENTER выравнивание ━━")
    align_map = {
        'ЗБ':           20,   # A-S (19) + запас
        'ОВИР':         20,
        'Свод':         21,   # A-T (20) + запас
        'Месяцы':       10,
        'Расходы ЗБ':   9,
        'Расходы ОВИР': 9,
    }
    for name, ncols in align_map.items():
        if name in sheet_ids:
            center_sheet(s, sheet_ids[name], ncols, name)

    print('\n✅ Все исправления применены')

if __name__ == '__main__':
    main()
