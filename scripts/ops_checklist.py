#!/usr/bin/env python3
"""Чек-лист открытия смены через бота.

Google Forms и таблица на телефоне работают плохо. Бот работает: он уже у всех
в телефоне, логина не надо, интернет нужен слабый.

Логика диалога — не 34 вопроса, а 6 блоков. Старший смены отвечает «ок»,
если в блоке всё выполнено, или называет номера невыполненных. Заполнение
занимает меньше минуты.

Команда бота: «открытие».

Кто может заполнять — лист «Команда» в таблице операционных данных.
Азиз правит его с iPad, код трогать не надо.
"""
import datetime
from doc_03_CL_01 import BLOCKS

SS = '1wPQb2QUYy_aTbZN7KjeQsa_FrNv4KGE2clNT5EHyHOI'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'
TAB = 'Открытие смены'
NFIXED = 4

STATE = {}          # chat_id → ход заполнения
_TEAM = {'ts': None, 'map': {}}
TRIGGERS = ('открытие', '/открытие', 'открытие смены', 'чек-лист', 'чеклист')
ALL_OK = ('ок', 'ok', 'всё', 'все', 'всё ок', 'все ок', 'да', '+', 'норм')
CANCEL = ('отмена', 'стоп', '/отмена', 'cancel')


def items():
    out, n = [], 0
    for block, rows in BLOCKS:
        cur = []
        for text, norm, photo in rows:
            n += 1
            cur.append((n, text, norm))
        out.append((block, cur))
    return out


BLOCK_ITEMS = items()
TOTAL = sum(len(x[1]) for x in BLOCK_ITEMS)


def team(sheets, force=False):
    """chat_id → (имя, точка). Кэш на 10 минут, чтобы не дёргать таблицу."""
    now = datetime.datetime.utcnow()
    if not force and _TEAM['ts'] and (now - _TEAM['ts']).seconds < 600:
        return _TEAM['map']
    m = {}
    try:
        v = sheets.get(B + SS + '/values/Команда!A2:E100', timeout=30).json().get('values', [])
        for r in v:
            if len(r) >= 3 and str(r[0]).strip():
                active = (r[4].strip().lower() if len(r) > 4 and r[4] else 'да')
                if active in ('да', 'yes', '1', 'true', ''):
                    m[str(r[0]).strip()] = (str(r[1]).strip(), str(r[2]).strip())
    except Exception:
        pass
    _TEAM['ts'], _TEAM['map'] = now, m
    return m


def _block_text(i, point, day):
    name, rows = BLOCK_ITEMS[i]
    head = (f'<b>Открытие смены · {point} · {day}</b>\n'
            f'Блок {i + 1} из {len(BLOCK_ITEMS)} — {name}\n\n') if i == 0 else \
           (f'<b>Блок {i + 1} из {len(BLOCK_ITEMS)} — {name}</b>\n\n')
    body = '\n'.join(f'{k + 1}. {t}' for k, (_, t, _) in enumerate(rows))
    tail = ('\n\nОтветь <b>ок</b>, если всё выполнено.\n'
            'Если нет — номера невыполненных через пробел: <code>2 5</code>')
    return head + body + tail


def _parse(answer, rows):
    """→ (список глобальных номеров невыполненных, ошибка или None)"""
    a = str(answer).strip().lower().replace('ё', 'е')
    if a in ALL_OK:
        return [], None
    nums = []
    for part in a.replace(',', ' ').replace(';', ' ').split():
        if not part.isdigit():
            return None, f'Не понял «{part}». Нужны номера через пробел или слово «ок».'
        k = int(part)
        if not (1 <= k <= len(rows)):
            return None, f'В этом блоке номера от 1 до {len(rows)}, а не {k}.'
        nums.append(rows[k - 1][0])
    return sorted(set(nums)), None


def _names():
    """№ пункта → (блок, текст)."""
    return {n: (blk, t) for blk, rows in BLOCK_ITEMS for n, t, _ in rows}


