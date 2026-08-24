#!/usr/bin/env python3
"""Mini App: чек-лист страницей внутри телеграма.

Личность приходит от телеграма подписанной — паролей нет, подделать нельзя.
"""
import os, json, hmac, hashlib, base64, random, time, datetime, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config as C
from . import storage as S
from . import bot as BOT
from . import vision as V
from . import forms as F
from . import score as SC

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(HERE, 'web', 'index.html')


def check_init_data(init_data, token):
    try:
        data = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        got = data.pop('hash', '')
        check = '\n'.join(f'{k}={v}' for k, v in sorted(data.items()))
        secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, got):
            return None
        age = time.time() - float(data.get('auth_date', 0))
        if age > C.INIT_MAX_AGE:
            return None
        return json.loads(data.get('user', '{}'))
    except Exception:
        return None


def _who(init_data):
    u = check_init_data(init_data, C.BOT_TOKEN)
    if not u:
        return None, None
    cid = str(u.get('id', ''))
    return cid, S.team().get(cid)


def init_payload(who):
    role = S.role_of(who)
    dept = S.dept_of(who)
    # Позиция на сегодня берётся из состава: человек может сегодня стоять
    # на кассе, а завтра в зале — и чек-листы должны открыться те, что нужно.
    try:
        from . import roster as RS
        dept = RS.dept_of(C.today(), who[0], dept)
    except Exception as e:
        print('позиция из состава:', e)
    # руководитель работает по обеим точкам — даём выбор; линейный закреплён
    pts = ([{'code': p, 'label': S.point_label(p)} for p in S.points()]
           if role in ('manager', 'coo') else
           [{'code': who[1], 'label': S.point_label(who[1])}])
    out = {'company': C.COMPANY, 'name': who[0], 'point': who[1],
           'point_label': S.point_label(who[1]), 'points': pts,
           'role': role, 'dept': dept, 'day': C.day_str(), 'lists': {}}
    # Поэтапный запуск: пока роль не в ROLLOUT, человек видит одно сообщение
    # и ничего больше. Лучше честное «скоро», чем половина системы.
    if C.ROLLOUT and role not in C.ROLLOUT:
        out['waiting'] = True
        return out
    out['can_fix'] = C.FIX_MODE and role in ('manager', 'coo')
    out['can_check'] = role in ('manager', 'coo')
    out['journals'] = [{'key': k, 'title': cl['title'], 'code': cl['code'],
                        'icon': cl.get('icon', '📌'), 'doc': cl.get('doc'),
                        'fields': cl.get('fields', [])}
                       for k, cl in C.visible(role, 'journal', dept, who[1]).items()]
    # Форма с требованием тренинга открывается только тому, кто его сдал:
    # не пускать к операции, которой человек не владеет, полезнее, чем
    # наказывать за необучение.
    out['forms'] = [{'key': k, 'title': cl['title'], 'code': cl['code'],
                     'icon': cl.get('icon', '📋'), 'doc': cl.get('doc'),
                     'columns': cl.get('columns', []),
                     'photo_required': bool(cl.get('photo_required')),
                     'locked': (bool(cl.get('requires'))
                                and not quiz_passed(cl['requires'], who[0])),
                     'requires': (C.form(cl['requires'])['title']
                                  if cl.get('requires') else '')}
                    for k, cl in C.visible(role, 'form', dept, who[1]).items()]
    # Правильные ответы наружу не уходят: страница открыта в браузере,
    # оттуда её видно целиком. Проверяет сервер.
    out['quizzes'] = [{'key': k, 'title': cl['title'], 'code': cl['code'],
                       'icon': cl.get('icon', '🎓'), 'doc': cl.get('doc'),
                       'minutes': cl.get('minutes', 5),
                       'pass': cl.get('pass', len(cl.get('questions', []))),
                       'intro': cl.get('intro', []),
                       'total': len(cl.get('questions', [])),
                       'passed': quiz_passed(k, who[0]),
                       'questions': [{'q': q['q'], 'options': q['options']}
                                     for q in cl.get('questions', [])]}
                      for k, cl in C.visible(role, 'quiz', dept, who[1]).items()]
    # Новичок: пока не сдал тренинги своей позиции, ему открыты приход
    # и обучение. Чек-листы и бланки появятся после — человек не должен
    # работать по правилам, которых не знает.
    try:
        left = F.training_left(role, dept, who[1], who[0]) \
            if role not in ('manager', 'coo') else []
    except Exception as e:
        print('обучение новичка:', e)
        left = []
    out['training_left'] = left
    if left:
        out['journals'], out['forms'] = [], []
    # Рабочие места смены — фиксированный список, один на человека.
    # Отдаём всем: выбор станции определяет, какой лист откроется,
    # а не наоборот. Без этого человек видит чужие станции и гадает.
    GROUPS = {'кухня': 'Кухня', 'цех': 'Цех', 'бар': 'Бар',
              'касса': 'Касса', 'зал': 'Зал'}
    out['stations'] = [
        {'key': st['key'], 'title': st['title'],
         'group': GROUPS.get(st['dept'] or '', 'Прочее')}
        for st in C.stations().values()]
    out['shift'] = shift_state(who)
    out['geo'] = {p: S.point_geo(p) for p in S.points()}
    # Кому можно сдать смену: свои же на точке. Список нужен всем, а не только
    # руководителю — передаёт смену тот, кто на ней стоял.
    out['mates'] = sorted({v[0] for v in S.team().values()
                           if v[1] == who[1] and v[0] != who[0]})
    if role in ('manager', 'coo'):
        try:
            from . import reports as RP
            out['pending'] = [
                {'key': x['key'], 'line': x['line'], 'title': x['title'],
                 'point': x['point'], 'who': x['who'], 'day': x['day'],
                 'at': x['at'], 'ok': int(x['ok']), 'tot': int(x['tot']),
                 'fails': x['fails'], 'comment': x['comment'],
                 'minutes': x['minutes'], 'fast': x['fast'],
                 'age': (C.today() - x['date']).days}
                for x in RP.pending(None if role == 'coo' else who[1])]
        except Exception:
            out['pending'] = []
        # Пункты всех чек-листов — руководителю, чтобы он мог пройти по ним
        # ещё раз при проверке, а не верить сводке «12 из 14».
        try:
            out['check_items'] = {
                k: [it['text'] for b in cl['blocks'] for it in b['items']]
                for k, cl in C.checklists().items()}
        except Exception as e:
            print('пункты для проверки:', e)
            out['check_items'] = {}
        try:
            from . import equipment as EQ
            out['equip_types'] = EQ.types_for_app()
            out['equip'] = EQ.all_items(None if role == 'coo' else who[1], False)
        except Exception:
            out['equip_types'], out['equip'] = [], []
        try:
            from . import tasks as TSK
            pt = None if role == 'coo' else who[1]
            late = {x['line'] for x in TSK.overdue(pt)}
            out['tasks'] = [dict(x, late=x['line'] in late)
                            for x in TSK.all_tasks(True, pt)]
        except Exception:
            out['tasks'] = []
        try:
            out['disputes'] = SC.disputes(None if role == 'coo' else who[1])
            out['awards'] = [{'event': e, 'pts': SC.RULES[e][0],
                              'why': SC.RULES[e][2]} for e in SC.AWARDABLE]
            out['team'] = sorted({v[0] for v in S.team().values()
                                  if v[1] == who[1] and v[0] != who[0]})
        except Exception as e:
            print('баллы для руководителя:', e)
            out['disputes'], out['awards'], out['team'] = [], [], []
    if role in ('manager', 'coo'):
        try:
            from . import kpi as K
            out['kpi'] = K.point_index(who[1], *K.period('week')[:2])
            out['kpi']['flags'] = [{'title': t, 'why': w}
                                   for t, _n, w in K.flags(who[1], *K.period('week')[:2])]
        except Exception:
            out['kpi'] = None
    try:
        out['score'] = SC.card(who[0], who[1])
    except Exception:
        out['score'] = None
    # Линейному сотруднику — своё: его заполнения, ждущие проверки,
    # его споры и состав смены. Видеть статус своей работы он должен;
    # чужие листы и начисления другим — нет.
    if role not in ('manager', 'coo'):
        try:
            from . import reports as RP
            out['pending'] = [
                {'key': x['key'], 'line': x['line'], 'title': x['title'],
                 'point': x['point'], 'who': x['who'], 'day': x['day'],
                 'at': x['at'], 'ok': int(x['ok']), 'tot': int(x['tot']),
                 'fails': x['fails'], 'comment': x['comment'],
                 'minutes': x['minutes'], 'fast': x['fast'],
                 'age': (C.today() - x['date']).days}
                for x in RP.pending(who[1]) if x['who'] == who[0]]
        except Exception as e:
            print('свои заполнения:', e)
            out['pending'] = []
        try:
            out['disputes'] = [x for x in SC.disputes(who[1])
                               if x.get('who') == who[0]]
        except Exception:
            out['disputes'] = []
    for key, cl in (C.for_role(role, dept, who[1]).items() if not left else []):
        photos = C.photo_items(key)
        random.shuffle(photos)
        out['lists'][key] = {
            'title': cl['title'], 'code': cl['code'], 'ask_time': cl['ask_time'],
            'deadline': C.deadline_for(cl, who[1]),
            'station': cl.get('station', ''), 'stage': cl.get('stage', ''),
            'part': cl.get('part') or [], 'when': cl.get('when', ''),
            'blocks': [{'name': b['name'], 'doc': b.get('doc'), 'items': [
                {'n': it['n'], 'text': it['text'], 'norm': it.get('norm', '')}
                for it in b['items']]} for b in cl['blocks']],
            'measures': [{'n': n, 'q': m['q'], 'norm': m['norm'], 'unit': m['unit'],
                          'min': m.get('min'), 'max': m.get('max'),
                          'ok_min': m.get('ok_min'), 'ok_max': m.get('ok_max')}
                         for n, m in cl['measures'].items()],
            'photos': [{'n': n, 'text': t} for n, t in photos[:C.PHOTOS_PER_RUN]],
        }
    # Что уже сдано сегодня на точке: приём не открывают, пока предыдущая
    # смена не сдала передачу.
    try:
        out['filled'] = S.filled_today(C.day_str(), who[1], list(out['lists']))
    except Exception as e:
        print('что сдано:', e)
        out['filled'] = {}
    return out


