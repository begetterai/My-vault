#!/usr/bin/env python3
"""Волна 0: структура папок + реестр документов + шаблоны на диске «УК РОМАШКА».
Существующие файлы НЕ трогаются — строим отдельную новую систему.
Times New Roman 13, без цветовой заливки (правило оформления Азиза)."""
import os, re, json, io
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CRED = '/home/user/My-vault/scripts/credentials/romashka-drive.json'
USER = 'base@azizkhaidarov.com'
DRIVE_ID = '0AA2YI8glLw-eUk9PVA'          # УК «РОМАШКА» (Holding HQ)
ROOT_NAME = '08_ОПЕРАЦИИ (Система документов 2026)'
MD = '/home/user/My-vault/1-Области/Ромашка/Система-документов-операций.md'
SC = ['https://www.googleapis.com/auth/drive',
      'https://www.googleapis.com/auth/spreadsheets']

s = AuthorizedSession(service_account.Credentials
      .from_service_account_file(CRED, scopes=SC).with_subject(USER))

CATS = [
 ("00", "Управление системой документов", "COO"),
 ("01", "Организация и роли",             "COO"),
 ("02", "Персонал",                        "COO"),
 ("03", "Смена и обслуживание",            "Управляющий точки"),
 ("04", "Кухня и производство",            "Управляющий (до найма ст. повара)"),
 ("05", "Товародвижение и склад",          "Закупщик + управляющий"),
 ("06", "Деньги и учёт",                   "COO"),
 ("07", "Качество и контроль",             "COO"),
 ("08", "Безопасность и соответствие",     "COO"),
 ("09", "Оборудование и инфраструктура",   "Управляющий точки"),
 ("10", "Развитие сети",                   "COO"),
]

# существующие документы (НЕ трогаем) — только справочная пометка в реестре
EXISTING = {
 "01-DK-01": "есть SOP — Управляющий (V.1) в 02.3_Менеджмент",
 "01-DK-03": "есть SOP — Повар (V.1) в 02_OPERATIONS_STANDARDS/SOP",
 "01-DK-04": "есть SOP — Кассир (V.1) там же",
 "01-DK-06": "есть SOP — Уборщица (V.1) там же",
 "01-DK-07": "есть SOP — Бариста (V.1) там же",
 "02-SOP-02": "заготовка Onboarding (V.0) — пустая",
 "03-SOP-02": "есть Регламент кассира (V.2) в 02.1_Зал_и_Касса",
 "03-SOP-03": "заготовка Кассовая дисциплина (V.0) — пустая",
 "03-SOP-04": "есть Правила урегулирования конфликтов (V.1)",
 "04-DK-01": "заготовка SOP Старший повар (V.0) — пустая",
 "04-POL-02": "есть Правила хранения продуктов и инвентаря (V.1)",
 "04-CL-01": "есть SOP — Генеральная уборка (V.1)",
 "05-SOP-01": "заготовка Правила приема товаров (V.0) — пустая",
 "06-REF-01": "есть Категории расходов в Poster (V.1)",
 "06-REF-02": "есть Архитектура Poster и логика P&L",
 "06-REF-03": "есть Ромашка — Super P&L 2026",
 "06-REF-04": "есть Ромашка — Дневной трекер 2026",
 "09-INS-01": "есть Правила работы вытяжки (V.1)",
 "09-POL-01": "есть Экономия электроэнергии и климат-контроль (V.1)",
 "04-TTK-*": "есть ~68 карточек в 03.2_Техкарты_и_ТТК",
}
# позиции, которых не было в markdown (нашлись на диске)
EXTRA = [
 ("01-DK-07", "Бариста", "DK", "01", "ответственность за напитки, стандарт кофе, чистота станции", 0),
 ("09-POL-01", "Экономия электроэнергии и климат-контроль", "POL", "09",
  "режимы работы техники, температура в зале, что выключать на ночь", 0),
]

