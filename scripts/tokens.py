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
# «Сейчас» — настоящее время, а не время последней записи в логе.
# Раньше брали последнюю запись, и пауза не считалась: окно стояло на
# месте, израсходованное из него не выпадало, и счётчик показывал старый
# расход как текущий. Лимит же скользит по часам, а не по сообщениям.
now = datetime.datetime.now(datetime.timezone.utc)
window = datetime.timedelta(hours=5)
inside = [(t, fr) for t, fr in rows if now - t <= window]
spent = sum(fr for _, fr in inside)
pct = spent / STOP * 100

print(f'за последние 5 часов: {spent:,} свежих токенов')
print(f'норма остановки:      {STOP:,}  ({pct:.0f}%)')
print(f'порог лимита:         {LIMIT:,}')

idle = (now - rows[-1][0]).total_seconds() / 60
if idle >= 5:
    print(f'последняя запись:     {idle:.0f} мин назад')


def frees(target):
    """Через сколько минут расход в окне опустится до target."""
    left = spent
    for t, fr in inside:
        left -= fr
        if left <= target:
            return (t + window - now).total_seconds() / 60
    return 0


# Сколько освободится в ближайший час — это и есть «обновление лимита»:
# самые старые траты выходят из окна и перестают считаться.
soon = sum(fr for t, fr in inside if now - t >= window - datetime.timedelta(hours=1))
if soon:
    print(f'освободится за час:   {soon:,}')
elif inside:
    # Молчание здесь читалось бы как «скоро отпустит». Говорим прямо,
    # когда из окна выпадет хоть что-то.
    wait = (inside[0][0] + window - now).total_seconds() / 60
    print(f'освободится за час:   ничего, первое — через {wait:.0f} мин')

if spent >= STOP:
    wait = frees(STOP)
    print(f'\nСТОП: норма выбрана. До нормы ждать {wait:.0f} мин '
          f'({wait / 60:.1f} ч), потом можно продолжать.')
elif spent >= STOP * 0.8:
    print('\nБлизко к норме — крупных чтений не начинать')
