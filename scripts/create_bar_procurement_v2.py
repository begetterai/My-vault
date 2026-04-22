#!/usr/bin/env python3
"""
Файл закупок Проекта «Бар» v2.
Учитывает имеющуюся посуду, объём хранения пива и алкоголя.
3 листа: Оборудование | Инвентарь | Стеклянная посуда
"""
import json, os
CREDENTIALS = os.path.join(os.path.dirname(__file__), "credentials", "romashka-drive.json")
FOLDER_ID   = "1u98T7m_J0Ly8yfKGpYkN_1M-nCKDea0e"

CLR_DARK  = {"red": 0.10, "green": 0.20, "blue": 0.35}
CLR_MID   = {"red": 0.18, "green": 0.32, "blue": 0.50}
CLR_WHITE = {"red": 1.00, "green": 1.00, "blue": 1.00}
CLR_HAVE  = {"red": 0.85, "green": 0.94, "blue": 0.85}
CLR_BUY   = {"red": 1.00, "green": 0.97, "blue": 0.82}
CLR_CRIT  = {"red": 1.00, "green": 0.90, "blue": 0.88}
FONT = "Times New Roman"


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


def blank(n):
    return {"values": [e() for _ in range(n)]}


# ─── ОБОРУДОВАНИЕ ─────────────────────────────────────────────────────────────
# (название, кол-во, ссылка, обоснование, примечание/статус)
EQUIPMENT = [
    (
        "Холодильный стол барный undercounter с рабочей поверхностью из нерж. стали (150–180 л)",
        1, "",
        "Рабочая зона бармена. Хранение: молоко 10 л, сливки 2 л, соки открытые, цитрусы 3–4 кг, гарниры, сиропы вскрытые. 150 л = стандарт на 1 рабочее место.",
        "⬜ Заказать"
    ),
    (
        "Морозильный стол барный undercounter (100–120 л)",
        1, "",
        "Мороженое для милкшейков, замороженные фрукты, заготовки. Рабочая поверхность — дополнительная зона.",
        "⬜ Заказать"
    ),
    (
        "Витринный холодильник барный вертикальный 3-дверный (600–700 л)",
        1, "",
        "Пиво: 10 видов × 24 бутылки = 240 бутылок. Вино белое/игристое: 15–20 бутылок. Водка (охлаждённая): 5 видов × 3 бутылки = 15 бутылок. Текила (охлаждённая): 4 вида × 2 бутылки = 8 бутылок. Итого ~280 бутылок → нужен объём от 600 л.",
        "⬜ Заказать"
    ),
    (
        "Ледогенератор кубиковый (30–50 кг/сутки)",
        1, "",
        "Без льда не работает ни один напиток. Расчёт: 150–200 г льда на порцию × 100 порций в день = 20–25 кг. Запас 30–50 кг/сут с учётом пиковой нагрузки.",
        "⬜ Заказать"
    ),
    (
        "Кофемашина рожковая полуавтомат 2-групповая",
        1, "",
        "10 кофейных позиций в меню. 2 группы — параллельное приготовление при очереди.",
        "⬜ Заказать"
    ),
    (
        "Кофемолка на зерно (под эспрессо)",
        1, "",
        "Помол перед приготовлением = качество. Обязательна при наличии кофемашины.",
        "⬜ Заказать"
    ),
    (
        "Темперовочная станция (коврик + тампер + игольчатый распределитель)",
        1, "",
        "Правильная подготовка таблетки кофе — прямо влияет на вкус эспрессо.",
        "⬜ Заказать"
    ),
    (
        "Бойлер / водонагреватель накопительный (8–10 л)",
        1, "",
        "Горячая вода для чаёв, рафа, горячих напитков. 8–10 л = достаточно для пиковой нагрузки (10–12 заварок подряд).",
        "⬜ Заказать"
    ),
    (
        "Блендер стационарный профессиональный (мощность от 1500 Вт)",
        1, "",
        "Милкшейки (4 позиции), возможно смузи. Бытовой не выдержит — нужен профессиональный с режимом дробления льда.",
        "⬜ Заказать"
    ),
]

