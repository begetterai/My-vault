#!/usr/bin/env python3
"""Экран личных денег — мини-приложение к личному боту.

Зачем экран, когда есть переписка. В переписке бот угадывает: разбирает
фразу, показывает, что понял, и ждёт «да». Это две-три реплики на одну
трату и один разговор за раз. На экране угадывать нечего — сумма набрана,
категория нажата, — и запись уходит сразу. Плюс видно то, чего в переписке
не показать без команды: сколько осталось по каждому лимиту прямо сейчас.

Живёт в том же процессе, что и бот: пишем в одну таблицу, и разводить
это по двум службам значит держать два ключа, два деплоя и два места,
где может сломаться.

Пускаем одного человека — того, чей chat_id в TELEGRAM_CHAT_ID. Подпись
телеграма (initData) проверяем по его же токену бота: чужой браузер такую
подпись не соберёт.
"""
import collections
import hashlib
import hmac
import json
import logging
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import budget_bot as B

log = logging.getLogger('budget.web')

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
PAGE = os.path.join(WEB, 'dengi.html')


def who(init_data):
    """id человека из подписи телеграма. Подпись не сошлась — пусто.

    Считаем ровно по документации: ключ — HMAC(«WebAppData», токен бота),
    проверяемая строка — все поля, кроме hash, по алфавиту через перевод
    строки.
    """
    try:
        q = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
        got = dict(q).get('hash', '')
        if not got:
            return ''
        check = '\n'.join(f'{k}={v}' for k, v in sorted(q) if k != 'hash')
        secret = hmac.new(b'WebAppData', B.TG_TOKEN.encode(), hashlib.sha256).digest()
        mine = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mine, got):
            return ''
        user = json.loads(dict(q).get('user') or '{}')
        return str(user.get('id') or '')
    except Exception as e:
        log.warning('подпись: %s', e)
        return ''


def rows_with_lines():
    """[(номер строки, дата, тип, категория, сумма, комментарий)] — весь журнал.

    Номер строки нужен, чтобы править и удалять не только последнюю запись.
    Он живёт до следующей записи: журнал пересортировывается по дате после
    каждого добавления. Поэтому клиент всегда получает свежие номера, а
    перед правкой мы сверяем содержимое.
    """
    r = B.SHEETS.get(B.API + B.BUDGET_SS + '/values/' + B._q('Operations!A2:I'),
                     params={'valueRenderOption': 'UNFORMATTED_VALUE'}, timeout=60)
    out = []
    for i, row in enumerate(r.json().get('values', []) if r.ok else []):
        row = list(row) + ['', '', '', '', '']
        if not str(row[0]).strip():
            continue
        d = B._row_date(row[0])
        out.append({'line': i + 2, 'date': str(d) if d else str(row[0]),
                    'kind': str(row[1]).strip(), 'cat': str(row[2]).strip(),
                    'amount': row[3], 'comment': str(row[4]).strip(),
                    'wallet': str(row[5]).strip(), 'to': str(row[6]).strip(),
                    'debt': str(row[7]).strip(),
                    'project': str(row[8]).strip()})
    return out


def month_numbers():
    """Итог месяца числами: заработано, потрачено, отложено, долг, остаток."""
    ym = B.now_local().strftime('%Y-%m')
    by, carry = {}, 0.0
    for r in rows_with_lines():
        try:
            amount = float(str(r['amount']).replace(',', '.'))
        except (ValueError, TypeError):
            continue
        key = (r['date'] or '')[:7]
        if key < ym:
            carry += B.CASH_SIGN.get(r['kind'], 0) * amount
        elif key == ym:
            by[r['kind']] = by.get(r['kind'], 0.0) + amount
    month = sum(B.CASH_SIGN[t] * by.get(t, 0.0) for t in B.CASH_SIGN)
    # «На руках» считаем от стартовых остатков кошельков, а не от нуля.
    # 14.09.2026 на экране стояли две разные правды: крупная строка сверху
    # показывала −1, а список кошельков под ней — 1 385,85. Журнал знает
    # только движение; сколько было до первой записи, знают кошельки.
    start = sum(s for _, s in B.wallets())
    # «Свободно» — всё, кроме накопительного кошелька. Отложенное лежит
    # рядом, но это не деньги на жизнь, и показывать их одной суммой
    # значит мешать откладывать.
    bal, unknown = B.wallet_balances()
    sav = B.save_wallet()
    put_away = bal.get(sav, 0.0) if sav else 0.0
    cash = start + carry + month
    return {'income': by.get('Доход', 0.0), 'spent': by.get('Расход', 0.0),
            'saved': by.get('Накопление', 0.0), 'debt': by.get('Погашение', 0.0),
            'month': month, 'carry': start + carry, 'cash': cash,
            'put_away': round(put_away, 2), 'free': round(cash - put_away, 2),
            'from_savings': round(sum(B.spent_by_cat(from_savings=True).values()), 2)}


