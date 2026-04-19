#!/usr/bin/env python3
"""
Создать ведомость на выдачу зарплаты ФОТ 04.2026.
Два листа: ЗБ (Лохути) и ОВИР (Турсунзода).
Столбцы: № | ФИО | Должность | Начислено | Аванс | Штраф | К выдаче | Подпись | Дата
"""

import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))

CREDENTIALS = os.path.join(os.path.dirname(__file__), "credentials", "romashka-drive.json")
FOT_SS_ID   = "1geMH__Xc32aLE9QabLjSXxgY_VFJah_d8ekL6uSkWDk"

# ── Цвета ─────────────────────────────────────────────────────────────────────
CLR_DARK  = {"red": 0.18, "green": 0.31, "blue": 0.18}
CLR_MID   = {"red": 0.24, "green": 0.42, "blue": 0.24}
CLR_SUB   = {"red": 0.75, "green": 0.88, "blue": 0.75}
CLR_GRAND = {"red": 0.55, "green": 0.75, "blue": 0.55}
CLR_WARN  = {"red": 1.00, "green": 0.93, "blue": 0.70}
CLR_WHITE = {"red": 1.00, "green": 1.00, "blue": 1.00}
CLR_GREY  = {"red": 0.96, "green": 0.96, "blue": 0.96}
CLR_SIGN  = {"red": 0.98, "green": 0.98, "blue": 0.95}  # кремовый — поле подписи
FONT = "Times New Roman"

# ── Ячейки ────────────────────────────────────────────────────────────────────
def c(v, bold=False, italic=False, bg=None, align="LEFT", fs=14, fg=None, num_fmt=None, wrap=True):
    if isinstance(v, (int, float)):
        uv = {"numberValue": float(v)}
    elif isinstance(v, str) and v.startswith("="):
        uv = {"formulaValue": v}
    else:
        uv = {"stringValue": str(v) if v is not None else ""}
    tf = {"fontFamily": FONT, "fontSize": fs, "bold": bold, "italic": italic}
    if fg:
        tf["foregroundColor"] = fg
    fmt = {"textFormat": tf, "horizontalAlignment": align,
           "wrapStrategy": "WRAP" if wrap else "CLIP",
           "verticalAlignment": "MIDDLE"}
    if bg:
        fmt["backgroundColor"] = bg
    if num_fmt:
        fmt["numberFormat"] = {"type": "NUMBER", "pattern": num_fmt}
    return {"userEnteredValue": uv, "userEnteredFormat": fmt}


def n(v, bold=False, bg=None, fs=14, fg=None):
    return c(v, bold=bold, bg=bg, align="RIGHT", fs=fs, fg=fg, num_fmt="# ##0")


def h(v, bg=None, fs=18, align="CENTER"):
    return c(v, bold=True, bg=bg or CLR_DARK, align=align, fs=fs, fg=CLR_WHITE)


def sec(v):
    return c(v, bold=True, bg=CLR_MID, fs=14, fg=CLR_WHITE)


def e(bg=None):
    return c("", bg=bg)


def row(*cells):
    return {"values": list(cells)}


def blank():
    return {"values": [e() for _ in range(9)]}


def border_cell(v, **kwargs):
    cell = c(v, **kwargs)
    cell["userEnteredFormat"]["borders"] = {
        "top":    {"style": "SOLID", "width": 1, "color": {"red": 0.6, "green": 0.6, "blue": 0.6}},
        "bottom": {"style": "SOLID", "width": 1, "color": {"red": 0.6, "green": 0.6, "blue": 0.6}},
        "left":   {"style": "SOLID", "width": 1, "color": {"red": 0.6, "green": 0.6, "blue": 0.6}},
        "right":  {"style": "SOLID", "width": 1, "color": {"red": 0.6, "green": 0.6, "blue": 0.6}},
    }
    return cell


def brow(*cells):
    return {"values": [border_cell(
        cl["userEnteredValue"].get("numberValue",
            cl["userEnteredValue"].get("formulaValue",
            cl["userEnteredValue"].get("stringValue", ""))),
        **{k: v for k, v in {
            "bold":    cl["userEnteredFormat"]["textFormat"].get("bold", False),
            "italic":  cl["userEnteredFormat"]["textFormat"].get("italic", False),
            "bg":      cl["userEnteredFormat"].get("backgroundColor"),
            "align":   cl["userEnteredFormat"].get("horizontalAlignment", "LEFT"),
            "fs":      cl["userEnteredFormat"]["textFormat"].get("fontSize", 14),
            "fg":      cl["userEnteredFormat"]["textFormat"].get("foregroundColor"),
            "num_fmt": cl["userEnteredFormat"].get("numberFormat", {}).get("pattern"),
        }.items() if v is not None}
    ) for cl in cells]}