# ─── ИНВЕНТАРЬ ────────────────────────────────────────────────────────────────
INVENTORY = [
    ("Boston Shaker нерж. (2 стакана)", 4, "", "Основной инструмент. 4 шт = 2 бармена работают одновременно."),
    ("Джиггер двойной 25/50 мл нерж.", 4, "", "Точный налив — стандарт рецептуры и контроль Food Cost."),
    ("Джиггер двойной 15/30 мл нерж.", 2, "", "Малые дозы: биттеры, ликёры."),
    ("Мадлер нерж. / деревянный", 4, "", "Мята, сахар, цитрус в коктейлях."),
    ("Барная ложка twisted 30 см нерж.", 4, "", "Смешивание, слои, декор."),
    ("Стрейнер Хоторна нерж.", 4, "", "Фильтрация льда из шейкера."),
    ("Файн стрейнер (мелкое сито) нерж.", 2, "", "Двойная фильтрация — чистые коктейли без крошки и мякоти."),
    ("Носики-поурер slow flow (для бутылок)", 20, "", "Контроль розлива сиропов и алкоголя. 1 на каждую открытую бутылку."),
    ("Питчер молочный 600 мл нерж.", 4, "", "Взбивание молока для кофе."),
    ("Питчер мерный 1 л нерж.", 2, "", "Замес больших порций."),
    ("Совок для льда (ice scoop) нерж.", 2, "", "Гигиенный набор льда — без рук."),
    ("Speed Rail / горка для бутылок настенная", 1, "", "Быстрый доступ к топовым бутылкам на рабочем месте."),
    ("Сквизер / ручная соковыжималка для цитрусов", 2, "", "Свежий сок лимона и лайма под коктейли и чаи."),
    ("Открывалка настенная + ручная", 3, "", "Настенная — на барную стойку, 2 ручных — в запас."),
    ("Штопор профессиональный sommelier", 2, "", "Вино в меню — 5 позиций + игристое."),
    ("Барный нож paring + чехол", 2, "", "Нарезка цитрусов и гарниров."),
    ("Разделочная доска малая HACCP пластик", 2, "", "Нарезка прямо на баре."),
    ("Диспенсер для сиропов (pump 10 мл)", 10, "", "1 насос = 10 мл — точность рецептуры. 10 шт = 10 видов сиропов."),
    ("Пинцет барный нерж.", 2, "", "Точная выкладка декора и гарниров."),
    ("Щипцы для льда нерж.", 4, "", "Гигиена при подаче льда."),
    ("Поднос подачи нескользящий прямоугольный", 4, "", "Подача к столам."),
    ("Коврик барный bar mat нерж./рез.", 2, "", "Сбор капель на стойке."),
    ("Контейнер для гарниров 6-ячейковый", 1, "", "Цедра, мята, вишня, лайм — всё под рукой."),
    ("Термометр молочный", 1, "", "Контроль взбивания молока: 60–65°C."),
    ("Темпер для кофе (58 мм)", 1, "", "Для кофемашины — если не входит в темперовочную станцию."),
]

# ─── СТЕКЛЯННАЯ ПОСУДА ────────────────────────────────────────────────────────
# (название, нужно_всего, уже_есть, к_покупке, ссылка, обоснование)
GLASSWARE = [
    # Имеется в наличии — не покупать
    ("Рокс (Old Fashioned) ~300 мл",
     144, 144, 0, "", "✅ ЕСТЬ 144 шт — достаточно. Виски, водка, ром на льду, шоты, короткие коктейли."),
    ("Чайник стеклянный заварочный 400–600 мл",
     20, 20, 0, "", "✅ ЕСТЬ 20 шт — достаточно. Подача горячих чаёв."),
    ("Чайник металлический 300–400 мл",
     30, 30, 0, "", "✅ ЕСТЬ 30 шт — достаточно. Подача горячих напитков."),
    ("Чайник (вид 3) — уточнить",
     20, 20, 0, "", "✅ ЕСТЬ 20 шт."),
    ("Чайник (вид 4) — уточнить",
     20, 20, 0, "", "✅ ЕСТЬ 20 шт."),
    ("Кувшин 1 л для соков и лимонадов",
     20, 20, 0, "", "✅ ЕСТЬ 20 шт — подача лимонадов/соков на стол."),
    ("Снифтер ~300 мл",
     24, 24, 0, "", "✅ ЕСТЬ 24 шт — виски neat, бренди, некоторые коктейли."),
    ("Гибралтар 250 мл",
     48, 48, 0, "", "✅ ЕСТЬ 48 шт — коктейли (все 250 мл), кортадо, маленькие порции."),

    # Нужно докупить
    ("Хайбол (Highball) 350–400 мл",
     60, 0, 60, "", "🛒 КУПИТЬ. Главный стакан бара: пиво в стакане, лимонады, длинные коктейли, чай в стакане."),
    ("Бокал красного вина 400–450 мл",
     30, 0, 30, "", "🛒 КУПИТЬ. 5 вин красных/полусладких в меню."),
    ("Бокал белого вина 280–300 мл",
     30, 0, 30, "", "🛒 КУПИТЬ. Белое вино, Совиньон, Рислинг."),
    ("Флюте / Шампанка 180–200 мл",
     20, 0, 20, "", "🛒 КУПИТЬ. Игристое вино (Санто Стефано, Брют), коктейль Белини."),
    ("Шот / Стопка 50 мл",
     40, 0, 40, "", "🛒 КУПИТЬ. Шоты текилы, водки, шотовые подачи."),
    ("Чашка эспрессо + блюдце 80–100 мл",
     20, 0, 20, "", "🛒 КУПИТЬ. Эспрессо, ристретто, доппио."),
    ("Чашка капучино + блюдце 200–250 мл",
     20, 0, 20, "", "🛒 КУПИТЬ. Капучино, латте, флэт уайт."),
]

