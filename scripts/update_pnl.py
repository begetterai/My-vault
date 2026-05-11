#!/usr/bin/env python3
"""
Ромашка — автоматическое заполнение P&L из Poster.
Cron: 1 2 1 * * python3 /home/user/My-vault/scripts/update_pnl.py
(запускается 1-го числа в 02:01 — заполняет предыдущий месяц)

Ручной запуск:
  python3 update_pnl.py            — предыдущий месяц
  python3 update_pnl.py 2026 4     — конкретный месяц
  python3 update_pnl.py 2026 1 4   — диапазон месяцев (январь–апрель)

Источники (Poster type=0 транзакции, все счета):
  строка 6   Выручка             dash.getAnalytics → revenue
  строка 18  Закупки (COGS)      категория Поставки (кухня+бар объединены)
  строка 19  Закупки бар         → 0 (всё идёт в строку 18)
  строки 27–28 ФОТ              НЕ берётся из Poster — вводится вручную
  строки 33–50  OpEx             по категориям (см. CATEGORY_ROWS)
  строка 56  Налоги              категория Налоги

Если категория не найдена в маппинге — предупреждение в stdout.
Добавить новую категорию: дописать в CATEGORY_ROWS.
"""
import json, os, sys, time, datetime, calendar, urllib.request, urllib.parse
from collections import defaultdict

os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS         = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'credentials', 'romashka-drive.json')
PNL_SS_ID     = '1l8Lau8K9997pyqJj-zjlILAkLoOHlQmPo6BAwqc5FBU'
POSTER_BASE   = 'https://joinposter.com/api'

LOCATIONS = [
    {'sheet': 'ЗБ',   'token': '398711:8746917c4a23ea897774040e039dfb76'},
    {'sheet': 'ОВИР', 'token': '935215:79675564e3d086d7e03d5fd56b50c8df'},
]

# ─── Маппинг: категория Poster → номер строки в P&L ────────────────────────
# Несколько категорий могут ссылаться на одну строку (суммируются).
# Коммунальные (строка 35): Электричество + Водоснабжение + Вывоз мусора + Коммунальные платежи
# Агрегатор (строка 39): Выплаты Beeyor (комиссия доставки)
# Инвентарь (строка 42): Покупка инвентаря
# CRM (строка 45): Poster
# Хозтовары (строка 46): Хозяйственные расходы
# Юридические (строка 48): Юридические расходы + Документы для заведения
# Прочие (строка 49): Прочие расходы + Неоплаченные счета
CATEGORY_ROWS = {
    'Поставки':                  18,  # COGS (кухня+бар вместе; строка 19 → 0)
    # ФОТ (строки 27–28) — вводится вручную, не берётся из Poster
    'Аренда помещения':          33,
    'Электричество':             35,
    'Коммунальные платежи':      35,
    'Водоснабжение':             35,
    'Вывоз мусора':              35,
    'Упаковка':                  36,
    'Расходы на логистику':      37,
    'Интернет':                  38,
    'Выплаты Beeyor':            39,  # агрегатор / комиссия доставки
    'Выплаты Teztar':            39,  # агрегатор Teztar
    'Расходы на заведение':      40,
    'Расходы на оборудование':   41,
    'Покупка инвентаря':         42,  # расходы на инвентарь
    'Poster':                    45,  # CRM / Poster
    'Хозяйственные расходы':     46,
    'Маркетинг':                 47,
    'Юридические расходы':       48,
    'Юридические расходы ':      48,  # Poster иногда пишет с пробелом
    'Документы для заведения':   48,
    'Прочие расходы':            49,
    'Форс - мажор':              50,  # ЗБ
    'Форс мажор':                50,  # ОВИР
    'Налоги':                    56,
}

# Категории-исключения: не расходы в P&L смысле
SKIP_CATS = {
    'Переводы', 'Внесения в кассу', 'Кассовые смены',
    'Открытие ФС', 'Выплаты дивидентов', 'Погашение долгов', 'Актуализация',
    # ФОТ вводится вручную в P&L, из Poster не берётся
    'ФОТ Производственный', 'ФОТ Административный',
}


def poster_get(token, method, params=None):
    p = {'token': token}
    if params:
        p.update(params)
    url = f"{POSTER_BASE}/{method}?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers={'User-Agent': 'RomashkaBot/1.0'}),
                timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"    ⚠️  {e}")
        return {}