def trend(months=6):
    """Деньги по месяцам: заработано, потрачено, отложено.

    Динамика — единственное, что показывает смысл цифры: 15 308
    ничего не значит рядом с 7 912, пока их не поставить рядом.
    """
    rows = rows_with_lines()
    now = B.now_local()
    keys = []
    y, m = now.year, now.month
    for _ in range(months):
        keys.append(f'{y:04d}-{m:02d}')
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    keys.reverse()
    out = {k: {'income': 0.0, 'spent': 0.0, 'saved': 0.0} for k in keys}
    sav = B.save_wallet()
    for r in rows:
        k = (r['date'] or '')[:7]
        if k not in out:
            continue
        try:
            a = float(str(r['amount']).replace(',', '.'))
        except (ValueError, TypeError):
            continue
        if r['kind'] == 'Доход':
            out[k]['income'] += a
        elif r['kind'] == 'Расход':
            out[k]['spent'] += a
        elif r['kind'] == 'Перевод' and sav and r.get('to') == sav:
            out[k]['saved'] += a
        elif r['kind'] == 'Накопление':
            out[k]['saved'] += a
    RU = ['', 'янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг',
          'сен', 'окт', 'ноя', 'дек']
    return [{'ym': k, 'label': RU[int(k[5:])],
             'income': round(out[k]['income'], 2),
             'spent': round(out[k]['spent'], 2),
             'saved': round(out[k]['saved'], 2)} for k in keys]


def cat_trend(months=3, top=6):
    """Крупнейшие категории по месяцам — что растёт, а что стоит."""
    rows = [r for r in rows_with_lines() if r['kind'] == 'Расход']
    now = B.now_local()
    keys, y, m = [], now.year, now.month
    for _ in range(months):
        keys.append(f'{y:04d}-{m:02d}')
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    keys.reverse()
    by = {}
    for r in rows:
        k = (r['date'] or '')[:7]
        if k not in keys:
            continue
        try:
            a = float(str(r['amount']).replace(',', '.'))
        except (ValueError, TypeError):
            continue
        by.setdefault(r['cat'], {kk: 0.0 for kk in keys})[k] += a
    order = sorted(by, key=lambda c: -sum(by[c].values()))[:top]
    return {'months': keys,
            'rows': [{'cat': c, 'values': [round(by[c][k], 2) for k in keys]}
                     for c in order]}


def measures():
    """Меры с целью и последними значениями. Цели нет — просто копим числа:
    выдуманный ориентир хуже, чем его отсутствие."""
    today = B.today_local()
    out = []
    for c in B.meas_cfg():
        if not c['on']:
            continue
        rows = sorted(B.meas_rows(c['name']), key=lambda r: r[0], reverse=True)
        last = rows[0] if rows else None
        goal = B._num(c['goal']) if c['goal'] else None
        hit = None
        if last and goal is not None:
            hit = last[2] <= goal if c['better'] == 'меньше' else last[2] >= goal
        out.append({'name': c['name'], 'unit': c['unit'], 'goal': c['goal'],
                    'better': c['better'], 'at': c['at'],
                    'today': next((v for d, _n, v in rows if d == today), None),
                    'last': None if not last else {'date': str(last[0]),
                                                   'value': last[2]},
                    'hit': hit,
                    'history': [{'date': str(d), 'value': v}
                                for d, _n, v in rows[:14]]})
    return out


MIN_DAYS = 30