# ── Данные ────────────────────────────────────────────────────────────────────
# (ФИО, Должность, Начислено, флаг предупреждения)
ZB_PROD = [
    ("Шарипов Азиз",     "Заготовщик",    2250, False),
    ("Шахнозаи Джума",   "Заготовщик",    2150, False),
    ("Абдиев Окил",      "Заготовщик",    2000, False),
    ("Джалилов Акбар",   "Старший повар", 1420, False),
    ("Ятимов Бобокалон", "Старший повар", 1460, False),
    ("Джобиров",         "Повар",          880, False),
    ("Саримсоков",       "Повар",         1290, False),
    ("Низовмов",         "Повар",         1184, False),
    ("Бобокалонов",      "Повар",         1040, False),
    ("Ориф",             "Повар",         1280, False),
    ("Тошева",           "Уборщица",      1400, False),
    ("Зебо",             "Уборщица",      1700, False),
    ("Файзалли",         "Бариста",       1360, False),
    ("Саидо",            "Бариста",        720, False),
    ("Фаёзова Нигина",   "Кассир",        1350, True),   # ⚠️ дубль ОВИР
    ("Валерия",          "Кассир",        1370, False),
]
ZB_PROD_REF = (22854, 3742, 228, 18884)

ZB_ADMIN = [
    ("Митюков Владимир", "Управляющий",   2000, False),
    ("Митюков Владимир", "Калькулятор",    500, True),   # ⚠️ дубль ОВИР
    ("Фируз",            "Адм. персонал",  750, True),
    ("Фарангис",         "Адм. персонал",  500, True),
    ("Муллабаев Махмуд", "Ассистент",      550, True),   # ⚠️ 3 позиции
    ("Мавлюда",          "Адм. персонал",  150, True),
    # Хайдаров Азиз — директор, начислен на обеих точках, включён в ОВИР
]
ZB_ADMIN_REF = (7450, None, None, 4450)

OVIR_PROD = [
    ("Шахром",           "Старший повар", 1650, False),
    ("Диёрбек",          "Старший повар", 1660, False),
    ("Рукия",            "Повар",          960, False),
    ("Мансур",           "Повар",         1248, False),
    ("Абубакр",          "Повар",          931, False),
    ("Шахбоз",           "Повар",         1296, False),
    ("Асила",            "Повар",         1160, False),
    ("Мухаммад",         "Повар",          880, False),
    ("Махтоб",           "Уборщица",      1500, False),
    ("Мавчуда",          "Уборщица",      1500, False),
    ("Исматзода",        "Бариста",       1550, False),
    ("Асема",            "Бариста",        960, False),
    ("Фаёзова Нигина",   "Кассир",        1350, True),   # ⚠️ дубль ЗБ
    ("Муллабаев Махмуд", "Кассир",        1930, True),   # ⚠️ 3 позиции
    ("Муслима",          "Кассир",         990, False),
]
OVIR_PROD_REF = (19565, 1896, 680, 14999)

OVIR_ADMIN = [
    ("Хайдаров Азиз",     "Директор",      3000, True),  # ⚠️ дубль ЗБ — платить 1 раз
    ("Рахматуллаев Дилчу","Управляющий",   2000, False),
    ("Рахматуллаев Дилчу","Доплата",       1400, False),
    ("Митюков Владимир",  "Калькулятор",    500, True),  # ⚠️ дубль ЗБ
    ("Фируз",             "Адм. персонал",  750, True),
    ("Фарангис",          "Адм. персонал",  500, True),
    ("Муллабаев Махмуд",  "Ассистент",      950, True),
    ("Мавлюда",           "Адм. персонал",  150, True),
]
OVIR_ADMIN_REF = (9250, None, None, 8404)

COLS = ["№", "ФИО", "Должность", "Начислено", "Аванс\n(ранее)", "Штраф", "К ВЫДАЧЕ", "Подпись", "Дата"]


