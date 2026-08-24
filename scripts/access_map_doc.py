#!/usr/bin/env python3
"""Полная структура доступов и документов — для проверки Азизом.

Собирается из двух живых источников: форм приложения и реестра документов.
Показывает факт, а не замысел: каждая строка проверяема.
"""
import sys, json, datetime, collections
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session, put_doc, folder_by_name, enforce_font

ROOT = '1cSLEkOXikhTv0g6lPxZ31xJca1Yu-q43'
REG = '1TzB9gjpJvj_ziBwKdVuOhfKezMVsdXzeLxQMJWz-cQk'
TAB = '00-REF-01 — Реестр документов операций'
JSON = '/home/user/My-vault/ops-system/checklists.romashka.json'
TODAY = datetime.date.today().strftime('%d.%m.%Y')
D = json.load(open(JSON, encoding='utf-8'))

STYLE = """<style>
@page { size: A4 portrait; margin: 15mm 12mm; }
body { font-family: 'Times New Roman', serif; font-size: 12pt; }
h1 { font-size: 21pt; margin: 0 0 4pt 0; }
h2 { font-size: 15pt; margin: 16pt 0 6pt 0; border-bottom: 1pt solid #000;
     padding-bottom: 3pt; }
h3 { font-size: 13pt; margin: 11pt 0 4pt 0; }
p, li, td, th { font-size: 11.5pt; line-height: 1.28; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0; }
th, td { border: 0.75pt solid #000; padding: 3.5pt 5pt; text-align: left;
         vertical-align: top; background: #fff; }
th { font-weight: bold; }
.note { font-size: 10.5pt; }
ul { margin: 3pt 0 3pt 16pt; } li { margin: 2pt 0; }
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
    out = visible(role, 'checklist', dept)
    if role in ('manager', 'coo'):
        out = [cl for cl in out if role in (cl.get('roles') or [])]
    return out


POS = [('Сотрудник кухни', 'staff', 'кухня'),
       ('Сотрудник цеха', 'staff', 'цех'),
       ('Бариста', 'staff', 'бар'),
       ('Кассир', 'staff', 'касса'),
       ('Уборщица-заготовщик', 'staff', 'зал'),
       ('Старший смены', 'senior', 'кухня'),
       ('Управляющий', 'manager', ''),
       ('Директор', 'coo', '')]

stations = [(k, cl) for k, cl in D.items()
            if k.startswith('shift_') and k not in ('shift_upr', 'shift_ssk')]


def build():
    s = session()
    rows = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{REG}/values/{TAB}!A2:M300'
                 ).json().get('values', [])
    docs = []
    for r in rows:
        r += [''] * 13
        if r[0].strip():
            docs.append({'code': r[0].strip(), 'name': r[1].strip(),
                         'cat': r[3].strip(), 'status': r[4].strip(),
                         'link': r[10].strip()})
    live = [d for d in docs if d['status'] != 'Отменён']
    bycat = collections.Counter(d['cat'] for d in live)

    b = f"""
<h1>Структура доступов и документов</h1>
<p class="note">Собрано из системы {TODAY}. Два источника: формы приложения
и реестр документов. Всё, что здесь написано, проверяемо — если строка
не сходится с приложением, значит расходится и в системе.</p>

<h2>1. Порядок работы: что за чем открывается</h2>
""" + tbl(['Шаг', 'Действие', 'Пока не сделано'],
          [['1', 'Выбор заведения: ЗБ или ОВИР', 'приход недоступен'],
           ['2', 'Приход: селфи с камеры и геометка', 'рабочее место недоступно'],
           ['3', 'Выбор рабочего места из девяти', 'чек-листы недоступны'],
           ['4', 'Работа: чек-лист места, журналы, бланки', '—']],
          ['8%', '52%', None]) + """
<p><b>Руководитель</b> шаг 3 пропускает: он не стоит на станции, а проверяет её.
<b>Новичок</b> до сдачи тренингов видит только обучение.</p>

<h2>2. Блоки экрана и кому что видно</h2>
""" + tbl(['№', 'Блок', 'Сотрудник', 'Управляющий и директор'],
          [['1', 'Обучение', 'тренинги своей позиции', 'все тренинги'],
           ['2', 'Моя работа',
            'чек-лист своего места, журналы, бланки',
            'свои листы: ежедневный + событийные'],
           ['3', 'Проверка',
            '<b>свои</b> заполнения на проверке и свои споры',
            '<b>чужие</b> заполнения: повторный проход по пунктам, '
            'разбор «✕», задачи, споры'],
           ['4', 'Люди и смена', 'состав на завтра — только смотрит',
            'состав правит и отправляет; начисляет баллы'],
           ['5', 'Оборудование', 'не виден', 'реестр по точке'],
           ['6', 'Личный кабинет', 'кто, роль, точка, позиция, баллы',
            'то же'],
           ['7', 'Точка', 'видит, заданы ли координаты',
            'задаёт координаты']],
          ['5%', '17%', '34%', None]) + f"""