def links():
    """Связки: что в дни с привычкой и что в дни без неё.

    Только два измеренных средних и число дней, на которых они посчитаны.
    Ни слова «корреляция», ни процентов значимости: они создают ощущение
    науки там, где пока гадание. Пока дней меньше тридцати на группу,
    экран сам говорит «мало данных» — 04.07 дашборд уже показывал
    «прибыль», которая была выручкой без расходов.
    """
    closed = collections.Counter()
    for t in B.tasks(done=True):
        d = B._row_date(t['when']) if t['when'] else None
        if d:
            closed[d] += 1
    meas = {}
    for c in B.meas_cfg():
        if c['on']:
            meas[c['name']] = ({d: v for d, _n, v in B.meas_rows(c['name'])},
                               c['unit'])
    out = []
    for cfg in B.habit_cfg():
        if not cfg['on']:
            continue
        yes, no = [], []
        for d, _n, ans, _w in B.habit_rows(cfg['name'], days_back=180):
            (yes if ans == 'был' else no).append(d)
        if not yes or not no:
            continue
        pairs = [('Закрыто дел', closed, '')]
        pairs += [(name, vals, unit) for name, (vals, unit) in meas.items()]
        rows = []
        for name, vals, unit in pairs:
            a = [vals.get(d, 0) if name == 'Закрыто дел' else vals[d]
                 for d in yes if name == 'Закрыто дел' or d in vals]
            b = [vals.get(d, 0) if name == 'Закрыто дел' else vals[d]
                 for d in no if name == 'Закрыто дел' or d in vals]
            if not a or not b:
                continue
            rows.append({'what': name, 'unit': unit,
                         'with': round(sum(a) / len(a), 2), 'n_with': len(a),
                         'without': round(sum(b) / len(b), 2), 'n_without': len(b),
                         'thin': min(len(a), len(b)) < MIN_DAYS})
        if rows:
            out.append({'habit': cfg['name'], 'rows': rows})
    return out


def project_list():
    out = []
    for p in B.projects():
        tasks = [t for t in B.tasks() if t['project'] == p['name']]
        done = [t for t in B.tasks(done=True) if t['project'] == p['name']]
        spent = B.project_spent(p)
        hb = next((h for h in habits() if h['name'] == p['habit']), None)
        out.append(dict(p, spent=spent, habit_state=hb and {
                            'name': hb['name'], 'done_week': hb['done_week'],
                            'plan': hb['plan']},
                        tasks=[{'line': t['line'], 'text': t['text'],
                                'due': t['due']} for t in tasks],
                        left=round(p['budget'] - spent, 2) if p['budget'] else None,
                        steps_done=len(done), steps_total=len(done) + len(tasks),
                        next_step=(sorted(tasks, key=lambda t: t['due'] or '9999')
                                   or [None])[0]))
    return out


def measure(body):
    name = str(body.get('name') or '').strip()
    if name not in [c['name'] for c in B.meas_cfg()]:
        return {'ok': False, 'error': 'Нет такой меры'}
    try:
        value = float(str(body.get('value', '')).replace(',', '.'))
    except (ValueError, TypeError):
        return {'ok': False, 'error': 'Нужно число'}
    return {'ok': True, 'line': B.meas_write(name, value)}


def settings_get(body):
    kind = str(body.get('kind') or '')
    if kind not in B.SETTINGS:
        return {'ok': False, 'error': 'Нет таких настроек'}
    return {'ok': True, **B.setting_rows(kind)}


def settings_save(body):
    kind = str(body.get('kind') or '')
    if kind not in B.SETTINGS:
        return {'ok': False, 'error': 'Нет таких настроек'}
    line = B.setting_save(kind, int(body.get('line') or 0),
                          body.get('values') or [])
    return {'ok': not line.startswith('⚠️'), 'line': line,
            'error': line.lstrip('⚠️ ') if line.startswith('⚠️') else ''}


def settings_drop(body):
    kind = str(body.get('kind') or '')
    if kind not in B.SETTINGS or not int(body.get('line') or 0):
        return {'ok': False, 'error': 'Нечего убирать'}
    return {'ok': True, 'line': B.setting_drop(kind, int(body['line']))}


def goal_add(body):
    """Цель по деньгам — как обычная настройка, но с проверкой типа."""
    kind = str(body.get('kind') or '').strip().lower()
    if not any(kind.startswith(k[:6]) for k in B.GOAL_KINDS):
        return {'ok': False, 'error': 'Тип: откладывать в месяц, накопить '
                                      'или закрыть долг'}
    line = B.setting_save('goals_money', int(body.get('line') or 0),
                          [str(body.get('name') or ''), kind,
                           str(body.get('amount') or ''),
                           str(body.get('due') or ''), 'да'])
    return {'ok': not line.startswith('⚠️'), 'line': line,
            'error': line.lstrip('⚠️ ') if line.startswith('⚠️') else ''}


def payload():
    """Всё, что нужно экрану за один запрос."""
    B.cache_on()
    try:
        return _payload()
    finally:
        B.cache_off()