# ── Построение листа ─────────────────────────────────────────────────────────
def build_sheet(location_name, prod_data, prod_ref, admin_data, admin_ref):
    rows = []
    A = rows.append

    # Шапка
    A(row(h(f"Сеть кафе «Ромашка» — {location_name}", fs=16),
          *[e(CLR_DARK)] * 8))
    A(row(h("ВЕДОМОСТЬ НА ВЫДАЧУ ЗАРАБОТНОЙ ПЛАТЫ — АПРЕЛЬ 2026", fs=18),
          *[e(CLR_DARK)] * 8))
    A(row(c("Период: 1–30 апреля 2026 г.", italic=True, fs=13),
          *[e()] * 8))
    A(blank())

    # Производство
    A(row(sec("ПРОИЗВОДСТВЕННЫЙ ПЕРСОНАЛ"),
          *[e(CLR_MID)] * 8))
    A(row(*[h(col, fs=14) for col in COLS]))

    start_row = len(rows) + 1  # для формул (1-based)
    counter = 1
    for фио, должность, нач, warn in prod_data:
        bg = CLR_WARN if warn else None
        row_formula_idx = len(rows) + 1
        A(row(
            c(counter, bg=bg, align="CENTER"),
            c(фио, bg=bg),
            c(должность, bg=bg),
            n(нач, bg=bg),
            e(bg),                                          # аванс — заполняет управляющий
            e(bg),                                          # штраф — заполняет управляющий
            c(f"=D{row_formula_idx+1}-E{row_formula_idx+1}-F{row_formula_idx+1}",
              bold=True, bg=bg, align="RIGHT", num_fmt="# ##0"),
            c("", bg=CLR_SIGN),                            # подпись
            c("", bg=CLR_SIGN),                            # дата
        ))
        counter += 1

    # Контрольная строка производства
    нач_r, авн_r, шт_r, выд_r = prod_ref
    A(row(
        c("ИТОГО производство", bold=True, bg=CLR_SUB),
        c("(контрольные данные из ФОТ)", italic=True, fs=12, bg=CLR_SUB),
        e(CLR_SUB),
        n(нач_r, bold=True, bg=CLR_SUB),
        n(авн_r, bold=True, bg=CLR_SUB),
        n(шт_r,  bold=True, bg=CLR_SUB),
        n(выд_r, bold=True, bg=CLR_SUB),
        e(CLR_SUB),
        e(CLR_SUB),
    ))
    A(blank())

    # Администрация
    A(row(sec("АДМИНИСТРАТИВНЫЙ ПЕРСОНАЛ"),
          *[e(CLR_MID)] * 8))
    A(row(*[h(col, fs=14) for col in COLS]))

    counter = 1
    for фио, должность, нач, warn in admin_data:
        bg = CLR_WARN if warn else None
        row_formula_idx = len(rows) + 1
        A(row(
            c(counter, bg=bg, align="CENTER"),
            c(фио, bg=bg),
            c(должность, bg=bg),
            n(нач, bg=bg),
            e(bg),
            e(bg),
            c(f"=D{row_formula_idx+1}-E{row_formula_idx+1}-F{row_formula_idx+1}",
              bold=True, bg=bg, align="RIGHT", num_fmt="# ##0"),
            c("", bg=CLR_SIGN),
            c("", bg=CLR_SIGN),
        ))
        counter += 1

    нач_a, _, _, выд_a = admin_ref
    A(row(
        c("ИТОГО администрация", bold=True, bg=CLR_SUB),
        c("(контрольные данные из ФОТ)", italic=True, fs=12, bg=CLR_SUB),
        e(CLR_SUB),
        n(нач_a, bold=True, bg=CLR_SUB),
        e(CLR_SUB), e(CLR_SUB),
        n(выд_a, bold=True, bg=CLR_SUB),
        e(CLR_SUB), e(CLR_SUB),
    ))
    A(blank())

    # Итого по точке
    grand_нач = prod_ref[0] + admin_ref[0]
    grand_выд = prod_ref[3] + admin_ref[3]
    A(row(
        h(f"ИТОГО {location_name.split('(')[0].strip()}", bg=CLR_DARK, align="LEFT", fs=14),
        e(CLR_DARK), e(CLR_DARK),
        n(grand_нач, bold=True, bg=CLR_DARK, fg=CLR_WHITE),
        e(CLR_DARK), e(CLR_DARK),
        n(grand_выд, bold=True, bg=CLR_DARK, fg=CLR_WHITE),
        e(CLR_DARK), e(CLR_DARK),
    ))
    A(blank())

    # Подписи
    A(row(
        c("Выдал:", bold=True), e(), e(),
        c("____________________________", align="CENTER"),
        c("Управляющий:", bold=True), e(),
        c("____________________________", align="CENTER"),
        e(), e(),
    ))
    A(row(
        e(),
        c("(ФИО, подпись)", italic=True, fs=12, align="CENTER"),
        e(), e(),
        e(),
        c("(ФИО, подпись)", italic=True, fs=12, align="CENTER"),
        e(), e(), e(),
    ))
    A(blank())
    A(row(
        c("Дата выдачи:", bold=True),
        c("«____» ______________ 2026 г.", fs=13),
        *[e()] * 7,
    ))
    A(row(
        c("⚠️ Строки, выделенные жёлтым, требуют уточнения перед выплатой.",
          italic=True, fs=12, fg={"red": 0.6, "green": 0.4, "blue": 0.0}),
        *[e()] * 8,
    ))

    return rows


