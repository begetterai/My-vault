#!/usr/bin/env python3
"""Детальный дебаг ОВИР: E5, E25/F25, E26/F26, E35/F35, E37/F37."""
import json, os, calendar, urllib.request, urllib.parse
from collections import defaultdict

POSTER_BASE = 'https://joinposter.com/api'
TOKEN = '935215:79675564e3d086d7e03d5fd56b50c8df'

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

MONTH_NAMES = {1:'Январь',2:'Февраль',3:'Март',4:'Апрель'}

# Категории для конкретных строк
ROW_CATS = {
    25: ['Расходы на заведение'],
    26: ['Расходы на оборудование'],
    35: ['Прочие расходы'],
    37: ['Форс мажор', 'Форс - мажор'],
}

def main():
    # ── E5: Закуп бара, Март (supply дубли?) ────────────────────────────────
    print("=" * 60)
    print("E5 — Закуп бара, Март 2026 (ОВИР, storage.getSupplies)")
    d_from, d_to = date_range(2026, 3)
    rs = poster_get(TOKEN, 'storage.getSupplies', {'dateFrom': d_from, 'dateTo': d_to})
    supplies = rs.get('response', []) or []
    seen = set()
    total_raw, total_dedup = 0, 0
    for s in supplies:
        name = (s.get('storage_name', '') or '').strip()
        if name != 'Бар':
            continue
        sid = s.get('supply_id')
        amt = int(s.get('supply_sum', 0)) / 100
        total_raw += amt
        dup = sid in seen
        if sid:
            seen.add(sid)
        print(f"  supply_id={sid}  сумма={amt:,.2f}{'  ← ДУБЛь' if dup else ''}")
        if not dup:
            total_dedup += amt
    print(f"  RAW={total_raw:,.2f}  DEDUP={total_dedup:,.2f}  (Main P&L=13873)")

    # ── Транзакции Март и Апрель по нужным категориям ───────────────────────
    for month in [3, 4]:
        d_from, d_to = date_range(2026, month)
        rt = poster_get(TOKEN, 'finance.getTransactions', {'dateFrom': d_from, 'dateTo': d_to})
        txns = rt.get('response', []) or []

        print()
        print("=" * 60)
        print(f"ОВИР {MONTH_NAMES[month]} 2026 — транзакции расходов по строкам 25,26,35,37")
        totals = defaultdict(float)
        for tx in txns:
            if tx.get('type') != '0':
                continue
            cat = (tx.get('category_name', '') or '').strip()
            amt = abs(int(tx.get('amount', 0))) / 100
            for row, cats in ROW_CATS.items():
                if cat in cats:
                    totals[row] += amt
                    print(f"  R{row}  {cat:<35} {amt:>10,.2f}  дата={tx.get('date','')[:10]}")
        print(f"  Итоги: R25={totals[25]:,.0f}  R26={totals[26]:,.0f}  R35={totals[35]:,.0f}  R37={totals[37]:,.0f}")

    # ── COGS ОВИР все месяцы — дубли ────────────────────────────────────────
    print()
    print("=" * 60)
    print("ОВИР COGS — все месяцы, проверка дублей")
    for month in [1, 2, 3, 4]:
        d_from, d_to = date_range(2026, month)
        rs = poster_get(TOKEN, 'storage.getSupplies', {'dateFrom': d_from, 'dateTo': d_to})
        supplies = rs.get('response', []) or []
        seen = set()
        by_storage = defaultdict(lambda: {'raw': 0, 'dedup': 0})
        for s in supplies:
            name = (s.get('storage_name', '') or '').strip()
            sid = s.get('supply_id')
            amt = int(s.get('supply_sum', 0)) / 100
            by_storage[name]['raw'] += amt
            if sid not in seen:
                by_storage[name]['dedup'] += amt
                if sid:
                    seen.add(sid)
        row_map = {'Кухня': 4, 'Бар': 5, 'Персоналка': 7, 'Расходные материалы': 8}
        print(f"\n  {MONTH_NAMES[month]}:")
        for name, row in row_map.items():
            d = by_storage.get(name, {'raw': 0, 'dedup': 0})
            diff = d['raw'] - d['dedup']
            marker = '  ← ДУБЛИ' if diff > 0 else ''
            print(f"    {name:<25} raw={d['raw']:>10,.0f}  dedup={d['dedup']:>10,.0f}{marker}")

if __name__ == '__main__':
    main()