def get_month_data(token, year, month):
    """Собирает все P&L данные за месяц из Poster."""
    date_from = f"{year}{month:02d}01"
    last_day  = calendar.monthrange(year, month)[1]
    date_to   = f"{year}{month:02d}{last_day:02d}"

    # Выручка
    ra = poster_get(token, 'dash.getAnalytics', {'dateFrom': date_from, 'dateTo': date_to})
    revenue = float(ra.get('response', {}).get('counters', {}).get('revenue', 0) or 0)

    # Транзакции расходов
    rt   = poster_get(token, 'finance.getTransactions', {'dateFrom': date_from, 'dateTo': date_to})
    txns = rt.get('response', []) or []

    # Поставки на склады — строки 43 (Персоналка) и 44 (Расходные материалы)
    rs = poster_get(token, 'storage.getSupplies', {'dateFrom': date_from, 'dateTo': date_to})
    supplies = rs.get('response', []) or []

    row_totals = defaultdict(float)

    if revenue > 0:
        row_totals[6] = revenue

    # Обнуляем строку 19 (бар): все Поставки пойдут в строку 18
    row_totals[19] = 0.0

    unknown_cats = defaultdict(float)

    for tx in txns:
        if tx.get('type') != '0':
            continue
        cat = (tx.get('category_name', '') or '').strip()
        if cat in SKIP_CATS:
            continue
        amt = abs(int(tx.get('amount', 0))) / 100
        if cat in CATEGORY_ROWS:
            row_totals[CATEGORY_ROWS[cat]] += amt
        else:
            unknown_cats[cat] += amt

    if unknown_cats:
        for cat, total in sorted(unknown_cats.items(), key=lambda x: -x[1]):
            print(f"    ⚠️  Неизвестная категория: «{cat}» = {total:,.0f}с → добавь в CATEGORY_ROWS")

    for s in supplies:
        name = (s.get('storage_name', '') or '').strip()
        amt  = int(s.get('supply_sum', 0)) / 100
        if name == 'Персоналка':
            row_totals[43] += amt
        elif name == 'Расходные материалы':
            row_totals[44] += amt

    return dict(row_totals)


def month_col(month):
    """Месяц (1–12) → буква столбца (B–M)."""
    return chr(ord('A') + month)  # 1→B, 2→C, ..., 12→M


def write_month(session, sheet, year, month, row_data):
    col = month_col(month)
    updates = [
        {'range': f"'{sheet}'!{col}{row}", 'values': [[round(val, 2)]]}
        for row, val in row_data.items()
    ]
    if not updates:
        return
    body = {'valueInputOption': 'USER_ENTERED', 'data': updates}
    r = session.post(
        f'https://sheets.googleapis.com/v4/spreadsheets/{PNL_SS_ID}/values:batchUpdate',
        headers={'Content-Type': 'application/json'},
        data=json.dumps(body), timeout=30)
    ok = r.status_code == 200
    print(f"    {'✅' if ok else '❌'} {col}{min(row_data)} : {len(updates)} ячеек")
    return ok


def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)


def run(year=None, month_from=None, month_to=None):
    today = datetime.date.today()
    if year is None:
        # По умолчанию — предыдущий месяц
        first_of_this = today.replace(day=1)
        prev = first_of_this - datetime.timedelta(days=1)
        year, month_from, month_to = prev.year, prev.month, prev.month
    if month_to is None:
        month_to = month_from

    session = get_session()
    print(f"P&L обновление {year}, месяцы {month_from}–{month_to}")

    for month in range(month_from, month_to + 1):
        mn = datetime.date(year, month, 1).strftime('%B %Y')
        print(f"\n── {mn} ──")
        for loc in LOCATIONS:
            print(f"  {loc['sheet']}...")
            data = get_month_data(loc['token'], year, month)
            rev  = data.get(6, 0)
            cogs = data.get(18, 0)
            opex = data.get(51, sum(v for k, v in data.items() if 33 <= k <= 50))
            print(f"    выручка={rev:,.0f}с  COGS={cogs:,.0f}с  OpEx={opex:,.0f}с")
            if rev > 0:
                write_month(session, loc['sheet'], year, month, data)
            else:
                print(f"    ⚠️  Нет данных — пропуск")
            time.sleep(0.5)


if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) == 0:
        run()
    elif len(args) == 2:
        run(int(args[0]), int(args[1]))
    elif len(args) == 3:
        run(int(args[0]), int(args[1]), int(args[2]))
    else:
        print("Использование: update_pnl.py [год] [месяц] [месяц_до]")
        sys.exit(1)
