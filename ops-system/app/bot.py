#!/usr/bin/env python3
"""Телеграм-бот: меню по ролям, чек-лист в чате, история, второй контур.

Всё, что бот знает о компании, приходит из конфига и листа «Команда».
"""
import datetime, random, requests

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


def say(chat_id, text, **kw):
    return tg('sendMessage', chat_id=chat_id, text=text, parse_mode='HTML', **kw)


def admin(text):
    if C.ADMIN_CHAT:
        say(C.ADMIN_CHAT, text)


# ── экраны ───────────────────────────────────────────────────────────────────
def menu_kb(role):
    kb = []
    if C.WEBAPP_URL:
        kb.append([{'text': '📱 Открыть приложение', 'web_app': {'url': C.WEBAPP_URL}}])
    kb += [[{'text': f'🧾 {cl["title"]} (в чате)', 'callback_data': f'cl:go:{k}'}]
           for k, cl in C.checklists().items()]
    kb.append([{'text': {'staff': '📋 Мои последние',
                         'manager': '📋 История точки'}.get(role, '📋 История — все точки'),
                'callback_data': 'cl:h:' + {'staff': 'me', 'manager': 'point'}.get(role, 'all')}])
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
    for key, cl in C.checklists().items():
        for r in S.get(cl['tab'], 'A2:P500'):
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
    v = [r for r in S.get(C.TABS['ideas'], 'A2:G200')
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
    sec = (datetime.datetime.utcnow() - st['started']).total_seconds()
    try:
        ok, tot, fails, line = S.save_fill(
            st['kind'], st['day'], st['point'], st['who'], st['marks'],
            st['measured'], st['photos_done'], st.get('time', ''),
            st.get('comment', ''), sec)
    except Exception as e:
        say(chat_id, f'⚠️ Не смог сохранить: {e}')
        STATE.pop(chat_id, None)
        return
    STATE.pop(chat_id, None)
    fast = sec < C.MIN_SECONDS
    say(chat_id, f'✅ Записал. <b>{ok} из {tot}</b> ({round(ok / tot * 100)}%), '
                 f'заняло {round(sec / 60)} мин.'
        + ('\n\n⚠️ Слишком быстро — управляющий это увидит.' if fast else ''))
    notify_check(st, ok, tot, fails, line, st.get('comment', ''), fast)


def notify_check(st, ok, tot, fails, line, comment, fast):
    cl = C.checklists()[st['kind']]
    nm = {n: t for n, _, t in C.flat(st['kind'])}
    lst = '\n'.join(f'   ❌ {n}. {nm[n]}' for n in fails[:8]) or '   всё выполнено'
    warn = '\n⚠️ заполнено быстрее норматива' if fast else ''
    txt = (f'🔎 <b>Проверь заполнение</b>\n{st["point"]} · {cl["title"].lower()} '
           f'{st["day"]} · {st["who"]}\n{ok}/{tot}{warn}\n{lst}'
           + (f'\n💬 {comment}' if comment else ''))
    kb = {'inline_keyboard': [[
        {'text': '✅ Проверил', 'callback_data': f'cl:ck:ok:{st["kind"]}:{line}'},
        {'text': '⚠️ Расхождение', 'callback_data': f'cl:ck:bad:{st["kind"]}:{line}'}]]}
    for cid in S.managers_of(st['point']):
        say(cid, txt, reply_markup=kb)
    if fails or fast:
        admin(txt)


# ── входные точки ────────────────────────────────────────────────────────────
def on_message(msg):
    chat_id = str(msg.get('chat', {}).get('id', ''))
    t = (msg.get('text') or '').strip()
    low = t.lower().replace('ё', 'е')
    st = STATE.get(chat_id)

    if chat_id in CHECK and not st:
        kind, line, name = CHECK.pop(chat_id)
        S.save_check(kind, line, name, 'bad', t[:300])
        say(chat_id, 'Записал расхождение.')
        admin(f'⚠️ <b>Расхождение при проверке</b> · {name}\n{t[:300]}')
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
            say(chat_id, 'Тебя нет в списке заполняющих. Обратись к управляющему.')
            return True
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
        try:
            float(t.replace(',', '.').replace('−', '-'))
        except ValueError:
            say(chat_id, 'Нужно число. Например: 4 или -19')
            return True
        st['measured'][st['measures_left'].pop(0)] = t[:20]
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
        st['time'] = t[:20]
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
            'kind': kind, 'day': datetime.date.today().strftime('%d.%m.%Y'),
            'point': who[1], 'who': who[0], 'i': 0, 'marks': {}, 'stage': 'blocks',
            'started': datetime.datetime.utcnow(),
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


def poll():
    offset = 0
    bad = 0
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
                try:
                    if 'callback_query' in upd:
                        on_callback(upd['callback_query'])
                    elif 'message' in upd:
                        on_message(upd['message'])
                except Exception as e:
                    print('обработка:', e)
        except Exception as e:
            print('цикл:', e)
            import time
            time.sleep(5)
