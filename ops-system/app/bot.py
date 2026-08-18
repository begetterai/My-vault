#!/usr/bin/env python3
"""Телеграм-бот: меню по ролям, чек-лист в чате, история, второй контур.

Всё, что бот знает о компании, приходит из конфига и листа «Команда».
"""
import datetime, random, re, requests

from . import config as C
from . import storage as S

API = 'https://api.telegram.org/bot'
STATE = {}          # chat_id → ход заполнения
CHECK = {}          # chat_id проверяющего → строка, к которой пишем расхождение
MENU_WORDS = ('чек-лист', 'чеклист', '/чеклист', 'смена', '/смена',
              'меню', '/меню', '/start', 'открытие', 'закрытие')
CANCEL = ('отмена', 'стоп', '/отмена')


def tg(method, **kw):
    """Вызов телеграма.

    Долгий опрос (getUpdates) держит соединение до kw['timeout'] секунд,
    поэтому ждать ответ надо ЗАВЕДОМО дольше — иначе связь рвётся раньше,
    чем приходит ответ, и бот молчит.
    """
    wait = int(kw.get('timeout', 0)) + 20
    try:
        return requests.post(f'{API}{C.BOT_TOKEN}/{method}',
                             json=kw, timeout=wait).json()
    except Exception as e:
        return {'ok': False, 'description': f'{type(e).__name__}: {e}'}


LIMIT = 3800        # телеграм режет на 4096; оставляем запас на разметку


def say(chat_id, text, **kw):
    """Длинный текст режем по строкам — клавиатура уходит с последней частью."""
    if len(text) <= LIMIT:
        return tg('sendMessage', chat_id=chat_id, text=text,
                  parse_mode='HTML', **kw)
    parts, cur = [], ''
    for ln in text.split('\n'):
        if len(cur) + len(ln) + 1 > LIMIT:
            parts.append(cur); cur = ''
        cur += ln + '\n'
    parts.append(cur)
    r = None
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        r = tg('sendMessage', chat_id=chat_id, text=part.rstrip(),
               parse_mode='HTML', **(kw if last else {}))
    return r


def admin(text):
    if C.ADMIN_CHAT:
        say(C.ADMIN_CHAT, text)


# ── проверки ввода ───────────────────────────────────────────────────────────
TIME_RE = re.compile(r'^([01]?\d|2[0-3])[:.\s]?([0-5]\d)$')


def parse_time(t):
    """«10:00», «10.00», «1000», «9:5» → «10:00» либо None."""
    m = TIME_RE.match(str(t).strip())
    return f'{int(m.group(1)):02d}:{m.group(2)}' if m else None


def parse_measure(t, m):
    """Число в границах ввода → (значение, ошибка)."""
    try:
        v = float(str(t).strip().replace(',', '.').replace('−', '-'))
    except ValueError:
        return None, 'Нужно число. Например: 4 или -19'
    lo, hi = m.get('min'), m.get('max')
    if lo is not None and v < lo or hi is not None and v > hi:
        return None, f'Значение вне допустимого: от {lo} до {hi} {m.get("unit", "")}'
    return v, None


def out_of_norm(v, m):
    """Число принято, но вне нормы — это сигнал, а не ошибка ввода."""
    lo, hi = m.get('ok_min'), m.get('ok_max')
    if lo is None and hi is None:
        return False
    return (lo is not None and v < lo) or (hi is not None and v > hi)


def norm_alerts(kind, measured):
    """[(вопрос, значение, норма)] по всем замерам вне нормы."""
    ms = C.checklists()[kind]['measures']
    out = []
    for n, val in measured.items():
        m = ms.get(n)
        if not m:
            continue
        try:
            v = float(str(val).replace(',', '.'))
        except ValueError:
            continue
        if out_of_norm(v, m):
            out.append((m['q'], val, m['norm'], m.get('unit', '')))
    return out


