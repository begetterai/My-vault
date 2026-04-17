#!/usr/bin/env python3
"""
Poster → Vault: автоматический финансовый отчёт
Использование:
  python3 poster_report.py           # отчёт за текущую неделю
  python3 poster_report.py week      # отчёт за текущую неделю
  python3 poster_report.py month     # отчёт за текущий месяц
  python3 poster_report.py day       # отчёт за сегодня
"""

import urllib.request
import urllib.parse
import json
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

# ── Конфиг ──────────────────────────────────────────────────────────────────
TOKEN = "398711:8746917c4a23ea897774040e039dfb76"
BASE_URL = "https://joinposter.com/api"
VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(VAULT, "1-Projects", "romashka", "finance", "reports")

# Локализация системных категорий
CAT_NAMES = {
    "book_category_action_actualization": "Актуализация",
    "book_category_action_banking_services": "Банковские услуги",
    "book_category_action_utility_bills": "Коммунальные",
    "book_category_action_water_supplies": "Водоснабжение",
    "book_category_action_waste_disposal": "Вывоз мусора",
    "book_category_action_electricity": "Электричество",
    "book_category_action_marketing": "Маркетинг",
    "book_category_action_ewallets": "Электронные переводы",
    "book_category_action_supplies": "Поставки",
    "book_category_action_household_expenses": "Хозяйственные расходы",
}

# Категории которые НЕ входят в P&L (внутренние переводы)
SKIP_CATEGORIES = {"Переводы", "Внесения в кассу", "Выплаты дивидентов", "Инвестиции"}

# ── API ──────────────────────────────────────────────────────────────────────
def api_get(method, params=None):
    if params is None:
        params = {}
    params["token"] = TOKEN
    url = f"{BASE_URL}/{method}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "RomashkaBot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"⚠️  API error [{method}]: {e}")
        return {"response": []}

# ── Данные ───────────────────────────────────────────────────────────────────
def get_categories():
    r = api_get("finance.getCategories")
    cats = {}
    for c in r.get("response", []):
        name = CAT_NAMES.get(c["name"], c["name"])
        cats[str(c["category_id"])] = name
    return cats

def get_accounts():
    r = api_get("finance.getAccounts")
    accounts = {}
    for a in r.get("response", []):
        balance = int(a["balance"]) / 100
        accounts[str(a["account_id"])] = {
            "name": a["name"],
            "balance": balance,
        }
    return accounts

def get_transactions(date_from, date_to):
    """Получить транзакции за период (dateFrom/dateTo: YYYYMMDD)"""
    r = api_get("finance.getTransactions", {
        "dateFrom": date_from,
        "dateTo": date_to,
    })
    return r.get("response", [])

def get_cash_shifts(date_from, date_to):
    r = api_get("finance.getCashShifts", {
        "dateFrom": date_from,
        "dateTo": date_to,
    })
    return r.get("response", [])

# ── Аналитика ────────────────────────────────────────────────────────────────
def analyze_transactions(transactions, categories):
    """Разбить транзакции по категориям."""
    income = defaultdict(float)    # доходы
    expenses = defaultdict(float)  # расходы
    by_day = defaultdict(lambda: {"income": 0.0, "expense": 0.0})

    for t in transactions:
        amount = int(t["amount"]) / 100
        cat_id = str(t.get("category_id", "0"))
        cat_name = categories.get(cat_id, t.get("category_name", "Прочее"))
        date = t["date"][:10]

        if cat_name in SKIP_CATEGORIES:
            continue

        if amount > 0:
            income[cat_name] += amount
            by_day[date]["income"] += amount
        else:
            expenses[cat_name] += abs(amount)
            by_day[date]["expense"] += abs(amount)

    return income, expenses, by_day

# ── Форматирование ───────────────────────────────────────────────────────────
def fmt(n):
    return f"{n:,.2f}".replace(",", " ") + " с"

