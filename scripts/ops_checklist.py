#!/usr/bin/env python3
"""Чек-листы смены в боте — меню и кнопки-иконки.

Как работает:
  1. Человек пишет «чек-лист» → бот показывает кнопки: какой документ заполняем.
  2. Выбрал — идут блоки. Все пункты по умолчанию ✅.
     Не выполнено — жмёшь номер, он становится ❌. Жмёшь ещё раз — обратно ✅.
  3. «Далее» — следующий блок. После последнего бот спрашивает время
     и причину по невыполненным.
  4. Пишет в таблицу, отвечает человеку, шлёт сводку Азизу.

Печатать почти ничего не надо — только время и комментарий.

Кто может заполнять — лист «Команда» в таблице операционных данных.
"""
import datetime
import checklists as CL

SS = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'

STATE = {}                      # chat_id → ход заполнения
_TEAM = {'ts': None, 'map': {}}
MENU = ('чек-лист', 'чеклист', '/чеклист', 'открытие', 'закрытие',
        'смена', '/смена', 'меню', '/меню')
CANCEL = ('отмена', 'стоп', '/отмена')


def team(sheets, force=False):
    """chat_id → (имя, точка). Кэш 10 минут, чтобы не дёргать таблицу."""
    now = datetime.datetime.utcnow()
    if not force and _TEAM['ts'] and (now - _TEAM['ts']).seconds < 600:
        return _TEAM['map']
    m = {}
    try:
        v = sheets.get(B + SS + '/values/Команда!A2:E100', timeout=30).json().get('values', [])
        for r in v:
            if len(r) >= 3 and str(r[0]).strip():
                act = (r[4].strip().lower() if len(r) > 4 and r[4] else 'да')
                if act in ('да', 'yes', '1', 'true', ''):
                    m[str(r[0]).strip()] = (str(r[1]).strip(), str(r[2]).strip())
    except Exception:
        pass
    _TEAM['ts'], _TEAM['map'] = now, m
    return m


# ── экраны ───────────────────────────────────────────────────────────────────
def _menu_kb():
    return {'inline_keyboard': [
        [{'text': f'🧾 {CL.KINDS[k]["title"]}', 'callback_data': f'cl:go:{k}'}]
        for k in ('open', 'close')
    ] + [[{'text': '✖️ Отмена', 'callback_data': 'cl:cancel'}]]}


def _block_screen(st):
    kind = st['kind']
    blocks = CL.by_block(kind)
    name, rows = blocks[st['i']]
    head = (f'<b>{CL.KINDS[kind]["title"]} · {st["point"]} · {st["day"]}</b>\n'
            f'Блок {st["i"] + 1} из {len(blocks)} — {name}\n\n')
    body = []
    kb, row = [], []
    for k, (n, text, norm) in enumerate(rows, 1):
        ok = st['marks'].get(n, True)
        body.append(f'{"✅" if ok else "❌"} <b>{k}.</b> {text}'
                    + (f' <i>({norm})</i>' if norm else ''))
        row.append({'text': f'{k} {"✅" if ok else "❌"}', 'callback_data': f'cl:t:{n}'})
        if len(row) == 3:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    tail = ('\n\n<i>Жми номер, если пункт НЕ выполнен — он станет ❌.</i>')
    last = st['i'] + 1 == len(blocks)
    kb.append([{'text': '✅ Готово, сохранить' if last else 'Далее ▶',
                'callback_data': 'cl:next'}])
    kb.append([{'text': '✖️ Отмена', 'callback_data': 'cl:cancel'}])
    return head + '\n'.join(body) + tail, {'inline_keyboard': kb}


def _fails(st):
    return sorted(n for n, ok in st['marks'].items() if not ok)


# ── запись ───────────────────────────────────────────────────────────────────
def _write(sheets, st, comment, filled_at):
    kind = st['kind']
    nm = {n: (b, t) for n, b, t in CL.flat(kind)}
    tab = CL.KINDS[kind]['tab']
    fails = _fails(st)
    tot = CL.total(kind)
    ok = tot - len(fails)
    row = [st['day'], st['point'], st['who'], filled_at, st.get('time', ''),
           ok, tot, round(ok / tot, 4),
           ', '.join(str(n) for n in fails) if fails else '—', comment]
    sheets.post(B + SS + '/values/' + tab.replace(' ', '%20') + '!A2:append',
                params={'valueInputOption': 'USER_ENTERED',
                        'insertDataOption': 'INSERT_ROWS'},
                json={'values': [row]}, timeout=60).raise_for_status()
    if fails:
        det = [[st['day'], st['point'], st['who'], CL.KINDS[kind]['title'],
                n, nm[n][0], nm[n][1]] for n in fails]
        sheets.post(B + SS + '/values/Невыполнено!A2:append',
                    params={'valueInputOption': 'USER_ENTERED',
                            'insertDataOption': 'INSERT_ROWS'},
                    json={'values': det}, timeout=60).raise_for_status()
    return ok, tot, fails


