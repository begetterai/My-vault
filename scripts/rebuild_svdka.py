#!/usr/bin/env python3
"""
Пересборка листа «Сводка» в ФОТ 04.2026.
Структура: ЗБ Производство | ОВИР Производство | Администрация | Итоги | Флаги
"""

import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))

CREDENTIALS = os.path.join(os.path.dirname(__file__), "credentials", "romashka-drive.json")
SS_ID = "1geMH__Xc32aLE9QabLjSXxgY_VFJah_d8ekL6uSkWDk"
SHEET_TITLE = "Сводка"

# ── Цвета ─────────────────────────────────────────────────────────────────────
CLR_DARK  = {"red": 0.18, "green": 0.31, "blue": 0.18}
CLR_MID   = {"red": 0.24, "green": 0.42, "blue": 0.24}
CLR_SUB   = {"red": 0.75, "green": 0.88, "blue": 0.75}
CLR_WARN  = {"red": 1.00, "green": 0.93, "blue": 0.70}
CLR_FLAG  = {"red": 1.00, "green": 0.80, "blue": 0.80}
CLR_RED   = {"red": 0.70, "green": 0.15, "blue": 0.15}
CLR_WHITE = {"red": 1.00, "green": 1.00, "blue": 1.00}
CLR_GREY  = {"red": 0.96, "green": 0.96, "blue": 0.96}
FONT = "Times New Roman"

# ── Ячейки ────────────────────────────────────────────────────────────────────
def c(v, bold=False, italic=False, bg=None, align="LEFT", fs=14, fg=None, num_fmt=None):
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
    if num_fmt:
        fmt["numberFormat"] = {"type": "NUMBER", "pattern": num_fmt}
    return {"userEnteredValue": uv, "userEnteredFormat": fmt}


def n(v, bold=False, bg=None, fs=14, fg=None):
    return c(v, bold=bold, bg=bg, align="RIGHT", fs=fs, fg=fg, num_fmt="# ##0")


def h(v, bg=None, fs=18, align="CENTER"):
    return c(v, bold=True, bg=bg or CLR_DARK, align=align, fs=fs, fg=CLR_WHITE)


def sec(v, fs=15):
    return c(v, bold=True, bg=CLR_MID, fs=fs, fg=CLR_WHITE)


def e(bg=None):
    return c("", bg=bg)


def row(*cells):
    return {"values": list(cells)}


def blank(bg=None):
    return {"values": [e(bg) for _ in range(8)]}


# ── Данные: ЗБ производство ───────────────────────────────────────────────────
ZB_STAFF = [
    ("Заготовщик",    "Шарипов Азиз",     2250, ""),
    ("Заготовщик",    "Шахнозаи Джума",   2150, ""),
    ("Заготовщик",    "Абдиев Окил",      2000, ""),
    ("Старший повар", "Джалилов Акбар",   1420, ""),
    ("Старший повар", "Ятимов Бобокалон", 1460, ""),
    ("Повар",         "Джобиров",          880, ""),
    ("Повар",         "Саримсоков",       1290, ""),
    ("Повар",         "Низовмов",         1184, ""),
    ("Повар",         "Бобокалонов",      1040, ""),
    ("Повар",         "Ориф",             1280, ""),
    ("Уборщица",      "Тошева",           1400, ""),
    ("Уборщица",      "Зебо",             1700, ""),
    ("Бариста",       "Файзалли",         1360, ""),
    ("Бариста",       "Саидо",             720, ""),
    ("Кассир",        "Фаёзова Нигина",   1350, "⚠️ числится также на ОВИР"),
    ("Кассир",        "Валерия",          1370, ""),
]
ZB_TOT = (22854, 3742, 228, 18884)  # начислено, аванс, штраф, к выдаче

# ── Данные: ОВИР производство ─────────────────────────────────────────────────
OVIR_STAFF = [
    ("Старший повар", "Шахром",            1650, ""),
    ("Старший повар", "Диёрбек",           1660, ""),
    ("Повар",         "Рукия",              960, ""),
    ("Повар",         "Мансур",            1248, ""),
    ("Повар",         "Абубакр",            931, ""),
    ("Повар",         "Шахбоз",            1296, ""),
    ("Повар",         "Асила",             1160, ""),
    ("Повар",         "Мухаммад",           880, ""),
    ("Уборщица",      "Махтоб",            1500, ""),
    ("Уборщица",      "Мавчуда",           1500, ""),
    ("Бариста",       "Исматзода",         1550, ""),
    ("Бариста",       "Асема",              960, ""),
    ("Кассир",        "Фаёзова Нигина",    1350, "⚠️ числится также на ЗБ — вероятно дубль"),
    ("Кассир",        "Муллабаев Махмуд",  1930, "⚠️ также ассистент ЗБ+ОВИР — итого 3430с"),
    ("Кассир",        "Муслима",            990, ""),
]
OVIR_TOT = (19565, 1896, 680, 14999)