def handover_notify(kind, day, point, who, to, ok, tot, fails, comment):
    """Смена сдана — принимающему сообщение; принята — сдавшему ответ.

    Без адресата передача остаётся словами на пересменке: сдал «вообще»,
    принял «вообще», спросить некого. Названный человек получает сообщение
    и открывает свой лист приёма.
    """
    cl = C.checklists().get(kind) or {}
    stage = cl.get('stage')
    if stage not in ('give', 'take'):
        return
    place = cl['title'].split(' · ')[0]

    def chat_of(name):
        return next((cid for cid, v in S.team().items()
                     if v[0] == name and v[1] == point), None)

    if stage == 'give':
        if not to:
            return
        cid = chat_of(to)
        if not cid:
            BOT.admin(f'⚠️ <b>Некому передать смену</b> · {point} · {place}\n'
                      f'{who} сдаёт «{to}», а такого человека на точке нет.')
            return
        BOT.say(cid, f'🔄 <b>Тебе сдают смену</b> · {place}\n'
                     f'{who} закрыл передачу: {ok} из {tot}.'
                     + (f'\nЗамечания: {comment}' if comment else '')
                     + '\n\nОткрой приложение и пройди «Приём» — '
                       'пока не принял, смена не сдана.')
        return

    # Приём: ответ тому, кто сдавал.
    give = f"{kind[:-len('_take')]}_give"
    src = S.filled_today(day, point, [give]).get(give) or {}
    cid = chat_of(src.get('who', ''))
    if not cid:
        return
    good = not fails
    head = '✅ <b>Смена принята</b>' if good else '⚠️ <b>Принята с замечаниями</b>'
    BOT.say(cid, f'{head} · {place}\n{who}: {ok} из {tot}.'
                 + (f'\nЧто не так: {comment}' if comment else ''))


