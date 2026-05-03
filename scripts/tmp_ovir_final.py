#!/usr/bin/env python3
"""
Задача 1: Исследование K-расхождений ОВИР vs ЗБ
K = D(Выручка Poster) - J(Итого оплат из finance)
Поле суммы: amount (не sum!)
"""
import requests
import json
from collections import Counter, defaultdict

OVIR_TOKEN = '935215:79675564e3d086d7e03d5fd56b50c8df'
ZB_TOKEN   = '398711:8746917c4a23ea897774040e039dfb76'

BASE_URL = 'https://joinposter.com/api/finance.getTransactions'

def fetch_transactions(token, date_yyyymmdd):
    url = f"{BASE_URL}?token={token}&dateFrom={date_yyyymmdd}&dateTo={date_yyyymmdd}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get('response', [])

def classify_payment(comment):
    """Логика из parse_payments()"""
    c = (comment or '').lower()
    if 'алиф' in c or 'alif' in c:
        return 'F(Alif/Beeyor)'
    elif 'душанбе сити' in c or 'dushanbe city' in c:
        return 'G(DC)'
    elif 'безналичной' in c:
        return 'H(Карта)'
    elif 'наличной' in c or 'наличные' in c:
        return 'E(Нал)'
    elif not comment or comment.strip() == '':
        return '?(пусто)'
    else:
        return f'?(другое: {comment[:40]})'

def analyze_day(token, label, date_yyyymmdd, known_D=None, known_J=None):
    print(f"\n{'='*70}")
    print(f"  {label}  дата={date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:]}")
    if known_D:
        print(f"  Ожидаемые: D={known_D}, J={known_J}, K={known_D-known_J}")
    print(f"{'='*70}")

    transactions = fetch_transactions(token, date_yyyymmdd)
    print(f"Всего транзакций: {len(transactions)}")

    type_counts = Counter(str(t.get('type', '?')) for t in transactions)
    for k, v in sorted(type_counts.items()):
        label_t = 'income' if k == '1' else 'expense' if k == '0' else 'transfer/other'
        print(f"  type={k} ({label_t}): {v} шт.")

    income = [t for t in transactions if str(t.get('type', '')) == '1']

    print(f"\n--- type=1 (income): {len(income)} транзакций ---")
    print(f"{'TID':>8}  {'Сумма':>10}  {'Счёт':>20}  {'Категория':>18}  Тип оплаты")
    print(f"{'':>8}  {'':>10}  {'comment':<60}")
    print("-" * 110)

    total_income = 0
    pay_groups = defaultdict(float)

    for t in income:
        tid   = t.get('transaction_id', '?')
        amt   = float(t.get('amount', 0)) / 100  # в Poster amount в копейках/тийинах
        comm  = t.get('comment', '') or ''
        acc_name = t.get('account_name', '') or ''
        cat_name = t.get('category_name', '') or ''
        pay_type = classify_payment(comm)
        total_income += amt
        pay_groups[pay_type] += amt

        print(f"{tid:>8}  {amt:>10.0f}  {acc_name:>20}  {cat_name:>18}  {pay_type}")
        if comm:
            print(f"{'':>8}  {'':>10}  comment: {repr(comm)}")

    print(f"\n{'ИТОГО type=1':>40}: {total_income:>10.0f}")
    print(f"\n--- Группировка по типам оплаты ---")
    for pt, val in sorted(pay_groups.items(), key=lambda x: -x[1]):
        print(f"  {pt:<30}: {val:>10.0f}")

    # Тип 0 для справки
    expenses = [t for t in transactions if str(t.get('type', '')) == '0']
    exp_total = sum(float(t.get('amount', 0))/100 for t in expenses)
    print(f"\n--- type=0 (expense): {len(expenses)} транзакций, итого={exp_total:.0f} ---")
    for t in expenses[:5]:
        comm = t.get('comment', '') or ''
        acc  = t.get('account_name', '') or ''
        cat  = t.get('category_name', '') or ''
        amt  = float(t.get('amount', 0))/100
        print(f"  {t.get('transaction_id'):>8}  {amt:>10.0f}  {acc:>20}  {cat:>20}  {repr(comm)[:50]}")
    if len(expenses) > 5:
        print(f"  ... ещё {len(expenses)-5} транзакций")

    return income, total_income, pay_groups


print("╔══════════════════════════════════════════════════════════════════════╗")
print("║       ИССЛЕДОВАНИЕ K-РАСХОЖДЕНИЙ ОВИР vs ЗБ                        ║")
print("║  K = D(Выручка) - J(E+F+G+H), где J берётся из finance.getTransact ║")
print("╚══════════════════════════════════════════════════════════════════════╝")
print("\nПримечание: amount в API приходит в тийинах (×100), делим на 100")

print("\n\n### ═══ 20.02.2026 ════════════════════════════════════════════")
ovir_i, ovir_total, ovir_grp = analyze_day(OVIR_TOKEN, 'ОВИР', '20260220', known_D=3862, known_J=6034)
zb_i, zb_total, zb_grp = analyze_day(ZB_TOKEN, 'ЗБ', '20260220')

print("\n\n### ═══ 07.03.2026 ════════════════════════════════════════════")
ovir2_i, ovir2_total, ovir2_grp = analyze_day(OVIR_TOKEN, 'ОВИР', '20260307', known_D=7930, known_J=9323)
zb2_i, zb2_total, zb2_grp = analyze_day(ZB_TOKEN, 'ЗБ', '20260307')


print("\n\n╔══════════════════════════════════════════════════════════════════════╗")
print("║                     СВОДНЫЙ АНАЛИЗ                                  ║")
print("╚══════════════════════════════════════════════════════════════════════╝")
print(f"\n20.02.2026 ОВИР:  type=1 итого = {ovir_total:.0f}")
print(f"  Данные задачи:  D={3862}, J={6034}, K={3862-6034}")
print(f"  Если amount уже в сомони (не в тийинах):")
ovir_raw = sum(float(t.get('amount',0)) for t in ovir_i)
print(f"  Raw sum = {ovir_raw:.0f}")