# ── Вспомогательные функции ───────────────────────────────────────────────────
def get_session():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS,
        scopes=["https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"])
    return AuthorizedSession(creds)


def get_folder_id(session, file_id):
    r = session.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}"
        "?fields=parents&supportsAllDrives=true")
    parents = r.json().get("parents", [])
    return parents[0] if parents else None


def create_ss(session, title, folder_id):
    body = {"name": title, "mimeType": "application/vnd.google-apps.spreadsheet"}
    if folder_id:
        body["parents"] = [folder_id]
    r = session.post(
        "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
        headers={"Content-Type": "application/json"},
        data=json.dumps(body))
    return r.json()["id"]


def add_sheet(session, ss_id, title, index):
    r = session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": [{"addSheet": {
            "properties": {"title": title, "index": index}}}]}))
    return r.json()["replies"][0]["addSheet"]["properties"]["sheetId"]


def rename_sheet(session, ss_id, sheet_id, title):
    session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "title": title},
            "fields": "title"}}]}))


def write_sheet(session, ss_id, sheet_id, rows):
    # Ширины столбцов: №|ФИО|Должность|Начислено|Аванс|Штраф|К выдаче|Подпись|Дата
    col_widths = [40, 190, 155, 110, 90, 80, 105, 165, 80]
    requests = [
        {
            "updateCells": {
                "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
                "rows": rows,
                "fields": "userEnteredValue,userEnteredFormat"
            }
        },
        # Заморозить первые 2 строки (шапка)
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id,
                               "gridProperties": {"frozenRowCount": 2}},
                "fields": "gridProperties.frozenRowCount"
            }
        },
        # Высота строк для подписей — сделать все строки повыше
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS",
                          "startIndex": 5, "endIndex": 5 + 35},
                "properties": {"pixelSize": 38},
                "fields": "pixelSize"
            }
        },
    ]
    for i, px in enumerate(col_widths):
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                          "startIndex": i, "endIndex": i + 1},
                "properties": {"pixelSize": px},
                "fields": "pixelSize"
            }
        })

    # Merge header rows across all 9 columns
    for r_idx in [0, 1]:
        requests.append({
            "mergeCells": {
                "range": {"sheetId": sheet_id, "startRowIndex": r_idx,
                          "endRowIndex": r_idx + 1,
                          "startColumnIndex": 0, "endColumnIndex": 9},
                "mergeType": "MERGE_ALL"
            }
        })

    r = session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": requests}))
    return r.status_code == 200


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("Авторизация...")
    session = get_session()

    print("Определяем папку ФОТ файла...")
    folder_id = get_folder_id(session, FOT_SS_ID)
    print(f"Папка: {folder_id}")

    title = "Ведомость на выдачу ФОТ — Апрель 2026"
    print(f"Создаём файл «{title}»...")
    ss_id = create_ss(session, title, folder_id)
    print(f"Создан: {ss_id}")

    # Получаем ID первого листа (Sheet1 по умолчанию)
    r = session.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}?fields=sheets.properties")
    sheets = r.json()["sheets"]
    default_sid = sheets[0]["properties"]["sheetId"]

    # Переименовываем Sheet1 → ЗБ
    rename_sheet(session, ss_id, default_sid, "ЗБ (Лохути)")

    # Добавляем лист ОВИР
    ovir_sid = add_sheet(session, ss_id, "ОВИР (Турсунзода)", 1)

    # ЗБ
    print("Заполняем лист ЗБ...")
    zb_rows = build_sheet("ЗБ (Лохути)", ZB_PROD, ZB_PROD_REF, ZB_ADMIN, ZB_ADMIN_REF)
    ok = write_sheet(session, ss_id, default_sid, zb_rows)
    print(f"ЗБ: {'✅' if ok else '❌'} ({len(zb_rows)} строк)")

    # ОВИР
    print("Заполняем лист ОВИР...")
    ovir_rows = build_sheet("ОВИР (Турсунзода)", OVIR_PROD, OVIR_PROD_REF, OVIR_ADMIN, OVIR_ADMIN_REF)
    ok = write_sheet(session, ss_id, ovir_sid, ovir_rows)
    print(f"ОВИР: {'✅' if ok else '❌'} ({len(ovir_rows)} строк)")

    print(f"\n✅ Готово!")
    print(f"https://docs.google.com/spreadsheets/d/{ss_id}/edit")


if __name__ == "__main__":
    main()
