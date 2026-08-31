#!/usr/bin/env python3
"""Явка, журналы и бланки — три типа ввода помимо чек-листа.

Общее правило всех трёх: запись нельзя удалить и нельзя отредактировать
задним числом. Ошибся — пишешь новую запись с пометкой. Иначе журнал
происшествий превращается в журнал того, что было удобно оставить.
"""
import datetime, math

from . import config as C
from . import storage as S

# Явка — не одна строка на день, а строка на смену. Человек может
# отработать первую смену на одной точке, сдать её и заступить на второй
# на другой: это два разных прихода и два ухода, а не один растянутый день.
SHIFT_COLS = ['Дата', 'Точка', 'Кто', 'Приход', 'Уход', 'Часов',
              'Опоздание, мин', 'Место — приход', 'Место — уход', 'Отметки',
              'Фото прихода', 'Смена']
JOURNAL_COLS = ['Дата', 'Время', 'Точка', 'Кто', 'Что', 'Где', 'Подробности',
                'Что сделали', 'Важность', 'Фото', 'Место', 'Статус', 'Решение']
FORM_COLS = ['Дата', 'Время', 'Точка', 'Кто', 'Документ', '№ строки',
             'Позиция', 'Кол-во', 'Ед.', 'Причина', 'Комментарий',
             'Фото', 'Место', 'Проверил']
QUIZ_COLS = ['Дата', 'Время', 'Точка', 'Кто', 'Тренинг', 'Правильно', 'Всего',
             'Порог', 'Сдал', 'Попытка', 'Минут', 'Ошибся в вопросах']


