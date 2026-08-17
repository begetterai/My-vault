#!/usr/bin/env python3
"""Чек-листы смены в боте.

Задача — не «поставить галочки», а сделать так, чтобы проверить точку было
дешевле, чем изобразить проверку. Четыре механизма:

  1. Ничего не отмечено заранее. Каждый пункт надо нажать: ✅ или ❌.
     Пока весь блок не отмечен, «Далее» не пускает. Протыкать нечего.
  2. Где нужен замер — спрашиваем число, а не галочку: температуры, касса.
     Число выдумать можно, но это уже осознанная ложь, а не небрежность.
  3. Фото. Каждый раз бот просит снимки ДВУХ случайных пунктов из тех,
     где в документе стоит «фото». Заранее не подготовишь — не знаешь каких.
  4. Время. Засекается от начала до конца. Быстрее трёх минут точку
     физически не обойти — такие заполнения помечаются и уходят Азизу.

Кто может заполнять — лист «Команда» в таблице операционных данных.
"""
import datetime, random
import checklists as CL

SS = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'

STATE = {}
CHECK = {}          # chat_id управляющего → строка, по которой пишем расхождение
_TEAM = {'ts': None, 'map': {}}
MENU = ('чек-лист', 'чеклист', '/чеклист', 'открытие', 'закрытие',
        'смена', '/смена', 'меню', '/меню')
CANCEL = ('отмена', 'стоп', '/отмена')


def team(sheets, force=False):
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
                    m[str(r[0]).strip()] = (str(r[1]).strip(), str(r[2]).strip(),
                                            (r[3].strip() if len(r) > 3 else ''))
    except Exception:
        pass
    _TEAM['ts'], _TEAM['map'] = now, m
    return m


# ── экраны ───────────────────────────────────────────────────────────────────
def _role(who):
    """Что человек может: заполнять, проверять, видеть всё."""
    r = (who[2] if len(who) > 2 else '').lower()
    if 'coo' in r or 'директор' in r:
        return 'coo'
    if 'правляющ' in r:
        return 'manager'
    return 'staff'


def _menu_kb(role):
    kb = [[{'text': f'🧾 {CL.KINDS[k]["title"]}', 'callback_data': f'cl:go:{k}'}]
          for k in ('open', 'close')]
    if role == 'staff':
        kb.append([{'text': '📋 Мои последние', 'callback_data': 'cl:h:me'}])
    elif role == 'manager':
        kb.append([{'text': '📋 История точки', 'callback_data': 'cl:h:point'}])
    else:
        kb.append([{'text': '📋 История — обе точки', 'callback_data': 'cl:h:all'}])
        kb.append([{'text': '💬 Идеи и задачи', 'callback_data': 'cl:h:ideas'}])
    kb.append([{'text': '✖️ Закрыть', 'callback_data': 'cl:cancel'}])
    return {'inline_keyboard': kb}


def _hist_rows(sheets, scope, who_name, point):
    """Последние заполнения обоих чек-листов, свежие сверху."""
    rr = sheets.get(B + SS + '/values:batchGet',
                    params={'ranges': ['Открытие смены', 'Закрытие смены'],
                            'valueRenderOption': 'FORMATTED_VALUE'},
                    timeout=60).json().get('valueRanges', [])
    out = []
    for vr, title in zip(rr, ('открытие', 'закрытие')):
        for r in (vr.get('values') or [])[1:]:
            if len(r) < 8:
                continue
            if scope == 'me' and (len(r) < 3 or r[2] != who_name):
                continue
            if scope == 'point' and r[1] != point:
                continue
            out.append({'d': r[0], 'p': r[1], 'who': r[2], 'kind': title,
                        'ok': r[5], 'tot': r[6], 'fails': r[8] if len(r) > 8 else '',
                        'min': r[12] if len(r) > 12 else '',
                        'chk': r[13] if len(r) > 13 else '',
                        'diff': r[15] if len(r) > 15 else ''})
    out.sort(key=lambda x: (x['d'][6:10], x['d'][3:5], x['d'][0:2]), reverse=True)
    return out[:12]