def shift_state(who):
    """Что с явкой сегодня: отмечен приход, отмечен уход."""
    try:
        found = F.shift_row(C.day_str(), who[1], who[0])
    except Exception:
        return {'in': '', 'out': ''}
    if not found:
        return {'in': '', 'out': ''}
    r = found[1]
    return {'in': r[3], 'out': r[4], 'hours': r[5], 'late': r[6]}


def shift(who, body):
    d = 'out' if body.get('direction') == 'out' else 'in'
    lat, lon = body.get('lat'), body.get('lon')
    link = ''
    if d == 'in':
        raw = photo_bytes(body.get('photo'))
        if not raw:
            return {'ok': False, 'error': 'Нужно фото. Сфотографируй себя '
                                          'на точке — это подтверждает, '
                                          'что пришёл именно ты.'}
        link = S.save_photo(raw, f'{who[1]}-приход-{C.day_str()}-{who[0]}')
    point = pick_point(who, body)
    # Время начала берём из состава: у повара цеха смена в 07:00, у кассира
    # в 09:30 — считать опоздание всем от одного часа неправильно.
    plan = body.get('plan')
    try:
        from . import roster as RS
        plan = RS.start_of(C.today(), who[0], plan)
    except Exception as e:
        print('состав:', e)
    msg, flag, line = F.mark_shift(d, C.day_str(), point, who[0], lat, lon,
                                   plan=plan, photo=link)
    if d == 'in':
        if lat is None:
            SC.add(point, who[0], 'geo_missing')
        # Опоздание — минус за каждую минуту (решение Азиза 21.08.2026).
        late = 0
        try:
            found = F.shift_row(C.day_str(), point, who[0])
            late = int(float(str(found[1][6] or 0).replace(',', '.'))) if found else 0
        except (ValueError, TypeError, IndexError):
            late = 0
        if late > 0:
            SC.add(point, who[0], 'late', qty=late)
    if flag:
        txt = f'📍 <b>Явка</b> · {point} · {who[0]}\n' + msg.replace('✅ ', '')
        if link:
            txt += f'\n<a href="{link}">фото прихода</a>'
        for cid in S.managers_of(point):
            BOT.say(cid, txt)
    return {'ok': True, 'message': msg, 'shift': shift_state(who)}


def quiz_passed(key, name):
    """Сдавал ли человек этот тренинг раньше. Таблицы нет — считаем, что нет."""
    try:
        return F.quiz_attempts(key, name)[1]
    except Exception:
        return False


def quiz(who, body):
    """Проверка знаний. Ответы сверяет сервер и возвращает разбор.

    Разбор возвращается всегда, даже когда не сдал: смысл тренинга —
    чтобы человек понял, а не чтобы получил отметку.
    """
    key = body.get('key')
    cl = C.forms().get(key)
    if not cl or cl['type'] != 'quiz':
        return {'ok': False, 'error': 'неизвестный тренинг'}
    qs = cl.get('questions', [])
    given = body.get('answers') or []
    if len(given) != len(qs):
        return {'ok': False, 'error': 'Ответь на все вопросы'}
    review, wrong = [], []
    for i, q in enumerate(qs):
        try:
            a = int(given[i])
        except (TypeError, ValueError):
            a = -1
        ok = a == q['correct']
        if not ok:
            wrong.append(i + 1)
        review.append({'n': i + 1, 'q': q['q'], 'ok': ok, 'your': a,
                       'correct': q['correct'], 'why': q.get('why', '')})
    right = len(qs) - len(wrong)
    need = int(cl.get('pass', len(qs)))
    point = pick_point(who, body)
    seconds = float(body.get('seconds') or 0)
    attempt, was = 1, False
    try:
        attempt, was = F.quiz_attempts(key, who[0])
    except Exception as e:
        print('попытки тренинга:', e)
    try:
        F.save_quiz(key, point, who[0], right, len(qs), need, wrong,
                    seconds, attempt)
    except Exception as e:
        print('запись тренинга:', e)
    done = right >= need
    if done and not was:
        SC.add(point, who[0], 'quiz_passed', cl['code'])
        txt = (f'🎓 <b>Тренинг пройден</b> · {point} · {who[0]}\n'
               f'{cl["title"]} — {right} из {len(qs)}, попытка {attempt}')
        for cid in S.managers_of(point):
            BOT.say(cid, txt)
    return {'ok': True, 'right': right, 'total': len(qs), 'need': need,
            'passed': done, 'attempt': attempt, 'review': review,
            'again': was}