# ── Drive helpers ────────────────────────────────────────────────────────────
def find(name, parent):
    q = f"name='{name}' and '{parent}' in parents and trashed=false"
    r = s.get('https://www.googleapis.com/drive/v3/files', params={
        'q': q, 'fields': 'files(id,name)', 'driveId': DRIVE_ID, 'corpora': 'drive',
        'includeItemsFromAllDrives': 'true', 'supportsAllDrives': 'true'}, timeout=30)
    f = r.json().get('files', [])
    return f[0]['id'] if f else None

def mkfolder(name, parent):
    ex = find(name, parent)
    if ex: return ex, False
    r = s.post('https://www.googleapis.com/drive/v3/files',
        params={'supportsAllDrives': 'true'},
        json={'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent]},
        timeout=30); r.raise_for_status()
    return r.json()['id'], True

def upload_as(name, parent, data, src_mime, dst_mime):
    """Загрузка с конвертацией в родной формат Google (Docs/Sheets)."""
    ex = find(name, parent)
    if ex: return ex, False
    meta = {'name': name, 'parents': [parent], 'mimeType': dst_mime}
    b = '----ops0'
    body = (f'--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'
            + json.dumps(meta) + f'\r\n--{b}\r\nContent-Type: {src_mime}\r\n\r\n').encode() \
           + data + f'\r\n--{b}--'.encode()
    r = s.post('https://www.googleapis.com/upload/drive/v3/files',
        params={'uploadType': 'multipart', 'supportsAllDrives': 'true'},
        headers={'Content-Type': f'multipart/related; boundary={b}'}, data=body, timeout=120)
    r.raise_for_status()
    return r.json()['id'], True

# ── читаем список документов из системного markdown ──────────────────────────
def parse_docs():
    t = open(MD, encoding='utf-8').read()
    part2 = t.split('# Часть 2.')[1].split('# Часть 3.')[0]
    out = []
    for line in part2.split('\n'):
        m = re.match(r'\|\s*(\d\d-[A-Z]{2,3}-[\w*]+)\s*\|\s*([^|]+?)\s*\|\s*([A-Z]{2,3})\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|', line)
        if not m: continue
        code, name, typ, status, content = m.groups()
        crit = 1 if '❗' in status else 0
        out.append((code, name, typ, code[:2], content, crit))
    for e in EXTRA:
        if not any(d[0] == e[0] for d in out): out.append(e)
    return sorted(out, key=lambda x: x[0])

DOCS = parse_docs()

# ── HTML шаблоны (конвертируются в Google Docs) ──────────────────────────────
CSS = ("<style>body{font-family:'Times New Roman',serif;font-size:13pt;}"
       "table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:5px;}"
       "th{background:#fff;font-weight:bold}h1{font-size:16pt}h2{font-size:14pt}</style>")

HEAD_TBL = """<table>
<tr><th style="width:28%">Код</th><td>__ - ___ - __</td></tr>
<tr><th>Название</th><td></td></tr>
<tr><th>Версия</th><td>v1.0</td></tr>
<tr><th>Дата ввода</th><td></td></tr>
<tr><th>Владелец</th><td></td></tr>
<tr><th>Утвердил</th><td>COO</td></tr>
<tr><th>Дата пересмотра</th><td></td></tr>
<tr><th>Область действия</th><td>ЗБ · ОВИР</td></tr>
</table>"""

FOOT = """<h2>Контроль</h2>
<p>Кто проверяет соблюдение: ______________________<br>
Как проверяет: ______________________<br>
Частота: ______________________</p>
<h2>Нарушение</h2>
<p>Что считается нарушением: ______________________<br>
Мера по дисциплинарной сетке: ______________________</p>
<h2>Лист ознакомления</h2>
<table>
<tr><th>ФИО</th><th>Должность</th><th>Дата</th><th>Подпись</th></tr>
<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
</table>"""

TEMPLATES = {
"00-FRM-01 — Шаблон регламента (SOP)": f"""{CSS}<h1>РЕГЛАМЕНТ (SOP) — название</h1>{HEAD_TBL}
<h2>Зачем этот регламент</h2><p>Какую проблему решает — 1–2 предложения.</p>
<h2>Когда запускается</h2><p>Триггер: событие, время или условие.</p>
<h2>Кто участвует</h2>
<table><tr><th>Роль</th><th>Что делает</th></tr>
<tr><td>&nbsp;</td><td>&nbsp;</td></tr><tr><td>&nbsp;</td><td>&nbsp;</td></tr></table>
<h2>Шаги</h2>
<table><tr><th style="width:8%">№</th><th>Действие</th><th style="width:18%">Кто</th><th style="width:16%">Норматив</th></tr>
<tr><td>1</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>2</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>3</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>4</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>5</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr></table>
<h2>Результат</h2><p>Что должно получиться на выходе.</p>
<h2>Типовые ошибки</h2>
<table><tr><th>Ошибка</th><th>Как избежать</th></tr>
<tr><td>&nbsp;</td><td>&nbsp;</td></tr><tr><td>&nbsp;</td><td>&nbsp;</td></tr></table>
{FOOT}""",

"00-FRM-02 — Шаблон должностной карты": f"""{CSS}<h1>ДОЛЖНОСТНАЯ КАРТА — название роли</h1>{HEAD_TBL}
<h2>Место в структуре</h2><p>Подчиняется: ______________<br>Руководит: ______________</p>
<h2>Зона ответственности</h2><p>Одним предложением: за что этот человек отвечает.</p>
<h2>Обязанности</h2><ul><li>&nbsp;</li><li>&nbsp;</li><li>&nbsp;</li><li>&nbsp;</li></ul>
<h2>KPI</h2>
<table><tr><th>Показатель</th><th>Цель</th><th>Как считается</th><th>Частота</th></tr>
<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr></table>
<h2>Права — что решает сам</h2><ul><li>&nbsp;</li><li>&nbsp;</li></ul>
<h2>Запрещено</h2><ul><li>&nbsp;</li><li>&nbsp;</li></ul>
<h2>С кем взаимодействует</h2><p>&nbsp;</p>
{FOOT}""",

"00-FRM-03 — Шаблон чек-листа": f"""{CSS}<h1>ЧЕК-ЛИСТ — название</h1>{HEAD_TBL}
<p><b>Точка:</b> ____________ <b>Дата:</b> ____________ <b>Смена:</b> ____________
<b>Заполнил:</b> ____________</p>
<table>
<tr><th style="width:7%">№</th><th>Что проверить</th><th style="width:12%">Отметка</th><th style="width:12%">Фото</th><th style="width:22%">Комментарий</th></tr>
<tr><td>1</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>2</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>3</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>4</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>5</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>6</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>7</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>8</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
</table>
<p><b>Подпись заполнившего:</b> ______________
&nbsp;&nbsp;<b>Проверил (управляющий):</b> ______________</p>
{FOOT}""",

"00-FRM-04 — Лист ознакомления": f"""{CSS}<h1>ЛИСТ ОЗНАКОМЛЕНИЯ</h1>
<p>Прикладывается к документу. Сотрудник, не подписавший лист, считается не ознакомленным —
спрашивать с него за нарушение этого документа нельзя.</p>
<table><tr><th style="width:28%">Документ (код и название)</th><td>&nbsp;</td></tr>
<tr><th>Версия</th><td>&nbsp;</td></tr><tr><th>Дата ввода</th><td>&nbsp;</td></tr></table>
<table>
<tr><th style="width:7%">№</th><th>ФИО</th><th style="width:20%">Должность</th><th style="width:14%">Дата</th><th style="width:18%">Подпись</th></tr>
""" + "".join(f"<tr><td>{i}</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>"
              for i in range(1, 16)) + "</table>",
}

# ── СБОРКА ───────────────────────────────────────────────────────────────────
def main():
    print("Диск: УК «РОМАШКА» (Holding HQ) · существующие файлы не трогаем\n")
    root, new = mkfolder(ROOT_NAME, DRIVE_ID)
    print(f"{'создана' if new else 'уже была'}: {ROOT_NAME}")

    folders = {}
    for num, name, owner in CATS:
        fid, new = mkfolder(f"{num} {name}", root)
        folders[num] = fid
        print(f"  {'+' if new else '·'} {num} {name}")

    # шаблоны в папку 00
    print("\nШаблоны:")
    for name, html in TEMPLATES.items():
        fid, new = upload_as(name, folders["00"], html.encode('utf-8'),
                             'text/html', 'application/vnd.google-apps.document')
        print(f"  {'+' if new else '·'} {name}")

    # реестр
    print("\nРеестр документов:")
    hdr = ["Код","Название","Тип","Категория","Статус","Приоритет","Владелец","Версия",
           "Дата ввода","Пересмотр","Ссылка","Что должен содержать","Примечание"]
    owner_by = {c[0]: c[2] for c in CATS}
    cat_by   = {c[0]: f"{c[0]} {c[1]}" for c in CATS}
    rows = [hdr]
    for code, name, typ, cat, content, crit in DOCS:
        rows.append([code, name, typ, cat_by.get(cat, cat), "Не начат",
                     "Критично" if crit else "", owner_by.get(cat, ""), "", "", "", "",
                     content, EXISTING.get(code, "")])
    csv = "\n".join(",".join('"' + str(c).replace('"', '""') + '"' for c in r) for r in rows)
    sid, new = upload_as("00-REF-01 — Реестр документов операций", folders["00"],
                         csv.encode('utf-8'), 'text/csv',
                         'application/vnd.google-apps.spreadsheet')
    print(f"  {'+' if new else '·'} 00-REF-01 — Реестр документов операций ({len(DOCS)} позиций)")

    # формат реестра: TNR 13, шапка жирная, закреплена, автофильтр, ширины
    meta = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{sid}',
                 params={'fields': 'sheets.properties'}, timeout=30).json()
    sh = meta['sheets'][0]['properties']['sheetId']
    reqs = [
      {'repeatCell': {'range': {'sheetId': sh},
        'cell': {'userEnteredFormat': {
          'textFormat': {'fontFamily': 'Times New Roman', 'fontSize': 13, 'bold': False},
          'backgroundColor': {'red': 1, 'green': 1, 'blue': 1},
          'verticalAlignment': 'TOP', 'wrapStrategy': 'WRAP'}},
        'fields': 'userEnteredFormat(textFormat,backgroundColor,verticalAlignment,wrapStrategy)'}},
      {'repeatCell': {'range': {'sheetId': sh, 'startRowIndex': 0, 'endRowIndex': 1},
        'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
        'fields': 'userEnteredFormat.textFormat.bold'}},
      {'updateSheetProperties': {'properties': {'sheetId': sh,
        'gridProperties': {'frozenRowCount': 1, 'frozenColumnCount': 1}},
        'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}},
      {'setBasicFilter': {'filter': {'range': {'sheetId': sh, 'startRowIndex': 0}}}},
    ]
    widths = [(0,1,90),(1,2,300),(2,3,60),(3,4,210),(4,5,110),(5,6,90),(6,7,180),
              (7,8,70),(8,9,100),(9,10,100),(10,11,150),(11,12,420),(12,13,300)]
    for a,b,px in widths:
        reqs.append({'updateDimensionProperties': {'range': {'sheetId': sh,
            'dimension': 'COLUMNS', 'startIndex': a, 'endIndex': b},
            'properties': {'pixelSize': px}, 'fields': 'pixelSize'}})
    s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate',
           json={'requests': reqs}, timeout=60).raise_for_status()
    print("     формат применён: TNR 13, шапка закреплена, фильтр включён")

    print(f"\nПапка:  https://drive.google.com/drive/folders/{root}")
    print(f"Реестр: https://docs.google.com/spreadsheets/d/{sid}")
    return root, sid

if __name__ == '__main__':
    main()