def _hist_text(rows, title):
    if not rows:
        return f'<b>{title}</b>\n\nПока ни одного заполнения.'
    lines = [f'<b>{title}</b>', '']
    for x in rows:
        chk = f'✅ пров. {x["chk"]}' if x['chk'] else '⚠️ не проверено'
        lines.append(f'<b>{x["d"]}</b> · {x["p"]} · {x["kind"]} · {x["who"]}')
        lines.append(f'   {x["ok"]}/{x["tot"]} · {x["min"]} мин · {chk}')
        if x['fails'] and x['fails'] != '—':
            lines.append(f'   ❌ пункты: {x["fails"]}')
        if x['diff']:
            lines.append(f'   ⚠️ {x["diff"]}')
    return '\n'.join(lines)


def _ideas_text(sheets):
    v = sheets.get(B + SS + '/values/Идеи%20и%20задачи!A2:G60',
                   timeout=60).json().get('values', [])
    open_ = [r for r in v if len(r) > 5 and r[5] != 'Закрыта'][-10:]
    if not open_:
        return '<b>Идеи и задачи</b>\n\nПусто.'
    lines = ['<b>Идеи и задачи — открытые</b>', '']
    for r in reversed(open_):
        lines.append(f'<b>{r[0]}</b> · {r[1]} · {r[2]}')
        lines.append(f'   {r[4]}')
        lines.append(f'   <i>{r[3]}</i>')
    return '\n'.join(lines)


def _icon(v):
    return '⬜' if v is None else ('✅' if v else '❌')


def _block_screen(st):
    kind = st['kind']
    blocks = CL.by_block(kind)
    name, rows = blocks[st['i']]
    left = sum(1 for n, _, _ in rows if st['marks'].get(n) is None)
    head = (f'<b>{CL.KINDS[kind]["title"]} · {st["point"]} · {st["day"]}</b>\n'
            f'Блок {st["i"] + 1} из {len(blocks)} — {name}\n\n')
    body, kb, row = [], [], []
    for k, (n, text, norm) in enumerate(rows, 1):
        v = st['marks'].get(n)
        body.append(f'{_icon(v)} <b>{k}.</b> {text}' + (f' <i>({norm})</i>' if norm else ''))
        row.append({'text': f'{k} {_icon(v)}', 'callback_data': f'cl:t:{n}'})
        if len(row) == 3:
            kb.append(row); row = []
    if row:
        kb.append(row)
    if left:
        tail = (f'\n\n<i>Отметь каждый пункт: первое нажатие — ✅ выполнено, '
                f'второе — ❌ не выполнено.\nОсталось отметить: {left}</i>')
        kb.append([{'text': f'⬜ Осталось {left} — отметь все',
                    'callback_data': 'cl:need'}])
    else:
        last = st['i'] + 1 == len(blocks)
        tail = '\n\n<i>Блок отмечен полностью.</i>'
        kb.append([{'text': 'Далее ▶' if not last else '▶ К замерам',
                    'callback_data': 'cl:next'}])
    kb.append([{'text': '💬 Заметка / задача', 'callback_data': 'cl:note'},
               {'text': '✖️ Отмена', 'callback_data': 'cl:cancel'}])
    return head + '\n'.join(body) + tail, {'inline_keyboard': kb}


def _fails(st):
    return sorted(n for n, v in st['marks'].items() if v is False)


def _ask_measure(st, tg, chat_id):
    n = st['measures_left'][0]
    q, norm, unit = CL.MEASURES[st['kind']][n]
    tg('sendMessage', chat_id=chat_id, parse_mode='HTML',
       text=f'📏 <b>{q}</b>\nНорма: {norm} {unit}\n\nНапиши число.')


