#!/usr/bin/env python3
"""Схема приложения: что с чем связано и когда открывается.

Собирается из живого checklists.romashka.json — то есть показывает не замысел,
а фактическое состояние системы. Пересобирать после любой правки форм.
"""
import sys, json, datetime, collections
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session, put_doc, folder_by_name, enforce_font

ROOT = '1cSLEkOXikhTv0g6lPxZ31xJca1Yu-q43'
JSON = '/home/user/My-vault/ops-system/checklists.romashka.json'
TODAY = datetime.date.today().strftime('%d.%m.%Y')
D = json.load(open(JSON, encoding='utf-8'))

STYLE = """<style>
@page { size: A4 portrait; margin: 16mm 14mm; }
body { font-family: 'Times New Roman', serif; font-size: 13pt; }
h1 { font-size: 22pt; margin: 0 0 4pt 0; }
h2 { font-size: 16pt; margin: 18pt 0 6pt 0; border-bottom: 1pt solid #000;
     padding-bottom: 3pt; }
h3 { font-size: 13.5pt; margin: 12pt 0 4pt 0; }
p, li, td, th { font-size: 12pt; line-height: 1.3; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; }
th, td { border: 0.75pt solid #000; padding: 4pt 6pt; text-align: left;
         vertical-align: top; background: #fff; }
th { font-weight: bold; }
.note { font-size: 11pt; }
ul { margin: 4pt 0 4pt 18pt; } li { margin: 2pt 0; }
</style>"""


def tbl(head, rows, w=None):
    w = w or [None] * len(head)
    h = ['<table><tr>']
    for i, c in enumerate(head):
        st = f' style="width:{w[i]}"' if w[i] else ''
        h.append(f'<th{st}>{c}</th>')
    h.append('</tr>')
    for r in rows:
        h.append('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>')
    h.append('</table>')
    return ''.join(h)


def visible(role, t, dept=''):
    out = []
    for k, cl in D.items():
        if cl.get('roles') and role not in cl['roles']:
            continue
        if cl.get('type') != t:
            continue
        cd = cl.get('dept') or ''
        cd = [x for x in ([cd] if isinstance(cd, str) else cd) if x]
        if cd and role not in ('manager', 'coo') and dept not in cd:
            continue
        out.append(cl)
    return out


def fills(role, dept=''):
    """Что человек заполняет сам. Руководитель — только свои листы."""
    out = visible(role, 'checklist', dept)
    if role in ('manager', 'coo'):
        out = [cl for cl in out if role in (cl.get('roles') or [])]
    return out


POS = [('Кухня', 'staff', 'кухня'), ('Цех', 'staff', 'цех'),
       ('Бар', 'staff', 'бар'), ('Касса', 'staff', 'касса'),
       ('Зал', 'staff', 'зал'),
       ('Старший смены', 'senior', 'кухня'),
       ('Управляющий', 'manager', ''), ('Директор', 'coo', '')]

stations = [cl for k, cl in D.items()
            if k.startswith('shift_') and k not in ('shift_upr', 'shift_ssk')]

