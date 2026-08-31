#!/usr/bin/env python3
"""Расписание: напоминания до дедлайна, эскалация после и отчёты руководителям.

Крутится отдельным потоком раз в минуту по местному времени точки.
Что уже отправлено, лежит во вкладке «Служебное»: до 31.08.2026 оно
помнилось только в памяти, а `restartPolicyType: ALWAYS` и каждый деплой
эту память обнуляли — и всё, что люди уже получили утром, приходило
второй раз.
"""
import datetime, threading, traceback

from . import config as C
from . import storage as S
from . import bot as BOT
from . import reports as R

TAB_DONE = 'Служебное'
_done = {'day': None, 'keys': set(), 'line': 0}


def _load_done(day):
    """(строка в таблице, уже отправленное за этот день)."""
    for i, r in enumerate(S.get(TAB_DONE, 'A2:B60')):
        r = list(r) + ['', '']
        if str(r[0]).strip() == day:
            return i + 2, {x.strip() for x in str(r[1]).split(',') if x.strip()}
    return 0, set()


def _save_done(day):
    val = ','.join(sorted(_done['keys']))
    if _done['line']:
        S.put(TAB_DONE, f"A{_done['line']}:B{_done['line']}", [[day, val]])
    else:
        _done['line'] = S.append(TAB_DONE, [[day, val]]) or 0


def once(key):
    """True — если сегодня это ещё не отправляли."""
    day = C.today().strftime('%d.%m.%Y')
    if _done['day'] != day:
        try:
            line, keys = _load_done(day)
        except Exception as e:
            print('журнал отправленного:', e)
            line, keys = 0, set()
        _done.update(day=day, keys=keys, line=line)
    if key in _done['keys']:
        return False
    _done['keys'].add(key)
    try:
        _save_done(day)
    except Exception as e:
        print('журнал отправленного:', e)
    return True


def hhmm(t):
    return C.op_minute(t)


def deadlines():
    """[(ключ, чек-лист, минута дедлайна, за сколько напомнить)]"""
    out = []
    for key, cl in C.checklists().items():
        if cl.get('deadline'):
            out.append((key, cl, int(cl.get('remind_before', 45))))
    return out


# ── напоминания и эскалация ──────────────────────────────────────────────────
def ready_workers(point, cl):
    """Кто на точке реально должен сдать этот чек-лист.

    Новичок, не сдавший тренинги позиции, из счёта выпадает: приложение
    ему чек-листы ещё не показывает, спрашивать за них нечестно.
    """
    from . import forms as F
    out = []
    for cid in S.workers_of(point, cl.get('dept'), cl.get('roles')):
        v = S.team().get(str(cid))
        if not v:
            continue
        try:
            if F.training_left(S.role_of(v), S.dept_of(v), point, v[0]):
                continue
        except Exception:
            pass
        out.append(cid)
    return out


def remind(key, cl, point, left):
    if not C.REMINDERS:
        return
    # Напоминание — тому, чей это чек-лист: своя позиция, своя роль.
    # Иначе кассир получает напоминания про кухню и перестаёт их читать.
    #
    # Некому сдавать — не с кого и спрашивать: позиция не занята, человека
    # на ней нет. Раньше такие напоминания падали на управляющего, и он
    # получал по десятку красных сообщений за раз ни о чём.
    who = ready_workers(point, cl)
    for cid in who:
        v = S.team().get(str(cid))
        BOT.say(cid, f'⏰ <b>{cl["title"]}</b> · {point}\n'
                     f'До дедлайна <b>{left} мин</b> '
                     f'(до {C.deadline_for(cl, point)}). '
                     f'Чек-лист ещё не заполнен.\n\n'
                     f'Открой приложение и пройди по точке.',
                reply_markup=BOT.menu_kb(S.role_of(v) if v else 'staff',
                                         S.dept_of(v) if v else '', point))


def overdue(key, cl, point):
    if not C.REMINDERS:
        return
    # Пустая позиция не «просрочена»: на ней сегодня никто не работает.
    if not ready_workers(point, cl):
        return
    txt = (f'🚨 <b>Просрочено</b> · {point}\n'
           f'{cl["title"].lower()} не заполнен '
           f'к {C.deadline_for(cl, point)}.')
    sent = set()
    for cid in S.managers_of(point):
        BOT.say(cid, txt)
        sent.add(str(cid))
    BOT.admin(txt, point, skip=sent)


