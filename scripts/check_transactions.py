#!/usr/bin/env python3
"""
Проверка корректности транзакций в Poster (ЗБ и ОВИР).
Флагирует проблемные записи по правилам категоризации.

Использование:
  python3 check_transactions.py                # текущий месяц
  python3 check_transactions.py 2026-04-01 2026-04-30  # конкретный период
  python3 check_transactions.py --week         # последние 7 дней

Документ с правилами категорий:
  https://docs.google.com/document/d/1pFqgbDmThuQF2qvtG_oqMY7BrNd81rt-bKynycv7g4s/edit
"""
import json, os, sys, urllib.request, urllib.parse, datetime
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'

LOCATIONS = [
    {'name': 'ЗБ',   'token': '398711:8746917c4a23ea897774040e039dfb76'},
    {'name': 'ОВИР', 'token': '935215:79675564e3d086d7e03d5fd56b50c8df'},
]
POSTER_BASE = 'https://joinposter.com/api'

# ─── ПОРОГИ ───────────────────────────────────────────────────────────────────
LARGE_TX_THRESHOLD = 5_000   # сом — транзакция требует подробного описания
MIN_COMMENT_LEN    = 5       # минимум символов в комментарии
PROCHIE_LIMIT      = 3       # больше N "Прочих расходов" за период — тревога

# ─── ПРАВИЛА ПЕРЕОПРЕДЕЛЕНИЯ КАТЕГОРИЙ ───────────────────────────────────────
# Если комментарий содержит ключевое слово → ожидаемая категория
KEYWORD_CATEGORY_RULES = [
    (['зарплата', 'аванс', 'оклад', 'зп ', ' зп', 'зарп'],
     'ФОТ',
     'похоже на зарплату'),

    (['аренда', 'арендная', 'субаренда'],
     'Аренда',
     'похоже на аренду'),

    (['коммунал', 'электр', 'водоснабж', 'газ ', 'вода ', 'отопл'],
     'Коммунальные услуги',
     'похоже на коммуналку'),

    (['ремонт', 'сантехник', 'электрик', 'мастер', 'установка', 'монтаж'],
     'Ремонт и обслуживание',
     'похоже на ремонт/сервис'),

    (['маркетинг', 'реклама', 'smm', 'instagram', 'продвижение', 'баннер', 'листовк'],
     'Маркетинг и реклама',
     'похоже на маркетинг'),

    (['продукты', 'мясо', 'рыба', 'курица', 'овощи', 'фрукты', 'масло',
      'мука', 'сахар', 'соль', 'специи', 'зелень', 'молоко', 'яйца',
      'сливки', 'творог', 'сметана', 'йогурт', 'сыр'],
     'Бар / Кухня',
     'похоже на закупку продуктов'),

    (['доставка', 'курьер', 'яндекс', 'wolt', 'jett'],
     'Доставка',
     'похоже на доставку'),

    (['налог', 'штраф', 'пеня', 'проверка', 'инспекц'],
     'Налоги и штрафы',
     'похоже на налог/штраф'),

    (['чистящ', 'моющ', 'дезинфекц', 'перчатки', 'мешки для мусора', 'салфетки',
      'губки', 'тряпки', 'хоз'],
     'Хозяйственные расходы',
     'похоже на хозтовары'),

    (['кассовый аппарат', 'фискальный', 'принтер чеков', 'pos-терминал'],
     'Оборудование и инвентарь',
     'похоже на оборудование'),
]

# Категории, в которых продукты питания были бы ошибочны
BAR_KITCHEN_CATEGORIES = {
    'Бар', 'Кухня', 'Барная продукция', 'Кухонная продукция',
    'Продукты', 'Напитки', 'Сырьё', 'Поставки',
}
FOOD_WRONG_CATS = {
    'Расходы на заведение', 'Прочие расходы', 'Хозяйственные расходы',
    'Расходы', 'Административные расходы'
}

