#!/usr/bin/env python3
"""Баллы: надбавки и удержания. Механика решена с Азизом 21.08.2026.

Документ: 01-POL-02 «Баллы: надбавки и удержания».
Заметка: 1-Области/Ромашка/Баллы-штрафы-механика.md

Главный принцип: сначала своя ежедневная работа, потом всё остальное.
За обязанности деньги не платят — обязанности дают допуск. Деньгами
оплачивается только то, что сверх.

Два счёта:
  · базовый — своя работа: +5 за полностью закрытый день, минусы за срывы;
  · доп     — сверх обязанностей: находки, замены, обучение.

Правило приоритета: базовый счёт в минусе — доп. счёт не платится вообще.
Иначе находками всегда можно перекрыть завал своей работы, и приоритет,
ради которого всё строится, исчезает.

1 балл = 1 сомони. Одна валюта: то, что человек не может посчитать в уме,
он считает несправедливым.
"""
import datetime

from . import config as C
from . import storage as S

BASE, EXTRA = 'базовый', 'доп'

# событие → (баллы, счёт, за что)
RULES = {
    # базовый счёт — своя ежедневная работа
    'day_closed':     (5,   BASE,  'День закрыт полностью'),
    'check_ok':       (5,   BASE,  'Чек-лист подтверждён управляющим'),
    'fill_late':      (-10, BASE,  'Чек-лист сдан позже срока'),
    'item_fail':      (-10, BASE,  'Невыполненный пункт — вина смены'),
    'mismatch':       (-30, BASE,  'Расхождение при проверке управляющим'),
    'late':           (-1,  BASE,  'Опоздание, за минуту'),
    # доп. счёт — сверх обязанностей. Замены, идеи и обучение начисляет
    # управляющий руками (AWARDABLE); находка и сданный тренинг — сами,
    # по факту записи и сдачи (решение Азиза 31.08.2026).
    'found_issue':    (5,   EXTRA, 'Нашёл и записал проблему'),
    'idea_accepted':  (20,  EXTRA, 'Идея принята в работу'),
    'replace_shift':  (20,  EXTRA, 'Вышел на замену за другого'),
    'taught':         (20,  EXTRA, 'Обучил новичка, тот сдал тренинг'),
    'quiz_passed':    (20,  EXTRA, 'Сдал тренинг с первого раза'),
    # наблюдение без денег: пороги не проверены на живой смене (01-POL-02)
    'too_fast':       (0,   BASE,  'Заполнено быстрее норматива — наблюдение'),
    # geo_missing убран 30.08.2026: место стало условием отметки, а не
    # пометкой — без координат ни приход, ни уход не записываются.
}

COLS = ['Дата', 'Точка', 'Кто', 'Событие', 'Баллы', 'За что', 'Ссылка',
        'Счёт', 'Период', 'Спор', 'Решение по спору']

# Потолок начислений в день: без него «нашёл проблему» превращается
# в двадцать записей за смену и сто баллов из воздуха.
DAY_CAP = {'found_issue': 3, 'replace_shift': 1, 'taught': 1,
           'idea_accepted': 2}

# Что управляющий может начислить руками из приложения.
AWARDABLE = ('replace_shift', 'taught', 'idea_accepted', 'found_issue')


def period_of(d=None):
    """(начало, конец, подпись) расчётного периода: 1–15 и 16–конец месяца."""
    d = d or C.today()
    if d.day <= 15:
        a = d.replace(day=1)
        b = d.replace(day=15)
    else:
        a = d.replace(day=16)
        nxt = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        b = nxt - datetime.timedelta(days=1)
    return a, b, f'{a.strftime("%d.%m")}–{b.strftime("%d.%m.%Y")}'


def add(point, who, event, link='', qty=1):
    """Записать балл. Тихо: человек видит итог в приложении, а не поток сообщений.

    qty — множитель для событий, которые считаются в единицах: минуты
    опоздания, количество невыполненных пунктов.
    """
    rule = RULES.get(event)
    if not rule:
        return 0
    pts, kind, why = rule
    cap = DAY_CAP.get(event)
    if cap and today_count(who, event) >= cap:
        return 0
    total = pts * max(1, int(qty))
    if qty and qty > 1 and event == 'late':
        why = f'Опоздание {int(qty)} мин'
    try:
        S.append(C.TABS['score'],
                 [[C.day_str(), point, who, event, total, why, link,
                   kind, period_of()[2], '', '']])
    except Exception as e:
        print('баллы:', e)
    if total < 0:
        _tell(point, who, total, why)
    return total


def _tell(point, who, pts, why):
    """Сказать человеку про списание в тот же день.

    Удержание, о котором узнали через неделю, воспринимается как подстава,
    даже когда оно справедливо. И пока случай свежий, его можно проверить
    по камере.
    """
    try:
        from . import bot as BOT
        for cid, v in S.team().items():
            if v[0] == who and v[1] == point:
                BOT.say(cid, f'➖ <b>{pts}</b> · {why}\n\n'
                             f'Не согласен? Открой приложение и нажми '
                             f'«Не согласен» рядом со списанием — управляющий '
                             f'разберёт сегодня.')
                break
    except Exception as e:
        print('сообщение о списании:', e)


