#!/usr/bin/env python3
"""Сквозная проверка приложения: код, данные, связи клиента и сервера.

Ловит то, что не ловит синтаксис: вызов несуществующей функции, обращение
к полю, которого сервер не отдаёт, ручку, которой нет на сервере, вкладку
не той ширины. Запускать после любой правки — дешевле, чем ловить это
на живой смене.
"""
import sys, os, re, ast, json, collections
sys.path.insert(0, '/home/user/My-vault/ops-system')
sys.path.insert(0, '/home/user/My-vault/scripts')

APP = '/home/user/My-vault/ops-system/app'
PAGE = '/home/user/My-vault/ops-system/web/index.html'
bad, warn = [], []


def js():
    s = open(PAGE, encoding='utf-8').read()
    return re.findall(r'<script[^>]*>(.*?)</script>', s, re.S)[-1], s


def check_python():
    for f in sorted(os.listdir(APP)):
        if f.endswith('.py'):
            try:
                ast.parse(open(os.path.join(APP, f), encoding='utf-8').read())
            except SyntaxError as e:
                bad.append(f'{f}: синтаксис — {e}')


def check_js_functions():
    """Наши функции: вызов без объявления и объявление без единой ссылки.

    Считаем не вызовы, а любые упоминания имени: функция может уходить
    ссылкой в список рендеров или в обработчик, и это не «не используется».
    """
    code, _ = js()
    declared = set(re.findall(
        r'^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)', code, re.M))
    declared |= set(re.findall(
        r'^\s*(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?[(\w]',
        code, re.M))
    # вызовы вида name(...) — но не obj.name(...)
    called = set(re.findall(r'(?<![.\w$])([a-zA-Z_$][\w$]{2,})\s*\(', code))
    known = declared | {
        'if', 'for', 'while', 'switch', 'catch', 'function', 'return', 'typeof',
        'parseInt', 'parseFloat', 'setTimeout', 'setInterval', 'clearTimeout',
        'clearInterval', 'fetch', 'confirm', 'alert', 'prompt', 'isNaN',
        'decodeURIComponent', 'encodeURIComponent', 'requestAnimationFrame',
        'async', 'await', 'var', 'let', 'const', 'new', 'delete', 'void',
        'Array', 'Object', 'String', 'Number', 'Boolean', 'Math', 'JSON',
        'Date', 'Set', 'Map', 'Promise', 'Error', 'RegExp',
        'FileReader', 'Image', 'Blob', 'URL', 'FormData', 'Intl'}
    for name in sorted(called - known):
        bad.append(f'js: {name}() вызывается, но нигде не объявлена')

    for name in sorted(declared):
        hits = len(re.findall(r'(?<![.\w$])' + re.escape(name) + r'(?![\w$])', code))
        if hits <= 1:
            warn.append(f'js: {name} объявлена, но нигде не используется')


def check_api():
    """Ручки, которые дёргает клиент, против маршрутов сервера."""
    code, _ = js()
    used = set(re.findall(r"fetch\('(/api/[a-z_]+)'", code))
    src = open(os.path.join(APP, 'webapp.py'), encoding='utf-8').read()
    have = set(re.findall(r"p(?:\.path)? == '(/api/[a-z_]+)'", src))
    for u in sorted(used - have):
        bad.append(f'клиент зовёт {u}, на сервере такого маршрута нет')
    for h in sorted(have - used - {'/api/init'}):
        warn.append(f'на сервере есть {h}, клиент его не зовёт')


def check_payload():
    """Поля DATA.*, которые читает клиент, против того, что кладёт сервер."""
    code, _ = js()
    src = open(os.path.join(APP, 'webapp.py'), encoding='utf-8').read()
    read = set(re.findall(r"DATA\.([a-z_]+)", code))
    read |= set(re.findall(r"DATA\?\.([a-z_]+)", code))
    sent = set(re.findall(r"out\['([a-z_]+)'\]", src))
    sent |= set(re.findall(r"'([a-z_]+)':", src[:src.index('def init_payload') + 3000]))
    for r in sorted(read - sent):
        bad.append(f'клиент читает DATA.{r}, сервер такого поля не кладёт')


