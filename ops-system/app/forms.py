#!/usr/bin/env python3
"""Явка, журналы и бланки — три типа ввода помимо чек-листа.

Общее правило всех трёх: запись нельзя удалить и нельзя отредактировать
задним числом. Ошибся — пишешь новую запись с пометкой. Иначе журнал
происшествий превращается в журнал того, что было удобно оставить.
"""
import datetime, math

from . import config as C
from . import storage as S

SHIFT_COLS = ['Дата', 'Точка', 'Кто', 'Приход', 'Уход', 'Часов',
              'Опоздание, мин', 'Место — приход', 'Место — уход', 'Отметки',
              'Фото прихода']
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
def shift_row(day, point, who):
    """Строка явки за день или None."""
    rows = S.get(C.TABS['shift'], 'A2:K')
    for i, r in enumerate(rows):
        if len(r) >= 3 and r[0].strip() == day and r[1].strip() == point \
                and r[2].strip() == who:
            return i + 2, list(r) + [''] * (11 - len(r))
    return None


def mark_shift(direction, day, point, who, lat, lon, plan=None, photo=''):
    """Приход или уход. → (сообщение, поздно ли, строка)

    Фото при приходе — вторая опора после геометки. Место подделывается
    чужим телефоном, лицо — нет.
    """
    geo, far = geo_check(point, lat, lon)
    now = C.now().strftime('%H:%M')
    found = shift_row(day, point, who)
    late = 0
    if direction == 'in':
        if found and found[1][3]:
            return f'Приход уже отмечен в {found[1][3]}.', False, found[0]
        if plan:
            late = max(0, mins(now) - mins(plan))
        row = [day, point, who, now, '', '', late, geo, '', 1, photo]
        line = found[0] if found else None
        if line:
            S.put(C.TABS['shift'], f'A{line}:K{line}', [row])
        else:
            line = S.append(C.TABS['shift'], [row])
        msg = f'✅ Приход отмечен: <b>{now}</b>'
        if late:
            msg += f'\n⚠️ Опоздание {late} мин'
        if far:
            msg += f'\n📍 {geo} — управляющий это увидит'
        return msg, bool(late or far), line
    # уход
    if not found or not found[1][3]:
        return 'Сначала отметь приход.', False, None
    line, r = found
    if r[4]:
        return f'Уход уже отмечен в {r[4]}.', False, line
    hours = round((mins(now) - mins(r[3])) / 60, 2)
    if hours < 0:
        hours = round(hours + 24, 2)
    S.put(C.TABS['shift'], f'E{line}:J{line}',
          [[now, hours, r[6], r[7], geo, 2]])
    msg = f'✅ Уход отмечен: <b>{now}</b>\nСмена: <b>{hours} ч</b>'
    if far:
        msg += f'\n📍 {geo} — управляющий это увидит'
    return msg, far, line


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