def _ask_photo(st, tg, chat_id):
    n, text = st['photos_left'][0]
    tg('sendMessage', chat_id=chat_id, parse_mode='HTML',
       text=f'📷 <b>Пришли фото:</b> {text}\n\n'
            f'<i>Снимок должен быть сделан сейчас, не из галереи.</i>')


def _advance(st, tg, chat_id, sheets, notify):
    """Двигает по стадиям: замеры → фото → время → комментарий → запись."""
    if st['measures_left']:
        st['stage'] = 'measure'; _ask_measure(st, tg, chat_id); return
    if st['photos_left']:
        st['stage'] = 'photo'; _ask_photo(st, tg, chat_id); return
    if st['stage'] != 'time' and 'time' not in st:
        st['stage'] = 'time'
        tg('sendMessage', chat_id=chat_id,
           text=CL.KINDS[st['kind']]['ask_time'] + ' Напиши время, например 10:00')
        return
    fails = _fails(st)
    if fails and 'comment' not in st:
        st['stage'] = 'comment'
        nm = {n: x for n, _, x in CL.flat(st['kind'])}
        lst = '\n'.join(f'❌ {n}. {nm[n]}' for n in fails)
        tg('sendMessage', chat_id=chat_id, parse_mode='HTML',
           text='Не выполнено:\n' + lst +
                '\n\nНапиши коротко, почему по каждому.')
        return
    _finish(chat_id, st, sheets, tg, notify, st.get('comment', ''))


# ── запись ───────────────────────────────────────────────────────────────────
def _write(sheets, st, comment, filled_at, seconds):
    kind = st['kind']
    nm = {n: (b, t) for n, b, t in CL.flat(kind)}
    fails = _fails(st)
    tot = CL.total(kind)
    ok = tot - len(fails)
    meas = '; '.join(f'{CL.MEASURES[kind][n][0]}: {v}' for n, v in st['measured'].items())
    row = [st['day'], st['point'], st['who'], filled_at, st.get('time', ''),
           ok, tot, round(ok / tot, 4),
           ', '.join(str(n) for n in fails) if fails else '—', comment,
           meas, ' '.join(st['photos_done']), round(seconds / 60, 1)]
    r = sheets.post(B + SS + '/values/' + CL.KINDS[kind]['tab'].replace(' ', '%20') + '!A2:append',
                    params={'valueInputOption': 'USER_ENTERED'},
                    json={'values': [row]}, timeout=60)
    r.raise_for_status()
    rng = (r.json().get('updates', {}) or {}).get('updatedRange', '')
    line = ''.join(c for c in rng.split('!')[-1].split(':')[0] if c.isdigit())
    if fails:
        det = [[st['day'], st['point'], st['who'], CL.KINDS[kind]['title'],
                n, nm[n][0], nm[n][1]] for n in fails]
        sheets.post(B + SS + '/values/Невыполнено!A2:append',
                    params={'valueInputOption': 'USER_ENTERED'},
                    json={'values': det}, timeout=60).raise_for_status()
    return ok, tot, fails, line