def handover_waiting(dstr):
    """Смену сдали поимённо, а названный её не принял.

    Пересменка держится на одном действии принимающего: пока он не прошёл
    приём, смена не сдана, место числится ничьим, а сдавший уже ушёл.
    Через четверть часа напоминаем обоим — решено Азизом 27.08.2026.
    """
    cls = C.checklists()
    gives = [k for k, cl in cls.items() if cl.get('stage') == 'give']
    if not gives:
        return
    for point in S.points():
        try:
            filled = S.filled_today(dstr, point, gives)
        except Exception as e:
            print('непринятые передачи:', e)
            continue
        if not filled:
            continue
        takes = {f'{k[:-len("_give")]}_take' for k in filled}
        try:
            done = S.filled_today(dstr, point, sorted(takes))
        except Exception as e:
            print('непринятые передачи:', e)
            continue
        for key, rec in filled.items():
            to = (rec.get('to') or '').strip()
            take = f'{key[:-len("_give")]}_take'
            if not to or take in done:
                continue
            gap = C.now_minute() - C.op_minute(rec.get('at', ''))
            if gap < 15 or not once(f'hand:{key}:{point}'):
                continue
            place = cls[key]['title'].split(' · ')[0]
            for name, text in (
                (to, f'🔔 <b>Смену ждут от тебя</b> · {place}\n'
                     f'{rec.get("who", "")} сдал её в {rec.get("at", "")} '
                     f'и назвал тебя. Пройди «Приём» — пока не принял, '
                     f'место ничьё.'),
                (rec.get('who', ''),
                 f'⏳ <b>Твою передачу ещё не приняли</b> · {place}\n'
                     f'{to} не прошёл приём. Напомни ему — пока он не принял, '
                     f'смена числится за тобой.')):
                cid = next((c for c, v in S.team().items() if v[0] == name), None)
                if cid:
                    BOT.say(cid, text)


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
    told = set()
    for point, items in by_point.items():
        for cid in S.managers_of(point):
            BOT.say(cid, f'⚠️ <b>{point}: ждут твоего подтверждения</b>\n'
                    + '\n'.join(f'   {i["kind"].lower()} · {i["who"]}' for i in items))
            told.add(str(cid))
    # Общий список по всем точкам — только тому, кто отвечает за сеть целиком.
    # Управляющему чужой точки он не нужен: у него своя рассылка выше.
    for cid, v in S.team().items():
        if S.role_of(v) == 'coo' and str(cid) not in told:
            BOT.say(cid, '\n'.join(L))
    if C.ADMIN_CHAT and str(C.ADMIN_CHAT) not in told:
        BOT.say(C.ADMIN_CHAT, '\n'.join(L))


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
        BOT.admin(txt, point, skip=sent)


def daily():
    day = C.today()
    BOT.admin(R.day_full(day))
    for cid, point in S.managers().items():
        BOT.say(cid, R.day_full(day, point))


def roster_ask():
    """21:00 — управляющему: собери состав на завтра.

    Черновик уже готов (состав сегодняшнего дня), ему остаётся поправить
    замены и отправить.
    """
    from . import roster as RS
    day = C.today() + datetime.timedelta(days=1)
    for cid, point in S.managers().items():
        if RS.planned(day, point):
            continue
        n = len(RS.template(point, day))
        kb = ({'inline_keyboard': [[{'text': '📅 Собрать состав',
                                     'web_app': {'url': C.WEBAPP_URL}}]]}
              if C.WEBAPP_URL else None)
        BOT.say(cid, f'📅 <b>Состав смены на завтра</b> · {RS.day_str(day)} · {point}\n'
                     f'Черновик готов: {n} чел. по сегодняшнему составу.\n'
                     f'Поправь замены и отправь — людям уйдёт вопрос '
                     f'«Буду / Не смогу».', reply_markup=kb)


def roster_summary():
    """21:30 — что известно про завтрашнюю смену."""
    from . import roster as RS
    day = C.today() + datetime.timedelta(days=1)
    for cid, point in S.managers().items():
        s = RS.summary(day, point)
        if not s:
            BOT.say(cid, f'⚠️ <b>Состава на завтра нет</b> · {point}\n'
                         f'В 23:00 система возьмёт сегодняшний состав.')
            continue
        L = [f'📅 <b>Завтра · {s["day"]} · {point}</b>']
        L.append('✅ Подтвердили: ' + (', '.join(r['who'] for r in s['yes']) or '—'))
        if s['no']:
            L.append('❌ Не смогут: ' + ', '.join(
                f'{r["who"]} ({r["dept"]})' for r in s['no']) + ' — нужна замена')
        if s['wait']:
            L.append('⏳ Молчат: ' + ', '.join(r['who'] for r in s['wait']))
        BOT.say(cid, '\n'.join(L))