def md_table(rows, headers):
    col_w = [max(len(str(r[i])) for r in ([headers] + rows)) for i in range(len(headers))]
    def row_str(r):
        return "| " + " | ".join(str(r[i]).ljust(col_w[i]) for i in range(len(headers))) + " |"
    sep = "| " + " | ".join("-" * col_w[i] for i in range(len(headers))) + " |"
    lines = [row_str(headers), sep] + [row_str(r) for r in rows]
    return "\n".join(lines)

# ── Генерация отчётов ─────────────────────────────────────────────────────────
def generate_daily_report(date: datetime):
    date_str = date.strftime("%Y%m%d")
    date_label = date.strftime("%Y-%m-%d")

    print(f"📥 Загрузка данных за {date_label}...")
    categories = get_categories()
    accounts = get_accounts()
    txns = get_transactions(date_str, date_str)

    income, expenses, _ = analyze_transactions(txns, categories)

    total_income = sum(income.values())
    total_expenses = sum(expenses.values())
    gross = total_income - total_expenses

    # Формируем markdown
    lines = [
        f"# Ежедневный отчёт — {date_label}",
        "",
        "#project/romashka #area/career",
        "",
        "---",
        "",
        "## Доходы",
        "",
    ]
    if income:
        rows = sorted(income.items(), key=lambda x: -x[1])
        lines.append(md_table([[r[0], fmt(r[1])] for r in rows], ["Категория", "Сумма"]))
    lines += ["", f"**Итого доходов: {fmt(total_income)}**", "", "---", "", "## Расходы", ""]
    if expenses:
        rows = sorted(expenses.items(), key=lambda x: -x[1])
        lines.append(md_table([[r[0], fmt(r[1])] for r in rows], ["Категория", "Сумма"]))
    lines += ["", f"**Итого расходов: {fmt(total_expenses)}**", "", "---", "", "## Итог дня", ""]
    lines += [
        f"| | |",
        f"|---|---|",
        f"| Доходы | {fmt(total_income)} |",
        f"| Расходы | {fmt(total_expenses)} |",
        f"| **Валовая прибыль** | **{fmt(gross)}** |",
    ]
    lines += ["", "---", "", "## Остатки счетов", ""]
    rows = [[a["name"], fmt(a["balance"])] for a in accounts.values()]
    lines.append(md_table(rows, ["Счёт", "Остаток"]))
    lines += ["", "---", f"*Сформировано автоматически из Poster {datetime.now().strftime('%Y-%m-%d %H:%M')}*"]

    return "\n".join(lines), f"день-{date_label}.md"


def generate_weekly_report(date: datetime):
    # Неделя: пн–вс текущей недели
    week_start = date - timedelta(days=date.weekday())
    week_end = week_start + timedelta(days=6)
    if week_end > date:
        week_end = date

    ds = week_start.strftime("%Y%m%d")
    de = week_end.strftime("%Y%m%d")
    week_label = f"{week_start.strftime('%Y')}-W{week_start.strftime('%V')}"
    label = f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}"

    print(f"📥 Загрузка данных за {label}...")
    categories = get_categories()
    accounts = get_accounts()
    txns = get_transactions(ds, de)

    income, expenses, by_day = analyze_transactions(txns, categories)

    total_income = sum(income.values())
    total_expenses = sum(expenses.values())
    gross = total_income - total_expenses

    lines = [
        f"# Еженедельный отчёт — {week_label} ({label})",
        "",
        "#project/romashka #area/career",
        "",
        "---",
        "",
        "## Выручка по дням",
        "",
    ]
    # По дням
    day_rows = []
    for i in range((week_end - week_start).days + 1):
        d = (week_start + timedelta(days=i)).strftime("%Y-%m-%d")
        info = by_day.get(d, {"income": 0.0, "expense": 0.0})
        day_rows.append([d, fmt(info["income"]), fmt(info["expense"]), fmt(info["income"] - info["expense"])])
    lines.append(md_table(day_rows, ["День", "Доходы", "Расходы", "Нетто"]))

    lines += ["", "---", "", "## Доходы", ""]
    if income:
        rows = sorted(income.items(), key=lambda x: -x[1])
        lines.append(md_table([[r[0], fmt(r[1])] for r in rows], ["Категория", "Сумма"]))
    lines += ["", f"**Итого: {fmt(total_income)}**", "", "---", "", "## Расходы", ""]
    if expenses:
        rows = sorted(expenses.items(), key=lambda x: -x[1])
        lines.append(md_table([[r[0], fmt(r[1])] for r in rows], ["Категория", "Сумма"]))
    lines += ["", f"**Итого: {fmt(total_expenses)}**", "", "---", "", "## Итог недели", ""]
    lines += [
        f"| | |",
        f"|---|---|",
        f"| Доходы | {fmt(total_income)} |",
        f"| Расходы | {fmt(total_expenses)} |",
        f"| **Валовая прибыль** | **{fmt(gross)}** |",
        f"| Маржа | {gross/total_income*100:.1f}% |" if total_income else "| Маржа | — |",
    ]
    lines += ["", "---", "", "## Остатки счетов", ""]
    rows = [[a["name"], fmt(a["balance"])] for a in accounts.values()]
    lines.append(md_table(rows, ["Счёт", "Остаток"]))
    lines += ["", "---", f"*Сформировано автоматически из Poster {datetime.now().strftime('%Y-%m-%d %H:%M')}*"]

    return "\n".join(lines), f"неделя-{week_label}.md"


