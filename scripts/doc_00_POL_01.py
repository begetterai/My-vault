#!/usr/bin/env python3
"""00-POL-01 «Правила ведения документов» — перенос из артефакта claude.ai.

Артефакт открывается только из аккаунта Азиза: его нельзя дать управляющему,
подписать или положить в общую папку. Документ о том, как вести документы,
сам нарушал правило от 22.08.2026. Здесь он становится обычным Google Doc
в нашем стандарте.

Текст перенесён как есть, без правок по смыслу. Служебное убрано: заголовок
и строка версии — они и так в шапке.
"""
import sys, re, io, datetime
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import (session, build_html, put_doc, folder_by_name,
                      enforce_font, registry_update)

ROOT = '1cSLEkOXikhTv0g6lPxZ31xJca1Yu-q43'
REG = '1TzB9gjpJvj_ziBwKdVuOhfKezMVsdXzeLxQMJWz-cQk'
SRC = ('/tmp/claude-0/-home-user-My-vault/'
       '606dd1b1-a624-5ef2-a06e-c6a894e680ba/scratchpad/00pol01.html')
TODAY = datetime.date.today().strftime('%d.%m.%Y')
NEXT = datetime.date.today().replace(
    year=datetime.date.today().year + 1).strftime('%d.%m.%Y')

META = {'code': '00-POL-01', 'kind': 'POL',
        'title': 'Правила ведения документов', 'version': 'v1.1',
        'date': TODAY, 'owner': 'COO', 'approved': 'COO', 'review': NEXT,
        'who': 'COO · управляющие точек · все, кто пишет и правит документы'}

CONTROL = {'Кто проверяет': 'COO — при каждом новом документе и на пересмотре',
           'Как проверяется': 'Новый документ сверяется с составом из части 2: '
                              'шапка, контроль, нарушение, лист ознакомления',
           'Где след': 'Реестр 00-REF-01 — код, версия, владелец, ссылка, '
                       'дата пересмотра'}

VIOLATION = [('Документ создан вне реестра — без кода и строки',
              'документ не действует, спрашивать по нему нельзя'),
             ('Действующий документ живёт вне Drive', 'перенести в Drive'),
             ('У документа нет владельца или контроля',
              'документ возвращается автору на доработку'),
             ('Правка внесена без смены версии в реестре', 'разбор на собрании')]


def body():
    src = io.open(SRC, encoding='utf-8').read()
    # Заголовок и строка версии уже стоят в шапке — второй раз не нужны.
    src = src.split('<hr>', 1)[1] if '<hr>' in src else src
    # Всё опускается на уровень: h1 в шапке занят названием документа.
    # Порядок важен — сначала внутренние заголовки, потом части, иначе
    # разделы категорий встанут вровень с «Частью 2».
    for a, b in (('h3', 'h4'), ('h2', 'h3'), ('h1', 'h2')):
        src = src.replace(f'<{a}>', f'<{b}@>').replace(f'</{a}>', f'</{b}@>')
    src = src.replace('@>', '>')
    src = src.replace('<thead>', '').replace('</thead>', '')
    src = src.replace('<tbody>', '').replace('</tbody>', '')
    note = ('<p class="note">Перенесено из черновика в Google Doc '
            f'{TODAY}. Текст без изменений по смыслу: правило 1.5 требует, '
            'чтобы действующий документ лежал там, где его может открыть '
            'и подписать любой сотрудник.</p>')
    return note + src


def main():
    s = session()
    folder = folder_by_name(s, '00 Управление системой документов', ROOT)
    html = build_html(META, body(), CONTROL, VIOLATION, sign_rows=10)
    name = f'{META["code"]} — {META["title"]} (v1.1)'
    fid, act = put_doc(s, name, folder, html)
    enforce_font(s, fid)
    link = f'https://docs.google.com/document/d/{fid}'
    got = registry_update(s, REG, META['code'], status='Готов', version='v1.1',
                          date=TODAY, review=NEXT, link=link)
    print(f'{name} — {act}, в реестре: {"обновлён" if got else "НЕТ СТРОКИ"}')
    print(link)


if __name__ == '__main__':
    main()
