#!/usr/bin/env python3
"""
Ромашка — Дневной трекер 2026
ЗБ: автоматически из Poster API (Янв–Апр).
ОВИР: вводится вручную (Poster не подключён).
Свод = ЗБ + ОВИР, план 660 000с/мес.
Настройки: плановые показатели по месяцам.
"""
import json, os, time, datetime, urllib.request, urllib.parse
from calendar import monthrange

os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS        = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'credentials', 'romashka-drive.json')
FOLDER_ID    = '1mYH2yvUiWnR5dKAYrFw_vQgM5SrvIH9g'   # 01.1_Управленческая_Отчетность
POSTER_TOKEN = '398711:8746917c4a23ea897774040e039dfb76'
POSTER_BASE  = 'https://joinposter.com/api'
FONT         = 'Times New Roman'

PLAN_ZB   = 300_000
PLAN_OVIR = 360_000
PLAN_SVOD = PLAN_ZB + PLAN_OVIR  # 660_000

DAYS_RU    = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
MONTHS_RU  = ['','Январь','Февраль','Март','Апрель','Май','Июнь',
               'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']

def rgb(r, g, b): return {"red": r/255, "green": g/255, "blue": b/255}

C_DARK    = rgb(20,  43,  75)
C_SEC     = rgb(31,  73, 125)
C_SUB     = rgb(65, 105, 185)
C_SUBHEAD = rgb(219, 229, 241)
C_GREEN   = rgb(198, 239, 206)
C_RED     = rgb(255, 199, 206)
C_GOLD    = rgb(255, 242, 204)
C_WEEKEND = rgb(230, 230, 245)
C_WHITE   = rgb(255, 255, 255)
C_GRAY    = rgb(245, 245, 245)

# ── Poster API ─────────────────────────────────────────────────────────────────
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

def poster_get_retry(method, params=None, retries=4):
    """Poster API call with retry and backoff."""
    for attempt in range(retries):
        r = poster_get(method, params)
        if r and 'response' in r:
            return r
        wait = 2 ** attempt
        print(f"    retry {attempt+1} (wait {wait}s)...")
        time.sleep(wait)
    return {}

def pull_daily_revenue():
    """Возвращает dict {date: revenue_float} для ЗБ, Янв–Апр 2026."""
    today = datetime.date.today()
    result = {}
    for year, month in [(2026, 1), (2026, 2), (2026, 3), (2026, 4)]:
        if datetime.date(year, month, 1) > today:
            break
        _, last = monthrange(year, month)
        end = min(datetime.date(year, month, last), today)
        ds, de = f"{year}{month:02d}01", end.strftime("%Y%m%d")
        print(f"  Poster ЗБ {year}-{month:02d}...")
        r = poster_get_retry('dash.getAnalytics', {'dateFrom': ds, 'dateTo': de})
        for i, val in enumerate(r.get('response', {}).get('data', [])):
            d = datetime.date(year, month, i + 1)
            if d <= today:
                v = float(val) if val else 0.0
                if v > 0:
                    result[d] = v
        time.sleep(1)
    print(f"  Загружено {len(result)} дней из Poster.")
    return result

# ── Google API helpers ─────────────────────────────────────────────────────────
def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/drive',
                       'https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def api_post(s, url, body):
    for attempt in range(6):
        try:
            r = s.post(url, headers={'Content-Type': 'application/json'},
                       data=json.dumps(body), timeout=90)
            if r.status_code == 503 or not r.content:
                print(f"    retry {attempt+1} (503/empty)...")
                time.sleep(2 ** attempt); continue
            return r
        except Exception as e:
            print(f"    retry {attempt+1} ({e})...")
            time.sleep(2 ** attempt)
    return None

