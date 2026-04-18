#!/usr/bin/env python3
"""
Аналитический отчёт Poster → Google Sheets.
Листы: KPI, Маржинальность, Аналитика продаж, Поставки.
Использование: python3 scripts/poster_analytics.py [YYYY-MM]
"""

import sys, os, json, urllib.request, urllib.parse
from datetime import datetime, timedelta
from calendar import monthrange
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))

TOKEN    = "398711:8746917c4a23ea897774040e039dfb76"
BASE_URL = "https://joinposter.com/api"
CREDENTIALS = os.path.join(os.path.dirname(__file__), "credentials", "romashka-drive.json")
FOLDER_ID   = "14NnVXa9k1h0dyS-vNch61A3-aSpJG_Jn"

DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

# ── Poster API ─────────────────────────────────────────────────────────────────
def api(method, params=None):
    p = {"token": TOKEN}
    if params:
        p.update(params)
    url = f"{BASE_URL}/{method}?{urllib.parse.urlencode(p)}"
    req = urllib.request.Request(url, headers={"User-Agent": "RomashkaBot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"⚠️  {method}: {e}")
        return {"response": []}


# ── Google Sheets helpers ──────────────────────────────────────────────────────
CLR_DARK   = {"red": 0.18, "green": 0.31, "blue": 0.31}
CLR_MID    = {"red": 0.23, "green": 0.47, "blue": 0.47}
CLR_GREEN  = {"red": 0.85, "green": 0.94, "blue": 0.85}
CLR_RED    = {"red": 0.99, "green": 0.90, "blue": 0.87}
CLR_YELLOW = {"red": 1.00, "green": 0.97, "blue": 0.82}
CLR_GREY   = {"red": 0.95, "green": 0.95, "blue": 0.95}
CLR_WHITE  = {"red": 1.0,  "green": 1.0,  "blue": 1.0}
CLR_WEEKEND= {"red": 0.93, "green": 0.93, "blue": 0.97}


def cv(v, bold=False, bg=None, num_fmt=None, align="LEFT", italic=False, fg=None, font_size=14):
    c = {}
    if isinstance(v, (int, float)):
        c["userEnteredValue"] = {"numberValue": v}
    elif isinstance(v, str) and v.startswith("="):
        c["userEnteredValue"] = {"formulaValue": v}
    else:
        c["userEnteredValue"] = {"stringValue": str(v) if v is not None else ""}
    fmt = {}
    tf = {"fontFamily": "Times New Roman", "fontSize": font_size}
    if bold:   tf["bold"] = True
    if italic: tf["italic"] = True
    if fg:     tf["foregroundColor"] = fg
    fmt["textFormat"] = tf
    if bg:     fmt["backgroundColor"] = bg
    if num_fmt: fmt["numberFormat"] = {"type": "NUMBER", "pattern": num_fmt}
    if align != "LEFT": fmt["horizontalAlignment"] = align
    c["userEnteredFormat"] = fmt
    return c


def hc(v, bg=None, align="CENTER"):
    return cv(v, bold=True, bg=bg or CLR_DARK, align=align,
              fg={"red": 1.0, "green": 1.0, "blue": 1.0}, font_size=18)


def mc(v, bg=None, bold=False):
    return cv(v, bold=bold, bg=bg, num_fmt='# ##0.00" с"', align="RIGHT")


def pc(v, bg=None, bold=False):
    return cv(f"{v:.1f}%", bold=bold, bg=bg, align="RIGHT")


def row(*cells):
    return {"values": list(cells)}


def get_session():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS,
        scopes=["https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"])
    return AuthorizedSession(creds)


def create_ss(session, title):
    r = session.post(
        "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"name": title,
                         "mimeType": "application/vnd.google-apps.spreadsheet",
                         "parents": [FOLDER_ID]}))
    return r.json()["id"]


def add_sheet(session, ss_id, title, idx):
    r = session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": [{"addSheet": {"properties": {"title": title, "index": idx}}}]}))
    return r.json()["replies"][0]["addSheet"]["properties"]["sheetId"]


def rename_sheet(session, ss_id, sid, title):
    session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": sid, "title": title}, "fields": "title"}}]}))


def write_rows(session, ss_id, sheet_name, rows):
    vals = []
    for r in rows:
        rv = []
        for c in r["values"]:
            uv = c.get("userEnteredValue", {})
            rv.append(uv.get("formulaValue", uv.get("numberValue", uv.get("stringValue", ""))))
        vals.append(rv)
    session.put(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/values/{sheet_name}!A1",
        headers={"Content-Type": "application/json"},
        params={"valueInputOption": "USER_ENTERED"},
        data=json.dumps({"values": vals}))