# ── экраны ───────────────────────────────────────────────────────────────────
def menu_kb(role):
    kb = []
    if C.WEBAPP_URL:
        kb.append([{'text': '📱 Открыть приложение', 'web_app': {'url': C.WEBAPP_URL}}])
    kb += [[{'text': f'🧾 {cl["title"]} (в чате)', 'callback_data': f'cl:go:{k}'}]
           for k, cl in C.for_role(role).items()]
    kb.append([{'text': {'staff': '📋 Мои последние',
                         'manager': '📋 История точки'}.get(role, '📋 История — все точки'),
                'callback_data': 'cl:h:' + {'staff': 'me', 'manager': 'point'}.get(role, 'all')}])
    if role in ('manager', 'coo'):
        kb.append([{'text': '➕ Добавить человека', 'callback_data': 'cl:addnew'}])
    if role == 'coo':
        kb.append([{'text': '💬 Идеи и задачи', 'callback_data': 'cl:h:ideas'}])
    kb.append([{'text': '✖️ Закрыть', 'callback_data': 'cl:cancel'}])
    return {'inline_keyboard': kb}


def icon(v):
    return '⬜' if v is None else ('✅' if v else '❌')


def block_screen(st):
    cl = C.checklists()[st['kind']]
    b = cl['blocks'][st['i']]
    left = sum(1 for it in b['items'] if st['marks'].get(it['n']) is None)
    head = (f'<b>{cl["title"]} · {st["point"]} · {st["day"]}</b>\n'
            f'Блок {st["i"] + 1} из {len(cl["blocks"])} — {b["name"]}\n\n')
    body, kb, row = [], [], []
    for k, it in enumerate(b['items'], 1):
        v = st['marks'].get(it['n'])
        body.append(f'{icon(v)} <b>{k}.</b> {it["text"]}'
                    + (f' <i>({it["norm"]})</i>' if it.get('norm') else ''))
        row.append({'text': f'{k} {icon(v)}', 'callback_data': f'cl:t:{it["n"]}'})
        if len(row) == 3:
            kb.append(row); row = []
    if row:
        kb.append(row)
    if left:
        tail = (f'\n\n<i>Отметь каждый пункт: первое нажатие — ✅, второе — ❌.\n'
                f'Осталось: {left}</i>')
        kb.append([{'text': f'⬜ Осталось {left}', 'callback_data': 'cl:need'}])
    else:
        last = st['i'] + 1 == len(cl['blocks'])
        tail = '\n\n<i>Блок отмечен полностью.</i>'
        kb.append([{'text': 'Далее ▶' if not last else '▶ К замерам',
                    'callback_data': 'cl:next'}])
    kb.append([{'text': '💬 Заметка / задача', 'callback_data': 'cl:note'},
               {'text': '✖️ Отмена', 'callback_data': 'cl:cancel'}])
    return head + '\n'.join(body) + tail, {'inline_keyboard': kb}


def history(scope, who):
    rows = []
    cls = list(C.for_role(S.role_of(who)).values())
    for cl, chunk in zip(cls, S.get_many([(cl['tab'], 'A2:P') for cl in cls])):
        for r in chunk:
            if len(r) < 8:
                continue
            if scope == 'me' and (len(r) < 3 or r[2] != who[0]):
                continue
            if scope == 'point' and r[1] != who[1]:
                continue
            rows.append((r, cl['title']))
    rows.sort(key=lambda x: (x[0][0][6:10], x[0][0][3:5], x[0][0][0:2]), reverse=True)
    if not rows:
        return 'Пока ни одного заполнения.'
    out = []
    for r, title in rows[:12]:
        chk = f'✅ пров. {r[13]}' if len(r) > 13 and r[13] else '⚠️ не проверено'
        out.append(f'<b>{r[0]}</b> · {r[1]} · {title.lower()} · {r[2]}')
        out.append(f'   {r[5]}/{r[6]} · {r[12] if len(r) > 12 else "?"} мин · {chk}')
        if len(r) > 8 and r[8] and r[8] != '—':
            out.append(f'   ❌ пункты: {r[8]}')
        if len(r) > 15 and r[15]:
            out.append(f'   ⚠️ {r[15]}')
    return '\n'.join(out)


