#!/usr/bin/env python3
"""
Ромашка — автоматическое заполнение P&L из Poster.
Cron: 1 2 1 * * python3 /home/user/My-vault/scripts/update_pnl.py
(запускается 1-го числа в 02:01 — заполняет предыдущий месяц)

Ручной запуск:
  python3 update_pnl.py            — предыдущий месяц
  python3 update_pnl.py 2026 4     — конкретный месяц
  python3 update_pnl.py 2026 1 4   — диапазон месяцев (январь–апрель)

Структура P&L (строки соответствуют Main P&L):
  строка 2   Выручка             dash.getAnalytics → revenue
  строка 4   Закупки кухня       storage.getSupplies → склад «Кухня»
  строка 5   Закупки бар         storage.getSupplies → склад «Бар»
  строка 7   Персоналка          storage.getSupplies → склад «Персоналка»
  строка 8   Расходные материалы storage.getSupplies → склад «Расходные материалы»
  строки 13,15 ФОТ              НЕ берётся из Poster — вводится вручную
  строки 18–37 OpEx             finance.getTransactions по категориям (см. CATEGORY_ROWS)
  строка 22  Электроэнергия      категории Электричество + Коммунальные платежи
  строка 40  Налоги              категория Налоги

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
# Строки соответствуют структуре Main P&L (47 строк).
# COGS (строки 4,5,7,8) берутся из storage.getSupplies, не из транзакций.
# ФОТ (строки 13,15) вводится вручную.
# Коммунальные (20) = формула: Электро(22) + Вода(23) + Мусор(24).
# OpEx (17) = SUM(18:37).
CATEGORY_ROWS = {
    'Аренда помещения':          19,
    'Электричество':             23,
    'Водоснабжение':             24,
    'Вывоз мусора':              25,
    'Расходы на заведение':      26,
    'Расходы на оборудование':   27,
    'Покупка инвентаря':         28,
    'Упаковка':                  29,
    'Расходы на логистику':      30,
    'Выплаты Beeyor':            31,  # агрегатор / комиссия доставки
    'Выплаты Teztar':            31,  # агрегатор Teztar
    'Маркетинг':                 32,
    'Poster':                    33,  # CRM
    'Интернет':                  34,
    'Хозяйственные расходы':     35,
    'Прочие расходы':            36,
    'Документы для заведения':   37,
    'Форс - мажор':              38,  # ЗБ
    'Форс мажор':                38,  # ОВИР
    'Налоги':                    41,
    'Погашение долгов':          45,
    'Инвестиции':                46,
    'Выплаты дивидентов':        47,  # опечатка в Poster
    'Выплаты дивидендов':        47,
}

# Категории-исключения: не расходы в P&L смысле
# Коррекции для поставок с неверной датой в Poster.
# Poster фильтрует по дате создания записи, изменить нельзя без пересоздания.
# Формат: (sheet, year, month, row) → дельта в сомах.
SUPPLY_DELTA = {
    ('ОВИР', 2026, 1, 5): -1383,  # supply_id=90 Кухня: Poster=Январь, фактически=Февраль
    ('ОВИР', 2026, 2, 5): +1383,
}

SKIP_CATS = {
    'Переводы', 'Внесения в кассу', 'Кассовые смены',
    'Открытие ФС', 'Актуализация',
    'Неоплаченные счета',
    # ФОТ вводится вручную в P&L, из Poster не берётся
    'ФОТ Производственный', 'ФОТ Административный',
    # Юридические расходы — не используются
    'Юридические расходы', 'Юридические расходы ',
    # Поставки на склады — берутся из storage.getSupplies, не из транзакций
    'Поставки',
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
    last_day  = calendar.monthrange(year, month)[1]
    date_from = f"{year}{month:02d}01"
    date_to   = f"{year}{month:02d}{last_day:02d}"
    month_str = f"{year}-{month:02d}"

    # Для транзакций расширяем диапазон на ±1 день:
    # Poster хранит время UTC, Душанбе UTC+5. Транзакции в начале месяца
    # (00:00–04:59 местного) попадают в предыдущий месяц по UTC.
    prev_day = (datetime.date(year, month, 1) - datetime.timedelta(days=1)).strftime('%Y%m%d')
    next_day = (datetime.date(year, month, last_day) + datetime.timedelta(days=1)).strftime('%Y%m%d')

    # Выручка
    ra = poster_get(token, 'dash.getAnalytics', {'dateFrom': date_from, 'dateTo': date_to})
    revenue = float(ra.get('response', {}).get('counters', {}).get('revenue', 0) or 0)

    # Транзакции расходов (расширенный диапазон + фильтр по отображаемой дате)
    rt   = poster_get(token, 'finance.getTransactions', {'dateFrom': prev_day, 'dateTo': next_day})
    txns = rt.get('response', []) or []

    # Поставки на склады — точный диапазон (Poster фильтрует поставки по дате записи)
    rs = poster_get(token, 'storage.getSupplies', {'dateFrom': date_from, 'dateTo': date_to})
    supplies = rs.get('response', []) or []

    # Инициализируем все строки данных нулём
    DATA_ROWS = [2, 5, 6, 8, 9, 14, 16, 19, 23, 24, 25, 26, 27, 28, 29,
                 30, 31, 32, 33, 34, 35, 36, 37, 38, 41, 45, 46, 47]
    row_totals = {r: 0.0 for r in DATA_ROWS}

    if revenue > 0:
        row_totals[2] = revenue

    unknown_cats = defaultdict(float)

    for tx in txns:
        if tx.get('type') != '0':
            continue
        # Фильтр по отображаемой (местной) дате транзакции
        if (tx.get('date', '') or '')[:7] != month_str:
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

    # COGS из storage.getSupplies по имени склада (дедупликация по supply_id)
    storage_row = {
        'Кухня':                5,
        'Бар':                  6,
        'Персоналка':           8,
        'Расходные материалы':  9,
    }
    seen_supply_ids = set()
    for s in supplies:
        sid = s.get('supply_id')
        if sid and sid in seen_supply_ids:
            continue
        if sid:
            seen_supply_ids.add(sid)
        name = (s.get('storage_name', '') or '').strip()
        amt  = int(s.get('supply_sum', 0)) / 100
        if name in storage_row:
            row_totals[storage_row[name]] += amt

    return row_totals


def month_col(month):
    """Месяц (1–12) → буква столбца (C–N)."""
    return chr(ord('B') + month)  # 1→C, 2→D, ..., 12→N


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
            for (sh, yr, mo, row), delta in SUPPLY_DELTA.items():
                if sh == loc['sheet'] and yr == year and mo == month:
                    data[row] = round(data.get(row, 0) + delta, 2)
            rev  = data.get(2, 0)
            cogs = data.get(5, 0) + data.get(6, 0) + data.get(8, 0) + data.get(9, 0)
            opex = sum(v for k, v in data.items() if 19 <= k <= 38)
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
