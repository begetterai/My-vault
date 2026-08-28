#!/usr/bin/env python3
"""Находка → задача.

Разрыв, который эта штука закрывает: до неё ❌ в чек-листе уходил строкой
в отчёт и умирал. Никто не назначен, срока нет — через неделю тот же пункт
снова красный, и так до бесконечности. Система только наблюдала.

ГЛАВНОЕ РЕШЕНИЕ: задача заводится НЕ на каждый ❌.

Пять невыполненных пунктов в день × две точки — это десять задач в сутки.
Через неделю список станет свалкой, и его перестанут открывать. Список
задач, который не разбирают, вреднее отсутствующего: он создаёт ощущение
контроля там, где контроля нет.

Автоматически задача заводится только там, где сигнал заведомо значимый:
  · пункт провалился три раза за неделю — это процесс, а не человек;
  · замер вне нормы — пищевая безопасность, ждать нельзя;
  · расхождение при проверке — второй круг нашёл несоответствие;
  · происшествие, поломка, нарушение или жалоба уровня «Серьёзное»/«Критично».

Всё остальное управляющий превращает в задачу руками — одной кнопкой
из карточки «На проверке». Осознанное действие вместо автоматического шума.
"""
import datetime

from . import config as C
from . import storage as S

TASK_COLS = ['Дата', 'Источник', 'Точка', 'Что сделать', 'Откуда взялось',
             'Ответственный', 'Срок', 'Важность', 'Статус',
             'Кто закрыл', 'Когда закрыл', 'Комментарий']

# важность → через сколько дней срок
DUE = {'Критично': 0, 'Серьёзное': 1, 'Заметное': 3, 'Мелочь': 7}
DEFAULT_DUE = 3

OPEN = 'Открыта'
DONE = 'Сделана'
DROP = 'Снята'


def _due(severity, days=None):
    d = DUE.get(severity, DEFAULT_DUE) if days is None else days
    return C.today() + datetime.timedelta(days=d)


def owner_for(point):
    """Ответственный по умолчанию — управляющий точки, иначе COO."""
    for cid, v in S.team().items():
        if v[1] == point and S.role_of(v) == 'manager':
            return v[0]
    for cid, v in S.team().items():
        if S.role_of(v) == 'coo':
            return v[0]
    return ''


def all_tasks(only_open=True, point=None):
    out = []
    for i, r in enumerate(S.get(C.TABS['tasks'], 'A2:L')):
        r = list(r) + [''] * 12
        if not str(r[3]).strip():
            continue
        st = str(r[8]).strip() or OPEN
        if only_open and st != OPEN:
            continue
        if point and str(r[2]).strip() != point:
            continue
        out.append({'line': i + 2, 'date': r[0].strip(), 'source': r[1].strip(),
                    'point': r[2].strip(), 'what': r[3].strip(),
                    'why': r[4].strip(), 'owner': r[5].strip(),
                    'due': r[6].strip(), 'severity': r[7].strip(),
                    'status': st})
    return out


def _key(point, what):
    """Ключ повтора: одна и та же находка на одной точке не плодит задачи."""
    return (point.strip().lower(), ' '.join(what.lower().split())[:120])


def exists(point, what):
    return any(_key(t['point'], t['what']) == _key(point, what)
               for t in all_tasks(only_open=True))


def add(point, what, why='', source='чек-лист', severity='Заметное',
        owner=None, days=None, notify=True):
    """Завести задачу. Дубли по точке и тексту не создаются."""
    what = ' '.join(str(what).split())[:200]
    if not what:
        return None
    if exists(point, what):
        return None
    owner = owner or owner_for(point)
    due = _due(severity, days)
    line = S.append(C.TABS['tasks'], [[
        C.day_str(), source, point, what, str(why)[:300], owner,
        due.strftime('%d.%m.%Y'), severity, OPEN, '', '', '']])
    if notify:
        _tell(point, what, why, owner, due, severity, source)
    return line


