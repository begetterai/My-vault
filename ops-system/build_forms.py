#!/usr/bin/env python3
"""Добавляет явку, журналы и бланки в файл форм. Идемпотентно."""
import json, collections, pathlib

FILE = pathlib.Path(__file__).parent / 'checklists.romashka.json'

WHERE = ['Зал', 'Кухня', 'Склад', 'Касса', 'Санузел', 'Улица и вход']
SEVERITY = ['Мелочь', 'Заметное', 'Серьёзное', 'Критично']


def f(key, label, kind='text', **kw):
    d = {'key': key, 'label': label, 'kind': kind}
    d.update(kw)
    return d


NEW = collections.OrderedDict()

# ── явка ─────────────────────────────────────────────────────────────────────
NEW['shift'] = {
    'title': 'Смена', 'code': '02-LOG-02', 'type': 'shift', 'icon': '⏱',
    'geo': True, 'tab': 'Явка',
}

# ── журналы ──────────────────────────────────────────────────────────────────
NEW['incident'] = {
    'title': 'Происшествие', 'code': '03-LOG-01', 'type': 'journal', 'icon': '🚨',
    'roles': [],
    'fields': [
        f('what', 'Что случилось', required=True, min_words=3,
          hint='Одной фразой: что именно произошло'),
        f('where', 'Где', 'choice', options=WHERE, required=True),
        f('details', 'Подробности', 'long',
          hint='Кто участвовал, во сколько, при каких обстоятельствах'),
        f('action', 'Что сделали прямо сейчас', required=True, min_words=3),
        f('severity', 'Насколько серьёзно', 'choice', options=SEVERITY, required=True),
    ],
    'photo': True,
}

NEW['breakdown'] = {
    'title': 'Поломка оборудования', 'code': '09-LOG-01', 'type': 'journal', 'icon': '🔧',
    'roles': [],
    'fields': [
        f('what', 'Что сломалось', required=True,
          hint='Название и место: «Холодильник на кухне, левый»'),
        f('where', 'Где', 'choice', options=WHERE, required=True),
        f('details', 'Как проявляется', 'long', required=True, min_words=3,
          hint='Не работает совсем, шумит, не держит температуру'),
        f('action', 'Можно ли работать дальше', 'choice', required=True,
          options=['Да, работаем', 'Работаем с ограничением', 'Нет, остановились']),
        f('severity', 'Насколько срочно', 'choice', options=SEVERITY, required=True),
    ],
    'photo': True,
}

NEW['violation'] = {
    'title': 'Нарушение', 'code': '07-LOG-01', 'type': 'journal', 'icon': '⚖️',
    'roles': ['manager', 'coo'],
    'fields': [
        f('what', 'Что нарушено', required=True, min_words=2,
          hint='Со ссылкой на правило: «Телефон на рабочем месте»'),
        f('details', 'Кто и при каких обстоятельствах', 'long', required=True, min_words=3),
        f('where', 'Где', 'choice', options=WHERE),
        f('action', 'Какая мера применена', 'choice', required=True,
          options=['Устное замечание', 'Письменное замечание',
                   'Разбор на планёрке', 'По дисциплинарной сетке']),
        f('severity', 'Тяжесть', 'choice', options=SEVERITY, required=True),
    ],
    'photo': True,
}

NEW['guest'] = {
    'title': 'Жалоба гостя', 'code': '07-LOG-02', 'type': 'journal', 'icon': '🗣',
    'roles': [],
    'fields': [
        f('what', 'Суть жалобы', required=True, min_words=3),
        f('where', 'Где', 'choice', options=WHERE),
        f('details', 'Что заказывал гость, во сколько', 'long'),
        f('action', 'Как решили на месте', required=True, min_words=3,
          hint='Заменили блюдо, вернули деньги, извинились'),
        f('severity', 'Гость ушёл', 'choice', required=True,
          options=['Довольным', 'Нейтрально', 'Недовольным', 'Скандал']),
    ],
    'photo': False,
}

# ── бланки ───────────────────────────────────────────────────────────────────
UNITS = ['кг', 'г', 'л', 'мл', 'шт', 'упак']

NEW['writeoff'] = {
    'title': 'Списание', 'code': '05-FRM-01', 'type': 'form', 'icon': '🗑',
    'roles': [],
    'photo_required': True,
    'columns': [
        f('item', 'Позиция', required=True),
        f('qty', 'Кол-во', 'number', required=True, min=0, max=100000),
        f('unit', 'Ед.', 'choice', options=UNITS, required=True),
        f('reason', 'Причина', 'choice', required=True,
          options=['Просрочка', 'Брак поставщика', 'Бой', 'Порча при хранении',
                   'Ошибка приготовления', 'Не продалось']),
        f('note', 'Комментарий'),
    ],
}

NEW['delivery'] = {
    'title': 'Приём поставки', 'code': '05-FRM-03', 'type': 'form', 'icon': '📦',
    'roles': ['manager', 'coo'],
    'photo_required': True,
    'columns': [
        f('item', 'Позиция', required=True),
        f('qty', 'Принято', 'number', required=True, min=0, max=100000),
        f('unit', 'Ед.', 'choice', options=UNITS, required=True),
        f('reason', 'Состояние', 'choice', required=True,
          options=['Принято полностью', 'Недовоз', 'Пересорт',
                   'Брак — вернули', 'Просрочка — вернули']),
        f('note', 'Поставщик и комментарий'),
    ],
}

NEW['inventory'] = {
    'title': 'Инвентаризация — сдача листа', 'code': '05-FRM-02',
    'type': 'form', 'icon': '📊',
    'roles': ['manager', 'coo'],
    'photo_required': True,
    'note': 'Пересчёт ведётся на БУМАЖНОМ листе — так требует регламент. '
            'Здесь фиксируются только итоги и фото листа.',
    'columns': [
        f('item', 'Позиция с расхождением', required=True),
        f('qty', 'Расхождение', 'number', required=True, min=-100000, max=100000),
        f('unit', 'Ед.', 'choice', options=UNITS, required=True),
        f('reason', 'Причина', 'choice', required=True,
          options=['Недостача', 'Излишек', 'Ошибка учёта',
                   'Не списали ранее', 'Причина не установлена']),
        f('note', 'Комментарий'),
    ],
}


def main():
    data = json.load(open(FILE, encoding='utf-8'),
                     object_pairs_hook=collections.OrderedDict)
    for key, cl in data.items():
        cl.setdefault('type', 'checklist')
    for key, cl in NEW.items():
        data[key] = cl
    json.dump(data, open(FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    for key, cl in data.items():
        t = cl.get('type', 'checklist')
        extra = {'checklist': lambda c: f'{sum(len(b["items"]) for b in c["blocks"])} пунктов',
                 'journal': lambda c: f'{len(c.get("fields", []))} полей',
                 'form': lambda c: f'{len(c.get("columns", []))} колонок',
                 'shift': lambda c: 'приход и уход'}[t](cl)
        print(f'{cl["code"]:11} {t:9} {cl["title"]:34} {extra:14} '
              f'роли: {",".join(cl.get("roles") or ["все"])}')


if __name__ == '__main__':
    main()