# Синонимы категорий — чтобы не флагировать семантически близкие категории
CATEGORY_ALIASES = {
    'фот':                    ['фот', 'зарплат'],
    'доставка':               ['доставк', 'логистик'],
    'аренда':                 ['аренд'],
    'коммунальные услуги':    ['коммунал', 'электр', 'водоснабж'],
    'ремонт и обслуживание':  ['ремонт', 'обслуживан', 'оборудован'],
    'маркетинг и реклама':    ['маркетинг', 'реклам', 'smm'],
    'налоги и штрафы':        ['налог', 'штраф', 'форс'],
    'оборудование и инвентарь': ['оборудован', 'инвентар'],
    'хозяйственные расходы':  ['хозяйствен', 'хозтовар'],
}

FOOD_KEYWORDS = [
    'продукты', 'мясо', 'рыба', 'курица', 'говядина', 'свинина',
    'овощи', 'фрукты', 'молоко', 'яйца', 'масло', 'мука', 'сахар',
    'сыр', 'сливки', 'творог', 'сметана', 'йогурт', 'зелень',
    'специи', 'соус', 'кетчуп', 'майонез', 'чай', 'кофе',
]


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


def fetch_transactions(token, date_from, date_to):
    ds = date_from.strftime('%Y%m%d')
    de = date_to.strftime('%Y%m%d')
    r = poster_get(token, 'finance.getTransactions', {'dateFrom': ds, 'dateTo': de})
    return r.get('response', [])


SKIP_CATS = {'Переводы', 'Внесения в кассу', 'Открытие ФС', 'Инкассация', 'Кассовые смены'}
# Poster: type=0 — расходы/переводы (отрицательные суммы); type=1 — приходы


def is_expense(t):
    return str(t.get('type', '')) == '0' and t.get('category_name', '') not in ('Кассовые смены',)


def amount_som(tx):
    return abs(int(tx.get('amount', 0))) / 100


def tx_date(tx):
    d = tx.get('date', '')
    return d[:10] if d else '?'


# ─── ПРАВИЛА ПРОВЕРКИ ─────────────────────────────────────────────────────────

def check_empty_comment(txs):
    """Расходные транзакции (не служебные категории) без комментария."""
    flags = []
    for t in txs:
        if not is_expense(t):
            continue
        cat = t.get('category_name', '') or ''
        if cat in SKIP_CATS:
            continue
        comment = (t.get('comment') or '').strip()
        if len(comment) < MIN_COMMENT_LEN:
            flags.append({
                'date': tx_date(t), 'amount': amount_som(t),
                'category': cat, 'comment': comment or '—',
                'issue': 'Нет комментария',
            })
    return flags


def check_prochie(txs):
    """Транзакции в категории «Прочие расходы»."""
    flags = []
    for t in txs:
        if not is_expense(t):
            continue
        cat = t.get('category_name', '') or ''
        if 'прочие' in cat.lower():
            comment = (t.get('comment') or '').strip()
            issue = ('Прочие расходы — короткое описание' if len(comment) < 10
                     else 'Прочие расходы — убедись что нет подходящей категории')
            flags.append({
                'date': tx_date(t), 'amount': amount_som(t),
                'category': cat, 'comment': comment or '—',
                'issue': issue,
            })
    return flags


def check_pereovody_no_detail(txs):
    """«Переводы» с кратким/отсутствующим комментарием.

    Каждый перевод в Poster создаёт 2 записи: type=0 (списание) и type=1 (зачисление).
    Смотрим только на type=0 (списание) чтобы не дублировать.
    """
    flags = []
    for t in txs:
        if str(t.get('type', '')) != '0':
            continue
        cat = t.get('category_name', '') or ''
        if cat != 'Переводы':
            continue
        comment = (t.get('comment') or '').strip()
        if len(comment) < MIN_COMMENT_LEN:
            flags.append({
                'date': tx_date(t), 'amount': amount_som(t),
                'category': cat, 'comment': comment or '—',
                'issue': 'Перевод без описания (откуда/куда)',
            })
    return flags


