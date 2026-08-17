#!/usr/bin/env python3
"""Mini App — чек-лист в виде страницы внутри телеграма.

Поднимается в отдельном потоке внутри бота, на порту Railway ($PORT).
Личность заполняющего приходит от телеграма подписанной (initData) —
паролей нет, подделать нельзя.

Маршруты:
    GET  /                 — страница
    GET  /api/init         — кто открыл, какие чек-листы, какие пункты
    POST /api/submit       — заполненный чек-лист + фото
    GET  /health           — проверка живости

Пишет теми же функциями, что и бот: одна запись, один формат.
"""
import os, sys, json, hmac, hashlib, base64, threading, datetime, random, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checklists as CL
import ops_checklist as OC

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, 'webapp', 'index.html')

_CTX = {'sheets': None, 'tg': None, 'notify': None, 'token': ''}


def setup(sheets, tg, notify, token):
    _CTX.update(sheets=sheets, tg=tg, notify=notify, token=token)


# ── проверка подписи телеграма ───────────────────────────────────────────────
def check_init_data(init_data, token):
    """Телеграм подписывает данные о пользователе. Проверяем — иначе любой
    может открыть страницу и записать что угодно от чужого имени."""
    try:
        pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
        data = dict(pairs)
        got = data.pop('hash', '')
        check = '\n'.join(f'{k}={v}' for k, v in sorted(data.items()))
        secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, got):
            return None
        return json.loads(data.get('user', '{}'))
    except Exception:
        return None


def _who(init_data):
    u = check_init_data(init_data, _CTX['token'])
    if not u:
        return None, None
    cid = str(u.get('id', ''))
    return cid, OC.team(_CTX['sheets']).get(cid)


# ── данные для страницы ──────────────────────────────────────────────────────
def init_payload(cid, who):
    out = {'name': who[0], 'point': who[1], 'role': who[2] if len(who) > 2 else '',
           'day': datetime.date.today().strftime('%d.%m.%Y'), 'lists': {}}
    for kind in ('open', 'close'):
        photos = CL.photo_items(kind)
        random.shuffle(photos)
        out['lists'][kind] = {
            'title': CL.KINDS[kind]['title'],
            'code': CL.KINDS[kind]['code'],
            'ask_time': CL.KINDS[kind]['ask_time'],
            'blocks': [{'name': b, 'items': [
                {'n': n, 'text': t, 'norm': norm} for n, t, norm in rows]}
                for b, rows in CL.by_block(kind)],
            'measures': [{'n': n, 'q': v[0], 'norm': v[1], 'unit': v[2]}
                         for n, v in CL.MEASURES.get(kind, {}).items()],
            'photos': [{'n': n, 'text': t} for n, t in photos[:CL.PHOTOS_PER_RUN]],
        }
    return out


def save_photo(data_url, name):
    """base64 из страницы → файл на Drive, возвращаем ссылку."""
    try:
        raw = base64.b64decode(data_url.split(',', 1)[1])
        folder = os.environ.get('SHIFT_PHOTOS_FOLDER') or _CTX.get('folder')
        meta = {'name': name + '.jpg'}
        if folder:
            meta['parents'] = [folder]
        r = _CTX['sheets'].post(
            'https://www.googleapis.com/upload/drive/v3/files'
            '?uploadType=multipart&supportsAllDrives=true&fields=webViewLink',
            files={'data': ('m', json.dumps(meta), 'application/json'),
                   'file': (meta['name'], raw, 'image/jpeg')}, timeout=120).json()
        return r.get('webViewLink', '')
    except Exception:
        return ''


