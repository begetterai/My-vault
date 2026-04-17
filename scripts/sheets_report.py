#!/usr/bin/env python3
"""
Создать Google Sheets отчёт за месяц из данных Poster.
Использование: python3 scripts/sheets_report.py [YYYY-MM]
"""

import sys, os, json
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from poster_report import (
    get_categories, get_accounts, get_transactions, analyze_transactions, SKIP_CATEGORIES
)

CREDENTIALS = os.path.join(os.path.dirname(__file__), "credentials", "romashka-drive.json")
FOLDER_ID = "14NnVXa9k1h0dyS-vNch61A3-aSpJG_Jn"

# ── Цвета ─────────────────────────────────────────────────────────────────────
CLR_HEADER   = {"red": 0.18, "green": 0.31, "blue": 0.31}  # тёмно-зелёный
CLR_INCOME   = {"red": 0.85, "green": 0.94, "blue": 0.85}  # светло-зелёный
CLR_EXPENSE  = {"red": 0.99, "green": 0.90, "blue": 0.87}  # светло-красный
CLR_TOTAL    = {"red": 0.95, "green": 0.95, "blue": 0.95}  # серый
CLR_PROFIT   = {"red": 0.78, "green": 0.92, "blue": 0.78}  # зелёный
CLR_WEEK_HDR = {"red": 0.23, "green": 0.47, "blue": 0.47}
WHITE        = {"red": 1.0,  "green": 1.0,  "blue": 1.0}


def get_session():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS,
        scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ],
    )
    return AuthorizedSession(creds)


# ── Хелперы Sheets API ────────────────────────────────────────────────────────
def cell(v, bold=False, bg=None, fmt=None, align="LEFT", wrap=False):
    c = {"userEnteredValue": {}}
    if isinstance(v, (int, float)):
        c["userEnteredValue"]["numberValue"] = v
    elif isinstance(v, str) and v.startswith("="):
        c["userEnteredValue"]["formulaValue"] = v
    else:
        c["userEnteredValue"]["stringValue"] = str(v) if v is not None else ""
    f = {}
    if bold:
        f["textFormat"] = {"bold": True}
    if bg:
        f["backgroundColor"] = bg
    if fmt:
        f["numberFormat"] = {"type": "NUMBER", "pattern": fmt}
    if align != "LEFT":
        f["horizontalAlignment"] = align
    if wrap:
        f["wrapStrategy"] = "WRAP"
    if f:
        c["userEnteredFormat"] = f
    return c


def hcell(v, bg=None, align="CENTER"):
    return cell(v, bold=True, bg=bg or CLR_HEADER, align=align)


def row(*cells):
    return {"values": list(cells)}


def bg_row(cells_list, bg):
    return {"values": [dict(c, userEnteredFormat={**c.get("userEnteredFormat", {}), "backgroundColor": bg}) for c in cells_list]}


def money_cell(v, bg=None, bold=False):
    c = cell(v, bold=bold, bg=bg, fmt='# ##0.00" с"', align="RIGHT")
    return c


def pct_cell(v, bg=None, bold=False):
    return cell(f"{v:.1f}%", bold=bold, bg=bg, align="RIGHT")


def color_cell(v, bold=False, color=None):
    c = cell(v, bold=bold)
    if color:
        c.setdefault("userEnteredFormat", {})["textFormat"] = {"bold": bold, "foregroundColor": color}
    return c


# ── Форматирование диапазона ───────────────────────────────────────────────────
def fmt_range(sid, r1, c1, r2, c2, **fmt_kwargs):
    return {
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                      "startColumnIndex": c1, "endColumnIndex": c2},
            "cell": {"userEnteredFormat": fmt_kwargs},
            "fields": "userEnteredFormat(" + ",".join(fmt_kwargs.keys()) + ")",
        }
    }


def col_width(sid, col, px):
    return {
        "updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": col, "endIndex": col + 1},
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    }


def freeze(sid, rows=1, cols=0):
    return {
        "updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": rows, "frozenColumnCount": cols}},
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
        }
    }


# ── Данные ─────────────────────────────────────────────────────────────────────
def build_data(year, month):
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    ds = f"{year}{month:02d}01"
    de = f"{year}{month:02d}{last_day:02d}"

    cats = get_categories()
    accounts = get_accounts()
    txns = get_transactions(ds, de)
    income, expenses, by_day = analyze_transactions(txns, cats)

    total_income = sum(income.values())
    total_expenses = sum(expenses.values())
    gross = total_income - total_expenses

    # По неделям
    weeks = defaultdict(lambda: {"income": 0.0, "expense": 0.0, "days": []})
    for i in range(last_day):
        d = datetime(year, month, i + 1)
        wk = d.strftime("%V")
        key = f"W{wk}"
        ds_day = d.strftime("%Y-%m-%d")
        info = by_day.get(ds_day, {"income": 0.0, "expense": 0.0})
        weeks[key]["income"] += info["income"]
        weeks[key]["expense"] += info["expense"]
        weeks[key]["days"].append(ds_day)

    return {
        "income": income,
        "expenses": expenses,
        "by_day": by_day,
        "weeks": weeks,
        "accounts": accounts,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "gross": gross,
        "year": year,
        "month": month,
        "last_day": last_day,
    }


