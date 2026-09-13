#!/usr/bin/env python3
"""Язык сообщений бота: каждому человеку — на его языке.

Почему перевод здесь, а не в текстах: сообщения склеиваются из кусков
с данными («До дедлайна 15 мин (до 10:00)»), и перевести их по точному
совпадению нельзя. Зато можно перевести на выходе — в момент отправки,
когда известно, кому пишем. Тогда ни один русский текст в коде не меняется,
а значит не меняются и ключи таблиц: отделы, события, названия колонок
остаются русскими, как и было.

Словарь тот же, что у приложения, — `web/tj.json`. Заголовки чек-листов
и названия документов уже в нём, поэтому «⏰ Санитарный чек-лист · ЗБ»
переводится без единой новой строки.

Фразы заменяем подстрокой, длинные первыми: короткий кусок иначе съел бы
начало длинного. Одиночные слова — только целиком, по границам слова:
иначе «бар» залез бы в середину «барака». Отсюда и нижняя граница длины —
короткое слово слишком легко совпадает случайно.
"""
import json, os, re

from . import storage as S

DICT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'web', 'tj.json')
MIN_PHRASE = 8
MIN_WORD = 4

_D = {'phrases': None, 'words': None}


def _load():
    if _D['phrases'] is not None:
        return
    try:
        with open(DICT, encoding='utf-8') as f:
            d = json.load(f)
    except Exception as e:
        print('словарь языка:', e)
        d = {}
    ok = [(k, v) for k, v in d.items() if v and v != k]
    _D['phrases'] = sorted(((k, v) for k, v in ok
                            if ' ' in k and len(k) >= MIN_PHRASE),
                           key=lambda kv: -len(kv[0]))
    _D['words'] = [(re.compile(r'\b' + re.escape(k) + r'\b'), v)
                   for k, v in sorted((kv for kv in ok
                                       if ' ' not in kv[0]
                                       and len(kv[0]) >= MIN_WORD),
                                      key=lambda kv: -len(kv[0]))]


def phrases():
    """[(русская фраза, перевод)] — длинные первыми. Читается один раз."""
    _load()
    return _D['phrases']


def words():
    """[(шаблон слова, перевод)] — отдельные слова вроде «кухня», «зал»."""
    _load()
    return _D['words']


def of(chat_id):
    """Язык человека из «Команды». Не нашли — русский."""
    try:
        v = S.team().get(str(chat_id))
        return v[6] if v and len(v) > 6 and v[6] in S.LANGS else 'ru'
    except Exception as e:
        print('язык человека:', e)
        return 'ru'


def t(text, lang):
    """Перевести готовое сообщение. Незнакомое остаётся по-русски."""
    if lang != 'tj' or not text:
        return text
    for ru, tj in phrases():
        if ru in text:
            text = text.replace(ru, tj)
    for pat, tj in words():
        text = pat.sub(tj, text)
    return text
