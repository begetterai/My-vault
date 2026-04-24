#!/usr/bin/env python3
"""
Диагностика finance.getTransactions для ЗБ и ОВИР.
Показывает все транзакции за период с разбивкой по типу и категории.
Помогает проверить что именно попадает в колонку M (Расходы) дневного трекера.

Типы транзакций в Poster:
  type=1 — приход (доходная операция, не продажи)
  type=2 — расход (все категории расходов)
  type=3 — перемещение между счетами
"""
import json, os, urllib.request, urllib.parse, datetime
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'

LOCATIONS = [
    {'name': 'ЗБ',   'token': '398711:8746917c4a23ea897774040e039dfb76'},
    {'name': 'ОВИР', 'token': '935215:79675564e3d086d7e03d5fd56b50c8df'},
]
POSTER_BASE = 'https://joinposter.com/api'
TYPE_LABEL = {'1': 'ПРИХОД', '2': 'РАСХОД', '3': 'ПЕРЕМЕЩЕНИЕ'}


def poster_get(token, method, params=None):
    p = {'token': token}
    if params:
        p.update(params)
    url = f"{POSTER_BASE}/{method}?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers={'User-Agent': 'RomashkaBot/1.0'}),
                timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f'  ⚠️  {e}')
        return {}


def check_location(name, token, date_from, date_to):
    ds = date_from.strftime('%Y%m%d')
    de = date_to.strftime('%Y%m%d')
    print(f'\n{"="*60}')
    print(f'  {name} | {date_from.strftime("%d.%m.%Y")} – {date_to.strftime("%d.%m.%Y")}')
    print(f'{"="*60}')

    r = poster_get(token, 'finance.getTransactions', {'dateFrom': ds, 'dateTo': de})
    txs = r.get('response', [])

    if not txs:
        print('  Нет транзакций.')
        return

    # Группировка по типу
    by_type = {}
    for t in txs:
        tp = str(t.get('type', '?'))
        by_type.setdefault(tp, []).append(t)

    for tp in sorted(by_type.keys()):
        items = by_type[tp]
        label = TYPE_LABEL.get(tp, f'type={tp}')
        total = sum(int(t.get('amount', 0)) / 100 for t in items)
        print(f'\n  [{label}] — {len(items)} записей, сумма: {total:,.0f} с')

        # Группировка по категории
        by_cat = {}
        for t in items:
            cat = t.get('category_name') or t.get('comment') or '—'
            by_cat.setdefault(cat, []).append(t)

        for cat, cat_items in sorted(by_cat.items(), key=lambda x: -sum(int(i.get('amount',0)) for i in x[1])):
            cat_sum = sum(int(i.get('amount', 0)) / 100 for i in cat_items)
            print(f'    {cat:<35} {cat_sum:>10,.0f} с  ({len(cat_items)} шт.)')

    # Итоги по типам
    print(f'\n  ИТОГО по типам:')
    total_expense = 0
    for tp in sorted(by_type.keys()):
        items = by_type[tp]
        total = sum(int(t.get('amount', 0)) / 100 for t in items)
        label = TYPE_LABEL.get(tp, f'type={tp}')
        print(f'    {label:<20} {total:>12,.0f} с')
        if tp == '2':
            total_expense = total

    print(f'\n  → В колонку M (Расходы) трекера попадёт: {total_expense:,.0f} с (только type=2)')

    # Детальный список type=2
    print(f'\n  Детали type=2 (расходы):')
    for t in sorted(by_type.get('2', []), key=lambda x: -int(x.get('amount', 0))):
        date_str = t.get('date', '')[:10]
        cat  = t.get('category_name') or '—'
        comm = t.get('comment') or ''
        amt  = int(t.get('amount', 0)) / 100
        print(f'    {date_str}  {cat:<30} {amt:>10,.0f} с  {comm[:40]}')


def main():
    # По умолчанию — текущий месяц
    today = datetime.date.today()
    date_from = today.replace(day=1)
    date_to   = today

    import sys
    if len(sys.argv) >= 3:
        date_from = datetime.date.fromisoformat(sys.argv[1])
        date_to   = datetime.date.fromisoformat(sys.argv[2])

    print(f'Период: {date_from.strftime("%d.%m.%Y")} – {date_to.strftime("%d.%m.%Y")}')

    for loc in LOCATIONS:
        check_location(loc['name'], loc['token'], date_from, date_to)


if __name__ == '__main__':
    main()
