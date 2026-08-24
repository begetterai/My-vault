#!/usr/bin/env python3
"""Формы приложения из тех же данных, что и документы листов смены.

Источник один: doc_03_CL_shift. Правится в скрипте — меняется и документ
на Drive, и форма в приложении. Иначе они разъедутся, и никто не заметит.

Ключи форм: shift_<место>. Старые формы не трогаются — их отключает Азиз
после проверки.
"""
import sys, json, re
sys.path.insert(0, '/home/user/My-vault/scripts')
import doc_03_CL_shift as M

JSON = '/home/user/My-vault/ops-system/checklists.romashka.json'

# место → (ключ формы, отдел в системе, роли, кто заполняет)
PLACES = {
 'К-С1': ('shift_sal1',  'кухня', None,                  'Сотрудник кухни, саладетта 1'),
 'К-С2': ('shift_sal2',  'кухня', None,                  'Сотрудник кухни, саладетта 2'),
 'К-Р':  ('shift_razd',  'кухня', None,                  'Сотрудник кухни, раздача'),
 'К-Ф':  ('shift_frit',  'кухня', None,                  'Сотрудник кухни, фритюр'),
 'К-СС': ('shift_ssk',   'кухня', ['senior', 'manager', 'coo'], 'Старший смены на кухне'),
 'Ц-М':  ('shift_ceh_m', 'цех',   None,                  'Сотрудник цеха, мясо и соусы'),
 'Ц-Л':  ('shift_ceh_l', 'цех',   None,                  'Сотрудник цеха, лаваши'),
 'Ц-Х':  ('shift_ceh_h', 'цех',   None,                  'Сотрудник цеха, выпечка'),
 'Б':    ('shift_bar',   'бар',   None,                  'Бариста смены'),
 'КС':   ('shift_kassa', 'касса', None,                  'Кассир смены'),
 'З':    ('shift_zal',   'зал',   None,                  'Уборщица-заготовщик'),
 'У':    ('shift_upr',   '',      ['manager', 'coo'],    'Управляющий точки'),
}

STAGES = [
 ('Этап 1. Открытие смены', 'open'),
 ('Этап 2. Рутина', 'routine'),
 ('Этап 3. Передача смены', 'give'),
 ('Этап 4. Приём смены', 'take'),
 ('Этап 5. Закрытие смены', 'close'),
 ('Этап 6. Сдача помещения', 'room'),
]


def clean(t):
    """Из документа приходит HTML — в приложении он не нужен."""
    return re.sub(r'<[^>]+>', '', t).replace('  ', ' ').strip()


def stages_for(code):
    """Те же шесть этапов, что в документе.

    Третий элемент — чья это часть дня. Открывающая смена отмечает открытие
    и передачу, закрывающая — приём и закрытие. Работает один человек весь
    день — отмечает открытие и закрытие, передавать некому.
    """
    o = M.collect(M.OPEN, code)
    c = M.collect(M.CLOSE, code)
    return [
        ('Этап 1. Открытие смены',
         [M.OPEN.PERSONAL] + o + [M.equip_block(code, 'на открытии')], 'open'),
        ('Этап 2. Рутина', [M.ROUTINE], 'all'),
        ('Этап 3. Передача смены',
         [M.GIVE, M.equip_block(code, 'при передаче')], 'handover'),
        ('Этап 4. Приём смены',
         [M.TAKE, M.equip_block(code, 'при приёме'), M.VERDICT], 'takeover'),
        ('Этап 5. Закрытие смены',
         c + [M.equip_block(code, 'на закрытии')], 'close'),
        ('Этап 6. Сдача помещения', [M.ROOM], 'close'),
    ]


def build(code, zone, who):
    key, dept, roles, title_who = PLACES[code]
    blocks = []
    for stage, groups, part in stages_for(code):
        items = []
        for name, rows in groups:
            for text, norm, photo in rows:
                items.append({'text': clean(text), 'norm': norm,
                              'photo': photo == 'фото'})
        if items:
            blocks.append({'name': stage, 'part': part, 'items': items})
    form = {'title': f'Смена · {zone}', 'code': f'03-CL-01/{code}',
            'type': 'checklist', 'ask_time': 'Во сколько закрыли этап?',
            'deadline': '10:00', 'blocks': blocks}
    if dept:
        form['dept'] = dept
    if roles:
        form['roles'] = roles
    return key, form


def main():
    data = json.load(open(JSON, encoding='utf-8'))
    added = 0
    for suffix, zone, who, _ in M.OPEN.POSITIONS:
        key, form = build(suffix, zone, who)
        data[key] = form
        added += 1
        n = sum(len(b['items']) for b in form['blocks'])
        print(f'{key:<14} {form["title"]:<34} блоков: {len(form["blocks"])}, пунктов: {n}')
    json.dump(data, open(JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\nформ в файле: {len(data)} (добавлено или обновлено: {added})')


if __name__ == '__main__':
    main()
