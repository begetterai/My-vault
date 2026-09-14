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
    r = B.SHEETS.get(B.API + B.BUDGET_SS + '/values/' + B._q('Operations!A2:H'),
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
                    'debt': str(row[7]).strip()})
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
    return {'income': by.get('Доход', 0.0), 'spent': by.get('Расход', 0.0),
            'saved': by.get('Накопление', 0.0), 'debt': by.get('Погашение', 0.0),
            'month': month, 'carry': start + carry, 'cash': start + carry + month}


def payload():
    """Всё, что нужно экрану за один запрос."""
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
        'balances': wallet_lines(),
        'habits': habits(),
        'debts': B.debt_state(),
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
                       wallet=str(body.get('wallet') or '').strip())
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
        '/api/debt_pay': debt_pay}


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