body = f"""
<h1>Приложение: связи и порядок</h1>
<p class="note">Собрано из системы {TODAY}. Показывает фактическое состояние,
а не замысел: если что-то не сходится с этим документом, значит расходится
и в приложении.</p>

<h2>1. Порядок: что за чем открывается</h2>
""" + tbl(['Шаг', 'Что происходит', 'Пока не сделано'],
          [['<b>1. Заведение</b>', 'Выбор точки: ЗБ или ОВИР',
            'Приход недоступен'],
           ['<b>2. Приход</b>', 'Селфи с камеры + геометка, время фиксируется',
            'Рабочее место недоступно'],
           ['<b>3. Рабочее место</b>',
            'Выбор одной из девяти станций. Живёт до конца дня',
            'Чек-листы недоступны'],
           ['<b>4. Работа</b>',
            'Чек-лист выбранного места, журналы, бланки, баллы', '—']],
          ['20%', '48%', None]) + """
<p><b>Исключение — руководитель.</b> Управляющий и директор не выбирают
рабочее место: они не стоят на станции, а проверяют её. У них после прихода
сразу открываются свои листы и блок «Проверка».</p>
<p><b>Исключение — новичок.</b> Пока не сданы тренинги позиции, чек-листы
и бланки закрыты, открыто только обучение. Человек не работает по правилам,
которых не знает.</p>

<h2>2. Блоки на экране</h2>
""" + tbl(['№', 'Блок', 'Кому виден', 'Что внутри'],
          [['1', 'Обучение', 'всем', 'тренинги позиции'],
           ['2', 'Моя работа', 'всем',
            'чек-листы: <b>Сегодня</b> — ежедневные, <b>По необходимости</b> — '
            'событийные; журналы; бланки'],
           ['3', '<b>Проверка</b>', 'управляющий, директор',
            'заполнения на проверке, задачи, споры по баллам'],
           ['4', 'Люди и смена', 'управляющий, директор',
            'состав на завтра, начисление баллов'],
           ['5', 'Оборудование', 'управляющий, директор', 'реестр по точке'],
           ['6', 'Личный кабинет', 'всем',
            'кто, роль, точка, позиция, расстояние; баллы за период'],
           ['7', 'Точка', 'всем',
            'координаты; задавать может только руководитель']],
          ['6%', '20%', '22%', None]) + """

<h2>3. Девять рабочих мест и их листы</h2>
""" + tbl(['Рабочее место', 'Отдел', 'Пунктов на день'],
          [[cl['title'].replace('Смена · ', ''), cl.get('dept', '—'),
            str(sum(len(b['items']) for b in cl['blocks']))]
           for cl in stations],
          ['46%', '22%', None]) + """
<p>Плюс два листа сверх станций: <b>Смена · Кухня — старший смены</b>
(его видит только старший смены, дополнительно к своей станции) и
<b>Смена · Управляющий</b> (только у управляющего и директора).</p>
<p class="note">Каждый лист — шесть этапов: открытие, рутина, передача,
приём, закрытие, сдача помещения. Оборудование проверяется четыре раза:
на открытии, при передаче, при приёме и на закрытии.</p>

<h2>4. Что видит каждая позиция</h2>
""" + tbl(['Позиция', 'Заполняет сам', 'Тренинги', 'Журналы', 'Бланки'],
          [[name, str(len(fills(role, dept))), str(len(visible(role, 'quiz', dept))),
            str(len(visible(role, 'journal', dept))),
            str(len(visible(role, 'form', dept)))]
           for name, role, dept in POS],
          ['26%', '20%', '18%', '18%', None]) + """
<p>У кухни в графе «заполняет сам» четыре — это четыре станции, из которых
человек выбирает свою. У старшего смены пять: четыре станции плюс его лист.</p>

<h2>5. Тренинги по позициям</h2>
""" + tbl(['Тренинг', 'Кому', 'Вопросов'],
          [[cl['title'],
            ', '.join(cl['dept']) if isinstance(cl.get('dept'), list)
            else (cl.get('dept') or 'всем'),
            str(len(cl.get('questions', [])))]
           for cl in D.values() if cl.get('type') == 'quiz'],
          ['44%', '38%', None]) + """

<h2>6. Тренинг открывает бланк</h2>
<p>Два бланка закрыты до сдачи тренинга: работу, которой человек не владеет,
проще не дать, чем потом наказывать за ошибку.</p>
""" + tbl(['Бланк', 'Откроется после тренинга'],
          [[D[k]['title'], D[cl['requires']]['title']]
           for k, cl in D.items() if cl.get('requires')],
          ['46%', None]) + """

<h2>7. Журналы и бланки</h2>
""" + tbl(['Тип', 'Что входит', 'Кому'],
          [['<b>Журналы</b> — записать событие',
            ' · '.join(cl['title'] for cl in D.values()
                       if cl.get('type') == 'journal'),
            'всем'],
           ['<b>Бланки</b> — оформить документ',
            ' · '.join(cl['title'] for cl in D.values()
                       if cl.get('type') == 'form'),
            'по позиции']],
          ['26%', '54%', None]) + """

<h2>8. Что система намеренно не делает</h2>
<ul>
<li><b>Не ведёт инвентаризацию.</b> Считают на бумаге, лист уходит
бухгалтеру-калькулятору, тот вносит в Poster, Poster считает расхождения.
В приложении есть только бланк «Инвентаризация — сдача листа» — отметка,
что лист сдан.</li>
<li><b>Не показывает сводки.</b> Ни индекса точки, ни обзора, ни рейтинга:
на обкатке они мешают привыкнуть к самой работе.</li>
<li><b>Не смешивает финансы с операционкой.</b> Выручка, средний чек
и фуд-кост остаются в Poster.</li>
</ul>

<h2>9. Кого пускает сейчас</h2>
<p>Поэтапный запуск: директор, управляющий, старший смены. Остальные видят
экран «Скоро подключим». Добавление позиции — одна переменная на сервере,
без выката кода.</p>
"""


def main():
    s = session()
    folder = folder_by_name(s, '00 Управление системой документов', ROOT)
    html = f'<html><head><meta charset="utf-8">{STYLE}</head><body>{body}</body></html>'
    name = 'СХЕМА ПРИЛОЖЕНИЯ — связи и порядок открытия'
    fid, act = put_doc(s, name, folder, html)
    enforce_font(s, fid)
    print(f'{name} — {act}')
    print(f'https://docs.google.com/document/d/{fid}')


if __name__ == '__main__':
    main()
