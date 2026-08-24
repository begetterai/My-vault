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


STAGE_RU = {'open': 'Открытие', 'give': 'Передача',
            'take': 'Приём', 'close': 'Закрытие'}
PART_RU = {'open': 'открывающая', 'close': 'закрывающая', 'one': 'один на день'}
ORDER = ('open', 'give', 'take', 'close')

STATIONS = []
for k, cl in D.items():
    st = cl.get('station')
    if st and st not in [x[0] for x in STATIONS]:
        STATIONS.append((st, cl['title'].split(' · ')[0], cl.get('dept', '—')))

EVENT = [k for k, cl in D.items()
         if cl.get('type') == 'checklist' and not cl.get('stage')]


def stage_lists(group):
    """Четыре листа одной группы — станции, старшего смены, управляющего."""
    out = []
    for st in ORDER:
        k = f'{group}_{st}'
        if k in D:
            out.append((st, D[k]))
    return out


def deadline(cl):
    d = cl.get('deadline', '—')
    by = cl.get('deadline_point') or {}
    if by:
        d += ' · ОВИР ' + ', '.join(by.values())
    return d


def build():
    st_rows = []
    for n, (key, name, dept) in enumerate(STATIONS, 1):
        for i, (st, cl) in enumerate(stage_lists(key)):
            st_rows.append([f'С{n}' if i == 0 else '',
                            name if i == 0 else '',
                            dept if i == 0 else '',
                            STAGE_RU[st], cl.get('code', ''),
                            deadline(cl),
                            ', '.join(PART_RU[x] for x in cl.get('part', [])),
                            str(items(cl)), ''])

    ev_rows = []
    for n, k in enumerate(EVENT, 1):
        cl = D[k]
        ev_rows.append([f'Ч{n}', cl['title'], cl.get('code', ''),
                        cl.get('deadline', 'по событию'),
                        str(items(cl)), who(cl), ''])

    extra = []
    for group, label in (('shift_ssk', 'Старший смены'),
                         ('shift_upr', 'Управляющий')):
        for i, (st, cl) in enumerate(stage_lists(group)):
            extra.append([label if i == 0 else '', STAGE_RU[st],
                          cl.get('code', ''), deadline(cl),
                          ', '.join(PART_RU[x] for x in cl.get('part', [])),
                          str(items(cl)), who(cl), ''])

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

<h2>1. Порядок: что за чем открывается</h2>
""" + tbl(['Шаг', 'Действие', 'Пока не сделано'],
          [['1', 'Заведение: ЗБ или ОВИР', 'смена дня недоступна'],
           ['2', '<b>Смена дня:</b> открывающая · закрывающая · '
            'один на весь день', 'приход недоступен'],
           ['3', 'Приход: селфи с камеры и геометка',
            'рабочее место недоступно'],
           ['4', 'Рабочее место — одно из десяти', 'чек-листы недоступны'],
           ['5', 'Работа: листы этапов своей смены', '—']],
          ['6%', '52%', None]) + """
<p><b>Смена решает, какие этапы дня твои.</b> Открывающая ставит точку
на ноги и передаёт; закрывающая принимает и закрывает; один на весь день
делает открытие и закрытие — передавать некому.</p>
<p><b>Этап не открыть раньше срока:</b> приём смены закрыт, пока предыдущая
смена не сдала передачу — принимать нечего. Управляющий и директор
рабочее место не выбирают, но смену дня выбирают: у них свои четыре листа.</p>

<h2>2. Десять рабочих мест — по четыре листа на каждое</h2>
<p class="note">В выборе места человеку показываются только станции своего
отдела: кухне — четыре, цеху — три, бару, кассе и залу — по одной.
Чужое место выбрать нельзя, его листы всё равно не открыты.</p>
""" + tbl(['№', 'Рабочее место', 'Отдел', 'Этап', 'Код', 'Срок',
           'Чья смена', 'Пунктов', 'Правка'],
          st_rows,
          ['3%', '15%', '6%', '9%', '11%', '13%', '15%', '7%', None]) + """