def journal(who, body):
    key = body.get('key')
    cl = C.forms().get(key)
    if not cl or cl['type'] != 'journal':
        return {'ok': False, 'error': 'неизвестная форма'}
    vals = {f['key']: str((body.get('values') or {}).get(f['key'], ''))[:400]
            for f in cl.get('fields', [])}
    for f in cl.get('fields', []):
        if f.get('required') and not vals.get(f['key']):
            return {'ok': False, 'error': f'Заполни: {f["label"]}'}
        if f.get('min_words') and len(vals.get(f['key'], '').split()) < f['min_words']:
            return {'ok': False, 'error': f'«{f["label"]}» — напиши фразой, '
                                          f'не одним словом'}
    point = pick_point(who, body)
    link = ''
    raw = photo_bytes(body.get('photo'))
    if raw:
        link = S.save_photo(raw, f'{point}-{C.day_str()}-{cl["code"]}')
    line = F.save_journal(key, point, who[0], vals, link,
                          body.get('lat'), body.get('lon'))
    # Записанное происшествие — это находка: доп. счёт, но подтверждает
    # управляющий, иначе баллы набираются записями «всё нормально».
    SC.add(point, who[0], 'found_issue', cl['code'])
    sev = vals.get('severity', '')
    txt = (f'{cl.get("icon", "📌")} <b>{cl["title"]}</b> · {point} · {who[0]}\n'
           + '\n'.join(f'<b>{f["label"]}:</b> {vals[f["key"]]}'
                        for f in cl.get('fields', []) if vals.get(f['key'])))
    sent = set()
    for cid in S.managers_of(point):
        BOT.say(cid, txt)
        sent.add(str(cid))
    if (sev in ('Серьёзное', 'Критично') or not sent) \
            and str(C.ADMIN_CHAT) not in sent:
        BOT.admin(txt)
    try:
        from . import tasks as TSK
        TSK.from_journal(point, cl['title'], vals.get('what', ''), sev, who[0])
    except Exception as e:
        print('задача из журнала:', e)
    return {'ok': True, 'line': line}


def blank(who, body):
    key = body.get('key')
    cl = C.forms().get(key)
    if not cl or cl['type'] != 'form':
        return {'ok': False, 'error': 'неизвестная форма'}
    need = cl.get('requires')
    if need and not quiz_passed(need, who[0]):
        return {'ok': False, 'error': f'Сначала сдай тренинг '
                                      f'«{C.form(need)["title"]}» — он в разделе '
                                      f'«Обучение».'}
    lines = [ln for ln in (body.get('lines') or [])
             if str(ln.get('item', '')).strip()]
    if not lines:
        return {'ok': False, 'error': 'Добавь хотя бы одну позицию'}
    if len(lines) > 200:
        return {'ok': False, 'error': 'Слишком много строк за раз'}
    point = pick_point(who, body)
    raw = photo_bytes(body.get('photo'))
    if cl.get('photo_required') and not raw:
        return {'ok': False, 'error': 'Нужно фото — без него запись не принимается'}
    link = S.save_photo(raw, f'{point}-{C.day_str()}-{cl["code"]}') if raw else ''
    line = F.save_form(key, point, who[0], lines, link,
                       body.get('lat'), body.get('lon'))
    total = sum(_num(ln.get('qty')) for ln in lines)
    txt = (f'{cl.get("icon", "📋")} <b>{cl["title"]}</b> · {point} · {who[0]}\n'
           f'Позиций: <b>{len(lines)}</b>, всего {round(total, 2)}\n'
           + '\n'.join(f'   {ln.get("item")} — {ln.get("qty")} {ln.get("unit", "")}'
                        f' · {ln.get("reason", "")}' for ln in lines[:10]))
    sent = set()
    for cid in S.managers_of(point):
        BOT.say(cid, txt)
        sent.add(str(cid))
    if str(C.ADMIN_CHAT) not in sent:
        BOT.admin(txt)
    return {'ok': True, 'line': line, 'count': len(lines)}


