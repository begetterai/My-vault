#!/usr/bin/env python3
"""Схема приложения — документ заменён.

Схема собиралась под прежнюю модель: станция = один чек-лист из шести этапов.
С 24.08.2026 этапы разведены по отдельным листам, добавлены смена дня
и поимённая передача. Держать три пересекающихся описания системы — значит
однажды прочитать устаревшее и поверить ему. Актуальное одно:
«ПРИВЯЗКА СТАНЦИЙ И ЧЕК-ЛИСТОВ — лист правок» (scripts/binding_map_doc.py).
"""
import sys, datetime
sys.path.insert(0, '/home/user/My-vault/scripts')
from ops_docs import session, put_doc, folder_by_name, enforce_font

ROOT = '1cSLEkOXikhTv0g6lPxZ31xJca1Yu-q43'
NAME = 'СХЕМА ПРИЛОЖЕНИЯ — связи и порядок открытия'
LIVE = ('https://docs.google.com/document/d/'
        '13JmA73UWfpqmgi3_ImKe9eGtJMa3_w-eU1PAg0biCCM')
TODAY = datetime.date.today().strftime('%d.%m.%Y')

STYLE = """<style>
@page { size: A4 portrait; margin: 20mm; }
body { font-family: 'Times New Roman', serif; font-size: 13pt; }
h1 { font-size: 20pt; margin: 0 0 10pt 0; }
p { font-size: 13pt; line-height: 1.4; }
</style>"""


def main():
    s = session()
    folder = folder_by_name(s, '00 Управление системой документов', ROOT)
    body = f"""
<h1>Документ заменён</h1>
<p>Эта схема описывала прежнюю модель: одно рабочее место — один чек-лист
из шести этапов. С 24.08.2026 этапы разведены по отдельным листам, появились
выбор смены дня и поимённая передача смены. Всё, что здесь было написано,
устарело.</p>
<p><b>Актуальный документ:</b><br>
<a href="{LIVE}">ПРИВЯЗКА СТАНЦИЙ И ЧЕК-ЛИСТОВ — лист правок</a></p>
<p>В нём: порядок открытия по шагам, десять рабочих мест по четыре листа,
листы старшего смены и управляющего, событийные чек-листы, тренинги
с регламентами, журналы и бланки, передача смены, правило закрытия дня
и сроки этапов.</p>
<p>Заменено {TODAY}.</p>
"""
    html = f'<html><head><meta charset="utf-8">{STYLE}</head><body>{body}</body></html>'
    fid, act = put_doc(s, NAME, folder, html)
    enforce_font(s, fid)
    print(f'{NAME} — {act} (заглушка со ссылкой на актуальный)')


if __name__ == '__main__':
    main()