<h2>3. Листы сверх станций</h2>
<p class="note">Рабочим местом не выбираются: открываются по роли
дополнительно к своему листу.</p>
""" + tbl(['Кто', 'Этап', 'Код', 'Срок', 'Чья смена', 'Пунктов',
           'Кому открыт', 'Правка'],
          extra, ['12%', '9%', '12%', '13%', '15%', '7%', '16%', None]) + f"""

<h2>4. Событийные чек-листы — {len(EVENT)}</h2>
<p class="note">Этапов и смен не имеют. Открываются в «Моя работа»:
со сроком — в «Сегодня», без срока — в «По необходимости».</p>
""" + tbl(['№', 'Чек-лист', 'Код', 'Срок', 'Пунктов', 'Кому открыт', 'Правка'],
          ev_rows, ['4%', '25%', '11%', '10%', '8%', '20%', None]) + f"""

<h2>5. Тренинги — {len(qz)}</h2>
<p class="note">Пока тренинги позиции не сданы, чек-листы и бланки закрыты:
открыто только обучение.</p>
""" + tbl(['Тренинг', 'Код', 'Кому', 'Вопросов', 'Правка'],
          qz, ['32%', '12%', '20%', '10%', None]) + f"""

<h2>6. Журналы и бланки — {len(jf)}</h2>
""" + tbl(['Что', 'Тип', 'Кому открыт', 'Откроется после тренинга', 'Правка'],
          jf, ['26%', '9%', '20%', '23%', None]) + """

<h2>7. Передача смены — поимённо</h2>
<p class="note">Сдал не «вообще», а названному человеку. Иначе на пересменке
спросить некого.</p>
""" + tbl(['Шаг', 'Что происходит'],
          [['1', 'Уходящий заполняет «Передача» и <b>обязан выбрать</b>, '
            'кому сдаёт. Без этого лист не отправляется'],
           ['2', 'Названному приходит сообщение в телеграм: смена ждёт приёмки'],
           ['3', '«Приём» открывается <b>только ему</b>. У остальных на этом '
            'месте лист закрыт с подписью, кто принимает'],
           ['4', 'Он проходит «Приём» — там блок «Итог приёмки»: принято '
            'полностью · с замечаниями · не принято'],
           ['5', 'Сдавшему возвращается ответ: принята или принята '
            'с замечаниями, с текстом'],
           ['—', 'Назвали человека, которого нет на точке — предупреждение '
            'уходит директору, а не теряется']],
          ['6%', None]) + """
<p>В таблице появилась колонка <b>«Кому сдал»</b> — по ней видна вся цепочка
пересменок за день.</p>

<h2>8. Когда день считается закрытым</h2>
<p>Балл «день закрыт» начисляется, когда на точке закрыто <b>каждое начатое
рабочее место</b>: по каждому месту, где сегодня сдали хоть один этап, сдан
и «Закрытие». Плюс сданы событийные листы со сроком — санитарный. Считаем
по начатым, а не по всем десяти: работают не все места каждый день,
и требовать закрытия пустой саладетты бессмысленно.</p>

<h2>9. Сроки этапов</h2>
<p class="note">Заданы Азизом 24.08.2026.</p>
""" + tbl(['Этап', 'Срок', 'Кто отмечает'],
          [['Открытие — рядовой сотрудник', '09:30', 'открывающая смена'],
           ['Открытие — управляющий', '09:50', 'открывающая смена'],
           ['Передача смены', '17:30', 'уходящий'],
           ['Приём смены', '17:30', 'заступающий'],
           ['Закрытие — ЗБ', '00:30', 'закрывающая смена'],
           ['Закрытие — ОВИР', '03:30',
            'закрывающая смена, дорабатывает до конца']],
          ['42%', '16%', None]) + """
<p>Сутки в системе операционные и кончаются в 05:00: закрытие в 00:30
и в 03:30 попадает в тот день, когда смена началась, а не в следующий.</p>
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