def generate_monthly_report(date: datetime):
    month_start = date.replace(day=1)
    ds = month_start.strftime("%Y%m%d")
    de = date.strftime("%Y%m%d")
    month_label = date.strftime("%Y-%m")
    month_ru = date.strftime("%B %Y")

    print(f"📥 Загрузка данных за {month_ru}...")
    categories = get_categories()
    accounts = get_accounts()
    txns = get_transactions(ds, de)

    income, expenses, by_day = analyze_transactions(txns, categories)

    total_income = sum(income.values())
    total_expenses = sum(expenses.values())
    gross = total_income - total_expenses

    lines = [
        f"# Ежемесячный отчёт — {month_ru}",
        "",
        "#project/romashka #area/career",
        "",
        "---",
        "",
        "## P&L",
        "",
        f"| Статья | Сумма | % выручки |",
        f"|--------|-------|-----------|",
        f"| **Выручка** | **{fmt(total_income)}** | 100% |",
    ]
    for cat, amt in sorted(expenses.items(), key=lambda x: -x[1]):
        pct = f"{amt/total_income*100:.1f}%" if total_income else "—"
        lines.append(f"| {cat} | {fmt(amt)} | {pct} |")
    lines += [
        f"| **Итого расходы** | **{fmt(total_expenses)}** | {total_expenses/total_income*100:.1f}% |" if total_income else f"| **Итого расходы** | **{fmt(total_expenses)}** | — |",
        f"| **Валовая прибыль** | **{fmt(gross)}** | {gross/total_income*100:.1f}% |" if total_income else f"| **Валовая прибыль** | **{fmt(gross)}** | — |",
    ]
    lines += ["", "---", "", "## Остатки счетов", ""]
    rows = [[a["name"], fmt(a["balance"])] for a in accounts.values()]
    lines.append(md_table(rows, ["Счёт", "Остаток"]))
    lines += ["", "---", "", "## Выводы", "", "**Что хорошо:**", "", "**Что плохо:**", "", "**Решения на следующий месяц:**", "- [ ]", "", "---", f"*Сформировано автоматически из Poster {datetime.now().strftime('%Y-%m-%d %H:%M')}*"]

    return "\n".join(lines), f"месяц-{month_label}.md"


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "week"
    today = datetime.now()

    os.makedirs(REPORTS_DIR, exist_ok=True)

    if mode == "day":
        content, filename = generate_daily_report(today)
    elif mode == "month":
        content, filename = generate_monthly_report(today)
    else:
        content, filename = generate_weekly_report(today)

    filepath = os.path.join(REPORTS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n✅ Отчёт сохранён: finance/reports/{filename}")

    # Загрузка в Google Drive
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from drive_upload import upload
        upload(filepath)
    except Exception as e:
        print(f"⚠️  Drive: {e}")

    print(content[:800])
    print("...")

if __name__ == "__main__":
    main()