def _payload():
    lim, used = B.limits(force=True), B.spent_by_cat()
    rows = rows_with_lines()
    return {
        'ok': True,
        'today': str(B.today_local()),
        'cats': sorted(B.BUDGET_CATS),
        'income_cats': sorted(B.INCOME_CATS),
        'saving_cats': sorted(B.SAVINGS_CATS),
        # Закрытая категория (лимит 0) с тратой — сразу наверх: это не
        # «сто процентов израсходовано», а покупка там, где решено не тратить.
        'limits': [{'cat': c, 'limit': lim[c], 'used': round(used.get(c, 0.0), 2)}
                   for c in sorted(lim, key=lambda c: -(
                       used.get(c, 0.0) / lim[c] if lim[c]
                       else (999 if used.get(c, 0.0) else 0)))],
        'no_limit': sorted(c for c in B.BUDGET_CATS if c not in lim),
        'month': month_numbers(),
        'last': list(reversed(rows))[:12],
        'wallets': [w for w, _ in B.wallets(force=True)],
        'save_wallet': B.save_wallet(),
        'balances': wallet_lines(),
        'habits': habits(),
        'debts': B.debt_state(),
        'tasks': task_list(),
        'trend': trend(),
        'cat_trend': cat_trend(),
        'measures': measures(),
        'projects': project_list(),
        'goals_money': B.money_goals(),
        'cycle': B.cycle_state(),
        'links': links(),
        'screen': B.screen_items(),
    }


def wallet_lines():
    """[{кошелёк, остаток}] плюс строка «без кошелька», если такие есть."""
    bal, unknown = B.wallet_balances()
    out = [{'name': w, 'value': round(bal.get(w, 0.0), 2)}
           for w, _ in B.wallets()]
    if abs(unknown) > 0.004:
        # Записи из переписки кошелька не знают. Показываем отдельно,
        # а не размазываем: иначе остаток врёт молча.
        out.append({'name': 'Без кошелька', 'value': round(unknown, 2)})
    return out


def habits():
    """Привычки для экрана: ответ за сегодня, неделя, цикл, причины пропусков.

    Считаем выполнение, а не результат: результат у зала приходит через
    месяцы, а выполнение — сегодня, и держит регулярность именно оно.
    """
    today = B.today_local()
    week_start = today - B.datetime.timedelta(days=today.weekday())
    out = []
    for cfg in B.habit_cfg():
        if not cfg['on']:
            continue
        rows = B.habit_rows(cfg['name'], days_back=120)
        by_day = {d: a for d, _n, a, _w in rows}
        week = []
        for i in range(7):
            d = week_start + B.datetime.timedelta(days=i)
            week.append({'day': B.WEEK_RU[i], 'date': str(d),
                         'answer': by_day.get(d, ''),
                         'planned': B.WEEK_RU[i] in cfg['days'],
                         'future': d > today})
        why = {}
        for _d, _n, a, w in rows:
            if a == 'не был' and w:
                why[w] = why.get(w, 0) + 1
        out.append({
            'name': cfg['name'], 'plan': cfg['plan'], 'at': cfg['at'],
            'days': cfg['days'],
            'today': by_day.get(today, ''),
            'asked_today': today in by_day,
            'week': week,
            'done_week': sum(1 for d, a in by_day.items()
                             if a == 'был' and d >= week_start),
            'done_all': sum(1 for a in by_day.values() if a == 'был'),
            'skipped_all': sum(1 for a in by_day.values() if a == 'не был'),
            'why': sorted(why.items(), key=lambda kv: -kv[1]),
            'reasons': B.SKIP_WHY,
        })
    return out


def habit(body):
    """Ответ на привычку с экрана: «был» / «не был» и причина."""
    name = str(body.get('name') or '').strip()
    answer = str(body.get('answer') or '').strip()
    why = str(body.get('why') or '').strip()
    if name not in [c['name'] for c in B.habit_cfg()]:
        return {'ok': False, 'error': 'Нет такого направления'}
    if answer not in ('был', 'не был'):
        # Причину дописываем к сегодняшнему ответу, не заводя новой строки.
        if why:
            B.habit_set_why(name, why)
            return {'ok': True, 'line': f'Записал причину: {why}'}
        return {'ok': False, 'error': 'Ответ — «был» или «не был»'}
    if B.habit_asked_today(name):
        B.habit_set_answer(name, answer)
    else:
        B.habit_write(name, answer, why)
    return {'ok': True, 'line': f'{name}: {answer}'}


