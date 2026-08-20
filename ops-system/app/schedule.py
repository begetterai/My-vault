#!/usr/bin/env python3
"""Расписание: напоминания до дедлайна, эскалация после и отчёты руководителям.

Крутится отдельным потоком раз в минуту по местному времени точки.
Что уже отправлено — помнится за текущий день, поэтому перезапуск сервиса
не рассылает повторно то, что люди уже получили.
"""
import datetime, threading, traceback

from . import config as C
from . import storage as S
from . import bot as BOT
from . import reports as R

_done = {'day': None, 'keys': set()}


def once(key):
    """True — если сегодня это ещё не отправляли."""
    today = C.today().isoformat()
    if _done['day'] != today:
        _done['day'], _done['keys'] = today, set()
    if key in _done['keys']:
        return False
    _done['keys'].add(key)
    return True


def hhmm(t):
    h, m = str(t).split(':')
    return int(h) * 60 + int(m)


def deadlines():
    """[(ключ, чек-лист, минута дедлайна, за сколько напомнить)]"""
    out = []
    for key, cl in C.checklists().items():
        if cl.get('deadline'):
            out.append((key, cl, hhmm(cl['deadline']), int(cl.get('remind_before', 45))))
    return out


# ── напоминания и эскалация ──────────────────────────────────────────────────
def remind(key, cl, point, left):
    who = S.staff_of(point) or S.managers_of(point)
    for cid in who:
        BOT.say(cid, f'⏰ <b>{cl["title"]}</b> · {point}\n'
                     f'До дедлайна <b>{left} мин</b> (до {cl["deadline"]}). '
                     f'Чек-лист ещё не заполнен.\n\n'
                     f'Открой приложение и пройди по точке.',
                reply_markup=BOT.menu_kb('staff'))


def overdue(key, cl, point):
    txt = (f'🚨 <b>Просрочено</b> · {point}\n'
           f'{cl["title"].lower()} не заполнен к {cl["deadline"]}.')
    sent = set()
    for cid in S.managers_of(point):
        BOT.say(cid, txt)
        sent.add(str(cid))
    if str(C.ADMIN_CHAT) not in sent:
        BOT.admin(txt)


def unconfirmed(day):
    """Заполнено, но управляющий не подтвердил дольше нормы — это второй контур
    не работает, и знать об этом должен COO."""
    late = []
    for x in R.fills(day, day):
        if not x['chk']:
            late.append(x)
    if not late:
        return
    L = [f'⚠️ <b>Не подтверждено управляющим</b> — {day.strftime("%d.%m")}', '']
    L += [f'   {x["point"]} · {x["kind"].lower()} · заполнил {x["who"]}' for x in late]
    L.append('')
    L.append('Пока управляющий не прошёл по точке, заполнение — это только слова.')
    by_point = {}
    for x in late:
        by_point.setdefault(x['point'], []).append(x)
    for point, items in by_point.items():
        for cid in S.managers_of(point):
            BOT.say(cid, f'⚠️ <b>{point}: ждут твоего подтверждения</b>\n'
                    + '\n'.join(f'   {i["kind"].lower()} · {i["who"]}' for i in items))
    BOT.admin('\n'.join(L))


# ── отчёты ───────────────────────────────────────────────────────────────────
def tasks_pass():
    """Повторяющиеся провалы превращаем в задачи, о просрочках напоминаем."""
    from . import tasks as TSK
    try:
        made = TSK.from_repeat_fails()
        if made:
            print(f'задач из повторов: {made}')
    except Exception as e:
        print('повторы → задачи:', e)
    try:
        late = TSK.overdue()
    except Exception as e:
        print('просрочки:', e)
        return
    if not late:
        return
    by = {}
    for t in late:
        by.setdefault(t['point'], []).append(t)
    for point, items in by.items():
        txt = (f'🔴 <b>Просроченные задачи · {point}</b>\n\n'
               + '\n'.join(f'· {t["what"]}\n   {t["owner"]} · срок был '
                            f'{t["due"]} · {t["late"]} дн. назад'
                            for t in items[:8]))
        sent = set()
        for cid in S.managers_of(point):
            BOT.say(cid, txt)
            sent.add(str(cid))
        if str(C.ADMIN_CHAT) not in sent:
            BOT.admin(txt)


def daily():
    day = C.today()
    BOT.admin(R.day_full(day))
    for cid, point in S.managers().items():
        BOT.say(cid, R.day_full(day, point))


def weekly():
    from . import kpi as K
    BOT.admin(R.week())
    BOT.admin(K.report('week'))
    for cid, point in S.managers().items():
        BOT.say(cid, R.week(point=point))
        BOT.say(cid, K.report('week', point))


def monthly():
    """Первого числа — итог месяца и квартал, если квартал закрылся."""
    from . import kpi as K
    prev = C.today().replace(day=1) - datetime.timedelta(days=1)
    BOT.admin(K.report('month', ref=prev))
    BOT.admin(K.people('month', ref=prev))
    if prev.month % 3 == 0:
        BOT.admin(K.report('quarter', ref=prev))
    for cid, point in S.managers().items():
        BOT.say(cid, K.report('month', point, ref=prev))


# ── цикл ─────────────────────────────────────────────────────────────────────
def tick():
    now = C.now()
    day = now.date()
    minute = now.hour * 60 + now.minute
    dstr = day.strftime('%d.%m.%Y')

    for key, cl, dead, before in deadlines():
        for point in S.points():
            if S.already_filled(key, dstr, point):
                continue
            if dead - before <= minute < dead and once(f'rem:{key}:{point}'):
                remind(key, cl, point, dead - minute)
            if minute >= dead and once(f'over:{key}:{point}'):
                overdue(key, cl, point)

    # Дашборд — раз в час: таблицу открывают в любой момент, она должна
    # показывать сегодняшнее, а не вчерашнее.
    if once(f'dash:{now.hour}'):
        try:
            from . import dashboard as DASH
            DASH.refresh()
        except Exception as e:
            print('дашборд:', e)

    # Копия — рано утром, когда никто не пишет: копируется целостное состояние
    if minute >= hhmm(C.BACKUP_AT) and once('backup'):
        try:
            from . import backup as BK
            BOT.admin(BK.run())
        except Exception as e:
            print('резервная копия:', e)
            try:
                BOT.admin(f'⚠️ Резервная копия не сделана: {e}')
            except Exception:
                pass

    if minute >= hhmm(C.DAILY_AT) and once('daily'):
        unconfirmed(day)
        tasks_pass()
        daily()

    if day.weekday() == 0 and minute >= hhmm(C.WEEKLY_AT) and once('weekly'):
        weekly()

    if day.day == 1 and minute >= hhmm(C.WEEKLY_AT) and once('monthly'):
        monthly()


def loop():
    import time
    while True:
        try:
            tick()
        except Exception:
            traceback.print_exc()
        time.sleep(60)


def start():
    threading.Thread(target=loop, daemon=True).start()