def roster_fallback():
    """23:00 — состава нет: берём сегодняшний состав, чтобы система не ослепла.

    Без состава она не знает, кто завтра работает: ни опоздания, ни невыходы,
    ни чьи чек-листы. Управляющий может проспать, система — нет.
    """
    from . import roster as RS
    day = C.today() + datetime.timedelta(days=1)
    for point in S.points():
        if RS.planned(day, point):
            continue
        people = RS.template(point, day)
        if not people:
            continue
        RS.save(day, point, people, 'система')
        for cid in S.managers_of(point):
            BOT.say(cid, f'📅 Состав на {RS.day_str(day)} · {point} не собран — '
                         f'взял сегодняшний состав ({len(people)} чел.). '
                         f'Поправь утром, если что-то не так.')


def mark_show():
    """Ночью: кто был в составе и не вышел. Отметка, без баллов.

    День берём текущий операционный: в 04:30 сутки, начавшиеся вчера утром,
    ещё не кончились — это и есть день, который разбираем.
    """
    from . import roster as RS
    day = C.today()
    try:
        missing = RS.mark_show(day)
    except Exception as e:
        print('отметка невыходов:', e)
        return
    if not missing:
        return
    txt = (f'🚫 <b>Не вышли · {RS.day_str(day)}</b>\n'
           + '\n'.join(f'· {r["who"]} · {r["point"]} · {r["dept"]}'
                       for r in missing)
           + '\n\nБаллы за это не снимаются — разбирается на собрании.')
    BOT.admin(txt)
    for cid, point in S.managers().items():
        if any(r['point'] == point for r in missing):
            BOT.say(cid, txt)


def close_stations():
    """Под утро: закрыть отрезки тех, кто не отметил уход.

    Конец берём из явки — там записан уход, если он есть. Нет и там —
    ставим срок закрытия точки: человек не мог работать дольше, чем
    работает заведение. Такие отрезки помечаем, чтобы их разобрали руками:
    в зарплату должно идти посчитанное, а не угаданное молча.
    """
    from . import forms as F
    day = C.day_str()
    left = S.hanging(day)
    if not left:
        return
    told = []
    for line, v in left:
        end = ''
        try:
            row = F.shift_row(day, v['point'], v['who']) \
                or F.open_shift(day, v['who'])
            end = (row[1][4] or '').strip() if row else ''
        except Exception as e:
            print('явка для отрезка:', e)
        by_shift = bool(end)
        if not end:
            cl = C.checklists().get(f"{v['station']}_close") or {}
            end = C.deadline_for(cl, v['point']) or '00:00'
        S.close_segments(day, v['who'], end)
        if not by_shift:
            told.append(f"· {v['who']} · {v['station']} · с {v['start']} — "
                        f"ухода нет, поставлен {end}")
    # Отрезки закрылись, а сама явка оставалась открытой навсегда: у Тохирова
    # смена от 30.08 висела без ухода и без часов. «Часов» — это зарплата,
    # пустая клетка в ней хуже, чем посчитанная с пометкой.
    try:
        for w in close_open_shifts(day):
            told.append(w)
    except Exception as e:
        print('закрытие явок:', e)
    # Пришёл, отметился — и ни одного места за смену. Так выглядит явка
    # ради явки: человек посидел и ушёл. Считать это работой нельзя.
    idle = []
    for _, v in S.segments(day):
        if v['station'] or v['minutes'] < 30:
            continue
        if any(x['who'] == v['who'] and x['station']
               for _, x in S.segments(day, who=v['who'])):
            continue
        idle.append(f"· {v['who']} · {v['point']} · {v['start']}–{v['end']} "
                    f"({v['minutes']} мин) — места не выбрал")
    # Разбирает беспорядок управляющий той точки, где он случился, —
    # значит и письмо должно уйти ему, а не одному человеку на всю сеть.
    for point in S.points():
        mine = [x for x in idle if f'· {point} ·' in x]
        if mine:
            BOT.admin('⚠️ <b>Явка без работы</b> · ' + day + '\n'
                      + '\n'.join(mine)
                      + '\n\nЧеловек отметил приход, но ни на одно место '
                        'не встал. Разберись, был ли он на смене.', point)
        mine = [x for x in told if f'· {point} ·' in x]
        if mine:
            BOT.admin('🕓 <b>Смена не закрыта</b> · ' + day + '\n'
                      + '\n'.join(mine)
                      + '\n\nЧасы посчитаны по времени закрытия точки. '
                        'Если человек ушёл раньше — поправь в «Станциях».', point)