def batch_fmt(session, ss_id, requests):
    if requests:
        session.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"requests": requests}))


def col_w(sid, col, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS",
                  "startIndex": col, "endIndex": col + 1},
        "properties": {"pixelSize": px}, "fields": "pixelSize"}}


def freeze(sid, r=1, c=0):
    return {"updateSheetProperties": {
        "properties": {"sheetId": sid,
                       "gridProperties": {"frozenRowCount": r, "frozenColumnCount": c}},
        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}}


def merge(sid, r1, c1, r2, c2):
    return {"mergeCells": {"range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                                     "startColumnIndex": c1, "endColumnIndex": c2},
                           "mergeType": "MERGE_ALL"}}


# ── Лист 1: KPI ────────────────────────────────────────────────────────────────
def build_kpi(sid, month_ru, an, prev_an, supplies_total, _, last_day, year, month):
    c  = an["counters"]
    pc2 = prev_an["counters"] if prev_an else None

    def delta(cur, prev):
        if prev and float(prev) > 0:
            d = (float(cur) - float(prev)) / float(prev) * 100
            return f"{'▲' if d >= 0 else '▼'} {abs(d):.1f}%"
        return "—"

    rows = []
    rows.append(row(hc(f"KPI — {month_ru}", bg=CLR_DARK),
                    hc("Значение", bg=CLR_DARK, align="RIGHT"),
                    hc("vs пред. мес.", bg=CLR_DARK, align="RIGHT")))

    rows.append(row(cv("Выручка", bold=True, bg=CLR_GREEN),
                    mc(float(c["revenue"]), bg=CLR_GREEN, bold=True),
                    cv(delta(c["revenue"], pc2["revenue"] if pc2 else None),
                       bold=True, bg=CLR_GREEN, align="RIGHT")))

    rows.append(row(cv("Валовая прибыль", bold=True, bg=CLR_GREEN),
                    mc(float(c["profit"]), bg=CLR_GREEN, bold=True),
                    cv(delta(c["profit"], pc2["profit"] if pc2 else None),
                       bold=True, bg=CLR_GREEN, align="RIGHT")))

    margin = float(c["profit"]) / float(c["revenue"]) * 100 if float(c["revenue"]) else 0
    rows.append(row(cv("Маржа", bg=CLR_GREEN),
                    cv(f"{margin:.1f}%", bg=CLR_GREEN, align="RIGHT"),
                    cv("", bg=CLR_GREEN)))

    rows.append(row(cv("")))

    rows.append(row(cv("Средний чек"),
                    mc(float(c["average_receipt"])),
                    cv(delta(c["average_receipt"], pc2["average_receipt"] if pc2 else None), align="RIGHT")))

    rows.append(row(cv("Чеков (транзакций)"),
                    cv(int(c["transactions"]), align="RIGHT"),
                    cv(delta(c["transactions"], pc2["transactions"] if pc2 else None), align="RIGHT")))

    rows.append(row(cv("Посетителей"),
                    cv(int(c["visitors"]), align="RIGHT"),
                    cv(delta(c["visitors"], pc2["visitors"] if pc2 else None), align="RIGHT")))

    rows.append(row(cv("Среднее время в заведении"),
                    cv(f"{float(c['average_time']):.1f} мин", align="RIGHT"),
                    cv("")))

    rows.append(row(cv("")))

    days_cnt = len([x for x in an["data"] if float(x) > 0])
    daily_avg = float(c["revenue"]) / days_cnt if days_cnt else 0
    rows.append(row(cv("Дней работы"), cv(days_cnt, align="RIGHT"), cv("")))
    rows.append(row(cv("Выручка в день (среднее)"), mc(daily_avg), cv("")))
    rows.append(row(cv("Закупки за месяц"), mc(supplies_total), cv("")))

    reqs = [freeze(sid), col_w(sid, 0, 230), col_w(sid, 1, 150), col_w(sid, 2, 130)]
    return rows, reqs


