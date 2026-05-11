#!/usr/bin/env python3
"""
Показывает детали Poster-данных для E4, C8, D22:
  E4  = Закуп кухни,             Март    (storage Кухня, март 2026)
  C8  = Расходные материалы,     Январь  (storage Расходные материалы, янв 2026)
  D22 = Электроэнергия,          Февраль (transactions категория Электричество/Коммунальные, фев 2026)
"""
import json, os, calendar, urllib.request, urllib.parse

POSTER_BASE = 'https://joinposter.com/api'

TOKENS = {
    'ЗБ': '398711:8746917c4a23ea897774040e039dfb76',
}

def poster_get(token, method, params=None):
    p = {'token': token}
    if params:
        p.update(params)
    url = f"{POSTER_BASE}/{method}?{urllib.parse.urlencode(p)}"
    with urllib.request.urlopen(
            urllib.request.Request(url, headers={'User-Agent': 'RomashkaBot/1.0'}),
            timeout=30) as r:
        return json.loads(r.read().decode())

def date_range(year, month):
    last = calendar.monthrange(year, month)[1]
    return f"{year}{month:02d}01", f"{year}{month:02d}{last:02d}"

def main():
    token = TOKENS['ЗБ']

    # ── C8: Расходные материалы, Январь ─────────────────────────────────────
    print("=" * 60)
    print("C8 — Расходные материалы, Январь 2026 (storage.getSupplies)")
    d_from, d_to = date_range(2026, 1)
    rs = poster_get(token, 'storage.getSupplies', {'dateFrom': d_from, 'dateTo': d_to})
    supplies = rs.get('response', []) or []
    total = 0
    for s in supplies:
        name = (s.get('storage_name', '') or '').strip()
        if name == 'Расходные материалы':
            amt = int(s.get('supply_sum', 0)) / 100
            total += amt
            print(f"  supply_id={s.get('supply_id')}  дата={s.get('supply_date','')}  "
                  f"склад={name}  сумма={amt:,.2f}")
    print(f"  ИТОГО: {total:,.2f}  (в таблице: 8108, Main P&L: 6414)")

    # ── E4: Закуп кухни, Март ───────────────────────────────────────────────
    print()
    print("=" * 60)
    print("E4 — Закуп кухни, Март 2026 (storage.getSupplies)")
    d_from, d_to = date_range(2026, 3)
    rs = poster_get(token, 'storage.getSupplies', {'dateFrom': d_from, 'dateTo': d_to})
    supplies = rs.get('response', []) or []
    total = 0
    for s in supplies:
        name = (s.get('storage_name', '') or '').strip()
        if name == 'Кухня':
            amt = int(s.get('supply_sum', 0)) / 100
            total += amt
            print(f"  supply_id={s.get('supply_id')}  дата={s.get('supply_date','')}  "
                  f"склад={name}  сумма={amt:,.2f}")
    print(f"  ИТОГО: {total:,.2f}  (в таблице: 127444, Main P&L: 118376)")

    # ── D22: Электроэнергия, Февраль ────────────────────────────────────────
    print()
    print("=" * 60)
    print("D22 — Электроэнергия, Февраль 2026 (finance.getTransactions)")
    d_from, d_to = date_range(2026, 2)
    rt = poster_get(token, 'finance.getTransactions', {'dateFrom': d_from, 'dateTo': d_to})
    txns = rt.get('response', []) or []
    total = 0
    for tx in txns:
        if tx.get('type') != '0':
            continue
        cat = (tx.get('category_name', '') or '').strip()
        if cat in ('Электричество', 'Коммунальные платежи'):
            amt = abs(int(tx.get('amount', 0))) / 100
            total += amt
            print(f"  tx_id={tx.get('transaction_id')}  дата={tx.get('date','')}  "
                  f"категория={cat}  сумма={amt:,.2f}")
    print(f"  ИТОГО: {total:,.2f}  (в таблице: 11524, Main P&L: 11014)")

if __name__ == '__main__':
    main()