def submit(cid, who, body):
    kind = body.get('kind')
    if kind not in CL.KINDS:
        return {'ok': False, 'error': 'неизвестный чек-лист'}
    day = datetime.date.today().strftime('%d.%m.%Y')
    marks = {int(k): bool(v) for k, v in (body.get('marks') or {}).items()}
    if len(marks) < CL.total(kind):
        return {'ok': False, 'error': 'отмечены не все пункты'}
    measured = {int(k): str(v)[:20] for k, v in (body.get('measures') or {}).items()}
    photos = []
    for p in body.get('photos') or []:
        link = save_photo(p.get('data', ''), f'{who[1]}-{day}-п{p.get("n")}')
        photos.append(link or f'п{p.get("n")}:есть')
    st = {'kind': kind, 'day': day, 'point': who[1], 'who': who[0],
          'marks': marks, 'measured': measured, 'photos_done': photos,
          'time': str(body.get('time', ''))[:20],
          'started': datetime.datetime.utcnow()}
    sec = float(body.get('seconds') or 0)
    comment = str(body.get('comment', ''))[:300]
    ok, tot, fails, line = OC._write(
        _CTX['sheets'], st, comment,
        datetime.datetime.utcnow().strftime('%H:%M'), sec)
    fast = sec < CL.MIN_SECONDS
    try:
        OC._ask_check(_CTX['sheets'], _CTX['tg'], st, ok, tot, fails, line, comment, fast)
    except Exception:
        pass
    if _CTX['notify'] and (fails or fast):
        nm = {n: t for n, _, t in CL.flat(kind)}
        lst = '\n'.join(f'   ❌ {n}. {nm[n]}' for n in fails[:8])
        warn = f'\n   ⚠️ Заполнено за {round(sec / 60, 1)} мин' if fast else ''
        _CTX['notify'](f'🧾 <b>{who[1]}</b> · {CL.KINDS[kind]["title"].lower()} '
                       f'{day} · {who[0]}\n{ok}/{tot}{warn}\n{lst}')
    return {'ok': True, 'done': ok, 'total': tot, 'minutes': round(sec / 60, 1),
            'fast': fast}


def note(cid, who, body):
    text = str(body.get('text', '')).strip()
    if len(text.split()) < 3:
        return {'ok': False, 'error': 'Напиши фразой — что не так и что делать'}
    OC.note_write(_CTX['sheets'], datetime.date.today().strftime('%d.%m.%Y'),
                  who[0], who[1], body.get('source', 'Mini App'), text[:400])
    if _CTX['notify']:
        _CTX['notify'](f'💬 <b>Идея с точки {who[1]}</b> · {who[0]}\n«{text[:300]}»')
    return {'ok': True}


# ── HTTP ─────────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == '/health':
            return self._send(200, {'ok': True})
        if path in ('/', '/index.html', '/app'):
            try:
                return self._send(200, open(PAGE, 'rb').read(),
                                  'text/html; charset=utf-8')
            except Exception as e:
                return self._send(500, {'error': str(e)})
        if path == '/api/init':
            init = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query).get('initData', [''])[0]
            cid, who = _who(init)
            if not who:
                return self._send(403, {'error': 'Тебя нет в списке заполняющих. '
                                                 'Обратись к управляющему.'})
            return self._send(200, init_payload(cid, who))
        self._send(404, {'error': 'not found'})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            n = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n) or b'{}')
        except Exception:
            return self._send(400, {'error': 'плохой запрос'})
        cid, who = _who(body.get('initData', ''))
        if not who:
            return self._send(403, {'error': 'нет доступа'})
        try:
            if path == '/api/submit':
                return self._send(200, submit(cid, who, body))
            if path == '/api/note':
                return self._send(200, note(cid, who, body))
        except Exception as e:
            return self._send(500, {'ok': False, 'error': str(e)})
        self._send(404, {'error': 'not found'})


def serve_in_background(port=None):
    port = int(port or os.environ.get('PORT') or 8080)
    srv = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port


if __name__ == '__main__':
    from ops_docs import session
    setup(session(), lambda *a, **k: None, None,
          os.environ.get('TELEGRAM_BOT_TOKEN', ''))
    srv, port = serve_in_background(os.environ.get('PORT', 8080))
    print(f'Mini App на http://127.0.0.1:{port}')
    threading.Event().wait()
