#!/usr/bin/env python3
"""
Создать To-Do таблицу проекта Лаунж-Бар в Drive.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))

CREDENTIALS = os.path.join(os.path.dirname(__file__), "credentials", "romashka-drive.json")
FOLDER_ID   = "19rwzlgcV9z6-m1FKZznaOGXaElMBa2oV"  # 07_РАЗВИТИЕ

CLR_DARK   = {"red": 0.18, "green": 0.31, "blue": 0.18}
CLR_MID    = {"red": 0.24, "green": 0.42, "blue": 0.24}
CLR_DONE   = {"red": 0.85, "green": 0.94, "blue": 0.85}
CLR_NEXT   = {"red": 1.00, "green": 0.97, "blue": 0.82}
CLR_BLOCK  = {"red": 0.99, "green": 0.87, "blue": 0.87}
CLR_SUB    = {"red": 0.93, "green": 0.93, "blue": 0.93}
CLR_WHITE  = {"red": 1.00, "green": 1.00, "blue": 1.00}
CLR_P1     = {"red": 0.90, "green": 0.20, "blue": 0.20}
CLR_P2     = {"red": 0.95, "green": 0.60, "blue": 0.10}
CLR_P3     = {"red": 0.30, "green": 0.60, "blue": 0.30}
FONT = "Times New Roman"


def c(v, bold=False, bg=None, align="LEFT", fs=13, fg=None, italic=False, wrap=True):
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
    return {"userEnteredValue": uv, "userEnteredFormat": fmt}


def h(v, bg=None, fs=16, align="CENTER"):
    return c(v, bold=True, bg=bg or CLR_DARK, align=align, fs=fs, fg=CLR_WHITE)


def sec(v):
    return c(v, bold=True, bg=CLR_MID, fs=14, fg=CLR_WHITE)


def e(bg=None):
    return c("", bg=bg)


def row(*cells):
    return {"values": list(cells)}


def blank():
    return {"values": [e() for _ in range(7)]}


# Статусы: ✅ Сделано | 🔄 В процессе | ⬜ Не начато | ⛔ Заблокировано
TASKS = [
    # (блок, задача, приоритет, статус, примечание)

    # БЛОК 1 — КОНЦЕПЦИЯ
    ("1. Концепция", "Определить формат бара: коктейльный / кофейный / чайный / алкогольный / микс", "p1", "⬜", "Ключевое решение — всё остальное из него"),
    ("1. Концепция", "Определить целевую аудиторию: возраст, портрет гостя, средний чек", "p1", "⬜", ""),
    ("1. Концепция", "Анализ конкурентов: что есть в Душанбе, цены, слабые места", "p1", "⬜", ""),
    ("1. Концепция", "Зафиксировать концепцию в документе: название, атмосфера, УТП", "p1", "⬜", ""),
    ("1. Концепция", "Определить режим работы: часы, дни, сезонность", "p2", "⬜", ""),

    # БЛОК 2 — ЭКОНОМИКА
    ("2. Экономика", "Финмодель: первоначальные вложения (оборудование, ремонт, депозит)", "p1", "⬜", ""),
    ("2. Экономика", "Финмодель: ежемесячные расходы (аренда, ФОТ, COGS)", "p1", "⬜", ""),
    ("2. Экономика", "Прогноз выручки: средний чек × гостей в день × дни", "p1", "⬜", ""),
    ("2. Экономика", "Точка безубыточности и срок окупаемости", "p1", "⬜", ""),
    ("2. Экономика", "Food/Drink Cost цель: напитки — до 25%, еда — до 32%", "p2", "⬜", ""),

    # БЛОК 3 — ПОМЕЩЕНИЕ И ЮРИДИКА
    ("3. Помещение", "Подтвердить помещение: площадь, состояние, что уже есть", "p1", "⬜", "Есть ли уже договор аренды?"),
    ("3. Помещение", "Проверить договор аренды: условия, срок, право на ремонт", "p1", "⬜", ""),
    ("3. Помещение", "Уточнить нужна ли лицензия на алкоголь (если он будет)", "p1", "⬜", "Ключевой вопрос для формата"),
    ("3. Помещение", "Замер помещения, схема расстановки бара и посадочных мест", "p2", "⬜", ""),
    ("3. Помещение", "Оценить объём ремонта и стоимость", "p2", "⬜", ""),

    # БЛОК 4 — ОБОРУДОВАНИЕ
    ("4. Оборудование", "Составить список оборудования под формат (барная стойка, холодильник, кофемашина, ледогенератор...)", "p1", "⬜", ""),
    ("4. Оборудование", "Запросить цены у поставщиков / найти б/у", "p1", "⬜", ""),
    ("4. Оборудование", "Выбрать поставщиков и согласовать покупку", "p2", "⬜", ""),
    ("4. Оборудование", "Закупка и доставка оборудования", "p2", "⬜", ""),
    ("4. Оборудование", "Монтаж и подключение", "p2", "⬜", ""),

    # БЛОК 5 — МЕНЮ
    ("5. Меню", "Разработать концепцию меню: категории, количество позиций", "p1", "⬜", ""),
    ("5. Меню", "Написать рецептуры на каждую позицию (техкарты)", "p1", "⬜", ""),
    ("5. Меню", "Рассчитать себестоимость каждой позиции", "p1", "⬜", ""),
    ("5. Меню", "Установить цены с учётом маржи и рынка", "p1", "⬜", ""),
    ("5. Меню", "Ввести позиции в Poster (склад, техкарты, списания)", "p2", "⬜", ""),
    ("5. Меню", "Фотосессия блюд/напитков для меню и SMM", "p3", "⬜", ""),

    # БЛОК 6 — ПЕРСОНАЛ
    ("6. Персонал", "Определить штат: сколько бариста/барменов нужно", "p1", "⬜", ""),
    ("6. Персонал", "Написать SOP бармена/бариста лаунж", "p1", "⬜", ""),
    ("6. Персонал", "Нанять и обучить персонал", "p1", "⬜", ""),
    ("6. Персонал", "Разработать систему мотивации (ставка + % с выручки?)", "p2", "⬜", ""),
    ("6. Персонал", "Ввести сотрудников в Poster", "p2", "⬜", ""),

    # БЛОК 7 — ЗАПУСК
    ("7. Запуск", "Мягкое открытие (soft launch) для проверки системы", "p1", "⬜", ""),
    ("7. Запуск", "Пост-открытие: собрать обратную связь, скорректировать меню", "p1", "⬜", ""),
    ("7. Запуск", "Маркетинг: анонс в соцсетях, сторис, офферы", "p2", "⬜", ""),
    ("7. Запуск", "Полноценное открытие", "p2", "⬜", ""),
    ("7. Запуск", "Первый месяц: трекинг выручки, Food Cost, гостей в день", "p2", "⬜", ""),
]

PRIO_COLORS = {"p1": CLR_P1, "p2": CLR_P2, "p3": CLR_P3}
PRIO_LABELS = {"p1": "🔴 P1", "p2": "🟡 P2", "p3": "🟢 P3"}
STATUS_BG = {
    "✅": CLR_DONE,
    "🔄": CLR_NEXT,
    "⬜": None,
    "⛔": CLR_BLOCK,
}

COLS = ["Блок", "Задача", "Приоритет", "Статус", "Ответственный", "Дедлайн", "Примечание"]


def build_rows():
    rows = []
    A = rows.append

    # Шапка
    A(row(h("ЛАУНЖ-БАР — ПЛАН ЗАПУСКА", fs=18),
          *[e(CLR_DARK)] * 6))
    A(row(h("Сеть кафе Ромашка | Трекер задач", fs=13, bg=CLR_MID),
          *[e(CLR_MID)] * 6))
    A(row(c("Статусы:  ✅ Сделано   🔄 В процессе   ⬜ Не начато   ⛔ Заблокировано",
            italic=True, fs=12), *[e()] * 6))
    A(blank())
    A(row(*[h(col, fs=14) for col in COLS]))

    current_block = None
    for блок, задача, приоритет, статус, примечание in TASKS:
        if блок != current_block:
            current_block = блок
            A(row(sec(блок), *[e(CLR_MID)] * 6))

        bg = STATUS_BG.get(статус)
        A(row(
            c(блок, bg=bg, fs=13),
            c(задача, bg=bg, fs=13),
            c(PRIO_LABELS[приоритет], bold=True, bg=bg, align="CENTER", fs=13,
              fg=PRIO_COLORS[приоритет]),
            c(статус, align="CENTER", bg=bg, fs=14),
            c("", bg=bg),          # ответственный
            c("", bg=bg),          # дедлайн
            c(примечание, bg=bg, italic=bool(примечание), fs=12),
        ))

    A(blank())
    A(row(c("Итого задач:", bold=True),
          c(f"{len(TASKS)} задач в 7 блоках", italic=True),
          *[e()] * 5))

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
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession

    print("Авторизация...")
    session = get_session()

    print("Создаём файл...")
    body = {
        "name": "Лаунж-Бар — План запуска",
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [FOLDER_ID]
    }
    r = session.post(
        "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
        headers={"Content-Type": "application/json"},
        data=json.dumps(body))
    ss_id = r.json()["id"]
    print(f"Создан: {ss_id}")

    # Получаем sheetId
    r = session.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}?fields=sheets.properties")
    sheet_id = r.json()["sheets"][0]["properties"]["sheetId"]

    # Переименовываем лист
    session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "title": "To-Do"},
            "fields": "title"}}]}))

    all_rows = build_rows()
    print(f"Строк: {len(all_rows)}")

    col_widths = [160, 380, 85, 75, 130, 100, 220]

    requests = [
        {
            "updateCells": {
                "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
                "rows": all_rows,
                "fields": "userEnteredValue,userEnteredFormat"
            }
        },
        # Заморозить шапку
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id,
                               "gridProperties": {"frozenRowCount": 5}},
                "fields": "gridProperties.frozenRowCount"
            }
        },
        # Merge заголовочных строк
        *[{"mergeCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": i,
                      "endRowIndex": i + 1, "startColumnIndex": 0, "endColumnIndex": 7},
            "mergeType": "MERGE_ALL"}} for i in [0, 1, 2]],
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

    r2 = session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": requests}))

    if r2.status_code == 200:
        print(f"✅ Готово!")
        print(f"https://docs.google.com/spreadsheets/d/{ss_id}/edit")
    else:
        print(f"❌ {r2.status_code}: {r2.text[:300]}")


if __name__ == "__main__":
    main()