def _num(x):
    try:
        return float(str(x).replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0


def pick_point(who, body):
    p = str(body.get('point') or '').strip() or who[1]
    if p != who[1] and S.role_of(who) not in ('manager', 'coo'):
        return who[1]
    return p if p in S.points() else who[1]


def photo_bytes(data_url):
    try:
        return base64.b64decode(str(data_url).split(',', 1)[1])
    except Exception:
        return b''


def submit(who, body):
    kind = body.get('kind')
    if kind not in C.checklists():
        return {'ok': False, 'error': 'неизвестный чек-лист'}
    day = C.day_str()
    marks = {int(k): bool(v) for k, v in (body.get('marks') or {}).items()}
    if len(marks) < C.total(kind):
        return {'ok': False, 'error': 'отмечены не все пункты'}
    measured = {}
    for k, v in (body.get('measures') or {}).items():
        m = C.checklists()[kind]['measures'].get(int(k))
        if not m:
            continue
        val, err = BOT.parse_measure(v, m)
        if err:
            return {'ok': False, 'error': f'{m["q"]}: {err}'}
        measured[int(k)] = str(v).strip()[:20]
    hhmm = BOT.parse_time(body.get('time', ''))
    if not hhmm:
        return {'ok': False, 'error': 'Время нужно в формате ЧЧ:ММ'}
    point = str(body.get('point') or '').strip() or who[1]
    if point != who[1] and S.role_of(who) not in ('manager', 'coo'):
        point = who[1]
    if point not in S.points():
        point = who[1]
    photos, shots = [], []
    for ph in (body.get('photos') or []):
        raw = b''
        try:
            raw = base64.b64decode(str(ph.get('data', '')).split(',', 1)[1])
        except Exception:
            pass
        n = ph.get('n')
        photos.append(S.save_photo(raw, f'{point}-{day}-п{n}') if raw else f'п{n}:есть')
        if raw:
            shots.append((int(n), raw))
    sec = float(body.get('seconds') or 0)
    tempo = BOT.tempo(body.get('marks_ts') or [])
    comment = str(body.get('comment', ''))[:300]
    part = str(body.get('part') or '') or None
    to = str(body.get('to') or '').strip()[:60]
    dup = S.already_filled(kind, day, point)
    ok, tot, fails, line = S.save_fill(
        kind, day, point, who[0], marks, measured, photos, hhmm, comment, sec,
        part, to)
    try:
        handover_notify(kind, day, point, who[0], to, ok, tot, fails, comment)
    except Exception as e:
        print('передача смены:', e)
    st = {'kind': kind, 'day': day, 'point': point, 'who': who[0]}
    try:
        fast = sec < C.MIN_SECONDS or (tempo is not None and tempo < C.MIN_GAP)
        BOT.notify_check(st, ok, tot, fails, line, comment, fast, bool(dup))
        BOT.award_fill(st, ok, tot, fails, fast, BOT.is_late(kind, point))
    except Exception:
        pass
    if V.enabled():
        V.review_async(kind, line, point, who[0], shots)
    from . import tasks as TSK
    for q, val, norm, unit in BOT.norm_alerts(kind, measured):
        BOT.admin(f'🌡 <b>Замер вне нормы</b> · {point} · {who[0]}\n'
                  f'{q}: <b>{val} {unit}</b> при норме {norm}')
        try:
            TSK.from_measure(point, q, val, norm, unit)
        except Exception as e:
            print('задача из замера:', e)
    return {'ok': True, 'done': ok, 'total': tot, 'dup': dup,
            'minutes': round(sec / 60, 1),
            'fast': sec < C.MIN_SECONDS or (tempo is not None and tempo < C.MIN_GAP)}


def fix(who, body):
    """Правка к пункту чек-листа. Только руководитель — это правка регламента."""
    if S.role_of(who) not in ('manager', 'coo'):
        return {'ok': False, 'error': 'Правки вносит руководитель'}
    comment = str(body.get('comment', '')).strip()
    if len(comment.split()) < 2:
        return {'ok': False, 'error': 'Напиши, что именно поправить'}
    S.save_fix(who[0], str(body.get('form', ''))[:60], str(body.get('block', ''))[:60],
               body.get('n', ''), str(body.get('text', ''))[:300],
               comment[:400], str(body.get('doc', ''))[:20])
    return {'ok': True}


def faults(key, line, who, body):
    """Разбор невыполненных пунктов управляющим: вина смены или нет.

    Без этого разбора система платит за враньё: честный ✕ минусует, а
    нарисованная галочка — нет. Система не отличает грязный пол от сломанного
    холодильника, управляющий отличает за две секунды.
    """
    guilty = [str(x) for x in (body.get('guilty') or [])]
    external = [str(x) for x in (body.get('external') or [])]
    if not guilty and not external:
        return
    try:
        r = S.get(C.checklists()[key]['tab'], f'A{line}:C{line}')
        point, filler = (r[0][1], r[0][2]) if r and len(r[0]) > 2 else (who[1], '')
    except Exception:
        point, filler = who[1], ''
    texts = {str(n): t for n, _b, t in C.flat(key)}
    for n in guilty:
        if filler:
            SC.add(point, filler, 'item_fail', f'{key}:{n}')
    if external:
        try:
            from . import tasks as TSK
            for n in external:
                TSK.from_fail(point, texts.get(n, f'пункт {n}'), who[0],
                              'не вина смены, нужна починка')
        except Exception as e:
            print('задача из пункта:', e)
    # Честно отмеченный ✕, оказавшийся не виной смены, — это находка.
    if filler and external:
        SC.add(point, filler, 'found_issue', key)


def check(who, body):
    """Второй круг: подтвердить заполнение либо описать расхождение."""
    if S.role_of(who) not in ('manager', 'coo'):
        return {'ok': False, 'error': 'Подтверждает руководитель'}
    key = str(body.get('key', ''))
    line = str(body.get('line', ''))
    verdict = 'ok' if body.get('verdict') == 'ok' else 'bad'
    note_txt = str(body.get('note', '')).strip()[:300]
    if key not in C.checklists() or not line.isdigit():
        return {'ok': False, 'error': 'не та запись'}
    if verdict == 'bad' and len(note_txt.split()) < 2:
        return {'ok': False, 'error': 'Опиши, что именно не сошлось'}
    S.save_check(key, line, who[0], verdict, note_txt)
    faults(key, line, who, body)
    if verdict == 'bad':
        try:
            from . import tasks as TSK
            r = S.get(C.checklists()[key]['tab'], f'A{line}:C{line}')
            pt, filler = (r[0][1], r[0][2]) if r and len(r[0]) > 2 else (who[1], '')
            TSK.from_mismatch(pt, C.checklists()[key]['title'], filler, note_txt)
        except Exception as e:
            print('задача из расхождения:', e)
    try:
        BOT._award_check(key, line, who[0], verdict)
    except Exception:
        pass
    try:
        BOT.final_report(key, line, verdict, who[0], note_txt)
    except Exception as e:
        print('итоговый отчёт:', e)
    return {'ok': True}


COORD_RE = __import__('re').compile(
    r'(-?\d{1,3}[.,]\d{3,})\s*[,\s]\s*(-?\d{1,3}[.,]\d{3,})')


def parse_coords(text):
    """«38.5767, 68.8002» или ссылка Google Карт → (широта, долгота).

    Задать координаты можно двумя способами: стоя на точке кнопкой — точнее
    всего; или вставив место с карты — когда до точки ещё надо доехать.
    """
    t = str(text).replace('%2C', ',')
    m = __import__('re').search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', t) or COORD_RE.search(t)
    if not m:
        return None
    try:
        return (float(m.group(1).replace(',', '.')),
                float(m.group(2).replace(',', '.')))
    except ValueError:
        return None


def set_geo(who, body):
    """Координаты точки задаются С МЕСТА, стоя на точке.

    Геокодирование по адресу для этого не годится: ошибка в сто метров
    превращает честную отметку в «ВНЕ ТОЧКИ». Стоя на пороге — точно.
    """
    if S.role_of(who) not in ('manager', 'coo'):
        return {'ok': False, 'error': 'Координаты задаёт руководитель'}
    point = pick_point(who, body)
    manual = str(body.get('manual', '')).strip()
    if manual:
        pair = parse_coords(manual)
        if not pair:
            return {'ok': False, 'error': 'Не разобрал координаты. Нужны два '
                                          'числа через запятую или ссылка '
                                          'на Google Карты.'}
        lat, lon = pair
    else:
        try:
            lat = float(body.get('lat'))
            lon = float(body.get('lon'))
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'Не получилось определить место. '
                                          'Разреши геопозицию и попробуй ещё раз.'}
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return {'ok': False, 'error': 'Такие координаты не бывают'}
    radius = body.get('radius')
    try:
        radius = int(radius) if radius else 150
    except (TypeError, ValueError):
        radius = 150
    rows = S.get(C.TABS['points'], 'A2:G50')
    line = None
    for i, r in enumerate(rows):
        if r and str(r[0]).strip() == point:
            line = i + 2
            break
    if not line:
        return {'ok': False, 'error': 'Точки нет в списке'}
    S.put(C.TABS['points'], f'E{line}:G{line}',
          [[round(lat, 6), round(lon, 6), radius]])
    S.points_map(force=True)
    BOT.admin(f'📍 <b>Координаты точки заданы</b> · {point}\n'
              f'{lat:.5f}, {lon:.5f} · радиус {radius} м\n'
              f'Задал: {who[0]}')
    return {'ok': True, 'lat': round(lat, 6), 'lon': round(lon, 6),
            'radius': radius}