def ideas_text():
    v = [r for r in S.get(C.TABS['ideas'], 'A2:G')
         if len(r) > 5 and r[5] != 'Закрыта']
    if not v:
        return 'Идей и задач пока нет.'
    out = ['<b>Открытые идеи и задачи</b>', '']
    for r in v[-10:][::-1]:
        out += [f'<b>{r[0]}</b> · {r[1]} · {r[2]}', f'   {r[4]}', f'   <i>{r[3]}</i>']
    return '\n'.join(out)


# ── ход заполнения ───────────────────────────────────────────────────────────
def ask_next(chat_id, st):
    cl = C.checklists()[st['kind']]
    if st['measures_left']:
        st['stage'] = 'measure'
        m = cl['measures'][st['measures_left'][0]]
        return say(chat_id, f'📏 <b>{m["q"]}</b>\nНорма: {m["norm"]} {m["unit"]}'
                            f'\n\nНапиши число.')
    if st['photos_left']:
        st['stage'] = 'photo'
        return say(chat_id, f'📷 <b>Пришли фото:</b> {st["photos_left"][0][1]}\n\n'
                            f'<i>Снимок должен быть сделан сейчас.</i>')
    if 'time' not in st:
        st['stage'] = 'time'
        return say(chat_id, cl['ask_time'] + ' Напиши время, например 10:00')
    fails = sorted(n for n, v in st['marks'].items() if v is False)
    if fails and 'comment' not in st:
        st['stage'] = 'comment'
        nm = {n: t for n, _, t in C.flat(st['kind'])}
        return say(chat_id, 'Не выполнено:\n'
                   + '\n'.join(f'❌ {n}. {nm[n]}' for n in fails)
                   + '\n\nНапиши коротко, почему по каждому.')
    finish(chat_id, st)


def finish(chat_id, st):
    sec = (C.now() - st['started']).total_seconds()
    try:
        dup = S.already_filled(st['kind'], st['day'], st['point'])
    except Exception:
        dup = None
    try:
        ok, tot, fails, line = S.save_fill(
            st['kind'], st['day'], st['point'], st['who'], st['marks'],
            st['measured'], st['photos_done'], st.get('time', ''),
            st.get('comment', ''), sec)
    except Exception as e:
        # НЕ стираем ход: человек прошёл 30 пунктов, терять их из-за сбоя сети нельзя
        say(chat_id, f'⚠️ Не смог сохранить: {e}\n\n'
                     'Отметки не потеряны. Напиши «ещё раз» — попробую снова.')
        st['stage'] = 'retry'
        return
    STATE.pop(chat_id, None)
    fast = sec < C.MIN_SECONDS
    say(chat_id, f'✅ Записал. <b>{ok} из {tot}</b> ({round(ok / tot * 100)}%), '
                 f'заняло {round(sec / 60)} мин.'
        + ('\n\n⚠️ Слишком быстро — управляющий это увидит.' if fast else ''))
    if dup:
        say(chat_id, f'♻️ Сегодня этот чек-лист уже заполнял {dup}. '
                     'Записал обе версии, управляющий увидит.')
    notify_check(st, ok, tot, fails, line, st.get('comment', ''), fast, bool(dup))


def full_list(kind, fails):
    """Весь чек-лист по блокам: что сделано и что нет. Не только провалы —
    руководитель должен видеть объём работы, а не только её обрыв."""
    cl = C.checklists()[kind]
    bad = set(int(n) for n in fails)
    L = []
    for b in cl['blocks']:
        done = sum(1 for it in b['items'] if it['n'] not in bad)
        L.append(f'<b>{b["name"]}</b> — {done}/{len(b["items"])}')
        for it in b['items']:
            mark = '❌' if it['n'] in bad else '✅'
            L.append(f'{mark} {it["n"]}. {it["text"]}')
        L.append('')
    return '\n'.join(L)