COLS_EQ  = ["Оборудование", "Кол-во", "Ссылка", "Обоснование / Расчёт объёма", "Статус"]
COLS_INV = ["Инвентарь", "Кол-во", "Ссылка", "Обоснование"]
COLS_GL  = ["Вид посуды", "Нужно всего", "Есть сейчас", "Докупить", "Ссылка", "Примечание"]
EQ_WIDTHS  = [310, 60, 190, 330, 110]
INV_WIDTHS = [280, 60, 190, 320]
GL_WIDTHS  = [250, 80, 80, 80, 190, 290]


def build_equipment():
    rows = []
    A = rows.append
    nc = 5
    A(row(h("🔧 ОБОРУДОВАНИЕ", fs=17), *[e(CLR_DARK)] * (nc-1)))
    A(row(c("Пиво + водка + текила — в витринном холодильнике. Молоко/сливки/цитрусы — в холодильном столе.",
            italic=True, fs=11, bg=CLR_MID, fg=CLR_WHITE), *[e(CLR_MID)] * (nc-1)))
    A(blank(nc))
    A(row(*[h(col, fs=13) for col in COLS_EQ]))
    for название, кол, ссылка, обосн, статус in EQUIPMENT:
        A(row(c(название, fs=13), c(кол, align="CENTER", fs=13),
              c(ссылка, fs=12), c(обосн, fs=12, italic=True),
              c(статус, align="CENTER", fs=12)))
    A(blank(nc))
    A(row(c(f"Итого: {len(EQUIPMENT)} единиц оборудования", bold=True, fs=13),
          *[e()] * (nc-1)))
    return rows


def build_inventory():
    rows = []
    A = rows.append
    nc = 4
    A(row(h("🍸 ИНВЕНТАРЬ БАРМЕНА", fs=17), *[e(CLR_DARK)] * (nc-1)))
    A(row(c("Весь инвентарь — стандарт для работы бара с коктейльным и кофейным меню.",
            italic=True, fs=11, bg=CLR_MID, fg=CLR_WHITE), *[e(CLR_MID)] * (nc-1)))
    A(blank(nc))
    A(row(*[h(col, fs=13) for col in COLS_INV]))
    for название, кол, ссылка, обосн in INVENTORY:
        A(row(c(название, fs=13), c(кол, align="CENTER", fs=13),
              c(ссылка, fs=12), c(обосн, fs=12, italic=True)))
    A(blank(nc))
    A(row(c(f"Итого позиций: {len(INVENTORY)} | Единиц: {sum(x[1] for x in INVENTORY)}", bold=True, fs=13),
          *[e()] * (nc-1)))
    return rows


