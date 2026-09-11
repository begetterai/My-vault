#!/usr/bin/env python3
"""Перенос чек-листов из JSON работающей системы в базу сайта.

Источник правды остаётся прежним — `ops-system/checklists.romashka.json`,
он собирается генераторами из `scripts/`. Здесь только раскладка по
таблицам: листы в `checklists`, пункты в `checklist_items`.

Запуск проверяет сам себя: число листов и пунктов после переноса
обязано совпасть с исходником. Молча потерянный пункт — это пункт,
который на точке больше никто не проверит.

    python3 site/db/import_checklists.py [--dsn ...]
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'ops-system', 'checklists.romashka.json')


def rows_from(raw):
    """→ (строки листов, строки пунктов). Нумерация — сквозная по листу."""
    forms, items = [], []
    for key, f in raw.items():
        n = 0
        for b in (f.get('blocks') or []):
            for it in (b.get('items') or []):
                n += 1
                items.append({
                    'key': key, 'n': n,
                    'block': b.get('name') or b.get('title') or '',
                    'text': (it.get('text') if isinstance(it, dict) else str(it)) or '',
                    'photo': bool(it.get('photo')) if isinstance(it, dict) else False,
                    'measure': json.dumps(it.get('measure'), ensure_ascii=False)
                               if isinstance(it, dict) and it.get('measure') else None,
                })
        forms.append({
            'key': key,
            'title': f.get('title') or key,
            'type': f.get('type') or 'checklist',
            'stage': f.get('stage'),
            'station': f.get('station'),
            'dept': f.get('dept') if isinstance(f.get('dept'), str) else None,
            'roles': f.get('roles') or [],
            'points': f.get('points') or [],
            'deadline': f.get('deadline') or '',
            'deadline_by': json.dumps(f.get('deadline_point') or {}, ensure_ascii=False),
            'deadline_from': f.get('deadline_from'),
            'deadline_plus': int(f.get('deadline_plus') or 0),
            'remind_before': int(f.get('remind_before') or 45),
            'total': int(f.get('total') or n),
        })
    return forms, items


def sql_value(v):
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        inner = ','.join('"' + str(x).replace('"', '\\"') + '"' for x in v)
        return "'{" + inner + "}'"
    return "'" + str(v).replace("'", "''") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='romashka_test')
    ap.add_argument('--user', default='postgres')
    args = ap.parse_args()

    raw = json.load(open(SRC, encoding='utf-8'))
    forms, items = rows_from(raw)
    print(f'в источнике: листов {len(forms)}, пунктов {len(items)}')

    lines = ['BEGIN;', 'TRUNCATE checklist_items, checklists CASCADE;']
    fcols = ['key', 'title', 'type', 'stage', 'station', 'dept', 'roles',
             'points', 'deadline', 'deadline_by', 'deadline_from',
             'deadline_plus', 'remind_before', 'total']
    for f in forms:
        vals = ', '.join(sql_value(f[c]) for c in fcols)
        lines.append(f'INSERT INTO checklists ({", ".join(fcols)}) VALUES ({vals});')
    icols = ['key', 'n', 'block', 'text', 'photo', 'measure']
    for it in items:
        vals = ', '.join(sql_value(it[c]) for c in icols)
        lines.append(f'INSERT INTO checklist_items ({", ".join(icols)}) '
                     f'VALUES ({vals});')
    lines.append('COMMIT;')

    sql = '\n'.join(lines)
    p = subprocess.run(['su', args.user, '-c',
                        f'psql -q -v ON_ERROR_STOP=1 -d {args.db} -f -'],
                       input=sql, text=True, capture_output=True)
    if p.returncode:
        print('ОШИБКА переноса:\n' + (p.stderr or p.stdout)[:2000])
        return 1

    # Сверка: в базе должно оказаться ровно столько же.
    q = ('select (select count(*) from checklists), '
         '(select count(*) from checklist_items), '
         "(select count(*) from checklist_items where photo)")
    r = subprocess.run(['su', args.user, '-c',
                        f'psql -At -F"|" -d {args.db} -c "{q}"'],
                       text=True, capture_output=True)
    got = (r.stdout or '').strip().split('|')
    if len(got) != 3:
        print('не смог проверить:', r.stderr[:300])
        return 1
    nf, ni, nph = (int(x) for x in got)
    photos = sum(1 for x in items if x['photo'])
    ok = nf == len(forms) and ni == len(items) and nph == photos
    print(f'в базе:      листов {nf}, пунктов {ni}, с фото {nph}')
    print('сверка:', 'сошлось' if ok else 'РАСХОЖДЕНИЕ')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