def check_forms():
    from app import config as C
    from app import storage as ST
    from app import forms as F
    D = C.forms()

    tabs = collections.defaultdict(set)
    for k, cl in D.items():
        tabs[cl['tab']].add(cl['type'])
    for t, ty in tabs.items():
        if len(ty) > 1:
            bad.append(f'вкладка «{t}» делится типами {ty}')

    groups = collections.defaultdict(dict)
    for k, cl in C.checklists().items():
        if cl.get('stage'):
            groups[k.rsplit('_', 1)[0]][cl['stage']] = cl
    for g, st in groups.items():
        miss = set(C.STAGES) - set(st)
        if miss:
            bad.append(f'{g}: нет этапов {miss}')

    WANT = {'open': ['open', 'one'], 'give': ['open'],
            'take': ['close'], 'close': ['close', 'one']}
    for g, st in groups.items():
        for s_, cl in st.items():
            if cl.get('part') != WANT[s_]:
                bad.append(f'{g}_{s_}: смены {cl.get("part")}')
            if not cl.get('deadline'):
                bad.append(f'{g}_{s_}: нет срока')

    for k, cl in D.items():
        if cl.get('requires') and cl['requires'] not in D:
            bad.append(f'{k}: битая ссылка requires')

    titles = collections.Counter(cl['title'] for cl in D.values()
                                 if cl.get('type') == 'quiz')
    for t, n in titles.items():
        if n > 1:
            bad.append(f'два тренинга с названием «{t}» — сдача перепутается')

    for k, cl in D.items():
        if cl.get('type') != 'quiz':
            continue
        d = cl.get('doc') or {}
        if not d.get('url'):
            bad.append(f'{k}: тренинг без ссылки на регламент — '
                       f'первый шаг не откроется')

    ROLES = {'staff', 'senior', 'manager', 'coo'}
    DEPTS = {'кухня', 'цех', 'бар', 'касса', 'зал', 'управление', ''}
    for k, cl in D.items():
        for r in cl.get('roles') or []:
            if r not in ROLES:
                bad.append(f'{k}: неизвестная роль {r}')
        d = cl.get('dept') or ''
        for x in ([d] if isinstance(d, str) else d):
            if x.lower() not in DEPTS:
                bad.append(f'{k}: неизвестный отдел {x}')

    POS = [('Кухня', 'staff', 'кухня'), ('Цех', 'staff', 'цех'),
           ('Бар', 'staff', 'бар'), ('Касса', 'staff', 'касса'),
           ('Зал', 'staff', 'зал'), ('Старший смены', 'senior', 'кухня'),
           ('Управляющий', 'manager', ''), ('Директор', 'coo', '')]
    for name, role, dept in POS:
        if not C.for_role(role, dept):
            bad.append(f'{name}: не видит ни одного листа')
    return D


def check_score():
    """События, которые реально начисляются, против таблицы RULES.

    Разбираем деревом, а не текстом: третий аргумент бывает тернарником,
    а рядом стоят cl['code'] и st['kind'] — текстовый поиск вытаскивал их
    как названия событий.
    """
    from app import score as SC
    used = set()

    def literal(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        if isinstance(node, ast.IfExp):
            return literal(node.body) | literal(node.orelse)
        return set()

    for f in ('bot.py', 'webapp.py', 'score.py'):
        tree = ast.parse(open(os.path.join(APP, f), encoding='utf-8').read())
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            fn = n.func
            name = (fn.attr if isinstance(fn, ast.Attribute)
                    else getattr(fn, 'id', ''))
            if name != 'add' or len(n.args) < 3:
                continue
            used |= literal(n.args[2])

    for e in sorted(used - set(SC.RULES)):
        bad.append(f'начисляется событие «{e}», которого нет в RULES')
    for e in sorted(set(SC.RULES) - used - set(SC.AWARDABLE)):
        warn.append(f'событие «{e}» описано в RULES, но нигде не начисляется')


def check_time():
    from app import config as C
    order = ['09:30', '09:50', '17:30', '00:30', '03:30']
    mins = [C.op_minute(t) for t in order]
    if mins != sorted(mins):
        bad.append(f'сроки этапов идут не по порядку суток: {list(zip(order, mins))}')
    if C.op_minute(C.CLOSE_DAY_AT) <= C.op_minute('03:30'):
        bad.append(f'закрытие дня в {C.CLOSE_DAY_AT} наступает раньше, '
                   f'чем закрывается ОВИР (03:30)')
    if C.op_minute(C.BACKUP_AT) > C.op_minute('09:30'):
        warn.append(f'копия в {C.BACKUP_AT} делается уже после начала работы')


def check_sheet():
    from ops_docs import session
    from app import config as C
    from app import storage as ST
    from app import forms as F
    SH = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'
    B = 'https://sheets.googleapis.com/v4/spreadsheets/'
    s = session()
    meta = s.get(B + SH, params={'fields': 'sheets.properties'}, timeout=60).json()
    have = {x['properties']['title']: x['properties'] for x in meta['sheets']}
    want = {'Ознакомление': ST.READ_COLS}
    for k, cl in C.forms().items():
        cols = ST.FILL_COLS if cl['type'] == 'checklist' else F.cols_for(cl)
        if cols:
            want[cl['tab']] = cols
    for t, cols in want.items():
        p = have.get(t)
        if not p:
            bad.append(f'в таблице нет вкладки «{t}»')
        elif p['gridProperties'].get('columnCount', 0) < len(cols):
            bad.append(f'вкладка «{t}» уже шапки: '
                       f'{p["gridProperties"]["columnCount"]} < {len(cols)}')
    return len(want), len(have)


def main():
    check_python()
    check_js_functions()
    check_api()
    check_payload()
    D = check_forms()
    check_score()
    check_time()
    try:
        nw, nh = check_sheet()
        sheet = f'{nw} форм ↔ {nh} вкладок'
    except Exception as e:
        sheet = f'не проверено: {e}'
        warn.append(f'таблица не проверена: {e}')

    from app import config as C
    print(f'форм: {len(D)} · чек-листов: {len(C.checklists())} · '
          f'станций: {len(C.stations())} · таблица: {sheet}')
    print(f'\nошибок: {len(bad)}')
    for x in bad:
        print('  ⚠️', x)
    print(f'\nзамечаний: {len(warn)}')
    for x in warn:
        print('  ·', x)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
