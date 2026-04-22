#!/usr/bin/env python3
"""
Создать сводное меню Проекта «Бар» в Google Sheets.
Все позиции по блокам с параметрами: выход, себестоимость, цена, Food Cost.
"""
import json, os
CREDENTIALS = os.path.join(os.path.dirname(__file__), "credentials", "romashka-drive.json")
FOLDER_ID   = "1u98T7m_J0Ly8yfKGpYkN_1M-nCKDea0e"

CLR_DARK  = {"red": 0.10, "green": 0.18, "blue": 0.10}
CLR_BLOCK = {
    "☕ Кофе":                  {"red": 0.25, "green": 0.15, "blue": 0.05},
    "🍵 Чай классика":          {"red": 0.10, "green": 0.25, "blue": 0.20},
    "🍓 Чай фруктовый":         {"red": 0.30, "green": 0.10, "blue": 0.15},
    "🍋 Лимонады":              {"red": 0.28, "green": 0.28, "blue": 0.05},
    "🍸 Коктейли б/а":          {"red": 0.08, "green": 0.22, "blue": 0.32},
    "🍹 Коктейли алк.":         {"red": 0.25, "green": 0.10, "blue": 0.20},
    "🥤 Милкшейки":             {"red": 0.22, "green": 0.15, "blue": 0.28},
    "🥃 Виски":                 {"red": 0.22, "green": 0.15, "blue": 0.05},
    "🍶 Ром":                   {"red": 0.18, "green": 0.12, "blue": 0.05},
    "🌵 Текила":                {"red": 0.20, "green": 0.20, "blue": 0.05},
    "🫧 Джин":                  {"red": 0.05, "green": 0.20, "blue": 0.28},
    "🍾 Водка":                 {"red": 0.20, "green": 0.20, "blue": 0.25},
    "🍯 Ликёры":                {"red": 0.25, "green": 0.18, "blue": 0.05},
    "🍷 Вино":                  {"red": 0.28, "green": 0.05, "blue": 0.10},
    "🥂 Игристое":              {"red": 0.28, "green": 0.20, "blue": 0.28},
    "🍺 Пиво":                  {"red": 0.22, "green": 0.18, "blue": 0.05},
    "🥤 Напитки":               {"red": 0.05, "green": 0.18, "blue": 0.25},
}
CLR_WHITE = {"red": 1.00, "green": 1.00, "blue": 1.00}
CLR_WARN  = {"red": 1.00, "green": 0.95, "blue": 0.80}
FONT = "Times New Roman"