# ── Лист 1: P&L ───────────────────────────────────────────────────────────────
def build_pl_sheet(d, sid):
    rows = []
    month_ru = datetime(d["year"], d["month"], 1).strftime("%B %Y")

    rows.append(row(hcell(f"P&L — {month_ru}", bg=CLR_HEADER),
                    hcell("Сумма", bg=CLR_HEADER, align="RIGHT"),
                    hcell("% выручки", bg=CLR_HEADER, align="RIGHT")))

    ti, te, gr = d["total_income"], d["total_expenses"], d["gross"]

    rows.append(row(cell("Выручка", bold=True, bg=CLR_INCOME),
                    money_cell(ti, bg=CLR_INCOME, bold=True),
                    pct_cell(100.0, bg=CLR_INCOME, bold=True)))
    rows.append(row(cell("")))

    rows.append(row(cell("Расходы", bold=True)))
    for cat, amt in sorted(d["expenses"].items(), key=lambda x: -x[1]):
        pct = amt / ti * 100 if ti else 0
        rows.append(row(cell(f"  {cat}", bg=CLR_EXPENSE),
                        money_cell(amt, bg=CLR_EXPENSE),
                        pct_cell(pct, bg=CLR_EXPENSE)))

    rows.append(row(cell("Итого расходов", bold=True, bg=CLR_TOTAL),
                    money_cell(te, bg=CLR_TOTAL, bold=True),
                    pct_cell(te / ti * 100 if ti else 0, bg=CLR_TOTAL, bold=True)))
    rows.append(row(cell("")))
    rows.append(row(cell("Валовая прибыль", bold=True, bg=CLR_PROFIT),
                    money_cell(gr, bg=CLR_PROFIT, bold=True),
                    pct_cell(gr / ti * 100 if ti else 0, bg=CLR_PROFIT, bold=True)))
    rows.append(row(cell("")))

    # Счета
    rows.append(row(hcell("Счёт", bg=CLR_WEEK_HDR),
                    hcell("Остаток", bg=CLR_WEEK_HDR, align="RIGHT"),
                    cell("")))
    for a in d["accounts"].values():
        bal = a["balance"]
        bg = CLR_EXPENSE if bal < 0 else None
        rows.append(row(cell(a["name"], bg=bg),
                        money_cell(bal, bg=bg, bold=bal < 0),
                        cell("")))

    data = [{"range": "P&L!A1", "values": [[c.get("userEnteredValue", {}).get("stringValue",
             c.get("userEnteredValue", {}).get("numberValue", "")) for c in r["values"]] for r in rows]}]

    requests = [
        freeze(sid, rows=1),
        col_width(sid, 0, 260),
        col_width(sid, 1, 130),
        col_width(sid, 2, 100),
    ]
    return rows, requests


# ── Лист 2: По дням ────────────────────────────────────────────────────────────
def build_days_sheet(d, sid):
    rows = []
    rows.append(row(hcell("Дата"), hcell("Доходы", align="RIGHT"),
                    hcell("Расходы", align="RIGHT"), hcell("Прибыль", align="RIGHT"),
                    hcell("Накопит.", align="RIGHT")))

    cumulative = 0.0
    for i in range(d["last_day"]):
        dt = datetime(d["year"], d["month"], i + 1)
        ds = dt.strftime("%Y-%m-%d")
        info = d["by_day"].get(ds, {"income": 0.0, "expense": 0.0})
        inc = info["income"]
        exp = info["expense"]
        net = inc - exp
        cumulative += net
        wday = dt.weekday()
        bg = {"red": 0.93, "green": 0.93, "blue": 0.97} if wday >= 5 else None
        rows.append(row(
            cell(dt.strftime("%d.%m %a"), bg=bg),
            money_cell(inc, bg=bg),
            money_cell(exp, bg=bg),
            money_cell(net, bg=bg, bold=(net < 0)),
            money_cell(cumulative, bg=bg),
        ))

    requests = [
        freeze(sid, rows=1),
        col_width(sid, 0, 110),
        col_width(sid, 1, 120),
        col_width(sid, 2, 120),
        col_width(sid, 3, 120),
        col_width(sid, 4, 130),
    ]
    return rows, requests


