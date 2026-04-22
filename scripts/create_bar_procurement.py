#!/usr/bin/env python3
"""
Создать файл закупок для Проекта «Бар» в Drive HoReCa.
3 листа: Оборудование | Инвентарь | Стеклянная посуда
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))

CREDENTIALS = os.path.join(os.path.dirname(__file__), "credentials", "romashka-drive.json")
FOLDER_ID   = "1u98T7m_J0Ly8yfKGpYkN_1M-nCKDea0e"  # Проект «Бар»

CLR_DARK  = {"red": 0.18, "green": 0.18, "blue": 0.30}   # тёмно-синий заголовок
CLR_MID   = {"red": 0.28, "green": 0.28, "blue": 0.45}   # средний
CLR_SEC   = {"red": 0.22, "green": 0.35, "blue": 0.55}   # секция
CLR_WHITE = {"red": 1.00, "green": 1.00, "blue": 1.00}
CLR_DONE  = {"red": 0.85, "green": 0.94, "blue": 0.85}
CLR_WARN  = {"red": 1.00, "green": 0.97, "blue": 0.82}
CLR_SUB   = {"red": 0.95, "green": 0.95, "blue": 0.98}
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
    return c(v, bold=True, bg=CLR_SEC, fs=13, fg=CLR_WHITE)


def e(bg=None):
    return c("", bg=bg)


def row(*cells):
    return {"values": list(cells)}


def blank(n=5):
    return {"values": [e() for _ in range(n)]}


# ─── ДАННЫЕ ────────────────────────────────────────────────────────────────────

EQUIPMENT = [
    # (название, кол-во, ссылка, обоснование)
    (
        "Холодильный стол барный (undercounter) с рабочей поверхностью из нерж. стали",
        1, "",
        "Основная барная линия — слева. Хранение скоропортящихся: соки, молоко, фреши, топпинги. Рабочая поверхность — основная зона приготовления напитков."
    ),
    (
        "Морозильный стол барный (undercounter)",
        1, "",
        "Барная линия — правая зона. Хранение замороженных ингредиентов, мороженого, заготовок. Двойная функция: хранение + рабочая поверхность."
    ),
    (
        "Ледогенератор кубиковый (куб или крошка, 30–50 кг/сутки)",
        1, "",
        "Критичное оборудование — без льда не работает ни один напиток. Размещение: отдельная зона по плану помещения."
    ),
    (
        "Бойлер / водонагреватель проточный или накопительный (от 5 л)",
        1, "",
        "Горячая вода для чаёв, раф-кофе, горячих напитков. Расположение: рядом с кофемашиной."
    ),
    (
        "Кофемашина рожковая полуавтомат (2-групповая)",
        1, "",
        "Приготовление эспрессо, капучино, латте, рафа — ключевая часть меню. 2 группы нужны при одновременном обслуживании нескольких гостей."
    ),
    (
        "Кофемолка под эспрессо (на зерно)",
        1, "",
        "Обязательна при наличии кофемашины — помол непосредственно перед приготовлением = качество вкуса. Размещение рядом с кофемашиной."
    ),
    (
        "Темперовочная станция (коврик, тампер, дозатор)",
        1, "",
        "Правильная подготовка кофейной таблетки — прямо влияет на вкус эспрессо. Стационарная точка у кофемашины."
    ),
    (
        "Холодильник барный витринный вертикальный (для напитков в бутылках)",
        1, "",
        "Выкладка и хранение безалкогольных напитков, соков в бутылках. Работает как точка продажи: гость видит ассортимент."
    ),
    (
        "Блендер стационарный профессиональный (Blendjet / Vitamix класс)",
        1, "",
        "Смузи, фраппе, молочные коктейли, измельчение льда. Необходим для холодных напитков на основе льда."
    ),
]

INVENTORY = [
    # (название, кол-во, ссылка, обоснование)
    ("Boston Shaker (стакан + стакан, нерж.)", 4, "", "Основной инструмент шейкера. 4 шт — работа двух барменов одновременно."),
    ("Джиггер двойной 25/50 мл нерж.", 4, "", "Точное измерение ингредиентов — стандарт качества и Food Cost."),
    ("Джиггер двойной 15/30 мл нерж.", 2, "", "Для малых доз (биттеры, ликёры)."),
    ("Мадлер деревянный / нерж.", 4, "", "Мятый сахар, цедра, ягоды в напитках."),
    ("Барная ложка (twisted, 30 см) нерж.", 4, "", "Смешивание, слои, украшение."),
    ("Стрейнер Хоторна нерж.", 4, "", "Фильтрация льда при переливании из шейкера."),
    ("Файн стрейнер (мелкое сито) нерж.", 2, "", "Двойная фильтрация для чистых коктейлей — убирает крошку льда и мякоть."),
    ("Носики-поурер для бутылок (slow flow)", 20, "", "Контроль розлива сиропов и ликёров, скорость работы."),
    ("Питчер для молока (600 мл) нерж.", 4, "", "Взбивание молока для кофейных напитков."),
    ("Питчер мерный (1 л) нерж.", 2, "", "Замес больших порций, отмер воды."),
    ("Совок для льда (ice scoop) нерж.", 2, "", "Безопасный набор льда — гигиена, без рук."),
    ("Горка для бутылок / Speed Rail настенная", 1, "", "Быстрый доступ к основным бутылкам на рабочем месте бармена."),
    ("Открывалка для бутылок (настенная + ручная)", 3, "", "Настенная — на барную стойку, ручные — в запас."),
    ("Штопор профессиональный (sommelier knife)", 2, "", "Открытие вина."),
    ("Барный нож (paring knife) + защитный чехол", 2, "", "Нарезка цитрусов, гарниры."),
    ("Разделочная доска маленькая (пластик HACCP)", 2, "", "Нарезка гарниров прямо на барной стойке."),
    ("Соковыжималка ручная для цитрусов", 2, "", "Свежий сок лимона/лайма/апельсина без покупки готового."),
    ("Диспенсер для сиропов (pump 1 cl)", 8, "", "Точный розлив сиропов — по 1 насосу ≈ 10 мл, стандарт рецептуры."),
    ("Ведро для льда с щипцами (для гостей)", 4, "", "Подача льда к напиткам на стол."),
    ("Щипцы для льда нерж.", 4, "", "Подача льда, гигиена."),
    ("Пинцет барный нерж.", 2, "", "Точная выкладка гарниров и украшений."),
    ("Поднос для подачи (прямоугольный, нескользящий)", 4, "", "Подача напитков к столу."),
    ("Коврик барный (bar mat, нерж./рез.)", 2, "", "На барную стойку — сбор капель, эстетика."),
    ("Контейнеры для гарниров (6-ячейковый)", 1, "", "Хранение нарезанных гарниров на барной стойке — цедра, вишня, мята."),
    ("Щётка для мытья стаканов (glasswasher brush)", 1, "", "Быстрая ручная мойка стаканов на баре."),
    ("Таймер цифровой", 1, "", "Контроль экстракции кофе, заваривания чая."),
    ("Термометр барный / молочный", 1, "", "Контроль температуры молока при взбивании (60–65°C)."),
]

GLASSWARE = [
    # (название, кол-во, ссылка, обоснование)
    ("Стакан Рокс (Old Fashioned, 300 мл)", 40, "", "Коктейли со льдом, виски, алкогольные шоты."),
    ("Стакан Хайбол (Highball, 350–400 мл)", 60, "", "Основной стакан для длинных напитков: лимонады, мохито, тоники. Самый ходовой."),
    ("Стакан Коллинз (Collins, 450–500 мл)", 30, "", "Большие освежающие напитки, фреши, смузи."),
    ("Бокал для красного вина (350–450 мл)", 30, "", "Подача вина."),
    ("Бокал для белого вина (250–300 мл)", 30, "", "Подача вина и лёгких коктейлей."),
    ("Флюте / Бокал для шампанского (180–200 мл)", 20, "", "Игристые напитки, шампанское, просекко."),
    ("Бокал Маргарита (300 мл)", 15, "", "Коктейли формата маргарита, дайкири."),
    ("Шот / Стопка (50 мл)", 40, "", "Шоты, бомбочки, дегустации."),
    ("Чайник заварочный (400–600 мл)", 20, "", "Подача чаёв. Количество = пиковая нагрузка."),
    ("Кружка для горячих напитков (300–350 мл)", 40, "", "Чай, глинтвейн, горячий шоколад."),
    ("Чашка эспрессо + блюдце (80–100 мл)", 20, "", "Эспрессо, ристретто."),
    ("Чашка капучино + блюдце (200–250 мл)", 20, "", "Капучино, латте, флэт уайт."),
]


# ─── ПОСТРОЕНИЕ ЛИСТА ─────────────────────────────────────────────────────────

COLS_5 = ["Полное название", "Кол-во", "Ссылка", "Обоснование", "Примечание / Статус"]
COL_WIDTHS = [320, 65, 200, 320, 160]


def build_sheet(title_label, data, note_col=True):
    rows = []
    A = rows.append
    ncols = 5

    # Шапка
    A(row(h(title_label, fs=17), *[e(CLR_DARK)] * (ncols - 1)))
    A(row(c("Файл актуален на 21.04.2026 — обновлять по мере закупок",
            italic=True, fs=11, bg=CLR_MID, fg=CLR_WHITE),
          *[e(CLR_MID)] * (ncols - 1)))
    A(blank(ncols))
    A(row(*[h(col, fs=13) for col in COLS_5]))

    for название, кол_во, ссылка, обоснование in data:
        A(row(
            c(название, fs=13, wrap=True),
            c(кол_во, align="CENTER", fs=13),
            c(ссылка, fs=12, fg={"red": 0.15, "green": 0.30, "blue": 0.70}),
            c(обоснование, fs=12, italic=True, wrap=True),
            c("⬜ Не закуплено", align="CENTER", fs=12),
        ))

    A(blank(ncols))
    A(row(
        c(f"Итого позиций: {len(data)}", bold=True, fs=13),
        c(f"Итого ед.: {sum(x[1] for x in data)}", bold=True, fs=13, align="CENTER"),
        *[e()] * (ncols - 2),
    ))

    return rows


def make_requests(sheet_id, rows, col_widths, frozen_rows=4):
    reqs = [
        {
            "updateCells": {
                "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
                "rows": rows,
                "fields": "userEnteredValue,userEnteredFormat"
            }
        },
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id,
                               "gridProperties": {"frozenRowCount": frozen_rows}},
                "fields": "gridProperties.frozenRowCount"
            }
        },
        # Merge header rows
        *[{"mergeCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": i,
                      "endRowIndex": i + 1, "startColumnIndex": 0, "endColumnIndex": 5},
            "mergeType": "MERGE_ALL"}} for i in [0, 1]],
    ]
    for i, px in enumerate(col_widths):
        reqs.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                          "startIndex": i, "endIndex": i + 1},
                "properties": {"pixelSize": px},
                "fields": "pixelSize"
            }
        })
    return reqs


def get_session():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS,
        scopes=["https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"])
    return AuthorizedSession(creds)


def main():
    print("Авторизация...")
    session = get_session()

    print("Создаём файл...")
    body = {
        "name": "Проект «Бар» — Закупки (Оборудование · Инвентарь · Посуда)",
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [FOLDER_ID]
    }
    r = session.post(
        "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
        headers={"Content-Type": "application/json"},
        data=json.dumps(body))
    ss_id = r.json()["id"]
    print(f"Файл создан: {ss_id}")

    # Получаем sheetId первого листа
    r = session.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}?fields=sheets.properties")
    sheets = r.json()["sheets"]
    first_id = sheets[0]["properties"]["sheetId"]

    sheet_defs = [
        ("Оборудование", EQUIPMENT),
        ("Инвентарь",    INVENTORY),
        ("Посуда",       GLASSWARE),
    ]

    # Переименуем первый лист и добавим ещё два
    rename_reqs = [{"updateSheetProperties": {
        "properties": {"sheetId": first_id, "title": sheet_defs[0][0]},
        "fields": "title"}}]
    for title, _ in sheet_defs[1:]:
        rename_reqs.append({"addSheet": {"properties": {"title": title}}})

    r2 = session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": rename_reqs}))

    # Получаем актуальные sheetId
    r3 = session.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}?fields=sheets.properties")
    id_map = {s["properties"]["title"]: s["properties"]["sheetId"]
              for s in r3.json()["sheets"]}
    print(f"Листы: {id_map}")

    # Заполняем каждый лист
    all_reqs = []
    for title, data in sheet_defs:
        sid = id_map[title]
        sheet_rows = build_sheet(f"{'🔧' if title=='Оборудование' else ('🍸' if title=='Инвентарь' else '🥂')} {title.upper()}", data)
        all_reqs.extend(make_requests(sid, sheet_rows, COL_WIDTHS))

    r4 = session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": all_reqs}))

    if r4.status_code == 200:
        print(f"✅ Готово!")
        print(f"https://docs.google.com/spreadsheets/d/{ss_id}/edit")
    else:
        print(f"❌ {r4.status_code}: {r4.text[:400]}")


if __name__ == "__main__":
    main()