def task_list():
    """Дела тремя группами: просрочено · сегодня · дальше.

    Без срока — в «дальше»: задача без даты не просрочена, она просто
    не назначена, и пугать ею каждый день нечестно.
    """
    today = str(B.today_local())
    groups = {'late': [], 'today': [], 'later': []}
    for t in B.tasks():
        due = t['due']
        key = 'late' if due and due < today else 'today' if due == today else 'later'
        groups[key].append(t)
    for g in groups.values():
        g.sort(key=lambda t: (t['due'] or '9999', -t['moved']))
    done_week = 0
    week_ago = str(B.today_local() - B.datetime.timedelta(days=7))
    for t in B.tasks(done=True):
        if t['when'] and t['when'] >= week_ago:
            done_week += 1
    return {'late': groups['late'], 'today': groups['today'],
            'later': groups['later'],
            'top': [t for t in B.tasks() if t['top']],
            'done_week': done_week}


def task_add(body):
    line = B.add_task(str(body.get('text') or ''),
                      str(body.get('area') or '').strip(),
                      str(body.get('project') or '').strip(),
                      str(body.get('due') or '').strip(),
                      str(body.get('repeat') or '').strip())
    return {'ok': not line.startswith('⚠️'), 'line': line,
            'error': line.lstrip('⚠️ ') if line.startswith('⚠️') else ''}


def task_close(body):
    line = B.close_task(int(body.get('line') or 0))
    return {'ok': not line.startswith('⚠️'), 'line': line,
            'error': line.lstrip('⚠️ ') if line.startswith('⚠️') else ''}


def task_move(body):
    line, moved = B.move_task(int(body.get('line') or 0),
                              int(body.get('days') or 1))
    return {'ok': not line.startswith('⚠️'), 'line': line, 'moved': moved,
            # Третий перенос — повод спросить, нужна ли задача вообще.
            'ask': moved >= 3,
            'error': line.lstrip('⚠️ ') if line.startswith('⚠️') else ''}


def task_top(body):
    lines = [int(x) for x in (body.get('lines') or [])][:3]
    return {'ok': True, 'n': B.set_top(lines)}


def debt_pay(body):
    """Платёж по долгу с экрана."""
    try:
        amount = float(str(body.get('amount', '')).replace(',', '.'))
    except (ValueError, TypeError):
        return {'ok': False, 'error': 'Нужна сумма'}
    if amount <= 0:
        return {'ok': False, 'error': 'Сумма должна быть больше нуля'}
    line = B.pay_debt(str(body.get('debt') or '').strip(), amount,
                      str(body.get('wallet') or '').strip(),
                      str(body.get('comment') or '').strip())
    return {'ok': not line.startswith('⚠️'), 'line': line,
            'error': line.lstrip('⚠️ ') if line.startswith('⚠️') else ''}


def transfer(body):
    """Перевод между своими кошельками."""
    try:
        amount = float(str(body.get('amount', '')).replace(',', '.'))
    except (ValueError, TypeError):
        return {'ok': False, 'error': 'Нужна сумма'}
    if amount <= 0:
        return {'ok': False, 'error': 'Сумма должна быть больше нуля'}
    line = B.add_transfer(amount, str(body.get('from') or '').strip(),
                          str(body.get('to') or '').strip(),
                          str(body.get('comment') or '').strip(),
                          str(body.get('date') or '').strip() or None)
    return {'ok': not line.startswith('⚠️'), 'line': line,
            'error': line.lstrip('⚠️ ') if line.startswith('⚠️') else ''}


def add(body):
    """Записать операцию. Категорию выбрал человек — не угадываем."""
    try:
        amount = float(str(body.get('amount', '')).replace(',', '.'))
    except (ValueError, TypeError):
        return {'ok': False, 'error': 'Нужна сумма'}
    if amount <= 0:
        return {'ok': False, 'error': 'Сумма должна быть больше нуля'}
    cat = str(body.get('cat') or 'Прочее').strip()
    kind = str(body.get('kind') or 'расход').strip()
    line = B.add_entry(amount, cat, kind, str(body.get('comment') or '').strip(),
                       str(body.get('date') or '').strip() or None,
                       wallet=str(body.get('wallet') or '').strip(),
                       project=str(body.get('project') or '').strip())
    return {'ok': True, 'line': line}