# ── Лист 3: По неделям ─────────────────────────────────────────────────────────
def build_weeks_sheet(d, sid):
    rows = []
    rows.append(row(hcell("Неделя"), hcell("Доходы", align="RIGHT"),
                    hcell("Расходы", align="RIGHT"), hcell("Прибыль", align="RIGHT"),
                    hcell("Маржа", align="RIGHT"), hcell("Δ vs пред. нед.", align="RIGHT")))

    week_list = sorted(d["weeks"].items())
    prev_profit = None
    for wk, wdata in week_list:
        inc = wdata["income"]
        exp = wdata["expense"]
        net = inc - exp
        margin = net / inc * 100 if inc else 0
        delta = net - prev_profit if prev_profit is not None else None
        delta_cell = money_cell(delta, bold=(delta is not None and delta < 0)) if delta is not None else cell("—", align="RIGHT")
        rows.append(row(
            cell(wk, bold=True),
            money_cell(inc),
            money_cell(exp),
            money_cell(net, bold=True),
            pct_cell(margin),
            delta_cell,
        ))
        prev_profit = net

    rows.append(row(cell("")))
    rows.append(row(
        cell("ИТОГО", bold=True, bg=CLR_TOTAL),
        money_cell(d["total_income"], bg=CLR_TOTAL, bold=True),
        money_cell(d["total_expenses"], bg=CLR_TOTAL, bold=True),
        money_cell(d["gross"], bg=CLR_TOTAL, bold=True),
        pct_cell(d["gross"] / d["total_income"] * 100 if d["total_income"] else 0, bg=CLR_TOTAL, bold=True),
        cell("", bg=CLR_TOTAL),
    ))

    requests = [
        freeze(sid, rows=1),
        col_width(sid, 0, 90),
        col_width(sid, 1, 130),
        col_width(sid, 2, 130),
        col_width(sid, 3, 130),
        col_width(sid, 4, 90),
        col_width(sid, 5, 140),
    ]
    return rows, requests


# ── Создание таблицы ───────────────────────────────────────────────────────────
def create_spreadsheet(session, title):
    r = session.post(
        "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "name": title,
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [FOLDER_ID],
        }),
    )
    return r.json()["id"]


def write_sheet(session, sheet_id, sheet_name, rows):
    values = []
    for r in rows:
        row_vals = []
        for c in r["values"]:
            uv = c.get("userEnteredValue", {})
            row_vals.append(
                uv.get("formulaValue", uv.get("numberValue", uv.get("stringValue", "")))
            )
        values.append(row_vals)

    session.put(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{sheet_name}!A1",
        headers={"Content-Type": "application/json"},
        params={"valueInputOption": "USER_ENTERED"},
        data=json.dumps({"values": values}),
    )


def batch_format(session, sheet_id, requests):
    if not requests:
        return
    session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": requests}),
    )


def add_sheet(session, sheet_id, title, sheet_index):
    r = session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": [{"addSheet": {"properties": {"title": title, "index": sheet_index}}}]}),
    )
    return r.json()["replies"][0]["addSheet"]["properties"]["sheetId"]


def rename_sheet(session, sheet_id, old_sid, title):
    session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": old_sid, "title": title},
            "fields": "title"
        }}]}),
    )


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg:
        year, month = int(arg.split("-")[0]), int(arg.split("-")[1])
    else:
        now = datetime.now()
        year, month = now.year, now.month

    month_label = datetime(year, month, 1).strftime("%Y-%m")
    month_ru = datetime(year, month, 1).strftime("%B %Y")
    title = f"Ромашка — отчёт {month_ru}"

    print(f"📊 Загрузка данных за {month_ru}...")
    d = build_data(year, month)
    print(f"   Выручка: {d['total_income']:,.0f} с | Расходы: {d['total_expenses']:,.0f} с | Прибыль: {d['gross']:,.0f} с")

    session = get_session()

    print("📋 Создаю таблицу в Google Drive...")
    ss_id = create_spreadsheet(session, title)

    # Получить ID первого листа
    r = session.get(f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}?fields=sheets.properties")
    first_sid = r.json()["sheets"][0]["properties"]["sheetId"]

    # Переименовать Sheet1 → P&L
    rename_sheet(session, ss_id, first_sid, "P&L")

    # Добавить листы
    days_sid  = add_sheet(session, ss_id, "По дням",   1)
    weeks_sid = add_sheet(session, ss_id, "По неделям", 2)

    # Записать данные
    pl_rows,    pl_reqs    = build_pl_sheet(d, first_sid)
    days_rows,  days_reqs  = build_days_sheet(d, days_sid)
    weeks_rows, weeks_reqs = build_weeks_sheet(d, weeks_sid)

    write_sheet(session, ss_id, "P&L",        pl_rows)
    write_sheet(session, ss_id, "По дням",    days_rows)
    write_sheet(session, ss_id, "По неделям", weeks_rows)

    # Форматирование
    batch_format(session, ss_id, pl_reqs + days_reqs + weeks_reqs)

    url = f"https://docs.google.com/spreadsheets/d/{ss_id}/edit"
    print(f"\n✅ Таблица готова: {url}")
    return url


if __name__ == "__main__":
    main()