def build_glassware():
    rows = []
    A = rows.append
    nc = 6
    have_total = sum(x[2] for x in GLASSWARE)
    buy_total  = sum(x[3] for x in GLASSWARE)

    A(row(h("🥂 СТЕКЛЯННАЯ ПОСУДА", fs=17), *[e(CLR_DARK)] * (nc-1)))
    A(row(c(f"Имеется: {have_total} шт (Рокс, Гибралтар, Чайники, Кувшины, Снифтер) | Докупить: {buy_total} шт",
            italic=True, fs=11, bg=CLR_MID, fg=CLR_WHITE), *[e(CLR_MID)] * (nc-1)))
    A(blank(nc))
    A(row(*[h(col, fs=13) for col in COLS_GL]))

    for название, нужно, есть, купить, ссылка, примечание in GLASSWARE:
        bg = CLR_HAVE if купить == 0 else CLR_BUY
        A(row(c(название, fs=13, bg=bg),
              c(нужно, align="CENTER", fs=13, bg=bg),
              c(есть,  align="CENTER", fs=13, bg=bg,
                fg={"red": 0.10, "green": 0.40, "blue": 0.10} if есть > 0 else None),
              c(купить, align="CENTER", fs=13, bg=bg,
                fg={"red": 0.70, "green": 0.10, "blue": 0.10} if купить > 0 else None,
                bold=купить > 0),
              c(ссылка, fs=12, bg=bg),
              c(примечание, fs=12, italic=True, bg=bg)))

    A(blank(nc))
    A(row(c("ИТОГО К ПОКУПКЕ:", bold=True, fs=13),
          e(), e(),
          c(buy_total, bold=True, align="CENTER", fs=14,
            fg={"red": 0.70, "green": 0.10, "blue": 0.10}),
          *[e()] * 2))
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
    print("Создаём файл закупок v2...")
    r = s.post(
        "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "name": "Проект «Бар» — Закупки (Оборудование · Инвентарь · Посуда)",
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [FOLDER_ID]
        }))
    ss_id = r.json()["id"]
    print(f"ID: {ss_id}")

    r2 = s.get(f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}?fields=sheets.properties")
    first_id = r2.json()["sheets"][0]["properties"]["sheetId"]

    sheet_defs = [
        ("Оборудование", build_equipment,  EQ_WIDTHS),
        ("Инвентарь",    build_inventory,  INV_WIDTHS),
        ("Посуда",       build_glassware,  GL_WIDTHS),
    ]

    rename_reqs = [{"updateSheetProperties": {
        "properties": {"sheetId": first_id, "title": sheet_defs[0][0]},
        "fields": "title"}}]
    for title, _, _ in sheet_defs[1:]:
        rename_reqs.append({"addSheet": {"properties": {"title": title}}})

    s.post(f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
           headers={"Content-Type": "application/json"},
           data=json.dumps({"requests": rename_reqs}))

    r3 = s.get(f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}?fields=sheets.properties")
    id_map = {sh["properties"]["title"]: sh["properties"]["sheetId"]
              for sh in r3.json()["sheets"]}

    all_reqs = []
    for title, builder, widths in sheet_defs:
        sid = id_map[title]
        sheet_rows = builder()
        nc = len(widths)
        all_reqs += [
            {"updateCells": {
                "start": {"sheetId": sid, "rowIndex": 0, "columnIndex": 0},
                "rows": sheet_rows,
                "fields": "userEnteredValue,userEnteredFormat"}},
            {"updateSheetProperties": {
                "properties": {"sheetId": sid,
                               "gridProperties": {"frozenRowCount": 4}},
                "fields": "gridProperties.frozenRowCount"}},
            *[{"mergeCells": {
                "range": {"sheetId": sid, "startRowIndex": i, "endRowIndex": i+1,
                          "startColumnIndex": 0, "endColumnIndex": nc},
                "mergeType": "MERGE_ALL"}} for i in [0, 1]],
        ]
        for i, px in enumerate(widths):
            all_reqs.append({"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS",
                          "startIndex": i, "endIndex": i+1},
                "properties": {"pixelSize": px}, "fields": "pixelSize"}})

    r4 = s.post(f"https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate",
                headers={"Content-Type": "application/json"},
                data=json.dumps({"requests": all_reqs}))

    if r4.status_code == 200:
        print(f"✅ Готово: https://docs.google.com/spreadsheets/d/{ss_id}/edit")
    else:
        print(f"❌ {r4.status_code}: {r4.text[:300]}")


if __name__ == "__main__":
    main()