# (блок, позиция, выход, примечание)
MENU = [
    # ☕ Кофе
    ("☕ Кофе", "Эспрессо",                "60 мл",   ""),
    ("☕ Кофе", "Доппио",                  "120 мл",  ""),
    ("☕ Кофе", "Американо",               "200 мл",  ""),
    ("☕ Кофе", "Капучино",                "200 мл",  ""),
    ("☕ Кофе", "Латте",                   "250 мл",  ""),
    ("☕ Кофе", "Классический бамбл",      "300 мл",  ""),
    ("☕ Кофе", "Айс Американо",           "300 мл",  ""),
    ("☕ Кофе", "Айс Капучино",            "300 мл",  ""),
    ("☕ Кофе", "Айс Латте",               "300 мл",  ""),
    ("☕ Кофе", "Манговый айс Латте",      "350 мл",  ""),

    # 🍵 Чай классика — 8 базовых + 3 премиум
    ("🍵 Чай классика", "Чёрный классический (Ассам)",  "500 мл", ""),
    ("🍵 Чай классика", "Молочный улун",                "500 мл", ""),
    ("🍵 Чай классика", "Жасмин",                       "500 мл", ""),
    ("🍵 Чай классика", "Каркаде",                      "500 мл", ""),
    ("🍵 Чай классика", "Ройбуш",                       "500 мл", ""),
    ("🍵 Чай классика", "Сенча",                        "500 мл", ""),
    ("🍵 Чай классика", "Дарджилинг",                   "500 мл", ""),
    ("🍵 Чай классика", "Ганпаудер",                    "500 мл", ""),
    ("🍵 Чай классика", "Да Хунь Пао ★",               "500 мл", "Премиум — китайский улун"),
    ("🍵 Чай классика", "Шен Пуэр ★",                  "500 мл", "Премиум — выдержанный"),
    ("🍵 Чай классика", "Те Гуаньинь ★",               "500 мл", "Премиум — улун"),

    # 🍓 Чай фруктовый — 4 позиции (без Массалы)
    ("🍓 Чай фруктовый", "Цитрусово-имбирный",          "500 мл", ""),
    ("🍓 Чай фруктовый", "Тропическая облепиха",         "500 мл", ""),
    ("🍓 Чай фруктовый", "Грушево-коричный",             "500 мл", ""),
    ("🍓 Чай фруктовый", "Смородиновый",                 "500 мл", ""),

    # 🍋 Лимонады
    ("🍋 Лимонады", "Классический",                    "350 мл", ""),
    ("🍋 Лимонады", "Персик — Личи",                   "350 мл", ""),
    ("🍋 Лимонады", "Манго — Маракуйя",                "350 мл", ""),
    ("🍋 Лимонады", "Вишня — Яблоко — Клубника",       "350 мл", ""),
    ("🍋 Лимонады", "Яблоко — Киви — Ананас",          "350 мл", ""),

    # 🍸 Коктейли безалкогольные
    ("🍸 Коктейли б/а", "Мохито Клубничный",           "250 мл", ""),
    ("🍸 Коктейли б/а", "Вирджин Палома",              "250 мл", ""),
    ("🍸 Коктейли б/а", "Пина Колада (б/а)",           "250 мл", ""),
    ("🍸 Коктейли б/а", "Пеликан",                     "250 мл", ""),
    ("🍸 Коктейли б/а", "Фруктовая поляна",            "250 мл", ""),

    # 🍹 Коктейли алкогольные
    ("🍹 Коктейли алк.", "Мохито Классический",        "250 мл", ""),
    ("🍹 Коктейли алк.", "Мохито Клубничный",          "250 мл", ""),
    ("🍹 Коктейли алк.", "Апероль Шприц",              "250 мл", ""),
    ("🍹 Коктейли алк.", "Маргарита",                  "250 мл", ""),
    ("🍹 Коктейли алк.", "Пино Колада",                "250 мл", ""),
    ("🍹 Коктейли алк.", "Белини",                     "250 мл", ""),
    ("🍹 Коктейли алк.", "Текила Санрайз",             "250 мл", ""),

    # 🥤 Милкшейки
    ("🥤 Милкшейки", "Клубничный",                    "300 мл", ""),
    ("🥤 Милкшейки", "Банановый",                     "300 мл", ""),
    ("🥤 Милкшейки", "Классический",                  "300 мл", ""),
    ("🥤 Милкшейки", "Шоколадный",                    "300 мл", ""),

    # 🥃 Виски
    ("🥃 Виски", "Джонни Уолкер Red Label",            "100 мл", "Шот 50 мл"),
    ("🥃 Виски", "Джеймсон",                           "100 мл", "Шот 50 мл"),
    ("🥃 Виски", "Чивас Ригал 12",                     "100 мл", "Шот 50 мл"),
    ("🥃 Виски", "Джек Дэниелс",                       "100 мл", "Шот 50 мл"),

    # 🍶 Ром
    ("🍶 Ром", "Капитан Морган Бланко",                "50 мл",  ""),
    ("🍶 Ром", "Капитан Морган Голд",                  "50 мл",  ""),
    ("🍶 Ром", "Капитан Морган Блэк",                  "50 мл",  ""),

    # 🌵 Текила
    ("🌵 Текила", "Ольмека Сильвер",                   "50 мл",  ""),
    ("🌵 Текила", "Ольмека Голд",                      "50 мл",  ""),
    ("🌵 Текила", "Сиерра Сильвер",                    "50 мл",  ""),
    ("🌵 Текила", "Сиерра Голд",                       "50 мл",  ""),

    # 🫧 Джин
    ("🫧 Джин", "Гордонс",                             "50 мл",  ""),
    ("🫧 Джин", "Бифитер",                             "50 мл",  ""),
    ("🫧 Джин", "Баристер Драй",                       "50 мл",  ""),

    # 🍾 Водка
    ("🍾 Водка", "Кеклик Саваж",                       "50 мл",  ""),
    ("🍾 Водка", "Кеклик Премиум",                     "50 мл",  ""),
    ("🍾 Водка", "Шохона Платинум",                    "50 мл",  ""),
    ("🍾 Водка", "Абсолют",                            "50 мл",  ""),
    ("🍾 Водка", "Чистые Росы",                        "50 мл",  ""),

    # 🍯 Ликёры
    ("🍯 Ликёры", "Егермейстер",                       "50 мл",  ""),
    ("🍯 Ликёры", "Куантро",                           "50 мл",  ""),
    ("🍯 Ликёры", "Апероль",                           "50 мл",  ""),

    # 🍷 Вино
    ("🍷 Вино", "Якобс Крик Совиньон Блан (б/с)",      "125 мл", "750 мл / бутылка"),
    ("🍷 Вино", "Якобс Крик Рислинг (б/с)",            "125 мл", "750 мл / бутылка"),
    ("🍷 Вино", "Якобс Крик Каберне (кр/с)",           "125 мл", "750 мл / бутылка"),
    ("🍷 Вино", "Якобс Крик Шираз Каберне (кр/с)",     "125 мл", "750 мл / бутылка"),
    ("🍷 Вино", "Хванчкара (кр/псл)",                  "125 мл", "750 мл / бутылка"),

    # 🥂 Игристое
    ("🥂 Игристое", "Санто Стефано",                   "150 мл", "750 мл / бутылка"),
    ("🥂 Игристое", "Российское Брют",                 "150 мл", "750 мл / бутылка"),

    # 🍺 Пиво
    ("🍺 Пиво", "Bud",                                 "500 мл", "бутылка"),
    ("🍺 Пиво", "Corona Extra",                        "500 мл", "бутылка"),
    ("🍺 Пиво", "Stella Artois",                       "400 мл", "бутылка"),
    ("🍺 Пиво", "Essa Грейпфрут",                      "500 мл", "бутылка"),
    ("🍺 Пиво", "Hoegarden нф Грейпфрут",              "500 мл", "бутылка"),
    ("🍺 Пиво", "Kozel Тёмный",                        "500 мл", "бутылка"),
    ("🍺 Пиво", "Guiness",                             "500 мл", "бутылка"),
    ("🍺 Пиво", "Pauliner",                            "500 мл", "ж/б"),
    ("🍺 Пиво", "Heineken",                            "330 мл", "бутылка"),
    ("🍺 Пиво", "Miller",                              "500 мл", "бутылка"),

    # 🥤 Напитки
    ("🥤 Напитки", "Кока-Кола",                        "500 мл", "бутылка"),
    ("🥤 Напитки", "Фанта",                            "500 мл", "бутылка"),
    ("🥤 Напитки", "Спрайт",                           "500 мл", "бутылка"),
    ("🥤 Напитки", "Кола Зеро",                        "500 мл", "бутылка"),
    ("🥤 Напитки", "Бон Аква",                         "500 мл", "бутылка"),
    ("🥤 Напитки", "Боржоми",                          "500 мл", "стекло"),
    ("🥤 Напитки", "Швепс",                            "500 мл", "бутылка"),
    ("🥤 Напитки", "Добрый Яблоко",                    "200 мл", "тетрапак"),
    ("🥤 Напитки", "Добрый Апельсин",                  "200 мл", "тетрапак"),
    ("🥤 Напитки", "Добрый Ананас",                    "200 мл", "тетрапак"),
    ("🥤 Напитки", "Добрый Вишня",                     "200 мл", "тетрапак"),
    ("🥤 Напитки", "Добрый Малина",                    "200 мл", "тетрапак"),
    ("🥤 Напитки", "Добрый Мультифрукт",               "200 мл", "тетрапак"),
    ("🥤 Напитки", "Добрый Грейпфрут",                 "200 мл", "тетрапак"),
    ("🥤 Напитки", "Добрый Томат",                     "200 мл", "тетрапак"),
]