def equip(who, body):
    """Добавить единицу оборудования или сменить её статус."""
    if S.role_of(who) not in ('manager', 'coo'):
        return {'ok': False, 'error': 'Оборудование заводит руководитель'}
    from . import equipment as EQ
    act = body.get('action', 'add')
    if act == 'status':
        line = str(body.get('line', ''))
        st = body.get('status')
        if not line.isdigit() or st not in (EQ.ACTIVE, EQ.BROKEN, EQ.OFF):
            return {'ok': False, 'error': 'не та запись'}
        EQ.set_status(line, st, who[0], str(body.get('note', '')))
        return {'ok': True}
    point = pick_point(who, body)
    raw = photo_bytes(body.get('photo'))
    link = (S.save_photo(raw, f'{point}-оборудование-{C.day_str()}')
            if raw else '')
    code, err = EQ.add(point, str(body.get('type', '')),
                       str(body.get('title', '')), str(body.get('model', '')),
                       str(body.get('serial', '')), str(body.get('installed', '')),
                       str(body.get('warranty', '')), link, who[0],
                       str(body.get('note', '')))
    if err:
        return {'ok': False, 'error': err}
    return {'ok': True, 'code': code}


def task_done(who, body):
    if S.role_of(who) not in ('manager', 'coo'):
        return {'ok': False, 'error': 'Задачи закрывает руководитель'}
    from . import tasks as TSK
    # ручное заведение задачи из находки
    if body.get('create'):
        what = str(body.get('what', '')).strip()
        if len(what.split()) < 2:
            return {'ok': False, 'error': 'Напиши задачу фразой'}
        pt = pick_point(who, body)
        TSK.from_fail(pt, what, who[0], str(body.get('why', ''))[:120])
        return {'ok': True}
    line = str(body.get('line', ''))
    if not line.isdigit():
        return {'ok': False, 'error': 'не та задача'}
    verdict = TSK.DROP if body.get('verdict') == 'drop' else TSK.DONE
    TSK.close(line, who[0], verdict, str(body.get('comment', '')))
    return {'ok': True}


