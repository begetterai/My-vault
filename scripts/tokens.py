#!/usr/bin/env python3
"""Сколько токенов израсходовано за скользящее 5-часовое окно.

Лимит тарифа считается по времени, поэтому важен не расход за сессию,
а расход за последние 5 часов. Норма остановки — см. CLAUDE.md.

Запуск: python3 scripts/tokens.py
"""
import json, glob, datetime

LOG = '/root/.claude/projects/-home-user-My-vault/*.jsonl'
LIMIT = 7_000_000   # эмпирический порог, на котором упирались в лимит
STOP = 6_000_000    # норма остановки

rows = []
for path in glob.glob(LOG):
    for line in open(path, encoding='utf-8'):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        u = (d.get('message') or {}).get('usage')
        ts = d.get('timestamp')
        if not u or not ts:
            continue
        t = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
        rows.append((t, u.get('input_tokens', 0) + u.get('output_tokens', 0)
                        + u.get('cache_creation_input_tokens', 0)))

if not rows:
    raise SystemExit('логи не найдены')

rows.sort()
now = rows[-1][0]
window = datetime.timedelta(hours=5)
spent = sum(fr for t, fr in rows if now - t <= window)
pct = spent / STOP * 100

print(f'за последние 5 часов: {spent:,} свежих токенов')
print(f'норма остановки:      {STOP:,}  ({pct:.0f}%)')
print(f'порог лимита:         {LIMIT:,}')
if spent >= STOP:
    print('\nСТОП: норма выбрана, закрываем хвосты и ждём сброса')
elif spent >= STOP * 0.8:
    print('\nБлизко к норме — крупных чтений не начинать')