COLS = ["Позиция", "Объём / Выход", "Себестоимость (с)", "Цена продажи (с)", "Food Cost %", "Примечание"]


def c(v, bold=False, bg=None, align="LEFT", fs=13, fg=None, italic=False):
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
           "wrapStrategy": "WRAP", "verticalAlignment": "MIDDLE"}
    if bg:
        fmt["backgroundColor"] = bg
    return {"userEnteredValue": uv, "userEnteredFormat": fmt}


def h(v, bg=None, fs=16):
    return c(v, bold=True, bg=bg or CLR_DARK, align="CENTER", fs=fs, fg=CLR_WHITE)


def e(bg=None):
    return c("", bg=bg)


def row(*cells):
    return {"values": list(cells)}


def build_rows():
    rows = []
    A = rows.append
    nc = len(COLS)

    A(row(h("БАРНАЯ КАРТА — МЕНЮ", fs=18), *[e(CLR_DARK)] * (nc - 1)))
    A(row(h(f"Проект «Бар» | {len(MENU)} позиций | Актуально на 22.04.2026", fs=12,
            bg={"red": 0.18, "green": 0.28, "blue": 0.18}), *[e({"red": 0.18, "green": 0.28, "blue": 0.18})] * (nc - 1)))
    A(row(*[e()] * nc))
    A(row(*[h(col, fs=13) for col in COLS]))

    current_block = None
    row_idx = 5  # 1-indexed, after header rows
    for блок, позиция, выход, примечание in MENU:
        if блок != current_block:
            current_block = блок
            bg = CLR_BLOCK.get(блок, CLR_DARK)
            A(row(c(блок, bold=True, bg=bg, fg=CLR_WHITE, fs=13),
                  *[e(bg)] * (nc - 1)))
            row_idx += 1

        # Food Cost formula (col E = index 5, С = col C index 3, D = col D index 4)
        # Row index in sheet for this data row
        fc_formula = f"=IF(D{row_idx+1}>0,C{row_idx+1}/D{row_idx+1},\"\")"

        A(row(
            c(позиция, fs=13),
            c(выход, align="CENTER", fs=13),
            c("", fs=13, align="RIGHT"),       # себестоимость — заполнить
            c("", fs=13, align="RIGHT"),       # цена продажи — заполнить
            c(fc_formula, align="CENTER", fs=13),
            c(примечание, italic=bool(примечание), fs=12),
        ))
        row_idx += 1

    A(row(*[e()] * nc))
    A(row(
        c(f"Итого позиций: {len(MENU)}", bold=True, fs=13),
        c("Food Cost цель: до 30% (алк), до 25% (кофе/чай)", italic=True, fs=12),
        *[e()] * (nc - 2),
    ))
    return rows