def notify_check(st, ok, tot, fails, line, comment, fast, dup=False):
    cl = C.checklists()[st['kind']]
    lst = full_list(st['kind'], fails)
    warn = ('\n⚠️ заполнено быстрее норматива' if fast else '') \
        + ('\n♻️ повторное заполнение за сегодня' if dup else '')
    txt = (f'🔎 <b>Проверь заполнение</b>\n{st["point"]} · {cl["title"].lower()} '
           f'{st["day"]} · {st["who"]}\nВыполнено <b>{ok} из {tot}</b>{warn}\n\n{lst}'
           + (f'💬 {comment}\n' if comment else '')
           + '\nПройди по точке и подтверди — или опиши, что не сошлось.')
    kb = {'inline_keyboard': [[
        {'text': '✅ Проверил', 'callback_data': f'cl:ck:ok:{st["kind"]}:{line}'},
        {'text': '⚠️ Расхождение', 'callback_data': f'cl:ck:bad:{st["kind"]}:{line}'}]]}
    sent = set()
    for cid in S.managers_of(st['point']):
        say(cid, txt, reply_markup=kb)
        sent.add(str(cid))
    if str(C.ADMIN_CHAT) in sent:
        return
    if not sent:
        # некому проверять — молчать нельзя, иначе второй контур просто исчезает
        say(C.ADMIN_CHAT, f'⚠️ У точки {st["point"]} нет управляющего.\n\n' + txt,
            reply_markup=kb)
    elif fails or fast or dup:
        admin(txt)


def pct(ok, tot):
    a, b = _num(ok), _num(tot)
    return f'{round(a / b * 100)}%' if a is not None and b else '—'


def _num(x):
    try:
        return float(str(x).replace(',', '.').replace(' ', ''))
    except (ValueError, TypeError):
        return None


def final_report(kind, line, verdict, checker, note=''):
    """Оба круга пройдены — COO получает итог. Это конец цикла по заполнению."""
    cl = C.checklists()[kind]
    rows = S.get(cl['tab'], f'A{line}:P{line}')
    if not rows:
        return
    r = rows[0] + [''] * (16 - len(rows[0]))
    mark = '✅ подтверждено' if verdict == 'ok' else '⚠️ расхождение'
    L = [f'📋 <b>Итог: {cl["title"].lower()} · {r[1]} · {r[0]}</b>', '',
         f'Заполнил: {r[2]} в {r[3]}, время открытия {r[4]}',
         f'Выполнено: <b>{r[5]} из {r[6]}</b> ({pct(r[5], r[6])})',
         f'Заняло: {r[12]} мин']
    nums = [int(x) for x in str(r[8]).split(',') if x.strip().isdigit()]
    L.append('')
    L.append(full_list(kind, nums))
    if r[9]:
        L.append(f'💬 {r[9]}')
    if r[10]:
        L.append('')
        L.append(f'<b>Замеры:</b> {r[10]}')
        # Разбираем по НАЗВАНИЮ замера, а не по порядку: если замер пропущен,
        # порядковая привязка молча припишет число не тому вопросу.
        by_q = {m['q'].strip().lower(): n for n, m in cl['measures'].items()}
        got = {}
        for part in str(r[10]).split(';'):
            if ':' in part:
                q, v = part.rsplit(':', 1)
                n = by_q.get(q.strip().lower())
                if n is not None:
                    got[n] = v.strip()
        for q, val, norm, unit in norm_alerts(kind, got):
            L.append(f'   ⚠️ {q}: {val} при норме {norm} {unit}')
    if r[11]:
        L.append(f'📷 фото: {len(str(r[11]).split())}')
    L.append('')
    L.append(f'<b>Проверка управляющим: {mark}</b> — {checker}')
    if note:
        L.append(f'   {note}')
    txt = '\n'.join(L)
    sent = set()
    for cid in S.managers_of(r[1]):
        say(cid, txt)
        sent.add(str(cid))
    if str(C.ADMIN_CHAT) not in sent:
        admin(txt)


# ── подключение человека ─────────────────────────────────────────────────────
_SEEN = set()               # кому уже сказали id — не спамим руководителю


def full_name(u):
    return ' '.join(x for x in (u.get('first_name'), u.get('last_name')) if x) \
        or (u.get('username') or 'без имени')


ROLES = ['Управляющий', 'Бариста', 'Кассир', 'Повар', 'Старший повар',
         'Уборщица', 'Закупщик']
ADD = {}            # chat_id руководителя → кого добавляем


