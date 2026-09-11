#!/usr/bin/env python3
"""Проверки слоя хранилища. Без сети, на локальной базе.

Проверяем не «работает ли запрос», а то, из-за чего система ломалась
в жизни: двойной приход, двое на одном месте, тёзки, пустое фото.

    python3 site/tests/test_storage.py
"""
import datetime
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'site'))

DB = os.environ.get('TEST_DB', 'romashka_probe')
os.environ['DATABASE_URL'] = f'postgresql:///{DB}'

ok = fail = 0


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f'  ✓ {name}')
    else:
        fail += 1
        print(f'  ✗ {name}')


def psql(cmd, db='postgres'):
    return subprocess.run(['su', 'postgres', '-c', f'psql -q -d {db} -c "{cmd}"'],
                          capture_output=True, text=True)


def setup():
    subprocess.run(['su', 'postgres', '-c', f'dropdb --if-exists {DB}'],
                   capture_output=True)
    subprocess.run(['su', 'postgres', '-c', f'createdb {DB}'], capture_output=True)
    subprocess.run(['su', 'postgres', '-c',
                    f'psql -q -d {DB} -f {ROOT}/site/db/schema.sql'],
                   capture_output=True)
    # Доступ для того пользователя, под которым идут тесты.
    me = subprocess.run(['whoami'], capture_output=True, text=True).stdout.strip()
    psql(f'CREATE ROLE {me} LOGIN SUPERUSER', 'postgres')
    psql(f'ALTER DATABASE {DB} OWNER TO {me}', 'postgres')


def main():
    setup()
    import app.storage as S

    day = datetime.date(2026, 9, 11)
    S.x("INSERT INTO points (code, label) VALUES ('ЗБ', 'ЗБ · Лохути 11')")
    a = S.x("INSERT INTO people (name, point_code, role, dept) "
            "VALUES ('Иванов', 'ЗБ', 'staff', 'бар') RETURNING id")['id']
    b = S.x("INSERT INTO people (name, point_code, role, dept) "
            "VALUES ('Иванов', 'ЗБ', 'staff', 'кухня') RETURNING id")['id']

    print('\nтёзки')
    check('два человека с одним именем заводятся', a != b)
    check('в составе оба, и они различимы', len(S.team()) == 2)

    print('\nприход')
    check('первая отметка проходит', S.start_day(day, 'ЗБ', a, 'open'))
    check('вторая не пишется', not S.start_day(day, 'ЗБ', a, 'open'))
    check('у тёзки своя явка', S.start_day(day, 'ЗБ', b, 'close'))
    check('явка Иванова №1 на месте', S.shift_row(day, 'ЗБ', a) is not None)

    print('\nрабочее место')
    check('встал на бар', S.take_station(day, 'ЗБ', 'shift_bar', a))
    check('второй на то же место не встал',
          not S.take_station(day, 'ЗБ', 'shift_bar', b))
    check('место числится за первым',
          S.stations_taken(day, 'ЗБ').get('shift_bar') == a)
    check('перешёл на кассу — бар освободился',
          S.take_station(day, 'ЗБ', 'shift_kassa', a)
          and 'shift_bar' not in S.stations_taken(day, 'ЗБ'))
    check('отрезок по бару сохранён с концом',
          any(r['station'] == 'shift_bar' and r['end_at']
              for r in S.segments(day, 'ЗБ', a)))

    print('\nзаполнение листа')
    S.x("INSERT INTO checklists (key, title, type, total) "
        "VALUES ('probe', 'Проба', 'checklist', 3)")
    fid = S.save_fill(day, 'ЗБ', 'probe', a, {1: True, 2: False, 3: True},
                      {2: '4°C'}, 3, comment='проба')
    got = S.filled_today(day, 'ЗБ', ['probe'])
    check('лист виден как сданный', 'probe' in got)
    check('автор записан идентификатором, имя подтянуто',
          got['probe']['person_id'] == a and got['probe']['who'] == 'Иванов')
    check('выполнено посчитано', got['probe']['done'] == 2)

    print('\nфото')
    try:
        S.add_photo(fid, 1, '')
        check('пустой путь не принимается', False)
    except Exception:
        check('пустой путь не принимается', True)
    S.add_photo(fid, 1, '/var/photos/2026-09-11-probe-1.jpg', 'abc')
    check('настоящее фото записалось',
          bool(S.q('SELECT 1 FROM fill_photos WHERE fill_id = %s', fid)))

    print('\nпароли')
    S.set_login(a, 'ivanov', 'Кс7мР2')
    p = S.by_login('ivanov')
    check('вход по логину находит человека', p and p['id'] == a)
    check('верный пароль принимается', S.check_password('Кс7мР2', p['pass_hash']))
    check('неверный отклоняется', not S.check_password('Кс7мР3', p['pass_hash']))

    print('\nадресация листов')
    m = S.x("INSERT INTO people (name, point_code, role) "
            "VALUES ('Владимир', 'ЗБ', 'manager') RETURNING id")['id']
    check('лист управляющего адресован ему',
          S.workers_of('ЗБ', None, ['manager', 'coo']) == [m])
    check('обычный лист руководителю не идёт',
          m not in S.workers_of('ЗБ', 'бар', None))
    check('лист бара идёт бармену', S.workers_of('ЗБ', 'бар', None) == [a])

    print('\nслужебный журнал')
    check('сегодня ещё не делали', not S.marked(day, 'backup'))
    S.mark(day, 'backup')
    check('после отметки — сделано', S.marked(day, 'backup'))
    S.mark(day, 'backup')
    check('повторная отметка не ломает', S.marked(day, 'backup'))

    print(f'\nпройдено {ok}, провалено {fail}')
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