def _write(sheets, day, point, who, fails, opened, comment, filled_at):
    """Пишет сводку в «Открытие смены» и по строке на каждый провал
    в «Невыполнено». Никаких 34 колонок галочек — таблицу читает человек."""
    nm = _names()
    ok = TOTAL - len(fails)
    short = ', '.join(str(n) for n in fails) if fails else '—'
    summary = [day, point, who, filled_at, opened, ok, TOTAL,
               round(ok / TOTAL, 4), short, comment]
    sheets.post(B + SS + '/values/' + TAB + '!A2:append',
                params={'valueInputOption': 'USER_ENTERED',
                        'insertDataOption': 'INSERT_ROWS'},
                json={'values': [summary]}, timeout=60).raise_for_status()
    if fails:
        rows = [[day, point, who, n, nm[n][0], nm[n][1]] for n in fails]
        sheets.post(B + SS + '/values/Невыполнено!A2:append',
                    params={'valueInputOption': 'USER_ENTERED',
                            'insertDataOption': 'INSERT_ROWS'},
                    json={'values': rows}, timeout=60).raise_for_status()


def try_handle(chat_id, text, sheets, send_to, notify=None, today=None):
    """Перехватывает сообщение, если это чек-лист. → True, если обработал.

    send_to(chat_id, text) — отправка. notify(text) — сообщение Азизу.
    """
    chat_id = str(chat_id)
    t = (text or '').strip()
    low = t.lower().replace('ё', 'е')
    st = STATE.get(chat_id)

    if st and low in CANCEL:
        STATE.pop(chat_id, None)
        send_to(chat_id, 'Отменил. Чек-лист не сохранён.')
        return True

    if st is None:
        if low not in TRIGGERS:
            return False
        who = team(sheets).get(chat_id)
        if not who:
            send_to(chat_id, 'Тебя нет в списке тех, кто заполняет чек-лист. '
                             'Обратись к управляющему.')
            return True
        name, point = who
        day = (today or datetime.date.today()).strftime('%d.%m.%Y')
        STATE[chat_id] = {'day': day, 'point': point, 'who': name,
                          'i': 0, 'fails': [], 'stage': 'blocks'}
        send_to(chat_id, _block_text(0, point, day))
        return True

    # идёт заполнение
    if st['stage'] == 'blocks':
        rows = BLOCK_ITEMS[st['i']][1]
        nums, err = _parse(t, rows)
        if err:
            send_to(chat_id, err)
            return True
        st['fails'].extend(nums)
        st['i'] += 1
        if st['i'] < len(BLOCK_ITEMS):
            send_to(chat_id, _block_text(st['i'], st['point'], st['day']))
        else:
            st['stage'] = 'opened'
            send_to(chat_id, 'Во сколько открылись? Напиши время, например <code>10:00</code>')
        return True

    if st['stage'] == 'opened':
        st['opened'] = t[:20]
        if st['fails']:
            st['stage'] = 'comment'
            names = {n: x for _, rows in BLOCK_ITEMS for n, x, _ in rows}
            lst = '\n'.join(f'✗ {n}. {names[n]}' for n in st['fails'])
            send_to(chat_id, 'Не выполнено:\n' + lst +
                    '\n\nНапиши коротко, почему. Если сказать нечего — напиши <b>нет</b>.')
        else:
            _finish(chat_id, st, sheets, send_to, notify, '')
        return True

    if st['stage'] == 'comment':
        _finish(chat_id, st, sheets, send_to, notify,
                '' if low in ('нет', 'no', '-') else t[:300])
        return True

    return False


def _finish(chat_id, st, sheets, send_to, notify, comment):
    try:
        _write(sheets, st['day'], st['point'], st['who'], st['fails'],
               st.get('opened', ''), comment,
               datetime.datetime.utcnow().strftime('%H:%M'))
    except Exception as e:
        send_to(chat_id, f'⚠️ Не смог сохранить: {e}\nСообщи управляющему.')
        STATE.pop(chat_id, None)
        return
    STATE.pop(chat_id, None)
    ok = TOTAL - len(st['fails'])
    pct = round(ok / TOTAL * 100)
    send_to(chat_id, f'✅ Записал. {ok} из {TOTAL} ({pct}%). Хорошей смены.')
    if notify and st['fails']:
        names = {n: x for _, rows in BLOCK_ITEMS for n, x, _ in rows}
        lst = '\n'.join(f'   ✗ {n}. {names[n]}' for n in st['fails'][:8])
        more = f'\n   … и ещё {len(st["fails"]) - 8}' if len(st['fails']) > 8 else ''
        cm = f'\n   💬 {comment}' if comment else ''
        notify(f'🧾 <b>{st["point"]}</b> · открытие {st["day"]} · {st["who"]}\n'
               f'{ok}/{TOTAL} ({pct}%)\n{lst}{more}{cm}')
