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
    # руководитель работает по обеим точкам — даём выбор; линейный закреплён
    pts = ([{'code': p, 'label': S.point_label(p)} for p in S.points()]
           if role in ('manager', 'coo') else
           [{'code': who[1], 'label': S.point_label(who[1])}])
    out = {'company': C.COMPANY, 'name': who[0], 'point': who[1],
           'point_label': S.point_label(who[1]), 'points': pts,
           'role': role, 'day': C.day_str(), 'lists': {}}
    out['can_fix'] = C.FIX_MODE and role in ('manager', 'coo')
    out['can_check'] = role in ('manager', 'coo')
    out['journals'] = [{'key': k, 'title': cl['title'], 'code': cl['code'],
                        'icon': cl.get('icon', '📌'), 'doc': cl.get('doc'),
                        'fields': cl.get('fields', [])}
                       for k, cl in C.visible(role, 'journal').items()]
    out['forms'] = [{'key': k, 'title': cl['title'], 'code': cl['code'],
                     'icon': cl.get('icon', '📋'), 'doc': cl.get('doc'),
                     'columns': cl.get('columns', []),
                     'photo_required': bool(cl.get('photo_required'))}
                    for k, cl in C.visible(role, 'form').items()]
    out['shift'] = shift_state(who)
    out['geo'] = {p: S.point_geo(p) for p in S.points()}
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
    for key, cl in C.for_role(role).items():
        photos = C.photo_items(key)
        random.shuffle(photos)
        out['lists'][key] = {
            'title': cl['title'], 'code': cl['code'], 'ask_time': cl['ask_time'],
            'deadline': cl.get('deadline', ''),
            'blocks': [{'name': b['name'], 'doc': b.get('doc'), 'items': [
                {'n': it['n'], 'text': it['text'], 'norm': it.get('norm', '')}
                for it in b['items']]} for b in cl['blocks']],
            'measures': [{'n': n, 'q': m['q'], 'norm': m['norm'], 'unit': m['unit'],
                          'min': m.get('min'), 'max': m.get('max'),
                          'ok_min': m.get('ok_min'), 'ok_max': m.get('ok_max')}
                         for n, m in cl['measures'].items()],
            'photos': [{'n': n, 'text': t} for n, t in photos[:C.PHOTOS_PER_RUN]],
        }
    return out


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
    msg, flag, line = F.mark_shift(d, C.day_str(), who[1], who[0], lat, lon,
                                   plan=body.get('plan'))
    if d == 'in':
        SC.add(who[1], who[0], 'geo_missing' if lat is None else 'shift_on_time')
    if flag:
        txt = f'📍 <b>Явка</b> · {who[1]} · {who[0]}\n' + msg.replace('✅ ', '')
        for cid in S.managers_of(who[1]):
            BOT.say(cid, txt)
    return {'ok': True, 'message': msg, 'shift': shift_state(who)}


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
    SC.add(point, who[0], 'journal', cl['code'])
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
    dup = S.already_filled(kind, day, point)
    ok, tot, fails, line = S.save_fill(
        kind, day, point, who[0], marks, measured, photos, hhmm, comment, sec)
    st = {'kind': kind, 'day': day, 'point': point, 'who': who[0]}
    try:
        fast = sec < C.MIN_SECONDS or (tempo is not None and tempo < C.MIN_GAP)
        BOT.notify_check(st, ok, tot, fails, line, comment, fast, bool(dup))
        BOT.award_fill(st, ok, tot, fails, fast, BOT.is_late(kind))
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
        except Exception as e:
            return self._send(500, {'ok': False, 'error': str(e)})
        self._send(404, {'error': 'not found'})


def serve_in_background(port=None):
    port = int(port or C.PORT)
    srv = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port
