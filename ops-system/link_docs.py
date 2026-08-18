#!/usr/bin/env python3
"""Сшивает формы приложения с документами реестра.

Каждый блок чек-листа получает код документа, который им управляет, и
ссылку на этот документ. В приложении под блоком появляется строка
«по регламенту 04-SOP-05» — человек читает норматив, не выходя из обхода.

Привязка идёт по БЛОКУ, а не по каждому пункту: блок и есть та единица,
которой соответствует один регламент. 174 пункта руками не свяжешь,
а 37 блоков — связываются осмысленно.

Скрипт идемпотентный. Ссылки берутся из реестра, поэтому переезд
документа в Drive не ломает связь — достаточно перезапустить.
"""
import json, collections, pathlib, sys

sys.path.insert(0, '/home/user/My-vault/scripts')

FILE = pathlib.Path(__file__).parent / 'checklists.romashka.json'
REG = '1TzB9gjpJvj_ziBwKdVuOhfKezMVsdXzeLxQMJWz-cQk'
B = 'https://sheets.googleapis.com/v4/spreadsheets/'

# форма → блок (по началу названия) → код документа
LINKS = {
    'open': {
        '1. Персонал':            '02-POL-03',   # внешний вид и гигиена
        '2. Помещение и зал':     '04-SOP-05',   # чистота помещений
        '3. Оборудование':        '09-SOP-01',   # ТО и действия при поломке
        '4. Продукты':            '04-POL-01',   # маркировка и сроки
        '5. Касса':               '03-SOP-02',   # работа с кассой и Poster
        '6. Готовность':          '03-POL-01',   # стандарт обслуживания
    },
    'close': {
        '1. Гости и зал':         '03-POL-01',
        '2. Касса':               '03-SOP-03',   # кассовая дисциплина и инкассация
        '3. Продукты':            '04-POL-02',   # товарное соседство и хранение
        '4. Оборудование':        '04-SOP-02',   # чистота теплового оборудования
        '5. Кухня':               '04-SOP-04',   # уборка станции
        '6. Закрытие точки':      '03-SOP-01',   # передача смены
    },
    'sanit': {
        '1. Личная гигиена':      '02-POL-03',
        '2. Руки и перчатки':     '04-POL-04',   # HACCP
        '3. Поверхности':         '04-SOP-04',
        '4. Хранение продуктов':  '04-POL-02',
        '5. Холод':               '04-SOP-03',   # чистота холодильного оборудования
        '6. Помещение и отходы':  '04-SOP-05',
        '7. Документы':           '04-LOG-01',   # температурный журнал
    },
    'visit': {
        '1. Взгляд гостя':        '03-POL-01',
        '2. Персонал в работе':   '02-POL-02',   # правило телефонов
        '3. Продукт':             '04-TTK-*',    # техкарты
        '4. Процессы':            '00-REF-01',   # реестр документов
        '5. Люди и климат':       '02-SOP-06',   # график, табель, замены
        '6. Деньги':              '06-SOP-01',   # протокол проверки транзакций
    },
    'hire': {
        '1. Формальности':        '02-SOP-01',   # найм и оформление
        '2. Готовность':          '02-SOP-06',
        '3. Отношение к работе':  '02-REF-01',   # профили должностей
        '4. Практика':            '02-SOP-03',   # стажировка и наставничество
        '5. Договорённости':      '02-POL-01',   # дисциплинарная сетка
    },
    'launch': {
        '1. Помещение':           '10-REF-01',   # критерии выбора локации
        '2. Оборудование':        '10-REF-02',   # комплектация точки
        '3. Товар и меню':        '05-REF-01',   # реестр поставщиков
        '4. Команда':             '10-SOP-01',   # запуск команды новой точки
        '5. Готовность':          '10-CL-01',
    },
    # журналы и бланки — документ на всю форму
    'incident':  {'*': '03-LOG-01'},
    'breakdown': {'*': '09-SOP-01'},
    'violation': {'*': '02-POL-01'},
    'guest':     {'*': '03-SOP-04'},
    'writeoff':  {'*': '05-SOP-04'},
    'delivery':  {'*': '05-SOP-01'},
    'inventory': {'*': '05-SOP-03'},
}


def registry():
    """код → (название, ссылка, статус)"""
    from ops_docs import session
    v = session().get(B + REG + '/values/A1:S200').json().get('values', [])
    out = {}
    for r in v[1:]:
        r = list(r) + [''] * 20
        code = r[0].strip()
        if code:
            out[code] = (r[1].strip(), r[10].strip(), r[4].strip())
    return out


def main():
    reg = registry()
    data = json.load(open(FILE, encoding='utf-8'),
                     object_pairs_hook=collections.OrderedDict)
    miss, done = [], 0
    for key, cl in data.items():
        links = LINKS.get(key, {})
        whole = links.get('*')
        if whole:
            name, url, st = reg.get(whole, ('', '', 'НЕТ В РЕЕСТРЕ'))
            cl['doc'] = {'code': whole, 'title': name, 'url': url}
            if whole not in reg:
                miss.append((key, '*', whole))
            done += 1
        for b in cl.get('blocks') or []:
            code = next((c for pre, c in links.items()
                         if pre != '*' and b['name'].startswith(pre)), None)
            if not code:
                miss.append((key, b['name'], '—'))
                continue
            name, url, st = reg.get(code, ('', '', 'НЕТ В РЕЕСТРЕ'))
            if code not in reg:
                miss.append((key, b['name'], code))
                continue
            b['doc'] = {'code': code, 'title': name, 'url': url}
            done += 1
    json.dump(data, open(FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print(f'связано: {done}')
    for key, blk, code in miss:
        print(f'  НЕ СВЯЗАН  {key:10} {blk[:34]:34} {code}')
    # что осталось без ссылки на файл
    nourl = sorted({b['doc']['code'] for cl in data.values()
                    for b in (cl.get('blocks') or []) if b.get('doc') and not b['doc']['url']}
                   | {cl['doc']['code'] for cl in data.values()
                      if cl.get('doc') and not cl['doc']['url']})
    if nourl:
        print('\nдокумент есть в реестре, но файла ещё нет:')
        for c in nourl:
            print(f'  {c:11} {reg.get(c, ("?",))[0][:52]}')


if __name__ == '__main__':
    main()
