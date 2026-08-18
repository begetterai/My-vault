#!/usr/bin/env python3
"""Точка входа: поднимает Mini App и телеграм-бота в одном процессе."""
import sys, datetime, threading

from . import config as C
from . import storage as S
from . import bot as BOT
from . import webapp as W
from . import reports as R


def main():
    miss = C.missing()
    if miss:
        print('Не заданы обязательные переменные: ' + ', '.join(miss))
        print('Смотри .env.example')
        sys.exit(1)

    if '--week' in sys.argv:
        txt = R.week()
        if '--send' in sys.argv and C.ADMIN_CHAT:
            BOT.say(C.ADMIN_CHAT, txt)
            print('отправлено')
        else:
            import re
            print(re.sub(r'<[^>]+>', '', txt))
        return

    if '--day' in sys.argv:
        import re
        print(re.sub(r'<[^>]+>', '',
                     R.day_block(C.today() - datetime.timedelta(days=1))))
        return

    try:
        name, title = BOT.whoami()
        print(f'бот: @{name} ({title})')
    except Exception as e:
        print('ОШИБКА: ' + str(e))
        print('Проверь переменную BOT_TOKEN — она пустая, с опечаткой или отозвана.')
        sys.exit(1)

    print(f'{C.COMPANY}: готовлю таблицу…')
    print('листы:', ', '.join(S.ensure_structure()))
    _, port = W.serve_in_background()
    print(f'Mini App на порту {port}; WEBAPP_URL={C.WEBAPP_URL or "не задан"}')
    print('бот запущен')
    BOT.poll()


if __name__ == '__main__':
    main()