def _same(row, want):
    """Та ли это строка, что человек видел на экране."""
    try:
        return (str(row['cat']) == str(want.get('cat'))
                and abs(float(row['amount']) - float(want.get('amount'))) < 0.005)
    except (ValueError, TypeError, KeyError):
        return False


def drop(body):
    """Удалить запись по номеру строки — любую, не только последнюю."""
    line = int(body.get('line') or 0)
    cur = next((r for r in rows_with_lines() if r['line'] == line), None)
    if not cur or not _same(cur, body):
        return {'ok': False, 'error': 'Запись изменилась — открой заново'}
    B.SHEETS.post(B.API + B.BUDGET_SS + ':batchUpdate', json={'requests': [
        {'deleteDimension': {'range': {'sheetId': 0, 'dimension': 'ROWS',
                                       'startIndex': line - 1, 'endIndex': line}}}]},
        timeout=60).raise_for_status()
    return {'ok': True}


FIELD = {'cat': 'C', 'amount': 'D', 'comment': 'E'}


def edit(body):
    """Поправить одно поле записи: категорию, сумму или комментарий."""
    field = str(body.get('field') or '')
    if field not in FIELD:
        return {'ok': False, 'error': 'Править можно категорию, сумму или комментарий'}
    line = int(body.get('line') or 0)
    cur = next((r for r in rows_with_lines() if r['line'] == line), None)
    if not cur or not _same(cur, body):
        return {'ok': False, 'error': 'Запись изменилась — открой заново'}
    value = body.get('value')
    if field == 'amount':
        try:
            value = float(str(value).replace(',', '.'))
        except (ValueError, TypeError):
            return {'ok': False, 'error': 'Нужно число'}
    elif field == 'cat' and str(value) not in (B.BUDGET_CATS | B.INCOME_CATS
                                               | B.SAVINGS_CATS | B.DEBT_CATS):
        return {'ok': False, 'error': 'Нет такой категории'}
    else:
        value = str(value).strip()[:80]
    B.SHEETS.put(B.API + B.BUDGET_SS + '/values/' + B._q(f'Operations!{FIELD[field]}{line}'),
                 params={'valueInputOption': 'USER_ENTERED'},
                 json={'values': [[value]]}, timeout=60).raise_for_status()
    return {'ok': True}


POST = {'/api/add': add, '/api/drop': drop, '/api/edit': edit,
        '/api/transfer': transfer, '/api/habit': habit,
        '/api/debt_pay': debt_pay, '/api/measure': measure,
        '/api/settings': settings_get, '/api/settings_save': settings_save,
        '/api/settings_drop': settings_drop, '/api/goal_add': goal_add, '/api/task_add': task_add,
        '/api/task_close': task_close, '/api/task_move': task_move,
        '/api/task_top': task_top}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        raw = body if isinstance(body, bytes) else json.dumps(
            body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _mine(self, init_data):
        uid = who(init_data)
        return bool(uid) and uid == str(B.ALLOWED)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path)
        if path.path in ('/', '/index.html', '/dengi.html'):
            try:
                with open(PAGE, 'rb') as f:
                    return self._send(200, f.read(), 'text/html; charset=utf-8')
            except OSError as e:
                return self._send(500, {'ok': False, 'error': str(e)})
        if path.path == '/api/init':
            q = urllib.parse.parse_qs(path.query)
            if not self._mine((q.get('initData') or [''])[0]):
                return self._send(403, {'ok': False, 'error': 'Это личное приложение'})
            try:
                return self._send(200, payload())
            except Exception as e:
                log.warning('init: %s', e)
                return self._send(500, {'ok': False, 'error': str(e)})
        self._send(404, {'ok': False, 'error': 'нет такой страницы'})

    def do_POST(self):
        fn = POST.get(urllib.parse.urlparse(self.path).path)
        if not fn:
            return self._send(404, {'ok': False, 'error': 'нет такого действия'})
        try:
            n = int(self.headers.get('Content-Length') or 0)
            body = json.loads(self.rfile.read(n) or b'{}')
        except (ValueError, TypeError):
            return self._send(400, {'ok': False, 'error': 'не разобрал запрос'})
        if not self._mine(str(body.get('initData') or '')):
            return self._send(403, {'ok': False, 'error': 'Это личное приложение'})
        try:
            return self._send(200, fn(body))
        except Exception as e:
            log.warning('%s: %s', self.path, e)
            return self._send(500, {'ok': False, 'error': str(e)})


def serve():
    """Поднять экран. Порт даёт Railway; локально — 8080."""
    port = int(os.environ.get('PORT', '8080'))
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
