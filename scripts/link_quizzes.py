#!/usr/bin/env python3
"""Связать тренинги с регламентами, которые они объясняют.

Ссылка берётся из реестра документов — не вписывается руками, иначе
разъедется при первом же переносе файла. Чего в реестре нет, о том скрипт
говорит вслух, а не подставляет пустоту молча.
"""
import sys, json, io, urllib.parse
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session

REG = '1TzB9gjpJvj_ziBwKdVuOhfKezMVsdXzeLxQMJWz-cQk'
TAB = '00-REF-01 — Реестр документов операций'
JSON = '/home/user/My-vault/ops-system/checklists.romashka.json'

# тренинг → код регламента, который он объясняет
LINK = {
 'edu_writeoff':  '05-SOP-04',   # Списания
 'edu_hygiene':   '02-POL-03',   # Гигиена и внешний вид
 'edu_cash':      '03-SOP-03',   # Кассовая дисциплина и инкассация
 'edu_marking':   '04-POL-01',   # Маркировка и сроки
 'edu_app':       '00-REF-04',   # Памятка: как работать в приложении
 'edu_delivery':  '05-SOP-01',   # Приём поставки
 'edu_mise':      '04-POL-03',   # Миз-ан-плас
 'edu_guest':     '07-LOG-02',   # Жалобы гостей
 'edu_handover':  '03-SOP-01',   # Передача смены
 'edu_fryer':     '04-INS-01',   # Стандарт фритюра
 'edu_vent':      '09-SOP-02',   # Вентиляция: вытяжка и приток
 'edu_storage':   '04-POL-02',   # Товарное соседство и хранение
 'edu_inventory': '05-SOP-03',   # Инвентаризация
 'edu_purchase':  '05-SOP-02',   # Закупка на базаре
 'edu_order':     '03-SOP-02',   # Работа с кассой и Poster
 'edu_points':    '01-POL-02',   # Баллы и штрафы
}


def registry():
    s = session()
    rows = s.get('https://sheets.googleapis.com/v4/spreadsheets/'
                 + REG + '/values/'
                 + urllib.parse.quote(f"'{TAB}'!A2:K300"), timeout=60
                 ).json().get('values', [])
    out = {}
    for r in rows:
        r = list(r) + [''] * 11
        if r[0].strip():
            out[r[0].strip()] = {'title': r[1].strip(), 'status': r[4].strip(),
                                 'url': r[10].strip()}
    return out


def main():
    reg = registry()
    D = json.load(open(JSON, encoding='utf-8'))
    ok, bad = 0, []
    for key, code in LINK.items():
        cl = D.get(key)
        if not cl:
            bad.append(f'{key}: тренинга нет в приложении')
            continue
        d = reg.get(code)
        if not d:
            bad.append(f'{key}: {code} нет в реестре — ссылки не будет')
            cl['doc'] = {'code': code, 'title': cl.get('doc', {}).get('title', ''),
                         'url': ''}
            continue
        if d['status'] == 'Отменён':
            # Учить по отменённому документу нельзя: ссылку не даём,
            # тренинг остаётся, а в отчёте видно, что регламента нет.
            bad.append(f'{key}: {code} «{d["title"]}» отменён — нужен новый')
            cl['doc'] = {'code': code, 'title': d['title'], 'url': ''}
            continue
        cl['doc'] = {'code': code, 'title': d['title'], 'url': d['url']}
        if d['url']:
            ok += 1
    json.dump(D, io.open(JSON, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'связано со ссылкой: {ok} из {len(LINK)}')
    for x in bad:
        print('  ⚠️', x)


if __name__ == '__main__':
    main()
