#!/usr/bin/env python3
"""Обзор: то, что руководителю нужно видеть, не листая.

Лист «Дашборд» в таблице остаётся складом данных — там удобно искать
конкретную строку за прошлый месяц. Но управлять по нему нельзя: девять
колонок и восемь блоков подряд на айпаде не читаются.

Здесь — пять экранных карточек, сверху то, на что надо реагировать сегодня,
ниже то, что показывает картину. Дашборд, который начинается с красивых
цифр за месяц, не помогает управлять сегодняшним днём.
"""
import datetime

from . import config as C
from . import storage as S

# Данные читаются из таблиц, а таблицы отвечают не мгновенно. Две минуты
# кэша — обзор всё ещё свежий, но открытие приложения не ждёт восьми чтений.
_CACHE = {'ts': None, 'key': None, 'data': None}
TTL = 120


def build(role, point=None, who=None):
    key = (role, point)
    now = datetime.datetime.utcnow()
    if _CACHE['key'] == key and _CACHE['ts'] \
            and (now - _CACHE['ts']).seconds < TTL:
        return _CACHE['data']
    data = _build(role, point, who)
    _CACHE.update(ts=now, key=key, data=data)
    return data


def _build(role, point, who):
    points = [point] if point else S.points()
    out = {'day': C.day_str(), 'points': points, 'now': C.now().strftime('%H:%M')}
    out['today'] = _today(points)
    out['index'] = _index(points)
    out['tasks'] = _tasks(point)
    out['points_sum'] = _points(point)
    out['attention'] = _attention(points, point, role)
    # Сравнение точек: директору важно не «как дела на ЗБ», а «где хуже».
    # Одна цифра рядом с другой отвечает на это быстрее, чем две карточки,
    # между которыми надо листать.
    if len(points) > 1:
        out['compare'] = _compare(points, out)
    return out


def _compare(points, out):
    idx = {x['point']: x for x in out['index']}
    today = {x['point']: x for x in out['today']}
    rows = []
    for p in points:
        t, i = today.get(p, {}), idx.get(p, {})
        try:
            from . import tasks as TSK
            late = len(TSK.overdue(p))
            openned = len(TSK.all_tasks(True, p))
        except Exception:
            late = openned = 0
        try:
            from . import score as SC
            _lbl, people = SC.period_totals(p)
            pay = sum(x['payable'] for x in people)
            minus = sum(1 for x in people if x['payable'] < 0)
        except Exception:
            pay = minus = 0
        rows.append({'point': p, 'label': S.point_label(p),
                     'index': i.get('total'), 'flags': len(i.get('flags') or []),
                     'late': t.get('late', 0), 'done': t.get('done', 0),
                     'waiting': t.get('waiting', 0),
                     'tasks_open': openned, 'tasks_late': late,
                     'pay': pay, 'minus': minus})
    return rows


def _today(points):
    """Что со сдачей чек-листов прямо сейчас: сдано, ждём, просрочено."""
    from . import forms as F
    now = C.now()
    minute = C.now_minute()
    day = C.day_str()
    out = []
    for p in points:
        done = late = waiting = 0
        items = []
        for key, cl in C.checklists().items():
            if not cl.get('deadline'):
                continue
            if cl.get('points') and p not in cl['points']:
                continue
            if not S.workers_of(p, cl.get('dept'), cl.get('roles')):
                continue
            filled = S.already_filled(key, day, p)
            dead = C.op_minute(C.deadline_for(cl, p))
            if filled:
                done += 1
                state = 'сдан'
            elif minute > dead:
                late += 1
                state = 'просрочен'
            else:
                waiting += 1
                state = 'ждём'
            items.append({'title': cl['title'], 'deadline': C.deadline_for(cl, p),
                          'state': state})
        out.append({'point': p, 'label': S.point_label(p), 'done': done,
                    'late': late, 'waiting': waiting, 'items': items})
    return out


def _index(points):
    """Индекс точки за неделю — одна цифра на точку, плюс составляющие."""
    from . import kpi as K
    since, until = K.period('week')[:2]
    out = []
    for p in points:
        try:
            idx = K.point_index(p, since, until)
            flags = [{'title': t, 'why': w} for t, _n, w in K.flags(p, since, until)]
        except Exception as e:
            print('индекс:', e)
            continue
        out.append({'point': p, 'label': S.point_label(p),
                    'total': idx.get('total'), 'parts': idx.get('parts', {}),
                    'flags': flags})
    return out


def _tasks(point):
    from . import tasks as TSK
    try:
        openned = TSK.all_tasks(True, point)
        late = TSK.overdue(point)
    except Exception as e:
        print('задачи в обзоре:', e)
        return {'open': 0, 'late': 0, 'list': []}
    return {'open': len(openned), 'late': len(late),
            'list': [{'what': t['what'], 'owner': t.get('owner', ''),
                      'due': t.get('due', ''), 'point': t.get('point', ''),
                      'late': t.get('late', 0)} for t in late[:5]]}


def _points(point):
    """Баллы текущего периода: к выплате по людям."""
    from . import score as SC
    try:
        label, people = SC.period_totals(point)
    except Exception as e:
        print('баллы в обзоре:', e)
        return {'period': '', 'people': [], 'sum': 0}
    return {'period': label, 'sum': sum(p['payable'] for p in people),
            'minus': sum(1 for p in people if p['payable'] < 0),
            'people': people[:8]}


def _attention(points, point, role):
    """Что требует руководителя лично. Пусто — значит сегодня всё ровно."""
    from . import score as SC
    out = []
    try:
        for d in SC.disputes(point):
            out.append({'kind': 'спор', 'text': f'{d["who"]}: «{d["text"][:60]}»',
                        'why': f'{d["date"]} · {d["why"]} ({d["pts"]:+d})'})
    except Exception as e:
        print('споры в обзоре:', e)
    try:
        from . import reports as RP
        for x in RP.pending(point)[:6]:
            out.append({'kind': 'на проверке',
                        'text': f'{x["title"]} · {x["point"]} · {x["who"]}',
                        'why': f'{x["day"]} · {x["ok"]} из {x["tot"]}'
                               + (' · быстро' if x.get('fast') else '')})
    except Exception as e:
        print('на проверке в обзоре:', e)
    try:
        from . import roster as RS
        day = C.today() + datetime.timedelta(days=1)
        for p in points:
            s = RS.summary(day, p)
            if not s:
                out.append({'kind': 'состав',
                            'text': f'{p}: состава на завтра нет',
                            'why': 'в 23:00 система возьмёт сегодняшний'})
                continue
            if s['no']:
                out.append({'kind': 'состав',
                            'text': f'{p}: не выйдут — '
                                    + ', '.join(r['who'] for r in s['no']),
                            'why': 'нужна замена на завтра'})
    except Exception as e:
        print('состав в обзоре:', e)
    return out