# ── Лист 2: Маржинальность ────────────────────────────────────────────────────
def build_margin(sid, products, cat_names):
    rows = []
    rows.append(row(hc("Категория"), hc("Блюдо"), hc("Цена", align="RIGHT"),
                    hc("Себест.", align="RIGHT"), hc("Прибыль", align="RIGHT"),
                    hc("Маржа", align="RIGHT"), hc("Статус")))

    # Группировка по категориям
    by_cat = defaultdict(list)
    for p in products:
        prices = list(p.get("price", {}).values())
        price = int(prices[0]) / 100 if prices else 0
        cost  = int(p.get("cost", 0)) / 100
        profits = list(p.get("profit", {}).values())
        profit = int(profits[0]) / 100 if profits else price - cost
        margin = profit / price * 100 if price > 0 else 0
        cid = str(p.get("menu_category_id", "0"))
        by_cat[cid].append({
            "name": p["product_name"], "price": price,
            "cost": cost, "profit": profit, "margin": margin,
            "out": p.get("out", 0)
        })

    for cid, dishes in sorted(by_cat.items(), key=lambda x: cat_names.get(x[0], "я")):
        cat = cat_names.get(cid, f"Категория {cid}")
        dishes_sorted = sorted(dishes, key=lambda x: -x["margin"])
        for i, d in enumerate(dishes_sorted):
            m = d["margin"]
            bg = CLR_GREEN if m >= 60 else (CLR_YELLOW if m >= 30 else CLR_RED) if d["price"] > 0 else None
            status = "⭐ Высокая" if m >= 60 else ("✅ Норм" if m >= 30 else ("⚠️  Низкая" if d["price"] > 0 else "❓ Нет цены"))
            rows.append(row(
                cv(cat if i == 0 else "", bold=(i == 0)),
                cv(d["name"], bg=bg),
                mc(d["price"], bg=bg),
                mc(d["cost"], bg=bg),
                mc(d["profit"], bg=bg),
                pc(m, bg=bg, bold=True),
                cv(status, bg=bg),
            ))
        rows.append(row(cv("")))

    reqs = [freeze(sid), col_w(sid, 0, 150), col_w(sid, 1, 200),
            col_w(sid, 2, 90), col_w(sid, 3, 90),
            col_w(sid, 4, 90), col_w(sid, 5, 80), col_w(sid, 6, 110)]
    return rows, reqs


# ── Лист 3: Аналитика продаж ──────────────────────────────────────────────────
def build_sales(sid, an, year, month):
    _, last_day = monthrange(year, month)
    rows = []

    # По дням
    rows.append(row(hc("По дням")))
    rows.append(row(hc("Дата"), hc("День"), hc("Выручка", align="RIGHT"),
                    hc(""), hc("")))
    daily = an["data"]
    for i, val in enumerate(daily):
        dt = datetime(year, month, i + 1)
        wday = dt.weekday()
        bg = CLR_WEEKEND if wday >= 5 else None
        rows.append(row(
            cv(dt.strftime("%d.%m"), bg=bg),
            cv(DAYS_RU[wday], bg=bg),
            mc(float(val), bg=bg, bold=(wday >= 5)),
            cv(""), cv("")
        ))

    rows.append(row(cv("")))

    # По часам
    rows.append(row(hc("По часам", bg=CLR_MID), hc("Выручка", bg=CLR_MID, align="RIGHT"),
                    hc("% от дня", bg=CLR_MID, align="RIGHT"), hc(""), hc("")))
    hourly = an["data_hourly"]
    total_hour = sum(float(x) for x in hourly if x != 0)
    for h, val in enumerate(hourly):
        v = float(val)
        if v == 0:
            continue
        pct = v / total_hour * 100 if total_hour else 0
        rows.append(row(cv(f"{h:02d}:00–{h+1:02d}:00"), mc(v), pc(pct),
                        cv(""), cv("")))

    rows.append(row(cv("")))

    # По дням недели
    rows.append(row(hc("По дням недели", bg=CLR_MID),
                    hc("Выручка", bg=CLR_MID, align="RIGHT"),
                    hc("% от недели", bg=CLR_MID, align="RIGHT"), hc(""), hc("")))
    weekday = an["data_weekday"]
    total_wday = sum(float(x) for x in weekday)
    for i, val in enumerate(weekday):
        v = float(val)
        pct = v / total_wday * 100 if total_wday else 0
        bg = CLR_WEEKEND if i >= 5 else None
        rows.append(row(cv(DAYS_RU[i], bg=bg), mc(v, bg=bg, bold=(i >= 5)),
                        pc(pct, bg=bg), cv(""), cv("")))

    reqs = [freeze(sid), col_w(sid, 0, 140), col_w(sid, 1, 90),
            col_w(sid, 2, 120), col_w(sid, 3, 20), col_w(sid, 4, 20)]
    return rows, reqs