# ── Данные: администрация ────────────────────────────────────────────────────
ADMIN_ZB = [
    ("Хайдаров Азиз",    "Директор",      "ЗБ",   3000, "⚠️ начислен также на ОВИР — платить 1 раз"),
    ("Митюков Владимир", "Управляющий",   "ЗБ",   2000, ""),
    ("Митюков Владимир", "Калькулятор",   "ЗБ",    500, "⚠️ калькулятор начислен и на ОВИР"),
    ("Фируз",            "Адм. персонал", "ЗБ",    750, "⚠️ числится на обеих точках — уточнить"),
    ("Фарангис",         "Адм. персонал", "ЗБ",    500, "⚠️ числится на обеих точках — уточнить"),
    ("Муллабаев Махмуд", "Ассистент",     "ЗБ",    550, "⚠️ также кассир ОВИР + ассистент ОВИР"),
    ("Мавлюда",          "Адм. персонал", "ЗБ",    150, "⚠️ числится на обеих точках — уточнить"),
]
ZB_ADM_TOT = (7450, 4450)

ADMIN_OVIR = [
    ("Хайдаров Азиз",     "Директор",      "ОВИР", 3000, "🔴 ДУБЛЬ — уже начислен на ЗБ"),
    ("Рахматуллаев Дилчу","Управляющий",   "ОВИР", 2000, ""),
    ("Рахматуллаев Дилчу","Доплата",       "ОВИР", 1400, ""),
    ("Митюков Владимир",  "Калькулятор",   "ОВИР",  500, "🔴 ДУБЛЬ — уже начислен на ЗБ"),
    ("Фируз",             "Адм. персонал", "ОВИР",  750, "⚠️ ДУБЛЬ?"),
    ("Фарангис",          "Адм. персонал", "ОВИР",  500, "⚠️ ДУБЛЬ?"),
    ("Муллабаев Махмуд",  "Ассистент",     "ОВИР",  950, "🔴 ДУБЛЬ — итого по 3 позициям: 3430с"),
    ("Мавлюда",           "Адм. персонал", "ОВИР",  150, "⚠️ ДУБЛЬ?"),
]
OVIR_ADM_TOT = (9250, 8404)

FLAGS = [
    ("🔴 1", "Фаёзова Нигина",
     "Кассир ЗБ (1350с) + кассир ОВИР (1350с) = 2700с. 30 смен за 15 дней — невозможно.",
     "Одна ставка? Уточнить перед выплатой."),
    ("🔴 2", "Муллабаев Махмуд",
     "Ассистент ЗБ (550) + Кассир ОВИР (1930) + Ассистент ОВИР (950) = 3430с.",
     "Три позиции одновременно. Проверить реальную занятость."),
    ("🔴 3", "Хайдаров Азиз",
     "Директор начислен на ЗБ (3000с) И на ОВИР (3000с) = 6000с итого.",
     "Подтверждено: платить 1 раз. Убрать дубль перед выплатой."),
    ("🟡 4", "Митюков Владимир",
     "Калькулятор начислен на ЗБ (500с) + ОВИР (500с) = 1000с.",
     "Он реально ведёт обе точки? Или ошибка копирования?"),
    ("🟡 5", "Фируз / Фарангис / Мавлюда",
     "Каждый начислен на ЗБ и ОВИР с одинаковой суммой.",
     "Работают на двух точках или ошибка дублирования?"),
]

