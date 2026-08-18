#!/usr/bin/env python3
"""Проверка фотоотчёта моделью зрения.

Задача не «сравнить картинки попиксельно» — свет, ракурс и время суток
каждый раз разные, и любое такое сравнение даст мусор. Задача другая:
показать модели эталон и текст пункта и спросить, выполнено ли требование.

Модель ошибается, поэтому её вердикт — сигнал руководителю, а не приговор
сотруднику. Промпт написан осторожным: при любом сомнении модель обязана
ответить «похоже на правду». Ложное обвинение дороже пропущенного нарушения:
один раз обвинишь honest сотрудника зря — систему перестанут уважать.

Без ключа модуль молчит и ничего не меняет в работе системы.
"""
import base64, json, os, re, threading, traceback

import requests

from . import config as C
from . import storage as S

KEY = os.environ.get('GEMINI_API_KEY', '').strip()
MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash').strip()
URL = 'https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent'

PROMPT = (
    'Ты проверяешь фотоотчёт сотрудника кафе. Отвечай только JSON, без пояснений.\n\n'
    'Пункт чек-листа: «{text}»\n'
    'Норматив: «{norm}»\n\n'
    '{ref}'
    'Оцени фото сотрудника: выполнено ли требование пункта.\n\n'
    'Важные правила:\n'
    '· Ракурс, освещение, время суток и мелкие детали ОТЛИЧАЮТСЯ — это нормально, '
    'это не нарушение.\n'
    '· Отвечай ok=false ТОЛЬКО если нарушение очевидно и его видно на фото.\n'
    '· Если сомневаешься, если кадр неясный, тёмный или срезанный — отвечай ok=true.\n'
    '· wrong_place=true ставь только если снято явно не то место и не тот объект.\n\n'
    'Формат ответа:\n'
    '{{"ok": true, "wrong_place": false, "why": "одно короткое предложение по-русски"}}'
)


def enabled():
    return bool(KEY)


# ── эталоны ──────────────────────────────────────────────────────────────────
_REF = {'ts': None, 'map': {}}
_BYTES = {}


def refs(force=False):
    """(документ, №) → ссылка на эталон. Колонка G листа «Пункты»."""
    import datetime
    now = datetime.datetime.utcnow()
    if not force and _REF['ts'] and (now - _REF['ts']).seconds < 900:
        return _REF['map']
    m = {}
    for r in S.get(C.TABS['items'], 'A2:G2000'):
        if len(r) >= 7 and str(r[6]).strip():
            m[(str(r[0]).strip(), str(r[1]).strip())] = str(r[6]).strip()
    _REF['ts'], _REF['map'] = now, m
    return m


def file_id(link):
    m = re.search(r'/d/([\w-]{10,})', link) or re.search(r'[?&]id=([\w-]{10,})', link)
    return m.group(1) if m else (link if re.fullmatch(r'[\w-]{10,}', link) else '')


def reference(doc, n):
    """Байты эталонного снимка или None. Скачанное держим в памяти."""
    link = refs().get((doc, str(n)))
    if not link:
        return None
    fid = file_id(link)
    if not fid:
        return None
    if fid in _BYTES:
        return _BYTES[fid]
    try:
        r = S.session().get(
            f'https://www.googleapis.com/drive/v3/files/{fid}'
            '?alt=media&supportsAllDrives=true', timeout=60)
        _BYTES[fid] = r.content if r.ok and len(r.content) > 1000 else None
    except Exception:
        _BYTES[fid] = None
    return _BYTES[fid]


# ── запрос к модели ──────────────────────────────────────────────────────────
def ask(photo, item_text, norm, ref_bytes=None):
    """→ {'ok': bool, 'wrong_place': bool, 'why': str} либо None, если не вышло."""
    if not KEY:
        return None
    ref_note = ('Первое изображение — ЭТАЛОН, как должно выглядеть правильно. '
                'Второе — фото сотрудника, снятое сейчас.\n\n') if ref_bytes else ''
    parts = [{'text': PROMPT.format(text=item_text, norm=norm or '—', ref=ref_note)}]
    for b in ([ref_bytes] if ref_bytes else []) + [photo]:
        parts.append({'inline_data': {'mime_type': 'image/jpeg',
                                      'data': base64.b64encode(b).decode()}})
    try:
        r = requests.post(URL.format(MODEL), params={'key': KEY},
                          json={'contents': [{'parts': parts}],
                                'generationConfig': {'temperature': 0,
                                                     'responseMimeType': 'application/json'}},
                          timeout=90)
        if not r.ok:
            print('vision:', r.status_code, r.text[:200])
            return None
        txt = r.json()['candidates'][0]['content']['parts'][0]['text']
        d = json.loads(txt)
        return {'ok': bool(d.get('ok', True)),
                'wrong_place': bool(d.get('wrong_place', False)),
                'why': str(d.get('why', ''))[:200]}
    except Exception as e:
        print('vision:', e)
        return None


# ── разбор всего заполнения ──────────────────────────────────────────────────
def review(kind, line, point, who, shots):
    """shots: [(№ пункта, байты фото)]. Пишет итог в лист и зовёт руководителя.

    Запускается в фоне: заполнение сотрудника не должно ждать модель.
    """
    if not KEY or not shots:
        return
    cl = C.checklists()[kind]
    names = {n: t for n, _, t in C.flat(kind)}
    norms = {}
    for b in cl['blocks']:
        for it in b['items']:
            norms[it['n']] = it.get('norm', '')
    out, bad = [], []
    for n, data in shots:
        v = ask(data, names.get(n, ''), norms.get(n, ''), reference(cl['title'], n))
        if not v:
            out.append(f'п{n}: не проверено')
            continue
        if v['ok'] and not v['wrong_place']:
            out.append(f'п{n}: ок')
        else:
            mark = 'не то место' if v['wrong_place'] else 'не по нормативу'
            out.append(f'п{n}: {mark} — {v["why"]}')
            bad.append((n, mark, v['why']))
    try:
        S.put(cl['tab'], f'Q{line}', [['; '.join(out)]])
    except Exception:
        traceback.print_exc()
    if not bad:
        return
    from . import bot as BOT
    txt = (f'📷 <b>Вопросы к фото</b> · {point} · {cl["title"].lower()}\n'
           f'Заполнил: {who}\n\n'
           + '\n'.join(f'   ⚠️ п.{n}. {names.get(n, "")}\n      {mark}: {why}'
                       for n, mark, why in bad)
           + '\n\n<i>Это мнение модели, а не факт нарушения. '
             'Посмотри снимок сам, прежде чем спрашивать с человека.</i>')
    sent = set()
    for cid in S.managers_of(point):
        BOT.say(cid, txt)
        sent.add(str(cid))
    if str(C.ADMIN_CHAT) not in sent:
        BOT.admin(txt)


def review_async(*a):
    threading.Thread(target=review, args=a, daemon=True).start()
