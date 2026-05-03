#!/usr/bin/env python3
"""
Задача 1: Исследование K-расхождений ОВИР vs ЗБ
K = D - J = Выручка - Итого оплат (E+F+G+H)
"""
import requests
import json
from collections import Counter

OVIR_TOKEN = '935215:79675564e3d086d7e03d5fd56b50c8df'
ZB_TOKEN   = '398711:8746917c4a23ea897774040e039dfb76'

BASE_URL = 'https://joinposter.com/api/finance.getTransactions'

def fetch_transactions(token, date_from, date_to):
    url = f"{BASE_URL}?token={token}&dateFrom={date_from}&dateTo={date_to}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data

def analyze_day(token, label, date_yyyymmdd):
    print(f"\n{'='*65}")
    print(f"  {label}  дата={date_yyyymmdd}")
    print(f"{'='*65}")
    data = fetch_transactions(token, date_yyyymmdd, date_yyyymmdd)

    if 'response' not in data:
        print(f"ERROR: {json.dumps(data, ensure_ascii=False)}")
        return []

    transactions = data['response']
    print(f"Всего транзакций: {len(transactions)}")

    type_counts = Counter(str(t.get('type', '?')) for t in transactions)
    for k, v in sorted(type_counts.items()):
        print(f"  type={k}: {v} шт.")

    # type=1 = income
    income = [t for t in transactions if str(t.get('type', '')) == '1']
    print(f"\n--- type=1 (income) транзакции: {len(income)} шт. ---")
    total_income = 0
    for t in income:
        tid   = t.get('transaction_id', t.get('id', '?'))
        amt   = float(t.get('sum', 0))
        comm  = t.get('comment', '') or ''
        acc   = t.get('account_id', '')
        cat   = t.get('category_id', '')
        total_income += amt
        comm_lower = comm.lower()
        # Определяем тип оплаты по логике parse_payments
        if 'алиф' in comm_lower or 'alif' in comm_lower:
            pay_type = 'F(Alif)'
        elif 'душанбе сити' in comm_lower:
            pay_type = 'G(DC)'
        elif 'безналичной' in comm_lower:
            pay_type = 'H(Карта)'
        else:
            pay_type = 'E(нал) или ?'
        print(f"  id={tid}  сумма={amt:>10.2f}  pay_type={pay_type}")
        print(f"    comment: {repr(comm)}")
        print(f"    account_id={acc}  category_id={cat}")

    print(f"\nИТОГО type=1: {total_income:.2f}")

    # Для полноты — тип 0
    expense = [t for t in transactions if str(t.get('type', '')) == '0']
    exp_total = sum(float(t.get('sum', 0)) for t in expense)
    print(f"ИТОГО type=0 (expense): {exp_total:.2f}")

    # Все прочие типы
    other = [t for t in transactions if str(t.get('type', '')) not in ('0', '1')]
    if other:
        print(f"\n--- Прочие типы ---")
        for t in other:
            print(f"  type={t.get('type')}  sum={t.get('sum')}  comment={repr(t.get('comment',''))}")

    return income


print("=== ИССЛЕДОВАНИЕ K-РАСХОЖДЕНИЙ ===")
print("K = D(Выручка) - J(E+F+G+H)")
print("ОВИР 20.02: D=3862, J=6034, K=-2172")
print("ОВИР 07.03: D=7930, J=9323, K=-1393")

# 20.02.2026
ovir_0220 = analyze_day(OVIR_TOKEN, 'ОВИР', '20260220')
zb_0220   = analyze_day(ZB_TOKEN,   'ЗБ',   '20260220')

print("\n\n" + "="*65)
print("=== 07.03.2026 ===")
print("="*65)

# 07.03.2026
ovir_0307 = analyze_day(OVIR_TOKEN, 'ОВИР', '20260307')
zb_0307   = analyze_day(ZB_TOKEN,   'ЗБ',   '20260307')