# ── Сборка листа ─────────────────────────────────────────────────────────────
def build_rows():
    rows = []
    A = rows.append
    COLS = ["Должность", "ФИО", "Точка", "Начислено", "Аванс", "Штраф", "К выдаче", "Примечание"]

    # Заголовок
    A(row(h("ФОТ — АПРЕЛЬ 2026 — СВОДНЫЙ ОТЧЁТ", fs=20),
          *[e(CLR_DARK)] * 7))
    A(blank())

    # Производство — ЗБ и ОВИР
    for label, staff, tot, pt in [
        ("ПРОИЗВОДСТВО — ТОЧКА ЗБ (Лохути)", ZB_STAFF, ZB_TOT, "ЗБ"),
        ("ПРОИЗВОДСТВО — ТОЧКА ОВИР (Турсунзода)", OVIR_STAFF, OVIR_TOT, "ОВИР"),
    ]:
        A(row(sec(label), *[e(CLR_MID)] * 7))
        A(row(*[h(col) for col in COLS]))
        for должность, фио, нач, флаг in staff:
            bg = CLR_WARN if флаг else None
            A(row(c(должность, bg=bg), c(фио, bg=bg),
                  c(pt, bg=bg, align="CENTER"), n(нач, bg=bg),
                  e(bg), e(bg), e(bg),
                  c(флаг, bg=bg, italic=bool(флаг))))
        нач, авн, шт, выд = tot
        A(row(c(f"ИТОГО {pt} — производство", bold=True, bg=CLR_SUB),
              e(CLR_SUB), e(CLR_SUB),
              n(нач, bold=True, bg=CLR_SUB),
              n(авн, bold=True, bg=CLR_SUB),
              n(шт,  bold=True, bg=CLR_SUB),
              n(выд, bold=True, bg=CLR_SUB),
              e(CLR_SUB)))
        A(blank())

    # Производство — итого обе точки
    p_нач = ZB_TOT[0] + OVIR_TOT[0]
    p_авн = ZB_TOT[1] + OVIR_TOT[1]
    p_шт  = ZB_TOT[2] + OVIR_TOT[2]
    p_выд = ZB_TOT[3] + OVIR_TOT[3]
    A(row(h("ИТОГО ПРОИЗВОДСТВО (ЗБ + ОВИР)", bg=CLR_MID, align="LEFT", fs=14),
          e(CLR_MID), e(CLR_MID),
          n(p_нач, bold=True, bg=CLR_MID, fg=CLR_WHITE),
          n(p_авн, bold=True, bg=CLR_MID, fg=CLR_WHITE),
          n(p_шт,  bold=True, bg=CLR_MID, fg=CLR_WHITE),
          n(p_выд, bold=True, bg=CLR_MID, fg=CLR_WHITE),
          e(CLR_MID)))
    A(blank())
    A(blank())

    # Администрация
    A(row(sec("АДМИНИСТРАТИВНЫЙ ПЕРСОНАЛ"), *[e(CLR_MID)] * 7))
    A(row(*[h(col) for col in COLS]))
    for grp, admin_list, adm_tot, pt in [
        ("— ЗБ (Лохути) —",       ADMIN_ZB,   ZB_ADM_TOT,   "ЗБ"),
        ("— ОВИР (Турсунзода) —",  ADMIN_OVIR, OVIR_ADM_TOT, "ОВИР"),
    ]:
        A(row(c(grp, bold=True, italic=True, bg=CLR_GREY),
              *[e(CLR_GREY)] * 7))
        for фио, должность, точка, нач, флаг in admin_list:
            is_dup = "ДУБЛЬ" in флаг
            bg = CLR_FLAG if is_dup else (CLR_WARN if флаг else None)
            A(row(c(должность, bg=bg), c(фио, bg=bg),
                  c(точка, bg=bg, align="CENTER"), n(нач, bg=bg),
                  e(bg), e(bg), e(bg),
                  c(флаг, bg=bg, italic=bool(флаг))))
        нач, выд = adm_tot
        A(row(c(f"ИТОГО {pt} — администрация", bold=True, bg=CLR_SUB),
              e(CLR_SUB), e(CLR_SUB),
              n(нач, bold=True, bg=CLR_SUB),
              e(CLR_SUB), e(CLR_SUB),
              n(выд, bold=True, bg=CLR_SUB),
              c("Включает дубли — см. флаги", italic=True, bg=CLR_SUB)))
        A(blank())

    # Итоговая сводка
    adm_нач = ZB_ADM_TOT[0] + OVIR_ADM_TOT[0]
    adm_выд = ZB_ADM_TOT[1] + OVIR_ADM_TOT[1]
    grand_нач = p_нач + adm_нач
    grand_выд = p_выд + adm_выд
    lc_pct = p_нач / 350000 * 100
    lc_color = {"red": 0.8, "green": 0.1, "blue": 0.1} if lc_pct > 25 else {"red": 0.1, "green": 0.5, "blue": 0.1}

    A(row(h("ИТОГОВАЯ СВОДКА ФОТ АПРЕЛЬ 2026", bg=CLR_DARK), *[e(CLR_DARK)] * 7))
    A(row(c("Производство — начислено", bold=True),
          e(), e(),
          n(p_нач, bold=True), n(p_авн, bold=True), n(p_шт, bold=True), n(p_выд, bold=True),
          e()))
    A(row(c("Администрация — начислено (вкл. дубли)", bold=True),
          e(), e(),
          n(adm_нач, bold=True, fg={"red": 0.7, "green": 0.2, "blue": 0.2}),
          e(), e(),
          n(adm_выд, bold=True, fg={"red": 0.7, "green": 0.2, "blue": 0.2}),
          c("⚠️ требует корректировки", italic=True)))
    A(row(c("ИТОГО ФОТ (до корректировок дублей)", bold=True, bg=CLR_SUB),
          e(CLR_SUB), e(CLR_SUB),
          n(grand_нач, bold=True, bg=CLR_SUB),
          e(CLR_SUB), e(CLR_SUB),
          n(grand_выд, bold=True, bg=CLR_SUB),
          e(CLR_SUB)))
    A(blank())
    A(row(c("% ФОТ производство от выручки", bold=True),
          e(), e(),
          c("Выручка апрель ≈ 350 000 с*", italic=True),
          e(), e(),
          c(f"Labor Cost: ~{lc_pct:.1f}%  (цель: 17%)", bold=True, fg=lc_color),
          c("* приблизительно из Poster", italic=True)))
    A(blank())
    A(blank())

    # Флаги
    A(row(h("⚠️  ФЛАГИ — К УТОЧНЕНИЮ ДО ВЫПЛАТЫ", bg=CLR_RED, fs=16),
          *[e(CLR_RED)] * 7))
    A(row(*[h(col, bg={"red": 0.55, "green": 0.12, "blue": 0.12})
            for col in ["#", "ФИО", "Описание", "Действие", "", "", "", ""]]))
    for num, фио, desc, action in FLAGS:
        A(row(c(num, bold=True, align="CENTER"),
              c(фио, bold=True),
              c(desc, bg=CLR_WARN),
              c(action, bg=CLR_FLAG, italic=True),
              e(), e(), e(), e()))

    return rows


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession

    print("Авторизация...")
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS,
        scopes=["https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"])
    session = AuthorizedSession(creds)

    print("Получаем метаданные файла...")
    r = session.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}?fields=sheets.properties")
    meta = r.json()

    sheet_id = None
    for sh in meta.get("sheets", []):
        if sh["properties"]["title"] == SHEET_TITLE:
            sheet_id = sh["properties"]["sheetId"]
            break

    if sheet_id is None:
        print(f"❌ Лист '{SHEET_TITLE}' не найден!")
        return
    print(f"Лист найден, sheetId={sheet_id}")

    all_rows = build_rows()
    print(f"Строк к записи: {len(all_rows)}")

    # Очистка
    session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": [{"updateCells": {
            "range": {"sheetId": sheet_id},
            "fields": "userEnteredValue,userEnteredFormat"
        }}]}))

    # Запись + форматирование
    requests = [{
        "updateCells": {
            "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
            "rows": all_rows,
            "fields": "userEnteredValue,userEnteredFormat"
        }
    }]

    # Ширины столбцов: Должность|ФИО|Точка|Нач|Авн|Штраф|К выдаче|Примечание
    for i, px in enumerate([155, 195, 65, 110, 90, 90, 110, 310]):
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                          "startIndex": i, "endIndex": i + 1},
                "properties": {"pixelSize": px},
                "fields": "pixelSize"
            }
        })

    # Закрепить строку заголовка
    requests.append({
        "updateSheetProperties": {
            "properties": {"sheetId": sheet_id,
                           "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"
        }
    })

    r2 = session.post(
        f"https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}:batchUpdate",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"requests": requests}))

    if r2.status_code == 200:
        print("✅ Сводка пересобрана!")
        print(f"https://docs.google.com/spreadsheets/d/{SS_ID}/edit#gid={sheet_id}")
    else:
        print(f"❌ Ошибка {r2.status_code}: {r2.text[:500]}")


if __name__ == "__main__":
    main()