def unknown(chat_id, u):
    """Человека нет в «Команде»: ему — его id, руководителю — кнопку «Добавить»."""
    name = full_name(u)
    tag = ('@' + u['username']) if u.get('username') else '—'
    say(chat_id, 'Тебя ещё нет в системе.\n\n'
                 f'<b>Твой ID: <code>{chat_id}</code></b>\n\n'
                 'Руководителю уже ушёл запрос. Как добавит — напиши «меню».')
    if chat_id not in _SEEN:
        _SEEN.add(chat_id)
        say(C.ADMIN_CHAT or chat_id,
            '👤 <b>Просится в систему</b>\n'
            f'{name} · {tag}\nID: <code>{chat_id}</code>',
            reply_markup={'inline_keyboard': [[
                {'text': f'➕ Добавить {name}', 'callback_data': f'cl:add:{chat_id}'}]]})
    return True


def add_ask_point(boss, add):
    pts = S.points()
    kb = [[{'text': p, 'callback_data': f'cl:ap:{p}'}] for p in pts]
    kb.append([{'text': '✏️ Другая точка', 'callback_data': 'cl:ap:'}])
    say(boss, f'Точка для <b>{add["name"]}</b>?',
        reply_markup={'inline_keyboard': kb})


def add_ask_role(boss, add):
    kb = [[{'text': r, 'callback_data': f'cl:ar:{r}'}] for r in ROLES]
    say(boss, f'Роль <b>{add["name"]}</b> на точке {add["point"]}?\n\n'
              'От роли зависит меню: управляющий видит историю точки '
              'и подтверждает заполнения, остальные — только свои.',
        reply_markup={'inline_keyboard': kb})


def add_done(boss, add):
    S.add_member(add['id'], add['name'], add['point'], add['role'])
    say(boss, f'✅ Добавил.\n<b>{add["name"]}</b> · {add["point"]} · {add["role"]}\n\n'
              'Пусть напишет боту «меню» — увидит своё.')
    say(add['id'], f'Готово. Ты в системе: <b>{add["point"]}</b> · {add["role"]}.\n'
                   'Напиши «меню» — покажу, что делать.')