def _tell(point, what, why, owner, due, severity, source):
    from . import bot as BOT
    mark = {'Критично': '🔴', 'Серьёзное': '🟠'}.get(severity, '🟡')
    txt = (f'{mark} <b>Задача</b> · {point}\n'
           f'<b>{what}</b>\n'
           + (f'<i>{why}</i>\n' if why else '')
           + f'Ответственный: <b>{owner or "не назначен"}</b>\n'
           f'Срок: <b>{due.strftime("%d.%m.%Y")}</b> · важность: {severity}\n'
           f'<i>Источник: {source}</i>')
    sent = set()
    for cid, v in S.team().items():
        if v[0] == owner:
            BOT.say(cid, txt)
            sent.add(str(cid))
    for cid in S.managers_of(point):
        if str(cid) not in sent:
            BOT.say(cid, txt)
            sent.add(str(cid))
    if severity in ('Критично', 'Серьёзное'):
        BOT.admin(txt, point, skip=sent)


def close(line, who, verdict=DONE, comment=''):
    S.put(C.TABS['tasks'], f'I{line}:L{line}',
          [[verdict, who, C.now().strftime('%d.%m %H:%M'), comment[:300]]])
    return True


def overdue(point=None):
    today = C.today()
    out = []
    for t in all_tasks(only_open=True, point=point):
        d = None
        for f in ('%d.%m.%Y', '%Y-%m-%d'):
            try:
                d = datetime.datetime.strptime(t['due'], f).date()
                break
            except ValueError:
                pass
        if d and d < today:
            t['late'] = (today - d).days
            out.append(t)
    return sorted(out, key=lambda x: -x['late'])


# ── откуда задачи берутся ────────────────────────────────────────────────────
def from_repeat_fails(days=7):
    """Пункт провалился REPEAT_FAIL раз за период — это процесс, не человек."""
    from collections import Counter
    from . import reports as R
    since = C.today() - datetime.timedelta(days=days)
    rows = [r for r in S.get(C.TABS['fails'], 'A2:G')
            if len(r) > 6 and R._d(r[0]) and R._d(r[0]) >= since]
    cnt = Counter((r[1].strip(), r[6].strip()) for r in rows)
    made = 0
    for (point, text), c in cnt.items():
        if c < C.REPEAT_FAIL or not text:
            continue
        if add(point, f'Разобраться, почему повторяется: {text}',
               why=f'Пункт не выполнен {c} раз за {days} дней',
               source='повтор в чек-листе', severity='Серьёзное'):
            made += 1
    return made


def from_measure(point, question, value, norm, unit=''):
    """Замер вне нормы — пищевая безопасность, срок сегодня."""
    return add(point, f'Привести в норму: {question}',
               why=f'Замер {value} {unit} при норме {norm}',
               source='замер вне нормы', severity='Критично', days=0)


def from_mismatch(point, title, who, note):
    """Управляющий нашёл расхождение при проверке."""
    return add(point, f'Устранить расхождение: {note[:120]}',
               why=f'{title}, заполнял {who}',
               source='проверка управляющим', severity='Серьёзное')


def from_journal(point, kind, what, severity, who):
    """Происшествие, поломка, нарушение, жалоба — только значимые."""
    if severity not in ('Серьёзное', 'Критично', 'Недовольным', 'Скандал'):
        return None
    sev = 'Критично' if severity in ('Критично', 'Скандал') else 'Серьёзное'
    return add(point, f'{kind}: {what[:140]}',
               why=f'Записал {who}, важность «{severity}»',
               source=kind.lower(), severity=sev)


def from_fail(point, text, who, title):
    """Ручное превращение находки в задачу — кнопкой из «На проверке»."""
    return add(point, f'Устранить: {text[:140]}',
               why=f'{title}, нашёл {who}', source='находка вручную',
               severity='Заметное')


# ── тексты ───────────────────────────────────────────────────────────────────
def text(point=None):
    t = all_tasks(only_open=True, point=point)
    if not t:
        return '✅ Открытых задач нет.'
    late = {x['line'] for x in overdue(point)}
    L = [f'📌 <b>Задачи: {len(t)}</b>'
         + (f' · просрочено {len(late)}' if late else ''), '']
    for x in sorted(t, key=lambda x: (x['line'] not in late, x['due'])):
        mark = '🔴' if x['line'] in late else (
            '🟠' if x['severity'] in ('Критично', 'Серьёзное') else '🟡')
        L.append(f'{mark} <b>{x["what"]}</b>')
        L.append(f'   {x["point"]} · {x["owner"] or "не назначен"} · '
                 f'до {x["due"]}' + (' · ПРОСРОЧЕНА' if x['line'] in late else ''))
        if x['why']:
            L.append(f'   <i>{x["why"]}</i>')
        L.append('')
    return '\n'.join(L)
