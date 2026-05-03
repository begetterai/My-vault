#!/usr/bin/env python3
"""
Задача 1: Исследование K-расхождений ОВИР vs ЗБ
"""
import requests
import json

OVIR_TOKEN = '935215:79675564e3d086d7e03d5fd56b50c8df'
ZB_TOKEN   = '398711:8746917c4a23ea897774040e039dfb76'

BASE_URL = 'https://joinposter.com/api/finance.getTransactions'

def fetch_transactions(token, date_from, date_to):
    url = f"{BASE_URL}?token={token}&dateFrom={date_from}&dateTo={date_to}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data

def analyze_day(token, label, date):
    date_str = date.replace('-', '')
    print(f"\n{'='*60}")
    print(f"  {label}  дата={date}")
    print(f"{'='*60}")
    data = fetch_transactions(token, date_str, date_str)

    if 'response' not in data:
        print(f"ERROR: {data}")
        return

    transactions = data['response']
    print(f"Всего транзакций: {len(transactions)}")

    # Фильтруем type=1 (доходы/income)
    income = [t for t in transactions if str(t.get('type', '')) == '1']
    print(f"type=1 (income): {len(income)}")

    print(f"\n--- type=1 транзакции ---")
    total = 0
    for t in income:
        tid   = t.get('transaction_id', t.get('id', '?'))
        amt   = float(t.get('sum', 0))
        comm  = t.get('comment', '')
        acc   = t.get('account_id', '')
        cat   = t.get('category_id', '')
        total += amt
        print(f"  id={tid}  сумма={amt:>10.2f}  account={acc}  category={cat}")
        print(f"    comment: {repr(comm)}")

    print(f"\nИТОГО type=1: {total:.2f}")

    # Также выведем type=0 (расходы) для полноты
    expense = [t for t in transactions if str(t.get('type', '')) == '0']
    print(f"\ntype=0 (expense): {len(expense)}")
    exp_total = sum(float(t.get('sum', 0)) for t in expense)
    print(f"ИТОГО type=0: {exp_total:.2f}")

    # Все типы
    print(f"\n--- Все типы транзакций (распределение) ---")
    from collections import Counter
    type_counts = Counter(str(t.get('type', '?')) for t in transactions)
    for k, v in sorted(type_counts.items()):
        print(f"  type={k}: {v} шт.")

    return income


print("=== ИССЛЕДОВАНИЕ K-РАСХОЖДЕНИЙ ===")
print("K = D - J = Выручка - (E+F+G+H)")
print("Анализируем: 20.02.2026 и 07.03.2026")

# ОВИР 20.02.2026
ovir_0220 = analyze_day(OVIR_TOKEN, 'ОВИР', '20220226')  # неверная дата - исправим

# Правильные даты
ovir_0220 = analyze_day(OVIR_TOKEN, 'ОВИР', '20260220')
zb_0220   = analyze_day(ZB_TOKEN,   'ЗБ',   '20260220')

ovir_0307 = analyze_day(OVIR_TOKEN, 'ОВИР', '20260307')
zb_0307   = analyze_day(ZB_TOKEN,   'ЗБ',   '20260307')