def get_session():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS,
        scopes=["https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"])
    return AuthorizedSession(creds)


def main():
    s = get_session()

    print("Создаём файл меню...")
    r = s.post(
        "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "name": "Барная карта — Полное меню (ТТК сводка)",
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [FOLDER_ID]
        }))
    ss_id = r.json()["id"]

    r2 = s.get(f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}?fields=sheets.properties")
    sheet_id = r2.json()["sheets"][0]["properties"]["sheetId"]

    s.post(f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
           headers={"Content-Type": "application/json"},
           data=json.dumps({"requests": [{"updateSheetProperties": {
               "properties": {"sheetId": sheet_id, "title": "Меню"},
               "fields": "title"}}]}))

    all_rows = build_rows()
    col_widths = [260, 90, 120, 120, 90, 180]

    reqs = [
        {"updateCells": {
            "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
            "rows": all_rows,
            "fields": "userEnteredValue,userEnteredFormat"}},
        {"updateSheetProperties": {
            "properties": {"sheetId": sheet_id,
                           "gridProperties": {"frozenRowCount": 4}},
            "fields": "gridProperties.frozenRowCount"}},
        *[{"mergeCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": i, "endRowIndex": i+1,
                      "startColumnIndex": 0, "endColumnIndex": 6},
            "mergeType": "MERGE_ALL"}} for i in [0, 1]],
    ]
    for i, px in enumerate(col_widths):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i+1},
            "properties": {"pixelSize": px}, "fields": "pixelSize"}})

    r3 = s.post(f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
                headers={"Content-Type": "application/json"},
                data=json.dumps({"requests": reqs}))

    if r3.status_code == 200:
        print(f"✅ Меню готово: https://docs.google.com/spreadsheets/d/{ss_id}/edit")
    else:
        print(f"❌ {r3.status_code}: {r3.text[:300]}")


if __name__ == "__main__":
    main()