# ── входные точки ────────────────────────────────────────────────────────────
def on_message(msg):
    chat_id = str(msg.get('chat', {}).get('id', ''))
    t = (msg.get('text') or '').strip()
    low = t.lower().replace('ё', 'е')
    st = STATE.get(chat_id)

    if low in ('/id', 'id', 'мой id') and not st:
        say(chat_id, f'Твой ID: <code>{chat_id}</code>')
        return True

    add = ADD.get(chat_id)
    if add and not st:
        if low in CANCEL:
            ADD.pop(chat_id, None)
            say(chat_id, 'Отменил, никого не добавил.')
        elif add['step'] == 'id':
            if not t.strip().lstrip('-').isdigit():
                say(chat_id, 'ID — это только цифры. Пришли номер или «отмена».')
                return True
            add['id'], add['step'] = t.strip(), 'name'
            say(chat_id, 'Как его зовут? Так он будет подписан во всех отчётах.')
        elif add['step'] == 'name':
            add['name'], add['step'] = t[:60], 'point'
            add_ask_point(chat_id, add)
        elif add['step'] == 'point':
            add['point'], add['step'] = t[:40], 'role'
            add_ask_role(chat_id, add)
        elif add['step'] == 'role':
            add['role'] = t[:40]
            ADD.pop(chat_id, None)
            add_done(chat_id, add)
        return True

    if chat_id in CHECK and not st:
        kind, line, name = CHECK.pop(chat_id)
        S.save_check(kind, line, name, 'bad', t[:300])
        say(chat_id, 'Записал расхождение.')
        try:
            final_report(kind, line, 'bad', name, t[:300])
        except Exception as e:
            print('итоговый отчёт:', e)
        return True

    if st and st.get('stage') == 'retry':
        if low in CANCEL:
            STATE.pop(chat_id, None)
            say(chat_id, 'Отменил. Ничего не сохранено.')
        else:
            say(chat_id, 'Пробую ещё раз…')
            finish(chat_id, st)
        return True

    if st and low in CANCEL:
        STATE.pop(chat_id, None)
        say(chat_id, 'Отменил. Ничего не сохранено.')
        return True

    if st is None:
        if low not in MENU_WORDS:
            return False
        who = S.team().get(chat_id)
        if not who:
            return unknown(chat_id, msg.get('from') or {})
        say(chat_id, f'<b>{who[0]}</b> · {who[1]}\nЧто делаем?',
            reply_markup=menu_kb(S.role_of(who)))
        return True

    stage = st['stage']
    if stage == 'note':
        if len(t.split()) < 3:
            say(chat_id, 'Коротко — потом не разберём. Напиши фразой: '
                         '<i>что не так и что с этим делать</i>.')
            return True
        src = f'{C.checklists()[st["kind"]]["code"]} блок {st["i"] + 1}'
        S.save_note(st['day'], st['who'], st['point'], src, t[:400])
        say(chat_id, f'💬 <b>Записал в «Идеи и задачи»</b>\n\n«{t[:300]}»\n\n'
                     f'{st["day"]} · {st["point"]} · {st["who"]}\n'
                     f'Источник: {src} · Статус: Новая')
        admin(f'💬 <b>Идея с точки {st["point"]}</b> · {st["who"]}\n«{t[:300]}»')
        st['stage'] = st.pop('note_return', 'blocks')
        return True

    if stage == 'measure':
        n = st['measures_left'][0]
        m = C.checklists()[st['kind']]['measures'][n]
        v, err = parse_measure(t, m)
        if err:
            say(chat_id, err)
            return True
        st['measured'][st['measures_left'].pop(0)] = t.strip()[:20]
        if out_of_norm(v, m):
            say(chat_id, f'⚠️ <b>{v} {m.get("unit", "")} — вне нормы</b> '
                         f'({m["norm"]} {m.get("unit", "")}).\n'
                         f'Запишу как есть. Если это не ошибка ввода — '
                         f'сообщи управляющему сейчас, не жди конца смены.')
            admin(f'🌡 <b>Замер вне нормы</b> · {st["point"]} · {st["who"]}\n'
                  f'{m["q"]}: <b>{v} {m.get("unit", "")}</b> '
                  f'при норме {m["norm"]}')
        ask_next(chat_id, st)
        return True

    if stage == 'photo':
        if 'photo' not in msg:
            say(chat_id, 'Нужно именно фото. Сфотографируй и пришли.')
            return True
        n, _ = st['photos_left'].pop(0)
        link = ''
        try:
            f = tg('getFile', file_id=msg['photo'][-1]['file_id'])
            path = f.get('result', {}).get('file_path')
            if path:
                raw = requests.get(
                    f'https://api.telegram.org/file/bot{C.BOT_TOKEN}/{path}',
                    timeout=60).content
                link = S.save_photo(raw, f'{st["point"]}-{st["day"]}-п{n}')
        except Exception:
            pass
        st['photos_done'].append(link or f'п{n}:есть')
        ask_next(chat_id, st)
        return True

    if stage == 'time':
        hhmm = parse_time(t)
        if not hhmm:
            say(chat_id, 'Нужно время в формате <b>ЧЧ:ММ</b> — например 10:00')
            return True
        st['time'] = hhmm
        ask_next(chat_id, st)
        return True

    if stage == 'comment':
        st['comment'] = '' if low in ('нет', 'no', '-') else t[:300]
        ask_next(chat_id, st)
        return True

    say(chat_id, 'Отмечай кнопками выше. «Отмена» — начать заново.')
    return True