def check_large_no_detail(txs):
    """Крупные расходы (>5 000 с) с коротким комментарием."""
    flags = []
    for t in txs:
        if not is_expense(t):
            continue
        cat = t.get('category_name', '') or ''
        if cat in SKIP_CATS:
            continue
        amt = amount_som(t)
        if amt < LARGE_TX_THRESHOLD:
            continue
        comment = (t.get('comment') or '').strip()
        if len(comment) < 10:
            flags.append({
                'date': tx_date(t), 'amount': amt,
                'category': cat, 'comment': comment or '—',
                'issue': f'Крупная транзакция ({amt:,.0f} с) — нужно подробное описание',
            })
    return flags


def check_wrong_category(txs):
    """Комментарий указывает на другую категорию, чем выбранная."""
    flags = []
    for t in txs:
        if not is_expense(t):
            continue
        cat = (t.get('category_name') or '').strip()
        if cat in SKIP_CATS:
            continue
        comment = (t.get('comment') or '').lower().strip()
        if not comment:
            continue

        for keywords, expected_cat, hint in KEYWORD_CATEGORY_RULES:
            if any(kw in comment for kw in keywords):
                cat_lower = cat.lower()
                expected_lower = expected_cat.lower().split(' /')[0].split('/')[0].strip()
                aliases = CATEGORY_ALIASES.get(expected_lower, [expected_lower])
                already_correct = any(a in cat_lower for a in aliases)
                if not already_correct and cat not in BAR_KITCHEN_CATEGORIES:
                    flags.append({
                        'date': tx_date(t), 'amount': amount_som(t),
                        'category': cat, 'comment': (t.get('comment') or '').strip(),
                        'issue': f'Вероятно неверная категория — {hint}, ожидается: {expected_cat}',
                    })
                break

    return flags


def check_food_in_wrong_cat(txs):
    """Ключевые слова продуктов в нетоварных категориях."""
    flags = []
    for t in txs:
        if not is_expense(t):
            continue
        cat = (t.get('category_name') or '').strip()
        if cat not in FOOD_WRONG_CATS:
            continue
        comment = (t.get('comment') or '').lower()
        if any(kw in comment for kw in FOOD_KEYWORDS):
            flags.append({
                'date': tx_date(t), 'amount': amount_som(t),
                'category': cat, 'comment': (t.get('comment') or '').strip(),
                'issue': f'Продукты/сырьё в категории «{cat}» — должно быть в «Бар» или «Кухня»',
            })
    return flags


def check_duplicates(txs):
    """Потенциальные дубли: одинаковые сумма + категория + комментарий + дата."""
    seen = {}
    flags = []
    for t in txs:
        if not is_expense(t):
            continue
        cat = t.get('category_name', '') or ''
        if cat in ('Переводы', 'Открытие ФС', 'Кассовые смены'):
            continue
        comment = (t.get('comment') or '').strip().lower()
        # Только если ВСЕ четыре поля одинаковы — настоящий дубль
        key = (tx_date(t), cat, int(t.get('amount', 0)), comment)
        if key in seen:
            amt = amount_som(t)
            flags.append({
                'date': tx_date(t), 'amount': amt,
                'category': cat, 'comment': (t.get('comment') or '').strip() or '—',
                'issue': 'Возможный дубль (сумма + категория + комментарий + дата совпадают)',
            })
        else:
            seen[key] = t
    return flags


# ─── ОТЧЁТ ───────────────────────────────────────────────────────────────────

ISSUE_WEIGHT = {
    'Нет комментария': 3,
    'Прочие расходы': 2,
    'Перевод': 2,
    'Крупная': 3,
    'Возможный дубль': 4,
    'Вероятно неверная': 2,
    'Продукты': 2,
}


def weight(flag):
    for k, w in ISSUE_WEIGHT.items():
        if k.lower() in flag['issue'].lower():
            return w
    return 1