def board(who, body):
    """Обзор для руководителя: то, на что реагируют сегодня, и картина недели."""
    role = S.role_of(who)
    if role not in ('manager', 'coo'):
        return {'ok': False, 'error': 'Обзор — для руководителя'}
    from . import board as BD
    pt = None if role == 'coo' else who[1]
    try:
        return {'ok': True, 'board': BD.build(role, pt, who[0])}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def roster(who, body):
    """Состав смены на завтра: черновик по вчерашнему составу и текущее состояние."""
    from . import roster as RS
    day = C.today() + datetime.timedelta(days=1)
    if body.get('day') == 'today':
        day = C.today()
    point = pick_point(who, body)
    boss = S.role_of(who) in ('manager', 'coo')
    mine = RS.for_person(day, who[0])
    out = {'ok': True, 'day': RS.day_str(day), 'point': point,
           'mine': mine, 'boss': boss}
    if boss:
        cur = RS.planned(day, point)
        out['people'] = cur or RS.template(point, day)
        out['sent'] = bool(cur)
        out['team'] = sorted({v[0] for v in S.team().values() if v[1] == point})
        out['depts'] = list(RS.START)
        out['starts'] = RS.START
    return out


def roster_save(who, body):
    """Управляющий отправил состав — людям сразу уходит вопрос «Буду / Не смогу»."""
    if S.role_of(who) not in ('manager', 'coo'):
        return {'ok': False, 'error': 'Состав смены собирает руководитель'}
    from . import roster as RS
    day = C.today() + datetime.timedelta(days=1)
    point = pick_point(who, body)
    people = [p for p in (body.get('people') or [])
              if str(p.get('who', '')).strip()]
    if not people:
        return {'ok': False, 'error': 'В составе никого нет'}
    if len(people) > 60:
        return {'ok': False, 'error': 'Слишком много строк'}
    names = {v[0]: cid for cid, v in S.team().items() if v[1] == point}
    for p in people:
        if p['who'] not in names:
            return {'ok': False, 'error': f'{p["who"]} не числится на этой точке'}
    ask = RS.save(day, point, people, who[0])
    sent = 0
    for p in people:
        if p['who'] not in ask:
            continue
        cid = names.get(p['who'])
        if not cid:
            continue
        line = (f'📅 <b>Завтра, {RS.day_str(day)}</b>\n'
                f'{p.get("dept", "—")} · с {p.get("start") or "—"}')
        if p.get('instead'):
            line += f'\nЗамена: вместо {p["instead"]}'
        BOT.say(cid, line + '\n\nПодтверди до 21:30.',
                reply_markup={'inline_keyboard': [[
                    {'text': '✅ Буду', 'callback_data': 'rs:y'},
                    {'text': '❌ Не смогу', 'callback_data': 'rs:n'}]]})
        sent += 1
    return {'ok': True, 'sent': sent, 'total': len(people)}


def roster_confirm(who, body):
    """Ответ сотрудника из приложения (в боте — те же кнопки)."""
    from . import roster as RS
    day = C.today() + datetime.timedelta(days=1)
    yes = bool(body.get('yes'))
    if not RS.confirm(day, who[0], yes):
        return {'ok': False, 'error': 'Тебя нет в составе на завтра'}
    if not yes:
        dept = RS.dept_of(day, who[0], '')
        busy = {r['who'] for r in RS.planned(day, who[1])}
        able = [x for x in S.cover_for(who[1], dept, exclude=busy)]
        txt = (f'⚠️ <b>Не выйдет завтра</b> · {who[1]} · {who[0]}\n'
               f'Позиция: {dept or "—"}. Нужна замена.\n'
               + ('Могут подменить: ' + ', '.join(able) if able
                  else 'Свободных, умеющих эту позицию, в команде нет.'))
        for cid in S.managers_of(who[1]):
            BOT.say(cid, txt)
        BOT.admin(txt)
    return {'ok': True}


def award(who, body):
    """Управляющий начисляет доп. балл: замена, обучение, принятая идея.

    Только через живого человека: всё, что начисляется по факту записи,
    накручивается за неделю.
    """
    if S.role_of(who) not in ('manager', 'coo'):
        return {'ok': False, 'error': 'Баллы начисляет руководитель'}
    event = str(body.get('event', ''))
    name = str(body.get('to', '')).strip()
    if event not in SC.AWARDABLE:
        return {'ok': False, 'error': 'неизвестное начисление'}
    point = pick_point(who, body)
    if name not in {v[0] for v in S.team().values() if v[1] == point}:
        return {'ok': False, 'error': 'Такого человека нет на этой точке'}
    pts = SC.add(point, name, event, f'начислил {who[0]}')
    if not pts:
        return {'ok': False, 'error': 'Сегодня по этому основанию уже начислено'}
    for cid, v in S.team().items():
        if v[0] == name and v[1] == point:
            BOT.say(cid, f'⭐️ <b>+{pts}</b> · {SC.RULES[event][2]}\n'
                         f'Начислил: {who[0]}')
    return {'ok': True, 'pts': pts}