def _finish(chat_id, st, sheets, tg, notify, comment):
    try:
        ok, tot, fails = _write(sheets, st, comment,
                                datetime.datetime.utcnow().strftime('%H:%M'))
    except Exception as e:
        tg('sendMessage', chat_id=chat_id,
           text=f'⚠️ Не смог сохранить: {e}\nСообщи управляющему.')
        STATE.pop(chat_id, None)
        return
    STATE.pop(chat_id, None)
    pct = round(ok / tot * 100)
    tg('sendMessage', chat_id=chat_id, parse_mode='HTML',
       text=f'✅ Записал. <b>{ok} из {tot}</b> ({pct}%). Хорошей смены.')
    if notify and fails:
        nm = {n: t for n, _, t in CL.flat(st['kind'])}
        lst = '\n'.join(f'   ❌ {n}. {nm[n]}' for n in fails[:8])
        more = f'\n   … и ещё {len(fails) - 8}' if len(fails) > 8 else ''
        cm = f'\n   💬 {comment}' if comment else ''
        notify(f'🧾 <b>{st["point"]}</b> · {CL.KINDS[st["kind"]]["title"].lower()} '
               f'{st["day"]} · {st["who"]}\n{ok}/{tot} ({pct}%)\n{lst}{more}{cm}')


# ── входные точки ────────────────────────────────────────────────────────────
def on_message(chat_id, text, sheets, tg, notify=None, today=None):
    """Текстовое сообщение. → True, если это про чек-лист."""
    chat_id = str(chat_id)
    t = (text or '').strip()
    low = t.lower().replace('ё', 'е')
    st = STATE.get(chat_id)

    if st and low in CANCEL:
        STATE.pop(chat_id, None)
        tg('sendMessage', chat_id=chat_id, text='Отменил. Ничего не сохранено.')
        return True

    if st is None:
        if low not in MENU:
            return False
        if not team(sheets).get(chat_id):
            tg('sendMessage', chat_id=chat_id,
               text='Тебя нет в списке заполняющих. Обратись к управляющему.')
            return True
        tg('sendMessage', chat_id=chat_id, text='Что заполняем?',
           reply_markup=_menu_kb())
        return True

    if st['stage'] == 'time':
        st['time'] = t[:20]
        fails = _fails(st)
        if fails:
            st['stage'] = 'comment'
            nm = {n: x for n, _, x in CL.flat(st['kind'])}
            lst = '\n'.join(f'❌ {n}. {nm[n]}' for n in fails)
            tg('sendMessage', chat_id=chat_id, parse_mode='HTML',
               text='Не выполнено:\n' + lst +
                    '\n\nНапиши коротко, почему. Нечего сказать — напиши <b>нет</b>.')
        else:
            _finish(chat_id, st, sheets, tg, notify, '')
        return True

    if st['stage'] == 'comment':
        _finish(chat_id, st, sheets, tg, notify,
                '' if low in ('нет', 'no', '-') else t[:300])
        return True

    if st['stage'] == 'blocks':
        tg('sendMessage', chat_id=chat_id,
           text='Отмечай кнопками выше. «Отмена» — если начать заново.')
        return True
    return False


def on_callback(cq, sheets, tg, notify=None, today=None):
    """Нажатие кнопки. → True, если это наша кнопка."""
    data = cq.get('data', '')
    if not data.startswith('cl:'):
        return False
    chat_id = str(cq['message']['chat']['id'])
    mid = cq['message']['message_id']
    ack = lambda txt='': tg('answerCallbackQuery', callback_query_id=cq['id'], text=txt)

    if data == 'cl:cancel':
        STATE.pop(chat_id, None)
        tg('editMessageText', chat_id=chat_id, message_id=mid,
           text='Отменил. Ничего не сохранено.')
        ack()
        return True

    if data.startswith('cl:go:'):
        kind = data.split(':')[2]
        who = team(sheets).get(chat_id)
        if not who or kind not in CL.KINDS:
            ack('Нет доступа')
            return True
        name, point = who
        day = (today or datetime.date.today()).strftime('%d.%m.%Y')
        STATE[chat_id] = {'kind': kind, 'day': day, 'point': point, 'who': name,
                          'i': 0, 'marks': {}, 'stage': 'blocks'}
        txt, kb = _block_screen(STATE[chat_id])
        tg('editMessageText', chat_id=chat_id, message_id=mid, text=txt,
           parse_mode='HTML', reply_markup=kb)
        ack()
        return True

    st = STATE.get(chat_id)
    if not st or st['stage'] != 'blocks':
        ack('Начни заново: напиши «чек-лист»')
        return True

    if data.startswith('cl:t:'):
        n = int(data.split(':')[2])
        st['marks'][n] = not st['marks'].get(n, True)
        txt, kb = _block_screen(st)
        tg('editMessageText', chat_id=chat_id, message_id=mid, text=txt,
           parse_mode='HTML', reply_markup=kb)
        ack('не выполнено' if not st['marks'][n] else 'выполнено')
        return True

    if data == 'cl:next':
        blocks = CL.by_block(st['kind'])
        # проставим ✅ всем, кого не трогали в этом блоке
        for n, _, _ in blocks[st['i']][1]:
            st['marks'].setdefault(n, True)
        st['i'] += 1
        if st['i'] < len(blocks):
            txt, kb = _block_screen(st)
            tg('editMessageText', chat_id=chat_id, message_id=mid, text=txt,
               parse_mode='HTML', reply_markup=kb)
        else:
            st['stage'] = 'time'
            done = sum(1 for v in st['marks'].values() if v)
            tot = CL.total(st['kind'])
            tg('editMessageText', chat_id=chat_id, message_id=mid, parse_mode='HTML',
               text=f'<b>{CL.KINDS[st["kind"]]["title"]} · {st["point"]} · {st["day"]}</b>\n'
                    f'Отмечено: {done} из {tot}')
            tg('sendMessage', chat_id=chat_id,
               text=CL.KINDS[st['kind']]['ask_time'] + ' Напиши время, например 10:00')
        ack()
        return True
    return False