def point_close(point):
    """Во сколько точка гасит свет: самый поздний срок листов закрытия.

    ЗБ — 00:30, ОВИР — 03:30. Дольше этого человек работать не мог,
    значит это и есть честный потолок для несделанной отметки.
    """
    times = [t for t in (C.deadline_for(cl, point)
                         for cl in C.checklists().values()
                         if cl.get('stage') == 'close') if t]
    return max(times, key=C.op_minute) if times else '00:00'


def close_open_shifts(day):
    """Явки без ухода: проставить уход, часы и пометку. → строки для письма.

    Уход берём по концу последнего отрезка человека — там уже стоит либо
    его настоящий уход, либо срок закрытия точки. Своего времени не
    выдумываем: посчитанное с пометкой можно поправить, пустую клетку —
    только вспомнить.
    """
    from . import forms as F
    out = []
    rows = S.get(C.TABS['shift'], 'A2:L')
    ends = {}
    for _, v in S.segments(day):
        if v.get('end'):
            ends[v['who']] = v['end']
    for i, r in enumerate(rows):
        r = list(r) + [''] * (12 - len(r))
        if not r[3].strip() or r[4].strip():
            continue
        # Не только за сегодня: пропущенная ночь оставляла строку открытой
        # навсегда. Смена от 30.08 висела без часов вторые сутки.
        try:
            d = datetime.datetime.strptime(r[0].strip(), '%d.%m.%Y').date()
        except ValueError:
            continue
        if d > C.today():
            continue
        who, point = r[2].strip(), r[1].strip()
        # Конец отрезка годится только для разбираемого дня: у вчерашней
        # строки сегодняшний отрезок — чужое время.
        end = ends.get(who) if r[0].strip() == day else ''
        if not end:
            end = point_close(point)
        line = i + 2
        hours = round((F.mins(end) - F.mins(r[3])) / 60, 2)
        if hours < 0:
            hours = round(hours + 24, 2)
        S.put(C.TABS['shift'], f'E{line}:J{line}',
              [[end, hours, r[6], r[7], 'ухода не было — закрыто автоматически',
                2]])
        out.append(f'· {who} · {point} · с {r[3]} — ухода нет, '
                   f'поставлен {end}, часов {hours}')
    return out


def close_day():
    """Под утро: кому засчитать полностью закрытый день (+5 баллов).

    Считается после того, как закрылась самая поздняя точка: ОВИР гасит свет
    в 03:30. Раньше — засчитаем день, который ещё идёт. День берём текущий
    операционный: до 05:00 это те самые сутки, что начались вчера утром.
    """
    from . import score as SC
    try:
        n = SC.close_day(C.today())
        if n:
            print(f'закрытый день засчитан: {n} чел.')
    except Exception as e:
        print('закрытие дня:', e)


def points_summary():
    """Субботняя сводка к воскресному собранию: итоги периода и споры."""
    from . import score as SC
    label, people = SC.period_totals()
    if not people:
        return
    head = f'💰 <b>Баллы · период {label}</b>\n\n'
    body = []
    for p in people:
        mark = ' ⚠️' if p['base'] < 0 else ''
        body.append(f'{p["who"]} · {p["point"]}: <b>{p["payable"]:+d}</b>'
                    f' (своя работа {p["base"]:+d}, сверх {p["extra"]:+d}){mark}')
    disp = SC.disputes()
    tail = ''
    if disp:
        tail = '\n\n⚖️ <b>Споры к разбору:</b>\n' + '\n'.join(
            f'· {d["who"]} · {d["date"]} · {d["why"]} ({d["pts"]:+d})\n  «{d["text"]}»'
            for d in disp[:15])
    txt = head + '\n'.join(body) + tail
    BOT.admin(txt)
    for cid, point in S.managers().items():
        _, mine = SC.period_totals(point)
        if mine:
            BOT.say(cid, head + '\n'.join(
                f'{p["who"]}: <b>{p["payable"]:+d}</b> '
                f'(своя {p["base"]:+d}, сверх {p["extra"]:+d})' for p in mine)
                + ('\n\n⚖️ Споры есть — см. приложение' if disp else ''))


def weekly():
    from . import kpi as K
    BOT.admin(R.week())
    BOT.admin(K.report('week'))
    for cid, point in S.managers().items():
        BOT.say(cid, R.week(point=point))
        BOT.say(cid, K.report('week', point))