# ── Лист 4: Поставки ──────────────────────────────────────────────────────────
def build_supplies(sid, supplies, year, month):
    rows = []
    rows.append(row(hc("Поставщик"), hc("Сумма", align="RIGHT"),
                    hc("% закупок", align="RIGHT"), hc("Поставок", align="RIGHT"),
                    hc("Ср. поставка", align="RIGHT")))

    by_sup = defaultdict(lambda: {"total": 0.0, "count": 0})
    for s in supplies:
        name = s["supplier_name"] or "Без поставщика"
        amt  = int(s["supply_sum"]) / 100
        by_sup[name]["total"] += amt
        by_sup[name]["count"] += 1

    total_sup = sum(v["total"] for v in by_sup.values())
    for name, data in sorted(by_sup.items(), key=lambda x: -x[1]["total"]):
        pct = data["total"] / total_sup * 100 if total_sup else 0
        avg = data["total"] / data["count"] if data["count"] else 0
        rows.append(row(
            cv(name),
            mc(data["total"], bold=True),
            pc(pct),
            cv(data["count"], align="RIGHT"),
            mc(avg),
        ))

    rows.append(row(cv("")))
    rows.append(row(cv("ИТОГО", bold=True, bg=CLR_GREY),
                    mc(total_sup, bg=CLR_GREY, bold=True),
                    pc(100.0, bg=CLR_GREY, bold=True),
                    cv(sum(v["count"] for v in by_sup.values()), align="RIGHT", bg=CLR_GREY),
                    cv("", bg=CLR_GREY)))

    reqs = [freeze(sid), col_w(sid, 0, 220), col_w(sid, 1, 130),
            col_w(sid, 2, 110), col_w(sid, 3, 90), col_w(sid, 4, 130)]
    return rows, reqs


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg:
        year, month = int(arg.split("-")[0]), int(arg.split("-")[1])
    else:
        now = datetime.now()
        year, month = now.year, now.month

    _, last_day = monthrange(year, month)
    ds = f"{year}{month:02d}01"
    de = f"{year}{month:02d}{last_day:02d}"
    month_ru = datetime(year, month, 1).strftime("%B %Y")

    # Предыдущий месяц для сравнения
    prev_dt = datetime(year, month, 1) - timedelta(days=1)
    prev_year, prev_month = prev_dt.year, prev_dt.month
    _, prev_last = monthrange(prev_year, prev_month)
    prev_ds = f"{prev_year}{prev_month:02d}01"
    prev_de = f"{prev_year}{prev_month:02d}{prev_last:02d}"

    print(f"📊 Загружаю данные за {month_ru}...")
    an = api("dash.getAnalytics", {"dateFrom": ds, "dateTo": de}).get("response", {})
    print(f"   Выручка: {float(an.get('counters', {}).get('revenue', 0)):,.0f} с")

    print("   Загружаю предыдущий месяц для сравнения...")
    prev_an = api("dash.getAnalytics", {"dateFrom": prev_ds, "dateTo": prev_de}).get("response")

    print("   Загружаю меню...")
    products = api("menu.getProducts").get("response", [])
    cats_raw = api("menu.getCategories").get("response", [])
    cat_names = {str(c["category_id"]): c["category_name"] for c in cats_raw}

    print("   Загружаю поставки...")
    supplies = api("storage.getSupplies", {"dateFrom": ds, "dateTo": de}).get("response", [])
    supplies_total = sum(int(s["supply_sum"]) / 100 for s in supplies)

    session = get_session()
    title = f"Ромашка — аналитика {month_ru}"
    print(f"\n📋 Создаю таблицу '{title}'...")

    ss_id = create_ss(session, title)
    r = session.get(f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}?fields=sheets.properties")
    first_sid = r.json()["sheets"][0]["properties"]["sheetId"]

    rename_sheet(session, ss_id, first_sid, "KPI")
    margin_sid  = add_sheet(session, ss_id, "Маржинальность", 1)
    sales_sid   = add_sheet(session, ss_id, "Аналитика продаж", 2)
    supply_sid  = add_sheet(session, ss_id, "Поставки", 3)

    kpi_rows,    kpi_reqs    = build_kpi(first_sid, month_ru, an, prev_an,
                                          supplies_total, None, last_day, year, month)
    margin_rows, margin_reqs = build_margin(margin_sid, products, cat_names)
    sales_rows,  sales_reqs  = build_sales(sales_sid, an, year, month)
    supply_rows, supply_reqs = build_supplies(supply_sid, supplies, year, month)

    write_rows(session, ss_id, "KPI",              kpi_rows)
    write_rows(session, ss_id, "Маржинальность",   margin_rows)
    write_rows(session, ss_id, "Аналитика продаж", sales_rows)
    write_rows(session, ss_id, "Поставки",         supply_rows)

    batch_fmt(session, ss_id, kpi_reqs + margin_reqs + sales_reqs + supply_reqs)

    url = f"https://docs.google.com/spreadsheets/d/{ss_id}/edit"
    print(f"\n✅ Готово: {url}")
    return url


if __name__ == "__main__":
    main()