def today_count(who, event):
    """Сколько раз событие уже начислено человеку сегодня."""
    d = C.today()
    return sum(1 for r in rows(since=d, until=d, who=who) if r['event'] == event)


def rows(since=None, until=None, point=None, who=None):
    out = []
    for i, r in enumerate(S.get(C.TABS['score'], 'A2:K'), start=2):
        if len(r) < 5:
            continue
        r = list(r) + [''] * (11 - len(r))
        d = _date(r[0])
        if not d:
            continue
        if since and d < since or until and d > until:
            continue
        if point and r[1].strip() != point:
            continue
        if who and r[2].strip() != who:
            continue
        try:
            pts = int(float(str(r[4]).replace(',', '.')))
        except ValueError:
            continue
        out.append({'line': i,
                    'date': d, 'point': r[1].strip(), 'who': r[2].strip(),
                    'event': r[3].strip(), 'pts': pts, 'why': r[5],
                    'link': r[6], 'kind': (r[7] or BASE).strip(),
                    'period': r[8], 'dispute': r[9], 'verdict': r[10]})
    return out


def _date(x):
    for f in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(str(x).strip(), f).date()
        except ValueError:
            pass
    return None


def balance(who, point=None, d=None):
    """Итог периода по правилу приоритета.

    Возвращает оба счёта и то, что реально пойдёт в ведомость.
    """
    a, b, label = period_of(d)
    rs = [r for r in rows(since=a, until=b, point=point, who=who)
          if not _dropped(r)]
    base = sum(r['pts'] for r in rs if r['kind'] != EXTRA)
    extra = sum(r['pts'] for r in rs if r['kind'] == EXTRA)
    # Базовый в минусе — доп. не платится. Ровно это заставляет делать
    # свою работу раньше, чем искать сверх.
    payable = base + (extra if base >= 0 else 0)
    return {'period': label, 'from': a.strftime('%d.%m'), 'to': b.strftime('%d.%m'),
            'base': base, 'extra': extra, 'payable': payable,
            'blocked': base < 0,
            'days_left': max(0, (b - min(C.today(), b)).days),
            'lines': [{'date': r['date'].strftime('%d.%m'), 'pts': r['pts'],
                       'why': r['why'], 'kind': r['kind'], 'event': r['event'],
                       'dispute': r['dispute'], 'verdict': r['verdict'],
                       'line': i}
                      for i, r in _numbered(rs)]}


def _dropped(r):
    """Списание, снятое управляющим после спора, в счёт не идёт."""
    return str(r.get('verdict', '')).strip().lower().startswith('снят')


def _numbered(rs):
    """Строки с их настоящими номерами в таблице.

    Раньше номер угадывался по связке «дата + кто + событие + баллы».
    Ключ не уникален: у Тохирова 31.08 оказалось два одинаковых списания,
    и спор, поданный со второй строки, управляющий разбирал в первой —
    вердикт писался не туда, а уведомление висело после каждого нажатия.
    Номер строки теперь идёт из самой выгрузки и ничего не угадывает.
    """
    return [(r.get('line'), r) for r in rs]


def dispute(line, who, text):
    """Сотрудник не согласен со списанием. Пишем в строку, решает управляющий."""
    if not str(line).isdigit():
        return False
    r = S.get(C.TABS['score'], f'A{line}:K{line}')
    if not r or len(r[0]) < 3 or str(r[0][2]).strip() != who:
        return False
    S.put(C.TABS['score'], f'J{line}:K{line}', [[text[:300], '']])
    return True


def resolve(line, verdict, note=''):
    """Управляющий разобрал спор: «снято» или «оставлено»."""
    if not str(line).isdigit():
        return False
    S.put(C.TABS['score'], f'K{line}:K{line}',
          [[('снято — ' if verdict == 'drop' else 'оставлено — ') + note[:200]]])
    return True


def disputes(point=None):
    """Споры, которые ещё не разобраны."""
    a, b, _ = period_of()
    out = []
    for line, r in _numbered([x for x in rows(since=a, until=b, point=point)
                              if x['dispute'] and not x['verdict']]):
        out.append({'line': line, 'who': r['who'], 'point': r['point'],
                    'date': r['date'].strftime('%d.%m'), 'pts': r['pts'],
                    'why': r['why'], 'text': r['dispute']})
    return out


