#!/usr/bin/env python3
"""Собрать строки интерфейса, которые видит человек, и свести их со словарём.

Русский текст — ключ словаря `web/tj.json`. Скрипт не переводит: он находит
все строки и показывает, каких в словаре ещё нет. Так видно покрытие
и не теряются строки, появившиеся после очередной правки страницы.

Запуск: python3 ops-system/build_lang.py [--json файл]
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, 'web', 'index.html')
DICT = os.path.join(HERE, 'web', 'tj.json')
CHECKS = os.path.join(HERE, 'checklists.romashka.json')
EQUIP = os.path.join(HERE, 'equipment.romashka.json')
RU = re.compile('[А-Яа-яЁё]')


def page_parts():
    s = open(PAGE, encoding='utf-8').read()
    code = re.findall(r'<script[^>]*>(.*?)</script>', s, re.S)[-1]
    markup = re.sub(r'<script[^>]*>.*?</script>', '', s, flags=re.S)
    markup = re.sub(r'<style[^>]*>.*?</style>', '', markup, flags=re.S)
    return code, markup


def from_markup(markup):
    """Текст подписей и переводимые атрибуты разметки."""
    out = []
    for a in ('placeholder', 'aria-label', 'title'):
        out += re.findall(a + r'="([^"]+)"', markup)
    markup = re.sub(r'<!--.*?-->', '', markup, flags=re.S)
    for chunk in re.split(r'<[^>]+>', markup):
        chunk = ' '.join(chunk.split())
        if chunk and RU.search(chunk):
            out.append(chunk)
    return out


def from_code(code):
    """Строковые литералы скрипта — без комментариев: их никто не видит."""
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.S)
    code = re.sub(r'(?m)^\s*//.*$', '', code)
    code = re.sub(r'(?m)([^:\'"/])//[^\'"\n]*$', r'\1', code)
    # Длинную подсказку в коде разбивают на несколько литералов через «+».
    # На экране это один текст, и ключом словаря должен быть он целиком,
    # а не куски: по куску перевод не найдётся никогда.
    # Кавычки разбираем по одной: внутри одинарной строки спокойно живут
    # двойные — это атрибуты вёрстки, и обрывать на них склейку нельзя.
    glues = [re.compile(r"'((?:[^'\\\n]|\\.)*)'\s*\+\s*'((?:[^'\\\n]|\\.)*)'"),
             re.compile(r'"((?:[^"\\\n]|\\.)*)"\s*\+\s*"((?:[^"\\\n]|\\.)*)"')]
    for glue, q in zip(glues, "'\""):
        while True:
            new = glue.sub(lambda m: q + m.group(1) + m.group(2) + q, code)
            if new == code:
                break
            code = new
    out = []
    for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"",
                         code):
        s = m.group(1) if m.group(1) is not None else m.group(2)
        if s and RU.search(s):
            out.append(s)
    return out


def from_tags(text):
    """Куски вёрстки внутри литералов: переводится только текст между тегами."""
    out = []
    for chunk in re.split(r'<[^>]+>', text):
        chunk = chunk.strip()
        if chunk and RU.search(chunk):
            out.append(chunk)
    return out


def from_content():
    """Пункты чек-листов, нормативы, вопросы тренингов, оборудование."""
    out = []

    def walk(v, key=''):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, str):
            # Коды, отделы и служебные поля не переводим: по ним система
            # ищет и сверяет, перевод их просто сломает.
            if key in ('text', 'norm', 'name', 'title', 'q', 'why', 'h', 'p',
                       'label', 'hint', 'options', 'ask_time') \
                    and RU.search(v):
                out.append(v.strip())

    for f in (CHECKS, EQUIP):
        if os.path.exists(f):
            walk(json.load(open(f, encoding='utf-8')))
    return out


def collect():
    code, markup = page_parts()
    ui = from_markup(markup)
    for s in from_code(code):
        ui += from_tags(s) if '<' in s and '>' in s else [s]
    seen, out = set(), []
    for s in ui + from_content():
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def main():
    have = json.load(open(DICT, encoding='utf-8')) if os.path.exists(DICT) else {}
    keys = collect()
    miss = [k for k in keys if k not in have]
    extra = [k for k in have if k not in keys]
    print(f'строк интерфейса и содержимого: {len(keys)}')
    print(f'переведено: {len(keys) - len(miss)} · осталось: {len(miss)}')
    if extra:
        print(f'в словаре есть лишнее (строки уже нет в коде): {len(extra)}')
    if '--json' in sys.argv:
        path = sys.argv[sys.argv.index('--json') + 1]
        json.dump(miss, open(path, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('непереведённое выгружено:', path)


if __name__ == '__main__':
    main()
