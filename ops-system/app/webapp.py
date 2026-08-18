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
    out = {'company': C.COMPANY, 'name': who[0], 'point': who[1],
           'role': role, 'day': C.day_str(), 'lists': {}}
    for key, cl in C.for_role(role).items():
        photos = C.photo_items(key)
        random.shuffle(photos)
        out['lists'][key] = {
            'title': cl['title'], 'code': cl['code'], 'ask_time': cl['ask_time'],
            'deadline': cl.get('deadline', ''),
            'blocks': [{'name': b['name'], 'items': [
                {'n': it['n'], 'text': it['text'], 'norm': it.get('norm', '')}
                for it in b['items']]} for b in cl['blocks']],
            'measures': [{'n': n, 'q': m['q'], 'norm': m['norm'], 'unit': m['unit'],
                          'min': m.get('min'), 'max': m.get('max'),
                          'ok_min': m.get('ok_min'), 'ok_max': m.get('ok_max')}
                         for n, m in cl['measures'].items()],
            'photos': [{'n': n, 'text': t} for n, t in photos[:C.PHOTOS_PER_RUN]],
        }
    return out


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
    photos, shots = [], []
    for ph in (body.get('photos') or []):
        raw = b''
        try:
            raw = base64.b64decode(str(ph.get('data', '')).split(',', 1)[1])
        except Exception:
            pass
        n = ph.get('n')
        photos.append(S.save_photo(raw, f'{who[1]}-{day}-п{n}') if raw else f'п{n}:есть')
        if raw:
            shots.append((int(n), raw))
    sec = float(body.get('seconds') or 0)
    comment = str(body.get('comment', ''))[:300]
    dup = S.already_filled(kind, day, who[1])
    ok, tot, fails, line = S.save_fill(
        kind, day, who[1], who[0], marks, measured, photos, hhmm, comment, sec)
    st = {'kind': kind, 'day': day, 'point': who[1], 'who': who[0]}
    try:
        BOT.notify_check(st, ok, tot, fails, line, comment,
                         sec < C.MIN_SECONDS, bool(dup))
    except Exception:
        pass
    if V.enabled():
        V.review_async(kind, line, who[1], who[0], shots)
    for q, val, norm, unit in BOT.norm_alerts(kind, measured):
        BOT.admin(f'🌡 <b>Замер вне нормы</b> · {who[1]} · {who[0]}\n'
                  f'{q}: <b>{val} {unit}</b> при норме {norm}')
    return {'ok': True, 'done': ok, 'total': tot, 'dup': dup,
            'minutes': round(sec / 60, 1), 'fast': sec < C.MIN_SECONDS}


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
        except Exception as e:
            return self._send(500, {'ok': False, 'error': str(e)})
        self._send(404, {'error': 'not found'})


def serve_in_background(port=None):
    port = int(port or C.PORT)
    srv = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port