def _finish(chat_id, st, sheets, tg, notify, comment):
    sec = (datetime.datetime.utcnow() - st['started']).total_seconds()
    try:
        ok, tot, fails, line = _write(sheets, st, comment,
                                      datetime.datetime.utcnow().strftime('%H:%M'), sec)
    except Exception as e:
        tg('sendMessage', chat_id=chat_id,
           text=f'⚠️ Не смог сохранить: {e}\nСообщи управляющему.')
        STATE.pop(chat_id, None); return
    STATE.pop(chat_id, None)
    pct = round(ok / tot * 100)
    fast = sec < CL.MIN_SECONDS
    tg('sendMessage', chat_id=chat_id, parse_mode='HTML',
       text=f'✅ Записал. <b>{ok} из {tot}</b> ({pct}%), заняло {round(sec / 60)} мин.'
            + ('\n\n⚠️ Слишком быстро — управляющий это увидит.' if fast else
               '\nХорошей смены.'))
    try:
        _ask_check(sheets, tg, st, ok, tot, fails, line, comment, fast)
    except Exception:
        pass
    if notify and (fails or fast):
        nm = {n: t for n, _, t in CL.flat(st['kind'])}
        lst = '\n'.join(f'   ❌ {n}. {nm[n]}' for n in fails[:8])
        more = f'\n   … и ещё {len(fails) - 8}' if len(fails) > 8 else ''
        cm = f'\n   💬 {comment}' if comment else ''
        ms = ('\n   📏 ' + '; '.join(f'{CL.MEASURES[st["kind"]][n][0]}: {v}'
                                    for n, v in st['measured'].items())) if st['measured'] else ''
        warn = f'\n   ⚠️ Заполнено за {round(sec / 60, 1)} мин — быстрее норматива' if fast else ''
        notify(f'🧾 <b>{st["point"]}</b> · {CL.KINDS[st["kind"]]["title"].lower()} '
               f'{st["day"]} · {st["who"]}\n{ok}/{tot} ({pct}%){warn}\n{lst}{more}{ms}{cm}')


def note_write(sheets, day, who, point, source, text):
    sheets.post(B + SS + '/values/Идеи%20и%20задачи!A2:append',
                params={'valueInputOption': 'USER_ENTERED'},
                json={'values': [[day, who, point, source, text, 'Новая', '']]},
                timeout=60).raise_for_status()


def _managers(sheets, point, exclude=None):
    """chat_id управляющих этой точки — им уходит запрос на перепроверку."""
    return [cid for cid, v in team(sheets).items()
            if len(v) > 2 and v[1] == point and 'правляющ' in v[2] and cid != exclude]


def _ask_check(sheets, tg, st, ok, tot, fails, line, comment, fast):
    """Второй контур: управляющий подтверждает или отмечает расхождение."""
    kind = st['kind']
    nm = {n: t for n, _, t in CL.flat(kind)}
    lst = '\n'.join(f'   ❌ {n}. {nm[n]}' for n in fails[:8]) or '   всё выполнено'
    warn = f'\n⚠️ заполнено за {round((datetime.datetime.utcnow() - st["started"]).total_seconds() / 60, 1)} мин' if fast else ''
    cm = f'\n💬 {comment}' if comment else ''
    txt = (f'🔎 <b>Проверь заполнение</b>\n'
           f'{st["point"]} · {CL.KINDS[kind]["title"].lower()} {st["day"]} · {st["who"]}\n'
           f'{ok}/{tot}{warn}\n{lst}{cm}')
    kb = {'inline_keyboard': [[
        {'text': '✅ Проверил, всё так', 'callback_data': f'cl:ck:ok:{kind}:{line}'},
        {'text': '⚠️ Есть расхождение', 'callback_data': f'cl:ck:bad:{kind}:{line}'}]]}
    for cid in _managers(sheets, st['point'], exclude=None):
        tg('sendMessage', chat_id=cid, text=txt, parse_mode='HTML', reply_markup=kb)


