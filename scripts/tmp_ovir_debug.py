#!/usr/bin/env python3
"""
Debug: посмотреть полную структуру транзакции
"""
import requests
import json

OVIR_TOKEN = '935215:79675564e3d086d7e03d5fd56b50c8df'
BASE_URL = 'https://joinposter.com/api/finance.getTransactions'

resp = requests.get(f"{BASE_URL}?token={OVIR_TOKEN}&dateFrom=20260220&dateTo=20260220", timeout=30)
data = resp.json()

transactions = data.get('response', [])
print(f"Total: {len(transactions)}")

# Полный вывод первых 3 транзакций
print("\n=== ПЕРВЫЕ 3 ТРАНЗАКЦИИ (полная структура) ===")
for t in transactions[:3]:
    print(json.dumps(t, ensure_ascii=False, indent=2))

# Ищем type=1 с ненулевыми полями
print("\n=== ВСЕ ПОЛЯ type=1 транзакций ===")
income = [t for t in transactions if str(t.get('type', '')) == '1']
for t in income:
    print(json.dumps(t, ensure_ascii=False, indent=2))
    print("---")