def close_day(d=None):
    """Раз в сутки: кто закрыл все свои чек-листы — тому +5.

    Считается по факту, а не по обещанию: берём людей, отметивших приход,
    и смотрим, сданы ли чек-листы их отдела за этот день.
    """
    d = d or C.today()
    day = d.strftime('%d.%m.%Y')
    done = 0
    try:
        shifts = [r for r in S.get(C.TABS['shift'], 'A2:K')
                  if len(r) >= 4 and r[0].strip() == day and r[3].strip()]
    except Exception as e:
        print('закрытие дня:', e)
        return 0
    # Что сдано на точке — один пакетный запрос на точку, а не по листу
    # на каждого человека.
    seen = {}

    def point_closed(point):
        """День на точке закрыт, когда каждое начатое рабочее место закрыто.

        Считаем по начатым, а не по всем: станций десять, работают не все
        каждый день, и требовать закрытия пустой саладетты бессмысленно.
        Событийные листы со сроком (санитарный) тоже должны быть сданы.
        """
        if point not in seen:
            seen[point] = S.filled_today(
                day, point, [k for k, cl in C.checklists().items()
                             if cl.get('deadline')])
        got = seen[point]
        if not got:
            return False
        groups = {k.rsplit('_', 1)[0] for k in got if C.checklists()[k].get('stage')}
        if not groups:
            return False
        if any(f'{g}_close' not in got for g in groups):
            return False
        return all(k in got for k, cl in C.checklists().items()
                   if cl.get('deadline') and not cl.get('stage')
                   and S.workers_of(point, cl.get('dept'), cl.get('roles')))

    for r in shifts:
        point, who = r[1].strip(), r[2].strip()
        if not point_closed(point):
            continue
        if any(x['event'] == 'day_closed' for x in rows(since=d, until=d, who=who)):
            continue
        add(point, who, 'day_closed')
        done += 1
    return done


def totals(since=None, until=None, point=None):
    """{имя: баллы} за период."""
    t = {}
    for r in rows(since, until, point):
        if _dropped(r):
            continue
        t[r['who']] = t.get(r['who'], 0) + r['pts']
    return dict(sorted(t.items(), key=lambda x: -x[1]))


def period_totals(point=None, d=None):
    """Итоги текущего периода по людям — для сводки к собранию."""
    a, b, label = period_of(d)
    people = {}
    for r in rows(since=a, until=b, point=point):
        if _dropped(r):
            continue
        p = people.setdefault(r['who'], {'who': r['who'], 'point': r['point'],
                                         'base': 0, 'extra': 0})
        p['extra' if r['kind'] == EXTRA else 'base'] += r['pts']
    for p in people.values():
        p['payable'] = p['base'] + (p['extra'] if p['base'] >= 0 else 0)
    return label, sorted(people.values(), key=lambda x: -x['payable'])


def light(who, point=None, d=None):
    """Светофор человека — вывод из баллов, а не отдельная оценка.

    Решение прожарки 23.08.2026. Раньше цвет ставился на глаз раз в месяц
    и спорил с баллами: два человека с одинаковым счётом могли получить
    разные цвета. Теперь цвет считается сам:

      период в плюсе        → зелёный  → премия по итогам месяца
      период в минусе       → жёлтый   → разговор один на один
      два минуса подряд     → красный  → дисциплинарная сетка
    """
    d = d or C.today()
    now = balance(who, point, d)
    a, _b, _l = period_of(d)
    prev = balance(who, point, a - datetime.timedelta(days=1))
    if now['payable'] >= 0:
        return {'color': 'зелёный', 'why': 'период закрыт в плюсе',
                'now': now['payable'], 'prev': prev['payable']}
    if prev['payable'] < 0:
        return {'color': 'красный', 'why': 'второй период подряд в минусе',
                'now': now['payable'], 'prev': prev['payable']}
    return {'color': 'жёлтый', 'why': 'период в минусе',
            'now': now['payable'], 'prev': prev['payable']}


def lights(point=None, d=None):
    """Светофор по всем людям точки — к собранию."""
    _label, people = period_totals(point, d)
    out = []
    for p in people:
        try:
            l = light(p['who'], point, d)
        except Exception as e:
            print('светофор:', e)
            continue
        out.append(dict(p, **{'color': l['color'], 'why': l['why']}))
    order = {'красный': 0, 'жёлтый': 1, 'зелёный': 2}
    return sorted(out, key=lambda x: (order.get(x['color'], 9), -x['payable']))


def streak(who, point=None):
    """Сколько дней подряд человек закрывал день полностью."""
    good, bad = set(), set()
    for r in rows(point=point, who=who):
        if r['event'] == 'day_closed':
            good.add(r['date'])
        if r['pts'] < 0:
            bad.add(r['date'])
    d, n = C.today(), 0
    while d in good and d not in bad:
        n += 1
        d -= datetime.timedelta(days=1)
    return n


def card(who, point):
    """Личная карточка для приложения: баланс периода и место в списке."""
    bal = balance(who, None)
    a, b, _ = period_of()
    board = totals(since=a, until=b, point=point)
    place = list(board).index(who) + 1 if who in board else None
    bal.update({'streak': streak(who, point), 'place': place, 'of': len(board),
                'board': [{'who': k, 'pts': v} for k, v in list(board.items())[:5]]})
    return bal


def week_board(point=None):
    a, b, _ = period_of()
    return totals(since=a, until=b, point=point)