def analyse_location(name, token, date_from, date_to):
    print(f'\n{"━"*65}')
    print(f'  {name}  |  {date_from.strftime("%d.%m.%Y")} – {date_to.strftime("%d.%m.%Y")}')
    print(f'{"━"*65}')

    txs = fetch_transactions(token, date_from, date_to)
    expense_txs = [t for t in txs if is_expense(t) and t.get('category_name', '') not in SKIP_CATS]

    if not txs:
        print('  Нет транзакций за период.\n')
        return []

    total_expense = sum(amount_som(t) for t in expense_txs)
    print(f'  Всего транзакций: {len(txs)}  |  Расходных: {len(expense_txs)}  |  Сумма расходов: {total_expense:,.0f} с')

    # Прогоняем все проверки
    all_flags = []
    checkers = [
        ('Без комментария',           check_empty_comment),
        ('Прочие расходы',             check_prochie),
        ('Переводы без описания',      check_pereovody_no_detail),
        ('Крупные без описания',       check_large_no_detail),
        ('Неверная категория',         check_wrong_category),
        ('Продукты не там',            check_food_in_wrong_cat),
        ('Возможные дубли',            check_duplicates),
    ]
    counts = {}
    for label, fn in checkers:
        found = fn(txs)
        counts[label] = len(found)
        all_flags.extend(found)

    # Краткая сводка
    print()
    issues_total = len(all_flags)
    if issues_total == 0:
        print('  ✅  Нарушений не найдено.')
        return []

    print(f'  ⚠️  Найдено проблем: {issues_total}')
    for label, cnt in counts.items():
        if cnt:
            print(f'       {label:<30} {cnt:>3} шт.')

    # Детальный список, отсортированный по важности и дате
    print(f'\n  {"ДАТА":<12} {"СУММА(с)":>10}  {"КАТЕГОРИЯ":<28}  ПРОБЛЕМА / КОММЕНТАРИЙ')
    print(f'  {"-"*11}  {"-"*10}  {"-"*28}  {"-"*35}')
    for f in sorted(all_flags, key=lambda x: (-weight(x), x['date'])):
        date_s   = f['date']
        amt_s    = f'{f["amount"]:>10,.0f}'
        cat_s    = (f['category'] or '—')[:27]
        issue_s  = f['issue']
        comm_s   = f['comment'][:40]
        print(f'  {date_s:<12}{amt_s}  {cat_s:<28}  {issue_s}')
        if comm_s and comm_s != '—':
            print(f'  {"":<12}{"":<10}  {"":<28}  → «{comm_s}»')

    return all_flags


def summary_stats(all_results):
    """Итоговая сводка по обеим точкам."""
    if not any(r for r in all_results.values()):
        print('\n\n✅  ИТОГО: Нарушений не найдено по обеим точкам.')
        return

    total = sum(len(v) for v in all_results.values())
    print(f'\n\n{"═"*65}')
    print(f'  ИТОГО: {total} проблемных транзакций')
    for loc, flags in all_results.items():
        if flags:
            top = sorted(flags, key=lambda x: -weight(x))[:3]
            print(f'\n  {loc}:  {len(flags)} проблем')
            for f in top:
                print(f'    • {f["date"]}  {f["amount"]:,.0f} с  {f["issue"][:55]}')
    print(f'\n  Документ с правилами категорий:')
    print(f'  https://docs.google.com/document/d/1pFqgbDmThuQF2qvtG_oqMY7BrNd81rt-bKynycv7g4s/edit')
    print(f'{"═"*65}')


def main():
    today = datetime.date.today()

    if '--week' in sys.argv:
        date_from = today - datetime.timedelta(days=7)
        date_to = today
    elif len(sys.argv) >= 3:
        try:
            date_from = datetime.date.fromisoformat(sys.argv[1])
            date_to   = datetime.date.fromisoformat(sys.argv[2])
        except ValueError:
            print('Использование: check_transactions.py 2026-04-01 2026-04-30')
            sys.exit(1)
    else:
        date_from = today.replace(day=1)
        date_to   = today

    print(f'Ромашка — Проверка транзакций Poster')
    print(f'Период: {date_from.strftime("%d.%m.%Y")} – {date_to.strftime("%d.%m.%Y")}')
    print(f'Запуск: {datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}')

    results = {}
    for loc in LOCATIONS:
        flags = analyse_location(loc['name'], loc['token'], date_from, date_to)
        results[loc['name']] = flags

    summary_stats(results)


if __name__ == '__main__':
    main()