<h2>3. Девять рабочих мест</h2>
""" + tbl(['Рабочее место', 'Отдел', 'Пунктов на день', 'Код'],
          [[cl['title'].replace('Смена · ', ''), cl.get('dept', '—'),
            str(sum(len(x['items']) for x in cl['blocks'])), cl.get('code', '')]
           for k, cl in stations],
          ['38%', '14%', '18%', None]) + """
<p>Сверх станций два листа: <b>старшего смены</b> (только у роли «Старший
смены», дополнительно к своей станции) и <b>управляющего</b>.</p>

<h2>4. Что доступно каждой позиции</h2>
""" + tbl(['Позиция', 'Чек-листы', 'Тренинги', 'Журналы', 'Бланки'],
          [[name, str(len(fills(role, dept))),
            str(len(visible(role, 'quiz', dept))),
            str(len(visible(role, 'journal', dept))),
            str(len(visible(role, 'form', dept)))]
           for name, role, dept in POS],
          ['30%', '18%', '17%', '17%', None]) + """

<h2>5. Тренинги: кому и сколько вопросов</h2>
""" + tbl(['Тренинг', 'Код', 'Кому', 'Вопросов'],
          [[cl['title'], cl.get('code', ''),
            ', '.join(cl['dept']) if isinstance(cl.get('dept'), list)
            else (cl.get('dept') or 'всем'),
            str(len(cl.get('questions', [])))]
           for cl in D.values() if cl.get('type') == 'quiz'],
          ['36%', '14%', '32%', None]) + """

<h2>6. Журналы и бланки</h2>
""" + tbl(['Что', 'Тип', 'Кому', 'Открывается после тренинга'],
          [[cl['title'], 'журнал' if cl['type'] == 'journal' else 'бланк',
            ', '.join(cl['dept']) if isinstance(cl.get('dept'), list)
            else (cl.get('dept') or 'всем'),
            D[cl['requires']]['title'] if cl.get('requires') else '—']
           for cl in D.values() if cl.get('type') in ('journal', 'form')],
          ['30%', '12%', '26%', None]) + f"""

<h2>7. Документы системы — {len(live)} действующих</h2>
""" + tbl(['Категория', 'Документов'],
          [[k, str(v)] for k, v in sorted(bycat.items())],
          ['72%', None]) + f"""
<p class="note">Отменено и выведено из системы: {len(docs) - len(live)}.
Готовых: {sum(1 for d in live if d['status'] == 'Готов')},
черновиков: {sum(1 for d in live if d['status'] == 'Черновик')}.</p>

<h2>8. Что система намеренно не делает</h2>
<ul>
<li><b>Не ведёт инвентаризацию</b> — считают на бумаге, лист уходит
бухгалтеру-калькулятору, дальше Poster. В приложении только отметка,
что лист сдан.</li>
<li><b>Не показывает сводок</b> — ни индекса точки, ни обзора, ни рейтинга.</li>
<li><b>Не смешивает финансы с операционкой</b> — выручка и фуд-кост в Poster.</li>
<li><b>Не даёт руководителю заполнять чужие листы</b> — только проверять.</li>
</ul>

<h2>9. Кого пускает сейчас</h2>
<p>Директор, управляющий, старший смены. Остальные видят «Скоро подключим».
Добавление позиции — одна настройка на сервере, без выката кода.</p>

<h2>10. Что требует твоего решения</h2>
""" + tbl(['Вопрос', 'Как сейчас'],
          [['Бланки у линейных позиций',
            'У каждой позиции доступен один бланк. Списание, претензия '
            'поставщику, план заготовок закреплены за руководителем — '
            'решить, кому открыть'],
           ['«Инвентаризация: проведение»',
            'Осталась чек-листом у руководителя, хотя приложение '
            'инвентаризацию не ведёт. Убрать или переименовать в «контроль»'],
           ['Санитарный чек-лист',
            'Без дедлайна, поэтому лежит в «по необходимости». '
            'Если он регулярный — назначить периодичность'],
           ['Тренинг открывает бланк',
            'Сейчас две связи: списание и приём поставки. '
            'Решить, какие ещё бланки закрывать до обучения']],
          ['30%', None])
    return b


def main():
    s = session()
    folder = folder_by_name(s, '00 Управление системой документов', ROOT)
    html = f'<html><head><meta charset="utf-8">{STYLE}</head><body>{build()}</body></html>'
    name = 'СТРУКТУРА ДОСТУПОВ И ДОКУМЕНТОВ'
    fid, act = put_doc(s, name, folder, html)
    enforce_font(s, fid)
    print(f'{name} — {act}')
    print(f'https://docs.google.com/document/d/{fid}')


if __name__ == '__main__':
    main()