def review_month():
    """1-го числа: разбор за прошлый месяц — правки людей и светофор.

    Решение прожарки 23.08.2026. Правки от смены копились в листе «Правки»
    и никто их не открывал: человек предлагает formulировку, она уходит
    в пустоту, и на третий раз он перестаёт писать. Теперь раз в месяц
    они приходят разбором, а принятые превращаются в баллы автору.
    """
    from . import score as SC
    L = ['📋 <b>Разбор за месяц</b>', '']

    try:
        fixes = [r for r in S.get(C.TABS['fixes'], 'A2:J')
                 if len(r) > 6 and not (len(r) > 8 and str(r[8]).strip())]
    except Exception as e:
        print('правки:', e)
        fixes = []
    L.append(f'✎ <b>Правки формулировок: {len(fixes)}</b>')
    if fixes:
        for r in fixes[:10]:
            r = list(r) + [''] * 10
            L.append(f'   · {r[1]} · {r[2]} п.{r[4]}: «{r[6][:80]}»')
        L.append('   <i>Разобрать: что принимаем — вношу в чек-лист, '
                 'автору доп. баллы.</i>')
    else:
        L.append('   <i>Предложений не было. Это тоже сигнал: либо всё '
                 'понятно, либо люди перестали писать.</i>')
    L.append('')

    try:
        rows = SC.lights()
    except Exception as e:
        print('светофор:', e)
        rows = []
    if rows:
        L.append('🚦 <b>Светофор по людям</b> — считается из баллов')
        icon = {'зелёный': '🟢', 'жёлтый': '🟡', 'красный': '🔴'}
        for p in rows:
            L.append(f'   {icon.get(p["color"], "·")} {p["who"]} · {p["point"]}'
                     f' · {p["payable"]:+d} — {p["why"]}')
        L.append('   <i>Зелёный — премия, жёлтый — разговор, '
                 'красный — дисциплинарная сетка.</i>')
    BOT.admin('\n'.join(L))
    for cid, point in S.managers().items():
        mine = [p for p in rows if p['point'] == point]
        if mine:
            BOT.say(cid, '🚦 <b>Светофор точки</b>\n' + '\n'.join(
                f'{p["who"]}: {p["color"]} ({p["payable"]:+d})' for p in mine))


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
    minute = C.now_minute()
    dstr = day.strftime('%d.%m.%Y')

    # Листов смены четыре десятка. Читать каждый по отдельности значит
    # сотню обращений к таблице в минуту — квота Google кончится за час.
    # Поэтому: точка снаружи, один пакетный запрос на все её листы.
    if C.REMINDERS:
        due = deadlines()
        for point in S.points():
            work = [(k, cl, before) for k, cl, before in due
                    # Цех есть только на ЗБ. Без этой проверки ОВИР каждый
                    # день получал бы «просрочено» по чужому чек-листу.
                    if not (cl.get('points') and point not in cl['points'])
                    # Некому сдавать — не с кого и спрашивать: позиция
                    # не занята. Новичок без обучения тоже не в счёт.
                    and ready_workers(point, cl)]
            if not work:
                continue
            filled = S.filled_today(dstr, point, [k for k, _, _ in work])
            for key, cl, before in work:
                if key in filled:
                    continue
                # Срок закрытия у точек разный: ЗБ гасит свет в 00:30,
                # ОВИР работает до 03:30.
                dead = hhmm(C.deadline_for(cl, point))
                if dead - before <= minute < dead and once(f'rem:{key}:{point}'):
                    remind(key, cl, point, dead - minute)
                if minute >= dead and once(f'over:{key}:{point}'):
                    overdue(key, cl, point)

    # Кто появился, сменил точку или ушёл — руководству, каждую минуту.
    # Состав и так читается кэшем на минуту, лишнего обращения нет.
    try:
        team_watch()
    except Exception as e:
        print('изменения по людям:', e)

    # Непринятая передача — раз в пять минут. Чаще незачем: порог всё равно
    # четверть часа, а каждый проход — четыре чтения таблицы.
    if now.minute % 5 == 0:
        try:
            handover_waiting(dstr)
        except Exception as e:
            print('непринятые передачи:', e)

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

    # Сводки отключены на время обкатки (23.08.2026): сначала люди привыкают
    # к самой работе в приложении, отчёты подключим, когда будет что сводить.
    # Напоминания о незакрытом и просроченных задачах остаются — это не сводка,
    # а сигнал к действию.
    if minute >= hhmm(C.DAILY_AT) and once('daily'):
        unconfirmed(day)
        tasks_pass()
        if C.SUMMARIES:
            daily()

    # Состав смены на завтра: запрос, сводка, запасной вариант.
    if minute >= hhmm(C.ROSTER_AT) and once('roster'):
        roster_ask()
    if minute >= hhmm(C.ROSTER_SUM_AT) and once('rostersum'):
        roster_summary()
    if minute >= hhmm(C.ROSTER_FALLBACK_AT) and once('rosterfb'):
        roster_fallback()

    # Закрытый день считаем после полуночи — за вчера, когда сутки закончились.
    if minute >= hhmm(C.CLOSE_DAY_AT) and once('closeday'):
        mark_show()
        close_stations()
        close_day()

    # Deep Clean — воскресенье, 10:00. Решение Азиза 31.08. Лист ведёт
    # управляющий: он объявляет субботник, обходит зоны и отмечает сам.
    # Без напоминания субботник вспоминается через раз.
    if day.weekday() == 6 and minute >= hhmm('10:00') and once('deepclean'):
        deepclean_reminder()

    # Суббота вечером — сводка к воскресному собранию.
    if (C.SUMMARIES and day.weekday() == 5
            and minute >= hhmm(C.SUMMARY_AT) and once('points')):
        points_summary()

    if (C.SUMMARIES and day.weekday() == 0
            and minute >= hhmm(C.WEEKLY_AT) and once('weekly')):
        weekly()

    if day.day == 1 and minute >= hhmm(C.WEEKLY_AT) and once('monthly'):
        monthly()
        review_month()