# ── геометка ─────────────────────────────────────────────────────────────────
def distance_m(lat1, lon1, lat2, lon2):
    """Расстояние по земле в метрах."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geo_check(point, lat, lon):
    """→ (текст для таблицы, далеко ли). Не блокируем, а помечаем.

    Блокировка сломает смену, если сел телефон или пропал GPS. Пометка
    честного человека не задевает, а «всегда без подтверждения» видно
    за неделю.
    """
    if lat is None or lon is None:
        return 'место не подтверждено', True
    ref = S.point_geo(point)
    if not ref:
        return f'{lat:.5f}, {lon:.5f}', False
    plat, plon, radius = ref
    d = distance_m(float(lat), float(lon), plat, plon)
    if d <= radius:
        return f'на точке ({int(d)} м)', False
    km = d / 1000
    far = f'{km:.1f} км' if km >= 1 else f'{int(d)} м'
    return f'ВНЕ ТОЧКИ — {far}', True


# ── явка ─────────────────────────────────────────────────────────────────────
def shift_row(day, point, who, only_open=False):
    """Строка явки. Последняя за день — или последняя незакрытая.

    Точку не спрашиваем при поиске открытой: человек мог прийти на одну,
    а заступить на второй смене на другую. Открытая явка у него одна
    в любом случае — иначе он числился бы на работе в двух местах сразу.
    """
    # strict: по этому чтению решается, открыта ли уже смена. Сбой чтения
    # раньше выглядел как «смены нет» — и приход отмечался второй раз.
    rows = S.get(C.TABS['shift'], 'A2:L', strict=True)
    found = None
    for i, r in enumerate(rows):
        r = list(r) + [''] * (12 - len(r))
        if r[0].strip() != day or r[2].strip() != who:
            continue
        if only_open:
            if r[3].strip() and not r[4].strip():
                found = (i + 2, r)
            continue
        if not point or r[1].strip() == point:
            found = (i + 2, r)
    return found


def open_shift(day, who):
    """Незакрытая явка человека за день, на любой точке."""
    return shift_row(day, None, who, only_open=True)


def mark_shift(direction, day, point, who, lat, lon, plan=None, photo='',
               part='', at=None, geo_note=''):
    """Приход или уход. → (сообщение, поздно ли, строка, записано ли)

    Фото при приходе — вторая опора после геометки. Место подделывается
    чужим телефоном, лицо — нет.

    Приход открывает НОВУЮ явку. Незакрытая уже есть — второй раз прийти
    нельзя: сначала закрой смену. Так за день набирается по строке на смену,
    и переход на другую точку виден как есть.
    """
    geo, far = geo_check(point, lat, lon)
    # Отметку вне точки разрешил живой человек — пишем это рядом с местом,
    # иначе в таблице останется просто «ВНЕ ТОЧКИ» и не видно, кто пустил.
    if geo_note:
        geo = f'{geo} — {geo_note}'
    now = at or C.now().strftime('%H:%M')
    live = open_shift(day, who)
    late = 0
    if direction == 'in':
        if live:
            # Отметка не записана — значит и последствий у неё быть не должно.
            # Раньше отсюда возвращались молча, а вызывающий всё равно шёл
            # дальше и начислял опоздание второй раз за тот же приход:
            # у Тохирова 31.08 вышло два списания по 38 минут на одну явку.
            return (f'Смена уже открыта с {live[1][3]}'
                    + (f' на точке {live[1][1].strip()}'
                       if live[1][1].strip() != point else '')
                    + '. Сначала закрой её — отметь уход или сдай смену.',
                    False, live[0], False)
        if plan:
            late = max(0, mins(now) - mins(plan))
        line = S.append(C.TABS['shift'],
                        [[day, point, who, now, '', '', late, geo, '', 1,
                          photo, S.PART_RU.get(part, '')]])
        msg = f'✅ Приход отмечен: <b>{now}</b>'
        if late:
            msg += f'\n⚠️ Опоздание {late} мин'
        if far:
            msg += f'\n📍 {geo}'
        return msg, bool(late or far), line, True
    # уход
    if not live:
        return 'Открытой смены нет — сначала отметь приход.', False, None, False
    line, r = live
    hours = round((mins(now) - mins(r[3])) / 60, 2)
    if hours < 0:
        hours = round(hours + 24, 2)
    S.put(C.TABS['shift'], f'E{line}:J{line}',
          [[now, hours, r[6], r[7], geo, 2]])
    msg = f'✅ Уход отмечен: <b>{now}</b>\nСмена: <b>{hours} ч</b>'
    if far:
        msg += f'\n📍 {geo}'
    return msg, far, line, True


def mins(hhmm):
    try:
        h, m = str(hhmm).split(':')
        return int(h) * 60 + int(m)
    except Exception:
        return 0


# ── журнал ───────────────────────────────────────────────────────────────────
def save_journal(key, point, who, values, photo_link, lat, lon):
    cl = C.form(key)
    geo, _ = geo_check(point, lat, lon)
    n = C.now()
    row = [n.strftime('%d.%m.%Y'), n.strftime('%H:%M'), point, who,
           values.get('what', ''), values.get('where', ''),
           values.get('details', ''), values.get('action', ''),
           values.get('severity', ''), photo_link, geo, 'Новая', '']
    return S.append(cl['tab'], [row])


# ── бланк ────────────────────────────────────────────────────────────────────
def save_form(key, point, who, lines, photo_link, lat, lon):
    """lines: [{item, qty, unit, reason, note}] → номер первой строки"""
    cl = C.form(key)
    geo, _ = geo_check(point, lat, lon)
    n = C.now()
    day, tm = n.strftime('%d.%m.%Y'), n.strftime('%H:%M')
    rows = [[day, tm, point, who, cl['title'], i + 1,
             ln.get('item', ''), ln.get('qty', ''), ln.get('unit', ''),
             ln.get('reason', ''), ln.get('note', ''),
             photo_link if i == 0 else '', geo if i == 0 else '', '']
            for i, ln in enumerate(lines)]
    return S.append(cl['tab'], rows)


# ── обучение ─────────────────────────────────────────────────────────────────
_QUIZ = {'ts': None, 'rows': []}


def quiz_rows(force=False):
    """Лист «Обучение» целиком, с коротким кэшем.

    Без кэша каждый вход в приложение читал бы лист по разу на тренинг —
    на восьми тренингах это восемь запросов на пустом месте.
    """
    now = datetime.datetime.utcnow()
    if not force and _QUIZ['ts'] and (now - _QUIZ['ts']).seconds < 60:
        return _QUIZ['rows']
    try:
        rows = S.get('Обучение', 'A2:L')
    except Exception:
        rows = []
    _QUIZ['ts'], _QUIZ['rows'] = now, rows
    return rows


def quiz_forget():
    """Сбросить кэш обучения.

    Вызывается сразу после записи результата: иначе человек сдал последний
    тренинг, нажал «Готово», а чек-листы не открылись — минуту система
    отвечает по старому списку. Этот баг уже ловили 24.08.2026.
    """
    _QUIZ['ts'] = None


def passed_titles(who):
    """Названия тренингов, которые человек сдал."""
    return {r[4].strip() for r in quiz_rows()
            if len(r) >= 9 and r[3].strip() == who
            and str(r[8]).strip().lower() in ('да', 'true')}


def quiz_attempts(key, who):
    """Сколько раз человек уже проходил этот тренинг и сдал ли.

    → (номер следующей попытки, сдавал ли раньше)
    """
    cl = C.form(key)
    n, passed = 0, False
    for r in quiz_rows():
        if len(r) >= 9 and r[3].strip() == who and r[4].strip() == cl['title']:
            n += 1
            passed = passed or str(r[8]).strip().lower() in ('да', 'true')
    return n + 1, passed


def training_left(role, dept, point, who):
    """Какие тренинги позиции человек ещё не сдал.

    Пока список не пуст, человек считается новичком: ему открыты приход
    и обучение, остальное — после. Смысл не в наказании: не пускать к работе,
    правил которой человек не знает, дешевле, чем разбирать последствия.
    """
    done = passed_titles(who)
    return [cl['title'] for cl in C.visible(role, 'quiz', dept, point).values()
            if cl['title'] not in done]


def save_quiz(key, point, who, right, total, need, wrong, seconds, attempt):
    cl = C.form(key)
    n = C.now()
    row = [n.strftime('%d.%m.%Y'), n.strftime('%H:%M'), point, who, cl['title'],
           right, total, need, 'да' if right >= need else 'нет', attempt,
           round(seconds / 60, 1), ', '.join(str(x) for x in wrong)]
    return S.append(cl['tab'], [row])


def cols_for(cl):
    return {'shift': SHIFT_COLS, 'journal': JOURNAL_COLS,
            'form': FORM_COLS, 'quiz': QUIZ_COLS}.get(cl['type'])
