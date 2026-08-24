#!/usr/bin/env python3
"""Привязка станций и чек-листов — лист для правок Азиза.

Собирается из живого checklists.romashka.json. Последняя колонка «Правка»
пустая: Азиз пишет в ней, что поменять, я применяю в JSON.
"""
import sys, json, datetime
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session, put_doc, folder_by_name, enforce_font

ROOT = '1cSLEkOXikhTv0g6lPxZ31xJca1Yu-q43'
JSON = '/home/user/My-vault/ops-system/checklists.romashka.json'
TODAY = datetime.date.today().strftime('%d.%m.%Y')
D = json.load(open(JSON, encoding='utf-8'))

ROLE = {'staff': 'сотрудник', 'senior': 'старший смены',
        'manager': 'управляющий', 'coo': 'директор'}
DEPT_POS = {'кухня': 'сотрудник кухни', 'цех': 'сотрудник цеха',
            'бар': 'бариста', 'касса': 'кассир',
            'зал': 'уборщица-заготовщик'}

STYLE = """<style>
@page { size: A4 portrait; margin: 14mm 10mm; }
body { font-family: 'Times New Roman', serif; font-size: 13pt; }
h1 { font-size: 20pt; margin: 0 0 4pt 0; }
h2 { font-size: 15pt; margin: 15pt 0 5pt 0; border-bottom: 1pt solid #000;
     padding-bottom: 3pt; }
p, li, td, th { font-size: 11pt; line-height: 1.25; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0; }
th, td { border: 0.75pt solid #000; padding: 3pt 4pt; text-align: left;
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


def items(cl):
    return sum(len(b['items']) for b in cl.get('blocks', []))


def who(cl):
    """Кто видит лист: роли, иначе позиция отдела, иначе все."""
    if cl.get('roles'):
        return ', '.join(ROLE.get(r, r) for r in cl['roles'])
    dept = cl.get('dept')
    if dept:
        d = dept if isinstance(dept, list) else [dept]
        return ', '.join(DEPT_POS.get(x, x) for x in d)
    return 'все'


ST_KEYS = [k for k in D
           if k.startswith('shift_') and k not in ('shift_upr', 'shift_ssk')]
EVENT = [k for k, cl in D.items()
         if cl.get('type') == 'checklist' and not k.startswith('shift_')]


def build():
    st_rows = []
    for n, k in enumerate(ST_KEYS, 1):
        cl = D[k]
        name = cl['title'].replace('Смена · ', '')
        st_rows.append([f'С{n}', name, cl.get('dept', '—'),
                        cl['title'], cl.get('code', ''),
                        str(items(cl)), who(cl), ''])

    ev_rows = []
    for n, k in enumerate(EVENT, 1):
        cl = D[k]
        ev_rows.append([f'Ч{n}', cl['title'], cl.get('code', ''),
                        cl.get('deadline', 'по событию'),
                        str(items(cl)), who(cl), ''])

    extra = []
    for k in ('shift_ssk', 'shift_upr'):
        cl = D[k]
        extra.append([cl['title'], cl.get('code', ''),
                      cl.get('deadline', '—'), str(items(cl)),
                      who(cl), ''])

    qz = [[cl['title'], cl.get('code', ''),
           ', '.join(cl['dept']) if isinstance(cl.get('dept'), list)
           else (cl.get('dept') or 'всем'),
           str(len(cl.get('questions', []))), '']
          for cl in D.values() if cl.get('type') == 'quiz']

    jf = [[cl['title'], 'журнал' if cl['type'] == 'journal' else 'бланк',
           who(cl), D[cl['requires']]['title'] if cl.get('requires') else '—',
           '']
          for cl in D.values() if cl.get('type') in ('journal', 'form')]

    return f"""
<h1>Привязка станций и чек-листов</h1>
<p class="note">Собрано из приложения {TODAY}. Показывает фактическое
состояние: как в этом документе — так и в приложении. Последняя колонка
<b>«Правка»</b> пустая — пиши в ней, что поменять, я применю.</p>

<h2>1. Станции и их чек-листы — {len(ST_KEYS)}</h2>
<p class="note">Станция и чек-лист — одно и то же: человек выбирает рабочее
место, открывается ровно его лист, чужие не видны.</p>
""" + tbl(['№', 'Станция', 'Отдел', 'Чек-лист', 'Код', 'Пунктов',
           'Кто может встать', 'Правка'],
          st_rows,
          ['4%', '17%', '7%', '19%', '11%', '7%', '17%', None]) + f"""

<h2>2. Листы сверх станций — 2</h2>
<p class="note">Не выбираются как рабочее место: открываются по роли
дополнительно к своему листу.</p>
""" + tbl(['Чек-лист', 'Код', 'Срок', 'Пунктов', 'Кому открыт', 'Правка'],
          extra, ['24%', '12%', '9%', '8%', '22%', None]) + f"""

<h2>3. Событийные чек-листы — {len(EVENT)}</h2>
<p class="note">Станции не имеют. Открываются в блоке «Моя работа»:
со сроком — в «Сегодня», без срока — в «По необходимости».</p>
""" + tbl(['№', 'Чек-лист', 'Код', 'Срок', 'Пунктов', 'Кому открыт', 'Правка'],
          ev_rows, ['4%', '25%', '11%', '10%', '8%', '20%', None]) + f"""

<h2>4. Тренинги — {len(qz)}</h2>
<p class="note">Пока тренинги позиции не сданы, чек-листы и бланки закрыты:
открыто только обучение.</p>
""" + tbl(['Тренинг', 'Код', 'Кому', 'Вопросов', 'Правка'],
          qz, ['32%', '12%', '20%', '10%', None]) + f"""

<h2>5. Журналы и бланки — {len(jf)}</h2>
""" + tbl(['Что', 'Тип', 'Кому открыт', 'Откроется после тренинга', 'Правка'],
          jf, ['26%', '9%', '20%', '23%', None]) + """

<h2>6. Порядок: что за чем открывается</h2>
""" + tbl(['Шаг', 'Действие', 'Пока не сделано'],
          [['1', 'Выбор заведения: ЗБ или ОВИР', 'приход недоступен'],
           ['2', 'Приход: селфи с камеры и геометка',
            'рабочее место недоступно'],
           ['3', 'Выбор станции — живёт до конца дня',
            'чек-листы недоступны'],
           ['4', 'Работа: лист своей станции, журналы, бланки', '—']],
          ['7%', '50%', None]) + """
<p><b>Управляющий и директор</b> шаг 3 пропускают: станцию не выбирают,
у них сразу свои листы и блок «Проверка» с чужими заполнениями.
<b>Новичок</b> до сдачи тренингов видит только обучение.</p>
"""


def main():
    s = session()
    folder = folder_by_name(s, '00 Управление системой документов', ROOT)
    html = ('<html><head><meta charset="utf-8">' + STYLE +
            '</head><body>' + build() + '</body></html>')
    name = 'ПРИВЯЗКА СТАНЦИЙ И ЧЕК-ЛИСТОВ — лист правок'
    fid, act = put_doc(s, name, folder, html)
    enforce_font(s, fid)
    print(f'{name} — {act}')
    print(f'https://docs.google.com/document/d/{fid}')


if __name__ == '__main__':
    main()