_PEOPLE = {}          # chat_id → (имя, точка, роль, отдел) на прошлой минуте


def team_watch():
    """Изменения в «Команде» → руководству и в журнал.

    Правка Азиза 31.08.2026: людей заводят и правят трое — он, Владимир
    и Дилчу, — часть через бота, часть руками в таблице. Раньше об этом
    знал только тот, кто правил. Сравниваем состав с прошлой минутой:
    так в журнал попадает любая правка, откуда бы она ни пришла.

    На первом проходе после запуска только запоминаем состав и молчим —
    иначе каждый перезапуск сервера выглядел бы как «добавили всех сразу».
    """
    global _PEOPLE
    cur = {str(cid): (v[0], v[1], v[2], v[3]) for cid, v in S.team().items()}
    if not cur:                       # пустой ответ таблицы — не потеря людей
        return
    if not _PEOPLE:
        _PEOPLE = cur
        return
    lines = []
    for cid, v in cur.items():
        old = _PEOPLE.get(cid)
        tail = ' · '.join(x for x in v[1:] if x)
        if old is None:
            lines.append(f'➕ <b>{v[0]}</b> — {tail}')
            S.log_person('добавлен', v[0], v[1], v[2], v[3])
        elif old != v:
            was = ' · '.join(x for x in old if x)
            lines.append(f'✏️ <b>{v[0]}</b> — {tail}\nбыло: {was}')
            S.log_person('изменён', v[0], v[1], v[2], v[3], was)
    for cid, old in _PEOPLE.items():
        if cid not in cur:
            lines.append(f'➖ <b>{old[0]}</b> — больше не в системе '
                         f'({" · ".join(x for x in old[1:] if x)})')
            S.log_person('убран', old[0], old[1], old[2], old[3])
    _PEOPLE = cur
    if lines:
        BOT.admin('👥 <b>Изменения по людям</b>\n\n' + '\n\n'.join(lines))


def deepclean_reminder():
    """Напоминание о субботнике — управляющим обеих точек."""
    txt = ('🧽 <b>Сегодня Deep Clean — субботник</b>\n\n'
           'Убирается всё заведение и все зоны одновременно. Объяви смене, '
           'распредели зоны и прими работу лично.\n\n'
           'Критерий один: провести сухой белой салфеткой по поверхностям '
           'и углам — салфетка остаётся чистой.\n\n'
           'Лист «Deep Clean — субботник» открыт в приложении. Фото «после» — '
           '3–5 на каждую зону.')
    kb = ({'inline_keyboard': [[{'text': '📱 Открыть приложение',
                                 'web_app': {'url': C.WEBAPP_URL}}]]}
          if C.WEBAPP_URL else None)
    for point in S.points():
        for cid in S.managers_of(point):
            BOT.say(cid, txt, **({'reply_markup': kb} if kb else {}))


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