def points(who, body):
    """Баланс периода со всеми строками — человек видит его в реальном времени."""
    try:
        return {'ok': True, 'balance': SC.balance(who[0], None)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def dispute(who, body):
    """«Не согласен» — спор по конкретному списанию.

    Управляющему уходит в тот же день: пока случай свежий, его ещё можно
    проверить по камере.
    """
    line = str(body.get('line', ''))
    text = str(body.get('text', '')).strip()
    if len(text.split()) < 2:
        return {'ok': False, 'error': 'Напиши фразой, с чем именно не согласен'}
    if not SC.dispute(line, who[0], text):
        return {'ok': False, 'error': 'Не нашёл это списание'}
    txt = (f'⚖️ <b>Спор по баллам</b> · {who[1]} · {who[0]}\n«{text[:250]}»\n'
           f'Строка {line} в листе «{C.TABS["score"]}»')
    for cid in S.managers_of(who[1]):
        BOT.say(cid, txt)
    BOT.admin(txt)
    return {'ok': True}


def dispute_resolve(who, body):
    """Управляющий разобрал спор: снять списание или оставить."""
    if S.role_of(who) not in ('manager', 'coo'):
        return {'ok': False, 'error': 'Споры разбирает руководитель'}
    line = str(body.get('line', ''))
    verdict = 'drop' if body.get('verdict') == 'drop' else 'keep'
    if not SC.resolve(line, verdict, str(body.get('note', ''))):
        return {'ok': False, 'error': 'не та строка'}
    return {'ok': True}


def note(who, body):
    text = str(body.get('text', '')).strip()
    if len(text.split()) < 3:
        return {'ok': False, 'error': 'Напиши фразой — что не так и что делать'}
    S.save_note(C.day_str(), who[0], who[1],
                body.get('source', 'Mini App'), text[:400])
    BOT.admin(f'💬 <b>Идея с точки {who[1]}</b> · {who[0]}\n«{text[:300]}»')
    return {'ok': True}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else \
            json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == '/health':
            return self._send(200, {'ok': True, 'company': C.COMPANY})
        if p.path in ('/', '/index.html', '/app'):
            try:
                return self._send(200, open(PAGE, 'rb').read(), 'text/html; charset=utf-8')
            except Exception as e:
                return self._send(500, {'error': str(e)})
        if p.path == '/api/init':
            init = urllib.parse.parse_qs(p.query).get('initData', [''])[0]
            u = check_init_data(init, C.BOT_TOKEN)
            if not u:
                return self._send(403, {'error': 'Открой страницу через бота — '
                                                 'иначе телеграм не подтверждает, кто ты.'})
            cid = str(u.get('id', ''))
            who = S.team().get(cid)
            if not who:
                try:
                    BOT.unknown(cid, u)
                except Exception:
                    pass
                return self._send(403, {'error': 'Тебя ещё нет в системе.',
                                        'chat_id': cid})
            return self._send(200, init_payload(who))
        self._send(404, {'error': 'not found'})

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            n = int(self.headers.get('Content-Length', 0))
            if n > C.MAX_BODY:
                return self._send(413, {'error': 'Слишком большой запрос. '
                                                 'Попробуй переснять фото.'})
            body = json.loads(self.rfile.read(n) or b'{}')
        except Exception:
            return self._send(400, {'error': 'плохой запрос'})
        _, who = _who(body.get('initData', ''))
        if not who:
            return self._send(403, {'error': 'нет доступа'})
        try:
            if p == '/api/submit':
                return self._send(200, submit(who, body))
            if p == '/api/note':
                return self._send(200, note(who, body))
            if p == '/api/geo':
                return self._send(200, set_geo(who, body))
            if p == '/api/equip':
                return self._send(200, equip(who, body))
            if p == '/api/task':
                return self._send(200, task_done(who, body))
            if p == '/api/check':
                return self._send(200, check(who, body))
            if p == '/api/fix':
                return self._send(200, fix(who, body))
            if p == '/api/shift':
                return self._send(200, shift(who, body))
            if p == '/api/journal':
                return self._send(200, journal(who, body))
            if p == '/api/form':
                return self._send(200, blank(who, body))
            if p == '/api/quiz':
                return self._send(200, quiz(who, body))
            if p == '/api/points':
                return self._send(200, points(who, body))
            if p == '/api/award':
                return self._send(200, award(who, body))
            if p == '/api/board':
                return self._send(200, board(who, body))
            if p == '/api/roster':
                return self._send(200, roster(who, body))
            if p == '/api/roster_save':
                return self._send(200, roster_save(who, body))
            if p == '/api/roster_confirm':
                return self._send(200, roster_confirm(who, body))
            if p == '/api/dispute':
                return self._send(200, dispute(who, body))
            if p == '/api/dispute_resolve':
                return self._send(200, dispute_resolve(who, body))
        except Exception as e:
            return self._send(500, {'ok': False, 'error': str(e)})
        self._send(404, {'error': 'not found'})


def serve_in_background(port=None):
    port = int(port or C.PORT)
    srv = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port
