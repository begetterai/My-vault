#!/usr/bin/env python3
"""Оборудование точки — модульная система.

Замысел Азиза: точка собирается из модулей. Добавил холодильник — вместе с
ним пришли пункты ежедневной проверки, замер температуры с нормой, правила
ухода и график ТО. Убрал — всё исчезло. Ничего не надо описывать заново.

Два слоя:
  · БИБЛИОТЕКА МОДУЛЕЙ (equipment.romashka.json) — что система знает про
    ТИП оборудования. Общая для всех клиентов, правится как данные.
  · РЕЕСТР ОБЪЕКТОВ (лист «Оборудование») — что физически стоит на точках.
    Заполняется на обходе, с телефона.

Реестр наполняется НЕ из офиса. Управляющий идёт по точке и добавляет
единицу за единицей: тип из списка, название, модель, фото. Так реестр
получается настоящим, а не переписанным из головы.
"""
import json
import os
import functools

from . import config as C
from . import storage as S

EQUIP_COLS = ['Код', 'Точка', 'Тип', 'Название', 'Модель', 'Серийный номер',
              'Установлен', 'Гарантия до', 'Ответственный', 'Статус',
              'Фото', 'Добавил', 'Когда добавил', 'Комментарий']

ACTIVE = 'Работает'
BROKEN = 'Неисправно'
OFF = 'Списано'

LIB_FILE = os.environ.get(
    'EQUIPMENT_FILE',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'equipment.romashka.json'))


@functools.lru_cache(maxsize=1)
def library():
    """Тип → описание модуля."""
    with open(LIB_FILE, encoding='utf-8') as f:
        lib = json.load(f)
    for key, m in lib.items():
        m['key'] = key
    return lib


def types_for_app():
    return [{'key': k, 'title': m['title'], 'icon': m.get('icon', '🔧')}
            for k, m in library().items()]


# ── реестр объектов ──────────────────────────────────────────────────────────
def all_items(point=None, only_active=True):
    out = []
    for i, r in enumerate(S.get(C.TABS['equip'], 'A2:N')):
        r = list(r) + [''] * 14
        code = str(r[0]).strip()
        if not code:
            continue
        st = str(r[9]).strip() or ACTIVE
        if only_active and st == OFF:
            continue
        if point and str(r[1]).strip() != point:
            continue
        out.append({'line': i + 2, 'code': code, 'point': r[1].strip(),
                    'type': r[2].strip(), 'title': r[3].strip(),
                    'model': r[4].strip(), 'serial': r[5].strip(),
                    'installed': r[6].strip(), 'warranty': r[7].strip(),
                    'owner': r[8].strip(), 'status': st,
                    'photo': r[10].strip(), 'note': r[13].strip()})
    return out


def next_code(point, type_key):
    """ЗБ-FRIDGE-2 — код объекта. Им подписываются все замеры и поломки."""
    n = sum(1 for x in all_items(point, only_active=False)
            if x['type'] == type_key) + 1
    return f'{point}-{type_key.upper()}-{n}'


def add(point, type_key, title, model='', serial='', installed='',
        warranty='', photo='', who='', note=''):
    lib = library()
    if type_key not in lib:
        return None, 'неизвестный тип оборудования'
    title = ' '.join(str(title).split())[:80] or lib[type_key]['title']
    code = next_code(point, type_key)
    S.append(C.TABS['equip'], [[
        code, point, type_key, title, str(model)[:60], str(serial)[:60],
        str(installed)[:12], str(warranty)[:12],
        _owner(point), ACTIVE, photo, who, C.day_str(), str(note)[:200]]])
    return code, None


def _owner(point):
    for cid, v in S.team().items():
        if v[1] == point and S.role_of(v) == 'manager':
            return v[0]
    return ''


def set_status(line, status, who='', note=''):
    S.put(C.TABS['equip'], f'J{line}', [[status]])
    if note:
        S.put(C.TABS['equip'], f'N{line}', [[f'{who}: {note}'[:200]]])
    return True


# ── что из этого попадает в чек-лист ─────────────────────────────────────────
def daily_items(point, rotate_by=None):
    """Пункты проверки оборудования для чек-листа точки.

    ГЛАВНАЯ ОСТОРОЖНОСТЬ: три холодильника, два гриля и кофемашина — это
    плюс 25–30 пунктов к утреннему обходу. Смена будет тратить час, и всё
    скатится ровно к тому, с чем мы боремся.

    Поэтому: замеры спрашиваются по ВСЕМ объектам всегда — температура
    важна каждый день. Остальные пункты идут по ротации: каждый день
    берётся часть объектов по кругу, за неделю проходят все.
    """
    items, measures = [], []
    objs = [x for x in all_items(point) if x['status'] == ACTIVE]
    lib = library()
    day = (rotate_by if rotate_by is not None else C.today().toordinal())

    for o in objs:
        m = lib.get(o['type'])
        if not m:
            continue
        for meas in m.get('measures', []):
            measures.append(dict(meas, q=f'{meas["q"]} · {o["title"]}',
                                 code=o['code']))

    # ротация: объекты делим на группы по дням недели
    with_daily = [o for o in objs if lib.get(o['type'], {}).get('daily')]
    if with_daily:
        per_day = max(1, round(len(with_daily) / 7 + 0.5))
        start = (day * per_day) % len(with_daily)
        pick = [with_daily[(start + i) % len(with_daily)]
                for i in range(min(per_day, len(with_daily)))]
        for o in pick:
            for it in lib[o['type']]['daily']:
                items.append({'text': f'{o["title"]}: {it["text"]}',
                              'norm': o['code'], 'photo': bool(it.get('photo'))})
    return items, measures


def card(code):
    """Карточка объекта: паспорт, уход, ТО, признаки неисправности."""
    o = next((x for x in all_items(None, only_active=False)
              if x['code'] == code), None)
    if not o:
        return None
    m = library().get(o['type'], {})
    return {**o, 'module': m['title'] if m else o['type'],
            'care': m.get('care', ''), 'to': m.get('to', []),
            'bad': m.get('bad', []), 'daily': m.get('daily', []),
            'measures': m.get('measures', [])}


def text(point=None):
    objs = all_items(point, only_active=False)
    if not objs:
        return ('Реестр оборудования пуст.\n\nОткрой приложение → раздел '
                '«Точка» → «Добавить оборудование» и пройди по точке, '
                'добавляя единицу за единицей.')
    lib = library()
    L = [f'🔧 <b>Оборудование: {len(objs)}</b>', '']
    by_point = {}
    for o in objs:
        by_point.setdefault(o['point'], []).append(o)
    for pt, items in by_point.items():
        L.append(f'<b>{S.point_label(pt)}</b>')
        for o in items:
            icon = lib.get(o['type'], {}).get('icon', '🔧')
            mark = '' if o['status'] == ACTIVE else f' — <b>{o["status"]}</b>'
            L.append(f'   {icon} {o["title"]}{mark}')
            L.append(f'      <code>{o["code"]}</code>'
                     + (f' · {o["model"]}' if o['model'] else ''))
        L.append('')
    return '\n'.join(L)