def write_values(s, ss_id, sheet_name, rows):
    body = {'valueInputOption': 'USER_ENTERED',
            'data': [{'range': f"'{sheet_name}'!A1",
                      'values': [[str(c) if c != '' else '' for c in row] for row in rows]}]}
    r = api_post(s, f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/values:batchUpdate', body)
    ok = r and r.status_code == 200
    print(f"  {'✅' if ok else '❌'} values: {sheet_name}")
    if not ok and r: print(r.text[:300])

def apply_fmt(s, ss_id, reqs, label=''):
    if not reqs: return
    for i in range(0, len(reqs), 40):
        r = api_post(s, f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
                     {'requests': reqs[i:i+40]})
        ok = r and r.status_code == 200
        print(f"  {'✅' if ok else '❌'} fmt chunk {i//40+1}: {label}")
        if not ok and r: print(r.text[:200])
        time.sleep(0.3)

# ── Format helpers ─────────────────────────────────────────────────────────────
def _repeat_cell(sid, r0, r1, c0, c1, bold=False, bg=None, fg=None, fs=11,
                 align='LEFT', fmt_type=None):
    tf = {'fontFamily': FONT, 'fontSize': fs, 'bold': bold}
    if fg: tf['foregroundColor'] = fg
    fmt = {'textFormat': tf, 'horizontalAlignment': align}
    if bg: fmt['backgroundColor'] = bg
    if fmt_type == 'pct':   fmt['numberFormat'] = {'type': 'NUMBER', 'pattern': '0.0%'}
    elif fmt_type == 'num': fmt['numberFormat'] = {'type': 'NUMBER', 'pattern': '#,##0'}
    elif fmt_type == 'num1':fmt['numberFormat'] = {'type': 'NUMBER', 'pattern': '#,##0.0'}
    fields = ['textFormat','horizontalAlignment','backgroundColor','numberFormat']
    return {'repeatCell': {
        'range': {'sheetId': sid, 'startRowIndex': r0, 'endRowIndex': r1,
                  'startColumnIndex': c0, 'endColumnIndex': c1},
        'cell': {'userEnteredFormat': fmt},
        'fields': ','.join(f'userEnteredFormat.{f}' for f in fields)}}

def fmt_row(sid, r, c0, c1, **kw):
    """Format a single row r (0-based)."""
    return _repeat_cell(sid, r, r+1, c0, c1, **kw)

def fmt_data_rows(sid, c0, c1, **kw):
    """Format all data rows (Jan 1 – Dec 31) in columns c0..c1."""
    return _repeat_cell(sid, DATA_R0, DATA_R1, c0, c1, **kw)

def col_w(sid, c, px):
    return {'updateDimensionProperties': {
        'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                  'startIndex': c, 'endIndex': c+1},
        'properties': {'pixelSize': px}, 'fields': 'pixelSize'}}

def freeze(sid, rows=2, cols=0):
    return {'updateSheetProperties': {
        'properties': {'sheetId': sid,
                       'gridProperties': {'frozenRowCount': rows, 'frozenColumnCount': cols}},
        'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}}

def merge(sid, r0, r1, c0, c1):
    return {'mergeCells': {
        'range': {'sheetId': sid, 'startRowIndex': r0, 'endRowIndex': r1,
                  'startColumnIndex': c0, 'endColumnIndex': c1},
        'mergeType': 'MERGE_ALL'}}

def cond_fmt(sid, r0, r1, c0, c1, formula, bg):
    return {'addConditionalFormatRule': {
        'rule': {
            'ranges': [{'sheetId': sid, 'startRowIndex': r0, 'endRowIndex': r1,
                        'startColumnIndex': c0, 'endColumnIndex': c1}],
            'booleanRule': {
                'condition': {'type': 'CUSTOM_FORMULA', 'values': [{'userEnteredValue': formula}]},
                'format': {'backgroundColor': bg}
            }
        }, 'index': 0}}

# ── Sheet builder ─────────────────────────────────────────────────────────────
NCOLS   = 10   # A–J
DATA_R0 = 2    # 0-based start of data rows (row 3 = Jan 1)
DATA_R1 = 367  # 0-based exclusive end (365 days → indices 2..366)
HEADERS = ['Дата','День','Выручка (с)','Нарастающий итог','% плана',
           'Норма/день','Откл. от нормы','Прогноз','Нужно в день','']

def build_values(title_suffix, plan, revenue_data=None, is_svod=False):
    """
    Строит список строк для листа.
    revenue_data: dict {date: float} — только для ЗБ.
    is_svod: True → C формулой из ЗБ + ОВИР.
    """
    rows = [[f'РОМАШКА — Дневной трекер 2026 | {title_suffix} | ПЛАН {plan:,} с/мес'] + [''] * (NCOLS-1),
            HEADERS]

    for m in range(1, 13):
        _, last = monthrange(2026, m)
        for d in range(1, last + 1):
            dt       = datetime.date(2026, m, d)
            row_idx  = len(rows) + 1   # 1-based sheet row

            date_str = dt.strftime('%d.%m.%Y')
            day_name = DAYS_RU[dt.weekday()]

            # C: revenue
            if is_svod:
                c_val = f"=IF(AND('ЗБ'!C{row_idx}=\"\",'ОВИР'!C{row_idx}=\"\"),\"\",IFERROR('ЗБ'!C{row_idx},0)+IFERROR('ОВИР'!C{row_idx},0))"
            elif revenue_data and dt in revenue_data:
                c_val = revenue_data[dt]
            else:
                c_val = ''

            # D: cumulative within month
            if len(rows) == 2:   # first data row (Jan 1 = row 3)
                d_val = f'=IF(C{row_idx}="","",C{row_idx})'
            else:
                prev = row_idx - 1
                d_val = f'=IF(C{row_idx}="","",IF(MONTH(A{row_idx})=MONTH(A{prev}),D{prev}+C{row_idx},C{row_idx}))'

            # E: % of plan
            e_val = f'=IFERROR(D{row_idx}/{plan},"")'

            # F: daily norm (plan / days in month)
            f_val = f'=IFERROR({plan}/DAY(EOMONTH(A{row_idx},0)),"")'

            # G: deviation from norm
            g_val = f'=IF(C{row_idx}="","",(C{row_idx}-F{row_idx}))'

            # H: month forecast at current pace
            h_val = f'=IFERROR(D{row_idx}/DAY(A{row_idx})*DAY(EOMONTH(A{row_idx},0)),"")'

            # I: needed per remaining day (blank for past months)
            i_val = (f'=IFERROR(IF(EOMONTH(A{row_idx},0)<TODAY(),"",({plan}-D{row_idx})'
                     f'/MAX(1,DAY(EOMONTH(A{row_idx},0))-DAY(A{row_idx})+1)),"")')

            rows.append([date_str, day_name, c_val, d_val, e_val, f_val, g_val, h_val, i_val, ''])

    return rows

def build_months_values(title):
    """Лист Месяцы: сводка по месяцам из ЗБ и ОВИР."""
    rows = [
        [title] + [''] * 8,
        ['Месяц','План ЗБ','Выручка ЗБ','% ЗБ','План ОВИР','Выручка ОВИР','% ОВИР','СВОД',
         '% СВОД']
    ]
    # For each month, find the last day row in ЗБ to read cumulative
    # Row 3 in ЗБ/ОВИР = Jan 1; last row of each month = row (2 + cumulative_days)
    day_offset = 2  # 2 header rows
    for m in range(1, 13):
        _, last = monthrange(2026, m)
        last_row = day_offset + last  # row of last day of this month
        month_name = MONTHS_RU[m]
        zb_rev  = f"='ЗБ'!D{last_row}"
        ov_rev  = f"='ОВИР'!D{last_row}"
        zb_pct  = f"=IFERROR({zb_rev}/{PLAN_ZB},\"\")"
        ov_pct  = f"=IFERROR({ov_rev}/{PLAN_OVIR},\"\")"
        svod    = f"=IFERROR({zb_rev}+{ov_rev},\"\")"
        svod_pct= f"=IFERROR(({zb_rev}+{ov_rev})/{PLAN_SVOD},\"\")"
        rows.append([month_name, PLAN_ZB, zb_rev, zb_pct,
                     PLAN_OVIR, ov_rev, ov_pct, svod, svod_pct])
        day_offset += last
    return rows

# ── Format for tracker sheet ───────────────────────────────────────────────────
DR = DATA_R0 + 1  # 1-based row number of first data row (= 3)

def format_tracker(sid):
    reqs = [
        freeze(sid, rows=2, cols=2),
        col_w(sid, 0,  95), col_w(sid, 1,  45), col_w(sid, 2, 105),
        col_w(sid, 3, 120), col_w(sid, 4,  80), col_w(sid, 5, 100),
        col_w(sid, 6,  95), col_w(sid, 7, 110), col_w(sid, 8, 105),
        # Row 1: title
        fmt_row(sid, 0, 0, NCOLS, bold=True, bg=C_DARK, fg=C_WHITE, fs=13, align='CENTER'),
        merge(sid, 0, 1, 0, NCOLS),
        # Row 2: headers
        fmt_row(sid, 1, 0, NCOLS, bold=True, bg=C_SUB, fg=C_WHITE, fs=11, align='CENTER'),
        # Data rows: base formatting (ranges over ALL 365 rows)
        fmt_data_rows(sid, 0, 2, fs=11, align='LEFT'),                    # A,B: date, day
        fmt_data_rows(sid, 2, 3, fs=11, align='RIGHT', fmt_type='num'),   # C: revenue
        fmt_data_rows(sid, 3, 4, fs=11, align='RIGHT', fmt_type='num'),   # D: cumulative
        fmt_data_rows(sid, 4, 5, fs=11, align='RIGHT', fmt_type='pct'),   # E: % plan
        fmt_data_rows(sid, 5, 6, fs=11, align='RIGHT', fmt_type='num1'),  # F: norm/day
        fmt_data_rows(sid, 6, 7, fs=11, align='RIGHT', fmt_type='num'),   # G: deviation
        fmt_data_rows(sid, 7, 8, fs=11, align='RIGHT', fmt_type='num'),   # H: forecast
        fmt_data_rows(sid, 8, 9, fs=11, align='RIGHT', fmt_type='num'),   # I: needed/day
    ]
    # Conditional: weekends → light purple (entire row)
    reqs.append(cond_fmt(sid, DATA_R0, DATA_R1, 0, NCOLS,
                         f'=WEEKDAY($A{DR},2)>=6', C_WEEKEND))
    # Conditional: today → gold (entire row)
    reqs.append(cond_fmt(sid, DATA_R0, DATA_R1, 0, NCOLS,
                         f'=$A{DR}=TODAY()', C_GOLD))
    # Conditional: deviation > 0 → green (col G)
    reqs.append(cond_fmt(sid, DATA_R0, DATA_R1, 6, 7,
                         f'=AND($G{DR}<>"",$G{DR}>0)', C_GREEN))
    # Conditional: deviation < 0 → red (col G)
    reqs.append(cond_fmt(sid, DATA_R0, DATA_R1, 6, 7,
                         f'=AND($G{DR}<>"",$G{DR}<0)', C_RED))
    return reqs

def format_months(sid):
    reqs = [
        freeze(sid, rows=2, cols=1),
        col_w(sid, 0, 110), col_w(sid, 1, 90), col_w(sid, 2, 110),
        col_w(sid, 3, 80),  col_w(sid, 4, 90), col_w(sid, 5, 110),
        col_w(sid, 6, 80),  col_w(sid, 7, 110),col_w(sid, 8, 80),
        fmt_row(sid, 0, 0, 9, bold=True, bg=C_DARK, fg=C_WHITE, fs=13, align='CENTER'),
        merge(sid, 0, 1, 0, 9),
        fmt_row(sid, 1, 0, 9, bold=True, bg=C_SUB,  fg=C_WHITE, fs=11, align='CENTER'),
    ]
    for i in range(12):
        r = i + 2
        reqs.append(fmt_row(sid, r, 0, 1, fs=11, bold=True, bg=C_GRAY))
        reqs.append(fmt_row(sid, r, 1, 9, fs=11, align='RIGHT', fmt_type='num'))
        reqs.append(fmt_row(sid, r, 3, 4, fs=11, align='RIGHT', fmt_type='pct'))
        reqs.append(fmt_row(sid, r, 6, 7, fs=11, align='RIGHT', fmt_type='pct'))
        reqs.append(fmt_row(sid, r, 8, 9, fs=11, align='RIGHT', fmt_type='pct'))
    return reqs

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print('Тянем данные из Poster...')
    daily_rev = pull_daily_revenue()

    s = get_session()
    print('\nСоздаём файл...')
    r = api_post(s, 'https://www.googleapis.com/drive/v3/files?supportsAllDrives=true',
                 {'name': 'Ромашка — Дневной трекер 2026',
                  'mimeType': 'application/vnd.google-apps.spreadsheet',
                  'parents': [FOLDER_ID]})
    ss_id = r.json()['id']
    print(f'ID: {ss_id}')

    # Get default sheet ID (retry: new file may need a moment)
    default_sid = None
    for attempt in range(5):
        time.sleep(2)
        r2 = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}?fields=sheets.properties', timeout=30)
        try:
            default_sid = r2.json()['sheets'][0]['properties']['sheetId']
            break
        except Exception:
            print(f'  retry get sheets {attempt+1}...')
    if default_sid is None:
        print('❌ Не удалось получить sheetId'); return

    # Create sheets
    r3 = api_post(s, f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate', {
        'requests': [
            {'updateSheetProperties': {'properties': {'sheetId': default_sid, 'title': 'ЗБ'},
                                       'fields': 'title'}},
            {'addSheet': {'properties': {'title': 'ОВИР',    'index': 1}}},
            {'addSheet': {'properties': {'title': 'Свод',    'index': 2}}},
            {'addSheet': {'properties': {'title': 'Месяцы',  'index': 3}}},
        ]
    })
    replies      = r3.json()['replies']
    ovir_sid     = replies[1]['addSheet']['properties']['sheetId']
    svod_sid     = replies[2]['addSheet']['properties']['sheetId']
    months_sid   = replies[3]['addSheet']['properties']['sheetId']
    print(f'Sheets: ЗБ={default_sid} ОВИР={ovir_sid} Свод={svod_sid} Месяцы={months_sid}')

    # ── ЗБ ──
    print('\n── ЗБ ──')
    zb_rows = build_values('ЗБ (Лохути 11)', PLAN_ZB, revenue_data=daily_rev)
    write_values(s, ss_id, 'ЗБ', zb_rows)
    time.sleep(1)
    apply_fmt(s, ss_id, format_tracker(default_sid), 'ЗБ')

    # ── ОВИР ──
    print('\n── ОВИР ──')
    ovir_rows = build_values('ОВИР (Турсунзода)', PLAN_OVIR)
    write_values(s, ss_id, 'ОВИР', ovir_rows)
    time.sleep(1)
    apply_fmt(s, ss_id, format_tracker(ovir_sid), 'ОВИР')

    # ── Свод ──
    print('\n── Свод ──')
    svod_rows = build_values('СВОД (ЗБ + ОВИР)', PLAN_SVOD, is_svod=True)
    write_values(s, ss_id, 'Свод', svod_rows)
    time.sleep(1)
    apply_fmt(s, ss_id, format_tracker(svod_sid), 'Свод')

    # ── Месяцы ──
    print('\n── Месяцы ──')
    months_rows = build_months_values('РОМАШКА — Выручка по месяцам 2026')
    write_values(s, ss_id, 'Месяцы', months_rows)
    time.sleep(1)
    apply_fmt(s, ss_id, format_months(months_sid), 'Месяцы')

    url = f'https://docs.google.com/spreadsheets/d/{ss_id}/edit'
    print(f'\n✅ Готово: {url}')
    print(f'\nID для update_daily_tracker.py:\nTRACKER_SS_ID = "{ss_id}"')
    return ss_id

if __name__ == '__main__':
    main()
