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
 'К-СС': ('shift_ssk',   'кухня', ['senior'],            'Старший смены на кухне'),
 'Ц-М':  ('shift_ceh_m', 'цех',   None,                  'Сотрудник цеха, мясо и соусы'),
 'Ц-Л':  ('shift_ceh_l', 'цех',   None,                  'Сотрудник цеха, лаваши'),
 'Ц-Х':  ('shift_ceh_h', 'цех',   None,                  'Сотрудник цеха, выпечка'),
 'Б':    ('shift_bar',   'бар',   None,                  'Бариста смены'),
 'КС':   ('shift_kassa', 'касса', None,                  'Кассир смены'),
 'З':    ('shift_zal',   'зал',   None,                  'Уборщица-заготовщик'),
 'У':    ('shift_upr',   '',      ['manager', 'coo'],    'Управляющий точки'),
}

# Этап дня → (ключ, как называется, кто его отмечает, каким сменам виден).
# Смены две: открывающая ставит точку на ноги и передаёт, закрывающая
# принимает и закрывает. Работает один человек весь день — передавать
# некому, у него только открытие и закрытие.
STAGES = [
 ('open',  'Открытие',  'О', 'утренний сотрудник', ['open', 'one']),
 ('give',  'Передача',  'П', 'уходящий, пересменка', ['open']),
 ('take',  'Приём',     'Т', 'заступающий, пересменка', ['close']),
 ('close', 'Закрытие',  'З', 'вечерний сотрудник', ['close', 'one']),
]

# Сроки этапов. Заданы Азизом 24.08.2026. Закрытие разное по точкам:
# ЗБ гасит свет в 00:30, ОВИР работает до 03:30 — вторая смена там
# дорабатывает до конца.
DEADLINE = {'open': '09:30', 'give': '17:30', 'take': '17:30',
            'close': '00:30'}
BY_POINT = {'close': {'ОВИР': '03:30'}}

# У управляющего свой день, короче дня точки: он приходит после открытия
# и уходит до закрытия. ЗБ — 10:00–21:00, ОВИР — 12:00–21:00. Сроки его
# листов считаются от этого, иначе оба просрочены каждый день.
DEADLINE_UPR = {'open': '10:30', 'close': '21:00'}
BY_POINT_UPR = {'open': {'ОВИР': '12:30'}}


def clean(t):
    """Из документа приходит HTML — в приложении он не нужен."""
    return re.sub(r'<[^>]+>', '', t).replace('  ', ' ').strip()


def groups_for(code, stage):
    """Содержимое этапа — те же блоки, что в документе листа смены.

    Рутина («чистоту поддерживал всю смену») висит на конце своей смены:
    у открывающей это передача, у закрывающей — закрытие. Сдача помещения
    приклеена к закрытию: три пункта отдельным листом никому не нужны.
    """
    if stage == 'open':
        return ([M.OPEN.PERSONAL] + M.collect(M.OPEN, code)
                + [M.equip_block(code, 'на открытии')])
    if stage == 'give':
        return [M.GIVE, M.equip_block(code, 'при передаче'), M.ROUTINE]
    if stage == 'take':
        return [M.TAKE, M.equip_block(code, 'при приёме'), M.VERDICT]
    if code == 'У':
        # Управляющий уходит в 21:00: свет, вентиляция и кондиционеры в это
        # время ещё работают, а помещение сдаёт тот, кто гасит его в 00:30.
        return M.collect(M.CLOSE, code) + [M.ROUTINE]
    return (M.collect(M.CLOSE, code) + [M.equip_block(code, 'на закрытии')]
            + [M.ROOM, M.ROUTINE])


def build(code, zone, who):
    """Четыре листа станции — по одному на этап дня."""
    key, dept, roles, title_who = PLACES[code]
    out = []
    for stage, name, letter, when, parts in STAGES:
        # Управляющий на точке один и работает весь день: передавать смену
        # ему некому, приём от кого-то — тоже. Остаются открытие и закрытие.
        if key == 'shift_upr' and stage in ('give', 'take'):
            continue
        blocks = []
        for gname, rows in groups_for(code, stage):
            items = [{'text': clean(text), 'norm': norm, 'photo': photo == 'фото'}
                     for text, norm, photo in rows]
            if items:
                blocks.append({'name': gname, 'items': items})
        if not blocks:
            continue
        dead = (DEADLINE_UPR.get(stage) if key == 'shift_upr' else None) \
            or DEADLINE[stage]
        form = {'title': f'{zone} · {name}', 'code': f'03-CL-01/{code}-{letter}',
                'type': 'checklist', 'ask_time': 'Во сколько закрыли этап?',
                'stage': stage, 'part': parts, 'when': when,
                'deadline': dead, 'blocks': blocks}
        by = (BY_POINT_UPR if key == 'shift_upr' else BY_POINT).get(stage)
        if by:
            form['deadline_point'] = dict(by)
        if key not in ('shift_ssk', 'shift_upr'):
            form['station'] = key
        if dept:
            form['dept'] = dept
        if roles:
            form['roles'] = roles
        out.append((f'{key}_{stage}', form))
    return out


def main():
    data = json.load(open(JSON, encoding='utf-8'))
    for k in [k for k, v in data.items()
              if k.startswith('shift_') and 'stage' not in v]:
        del data[k]                      # лист из шести этапов заменён на четыре
    added = 0
    for suffix, zone, who, _ in M.OPEN.POSITIONS:
        for key, form in build(suffix, zone, who):
            data[key] = form
            added += 1
            n = sum(len(b['items']) for b in form['blocks'])
            print(f'{key:<20} {form["title"]:<34} пунктов: {n}')
    json.dump(data, open(JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\nформ в файле: {len(data)} (листов смены: {added})')


if __name__ == '__main__':
    main()