# ── входные точки ────────────────────────────────────────────────────────────
def on_message(chat_id, msg_or_text, sheets, tg, notify=None, today=None,
               save_photo=None):
    """Текст или фото. → True, если это про чек-лист."""
    chat_id = str(chat_id)
    msg = msg_or_text if isinstance(msg_or_text, dict) else {'text': msg_or_text}
    t = (msg.get('text') or '').strip()
    low = t.lower().replace('ё', 'е')
    st = STATE.get(chat_id)

    # управляющий описывает расхождение
    if chat_id in CHECK and not st:
        kind, line, name = CHECK.pop(chat_id)
        tab = CL.KINDS[kind]['tab'].replace(' ', '%20')
        sheets.put(B + SS + f'/values/{tab}!P{line}',
                   params={'valueInputOption': 'USER_ENTERED'},
                   json={'values': [[t[:300]]]}, timeout=60)
        tg('sendMessage', chat_id=chat_id, text='Записал расхождение.')
        if notify:
            notify(f'⚠️ <b>Расхождение при проверке</b> · {name}\n{t[:300]}')
        return True

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
        who = team(sheets)[chat_id]
        tg('sendMessage', chat_id=chat_id, parse_mode='HTML',
           text=f'<b>{who[0]}</b> · {who[1]}\nЧто делаем?',
           reply_markup=_menu_kb(_role(who)))
        return True

    if st['stage'] == 'note':
        try:
            note_write(sheets, st['day'], st['who'], st['point'],
                       f'{CL.KINDS[st["kind"]]["code"]} блок {st["i"] + 1}', t[:400])
            tg('sendMessage', chat_id=chat_id, text='💬 Записал в «Идеи и задачи».')
        except Exception as e:
            tg('sendMessage', chat_id=chat_id, text=f'Не смог записать: {e}')
        st['stage'] = st.pop('note_return', 'blocks')
        return True

    if st['stage'] == 'measure':
        val = t.replace(',', '.').replace('−', '-')
        try:
            float(val)
        except ValueError:
            tg('sendMessage', chat_id=chat_id, text='Нужно число. Например: 4 или -19')
            return True
        st['measured'][st['measures_left'].pop(0)] = t[:20]
        _advance(st, tg, chat_id, sheets, notify)
        return True

    if st['stage'] == 'photo':
        if 'photo' not in msg:
            tg('sendMessage', chat_id=chat_id,
               text='Нужно именно фото. Сфотографируй и пришли.')
            return True
        n, text = st['photos_left'].pop(0)
        link = ''
        if save_photo:
            try:
                link = save_photo(msg['photo'][-1]['file_id'],
                                  f'{st["point"]}-{st["day"]}-п{n}') or ''
            except Exception:
                link = ''
        st['photos_done'].append(link or f'п{n}:есть')
        _advance(st, tg, chat_id, sheets, notify)
        return True

    if st['stage'] == 'time':
        st['time'] = t[:20]
        _advance(st, tg, chat_id, sheets, notify)
        return True

    if st['stage'] == 'comment':
        st['comment'] = '' if low in ('нет', 'no', '-') else t[:300]
        _advance(st, tg, chat_id, sheets, notify)
        return True

    if st['stage'] == 'blocks':
        tg('sendMessage', chat_id=chat_id,
           text='Отмечай кнопками выше. «Отмена» — начать заново.')
        return True
    return False