def on_callback(cq):
    data = cq.get('data', '')
    if not data.startswith('cl:'):
        return False
    chat_id = str(cq['message']['chat']['id'])
    mid = cq['message']['message_id']
    ack = lambda s='': tg('answerCallbackQuery', callback_query_id=cq['id'], text=s)
    who = S.team().get(chat_id)

    if data == 'cl:cancel':
        STATE.pop(chat_id, None)
        tg('editMessageText', chat_id=chat_id, message_id=mid, text='Закрыл.')
        return ack() or True
    if data == 'cl:need':
        return ack('Сначала отметь все пункты блока') or True

    if data == 'cl:addnew':
        if S.role_of(who or ('', '', '')) not in ('manager', 'coo'):
            return ack('Добавляет только руководитель') or True
        ADD[chat_id] = {'step': 'id'}
        tg('editMessageText', chat_id=chat_id, message_id=mid,
           text='Пришли ID человека. Чтобы его узнать — пусть напишет '
                'этому боту «id», бот ответит номером.')
        return ack() or True
    if data.startswith('cl:add:'):
        if S.role_of(who or ('', '', '')) not in ('manager', 'coo'):
            return ack('Добавляет только руководитель') or True
        ADD[chat_id] = {'id': data.split(':', 2)[2], 'step': 'name'}
        tg('editMessageText', chat_id=chat_id, message_id=mid,
           text='Добавляем. Как его зовут? Напиши имя — так он будет '
                'подписан во всех отчётах.')
        return ack() or True
    if data.startswith('cl:ap:') and chat_id in ADD:
        p = data.split(':', 2)[2]
        if not p:
            return ack('Напиши название точки текстом') or True
        ADD[chat_id]['point'], ADD[chat_id]['step'] = p, 'role'
        add_ask_role(chat_id, ADD[chat_id])
        return ack() or True
    if data.startswith('cl:ar:') and chat_id in ADD:
        ADD[chat_id]['role'] = data.split(':', 2)[2]
        add_done(chat_id, ADD.pop(chat_id))
        return ack() or True

    if not who:
        return ack('Нет доступа') or True

    if data == 'cl:menu':
        tg('editMessageText', chat_id=chat_id, message_id=mid, parse_mode='HTML',
           text=f'<b>{who[0]}</b> · {who[1]}\nЧто делаем?',
           reply_markup=menu_kb(S.role_of(who)))
        return ack() or True

    if data.startswith('cl:h:'):
        scope = data.split(':')[2]
        txt = ideas_text() if scope == 'ideas' else history(scope, who)
        tg('editMessageText', chat_id=chat_id, message_id=mid, text=txt,
           parse_mode='HTML', reply_markup={'inline_keyboard': [
               [{'text': '◀ Назад', 'callback_data': 'cl:menu'}]]})
        return ack() or True

    if data.startswith('cl:ck:'):
        _, _, verdict, kind, line = data.split(':')
        if verdict == 'ok':
            S.save_check(kind, line, who[0], 'ok')
            tg('editMessageText', chat_id=chat_id, message_id=mid,
               text=cq['message'].get('text', '') + f'\n\n✅ Проверил: {who[0]}')
            try:
                final_report(kind, line, 'ok', who[0])
            except Exception as e:
                print('итоговый отчёт:', e)
            return ack('Записал') or True
        CHECK[chat_id] = (kind, line, who[0])
        say(chat_id, 'Напиши, что именно не сошлось.')
        return ack() or True

    if data.startswith('cl:go:'):
        kind = data.split(':')[2]
        if kind not in C.checklists():
            return ack('Нет такого чек-листа') or True
        photos = C.photo_items(kind)
        random.shuffle(photos)
        STATE[chat_id] = {
            'kind': kind, 'day': C.day_str(),
            'point': who[1], 'who': who[0], 'i': 0, 'marks': {}, 'stage': 'blocks',
            'started': C.now(),
            'measures_left': list(C.checklists()[kind]['measures'].keys()),
            'measured': {}, 'photos_left': photos[:C.PHOTOS_PER_RUN],
            'photos_done': []}
        txt, kb = block_screen(STATE[chat_id])
        tg('editMessageText', chat_id=chat_id, message_id=mid, text=txt,
           parse_mode='HTML', reply_markup=kb)
        return ack() or True

    st = STATE.get(chat_id)
    if not st or st['stage'] not in ('blocks',):
        if data == 'cl:note' and st:
            st['note_return'] = st['stage']; st['stage'] = 'note'
            say(chat_id, '💬 <b>Что добавить в регламент или что сделать?</b>\n\n'
                         'Пиши целой фразой, чтобы через неделю было понятно.')
            return ack() or True
        return ack('Начни заново: напиши «чек-лист»') or True

    if data == 'cl:note':
        st['note_return'] = st['stage']; st['stage'] = 'note'
        say(chat_id, '💬 <b>Что добавить в регламент или что сделать?</b>\n\n'
                     'Пиши целой фразой, чтобы через неделю было понятно.\n\n'
                     '<i>Например: «Купить второй термощуп, одного на две станции '
                     'не хватает»</i>')
        return ack() or True

    if data.startswith('cl:t:'):
        n = int(data.split(':')[2])
        v = st['marks'].get(n)
        st['marks'][n] = True if v is None else (False if v else True)
        txt, kb = block_screen(st)
        tg('editMessageText', chat_id=chat_id, message_id=mid, text=txt,
           parse_mode='HTML', reply_markup=kb)
        return ack('выполнено' if st['marks'][n] else 'НЕ выполнено') or True

    if data == 'cl:next':
        cl = C.checklists()[st['kind']]
        if any(st['marks'].get(it['n']) is None for it in cl['blocks'][st['i']]['items']):
            return ack('Отметь все пункты блока') or True
        st['i'] += 1
        if st['i'] < len(cl['blocks']):
            txt, kb = block_screen(st)
            tg('editMessageText', chat_id=chat_id, message_id=mid, text=txt,
               parse_mode='HTML', reply_markup=kb)
        else:
            done = sum(1 for v in st['marks'].values() if v)
            tg('editMessageText', chat_id=chat_id, message_id=mid, parse_mode='HTML',
               text=f'<b>{cl["title"]} · {st["point"]} · {st["day"]}</b>\n'
                    f'Отмечено: {done} из {cl["total"]}')
            ask_next(chat_id, st)
        return ack() or True
    return False