def on_callback(cq, sheets, tg, notify=None, today=None):
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
        ack(); return True

    if data.startswith('cl:h:'):
        scope = data.split(':')[2]
        who = team(sheets).get(chat_id)
        if not who:
            ack('Нет доступа'); return True
        if scope == 'ideas':
            txt = _ideas_text(sheets)
        else:
            rows = _hist_rows(sheets, scope, who[0], who[1])
            title = {'me': f'Мои последние — {who[0]}',
                     'point': f'История · {who[1]}',
                     'all': 'История · обе точки'}[scope]
            txt = _hist_text(rows, title)
        tg('editMessageText', chat_id=chat_id, message_id=mid, text=txt,
           parse_mode='HTML',
           reply_markup={'inline_keyboard': [[
               {'text': '◀ Назад', 'callback_data': 'cl:menu'}]]})
        ack(); return True

    if data == 'cl:menu':
        who = team(sheets).get(chat_id)
        if not who:
            ack('Нет доступа'); return True
        tg('editMessageText', chat_id=chat_id, message_id=mid, parse_mode='HTML',
           text=f'<b>{who[0]}</b> · {who[1]}\nЧто делаем?',
           reply_markup=_menu_kb(_role(who)))
        ack(); return True

    if data == 'cl:need':
        ack('Сначала отметь все пункты блока'); return True

    if data == 'cl:note':
        st = STATE.get(chat_id)
        if st:
            st['note_return'] = st['stage']; st['stage'] = 'note'
            tg('sendMessage', chat_id=chat_id, parse_mode='HTML',
               text='💬 Напиши, что добавить в регламент или что сделать.\n'
                    '<i>Попадёт в лист «Идеи и задачи», разберём на планёрке.</i>')
        ack(); return True

    if data.startswith('cl:ck:'):
        _, _, verdict, kind, line = data.split(':')
        who = team(sheets).get(chat_id)
        name = who[0] if who else 'управляющий'
        tab = CL.KINDS[kind]['tab'].replace(' ', '%20')
        stamp = datetime.datetime.utcnow().strftime('%d.%m %H:%M')
        sheets.put(B + SS + f'/values/{tab}!N{line}:P{line}',
                   params={'valueInputOption': 'USER_ENTERED'},
                   json={'values': [[name, stamp,
                                     '' if verdict == 'ok' else 'ДА — см. комментарий']]},
                   timeout=60)
        if verdict == 'ok':
            tg('editMessageText', chat_id=chat_id, message_id=mid,
               text=cq['message']['text'] + f'\n\n✅ Проверил: {name}, {stamp}')
            ack('Записал')
        else:
            CHECK[chat_id] = (kind, line, name)
            tg('sendMessage', chat_id=chat_id,
               text='Напиши, что именно не сошлось.')
            ack()
        return True

    if data.startswith('cl:go:'):
        kind = data.split(':')[2]
        who = team(sheets).get(chat_id)
        if not who or kind not in CL.KINDS:
            ack('Нет доступа'); return True
        name, point = who[0], who[1]
        day = (today or datetime.date.today()).strftime('%d.%m.%Y')
        photos = CL.photo_items(kind)
        random.shuffle(photos)
        STATE[chat_id] = {
            'kind': kind, 'day': day, 'point': point, 'who': name,
            'i': 0, 'marks': {}, 'stage': 'blocks',
            'started': datetime.datetime.utcnow(),
            'measures_left': list(CL.MEASURES.get(kind, {}).keys()),
            'measured': {},
            'photos_left': photos[:CL.PHOTOS_PER_RUN],
            'photos_done': [],
        }
        txt, kb = _block_screen(STATE[chat_id])
        tg('editMessageText', chat_id=chat_id, message_id=mid, text=txt,
           parse_mode='HTML', reply_markup=kb)
        ack(); return True

    st = STATE.get(chat_id)
    if not st or st['stage'] != 'blocks':
        ack('Начни заново: напиши «чек-лист»'); return True

    if data.startswith('cl:t:'):
        n = int(data.split(':')[2])
        v = st['marks'].get(n)
        st['marks'][n] = True if v is None else (False if v else True)
        txt, kb = _block_screen(st)
        tg('editMessageText', chat_id=chat_id, message_id=mid, text=txt,
           parse_mode='HTML', reply_markup=kb)
        ack('выполнено' if st['marks'][n] else 'НЕ выполнено'); return True

    if data == 'cl:next':
        blocks = CL.by_block(st['kind'])
        if any(st['marks'].get(n) is None for n, _, _ in blocks[st['i']][1]):
            ack('Отметь все пункты блока'); return True
        st['i'] += 1
        if st['i'] < len(blocks):
            txt, kb = _block_screen(st)
            tg('editMessageText', chat_id=chat_id, message_id=mid, text=txt,
               parse_mode='HTML', reply_markup=kb)
        else:
            done = sum(1 for v in st['marks'].values() if v)
            tg('editMessageText', chat_id=chat_id, message_id=mid, parse_mode='HTML',
               text=f'<b>{CL.KINDS[st["kind"]]["title"]} · {st["point"]} · {st["day"]}</b>\n'
                    f'Отмечено: {done} из {CL.total(st["kind"])}')
            _advance(st, tg, chat_id, sheets, notify)
        ack(); return True
    return False