def whoami():
    """Спрашиваем у телеграма, кто мы. Молчащий бот — почти всегда плохой токен."""
    r = tg('getMe')
    if not r.get('ok'):
        raise RuntimeError('Телеграм отклонил токен: '
                           + str(r.get('description') or r))
    u = r['result']
    return u.get('username'), u.get('first_name')


# ── разбор входящих ──────────────────────────────────────────────────────────
WORKERS = int(__import__('os').environ.get('WORKERS', '6'))
_QS = []


def _chat_of(upd):
    m = upd.get('message') or (upd.get('callback_query') or {}).get('message') or {}
    return str((m.get('chat') or {}).get('id', ''))


def _worker(q):
    while True:
        upd = q.get()
        try:
            if 'callback_query' in upd:
                on_callback(upd['callback_query'])
            elif 'message' in upd:
                on_message(upd['message'])
        except Exception as e:
            print('обработка:', e)


def start_workers():
    """Обновления идут в очереди по числу потоков.

    Раньше бот разбирал их по одному: пока чьё-то сохранение в таблицу шло
    две секунды, у всех остальных кнопки не отвечали. Теперь очереди
    работают параллельно, но нажатия ОДНОГО человека всегда попадают в одну
    и ту же очередь — порядок его шагов не перепутается.
    """
    import queue, threading
    for _ in range(max(1, WORKERS)):
        q = queue.Queue()
        _QS.append(q)
        threading.Thread(target=_worker, args=(q,), daemon=True).start()


def dispatch(upd):
    chat = _chat_of(upd)
    if not _QS:
        start_workers()
    _QS[hash(chat) % len(_QS)].put(upd)


def poll():
    offset = 0
    bad = 0
    start_workers()
    while True:
        try:
            r = tg('getUpdates', offset=offset, timeout=25,
                   allowed_updates=['message', 'callback_query'])
            if not r.get('ok'):
                bad += 1
                if bad in (1, 10, 100):      # не засоряем лог каждые 25 секунд
                    print('телеграм не отвечает:', r.get('description') or r)
                import time
                time.sleep(3)
                continue
            bad = 0
            for upd in r.get('result') or []:
                offset = upd['update_id'] + 1
                dispatch(upd)
        except Exception as e:
            print('цикл:', e)
            import time
            time.sleep(5)
