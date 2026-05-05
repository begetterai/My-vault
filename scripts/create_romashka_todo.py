#!/usr/bin/env python3
"""Создаёт Google Sheets «Ромашка — Систематизация: To-Do» в папке AI."""
import os, sys, json, time
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS     = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'romashka-drive.json')
FOLDER_ID = '14NnVXa9k1h0dyS-vNch61A3-aSpJG_Jn'   # AI → Ромашка

FONT  = 'Times New Roman'

def rgb(r, g, b): return {'red': r/255, 'green': g/255, 'blue': b/255}

C_HEADER  = rgb(20,  43,  75)    # тёмно-синий
C_BLOCK1  = rgb(31,  73, 125)    # финансы
C_BLOCK2  = rgb(68, 114, 196)    # операции
C_BLOCK3  = rgb(84, 130,  53)    # персонал
C_BLOCK4  = rgb(197, 90,  17)    # меню
C_BLOCK5  = rgb(112,  48, 160)   # склад
C_BLOCK6  = rgb(0,  112, 192)    # аналитика
C_BLOCK7  = rgb(192,   0,   0)   # маркетинг
C_BLOCK8  = rgb(64,  64,  64)    # юридическое
C_WHITE   = rgb(255, 255, 255)
C_DONE    = rgb(198, 239, 206)   # зелёный — готово
C_WIP     = rgb(255, 242, 204)   # жёлтый — в процессе
C_TODO    = rgb(255, 199, 206)   # красный — не начато
C_LGRAY   = rgb(242, 242, 242)

STATUS_DONE = '✅ Готово'
STATUS_WIP  = '🔄 В процессе'
STATUS_TODO = '❌ Не начато'
P1, P2, P3 = 'P1', 'P2', 'P3'

# ── ДАННЫЕ ────────────────────────────────────────────────────────────────────
# (блок, задача, статус, приоритет, комментарий)
TASKS = [
    # ── БЛОК 1: ФИНАНСОВЫЙ УЧЁТ ──────────────────────────────────────────────
    ('БЛОК 1 — ФИНАНСОВЫЙ УЧЁТ', None, None, None, None),
    ('', 'Super P&L 2026 (ЗБ + ОВИР + Свод + KPI + Cash Flow)', STATUS_DONE, P1, 'ID: 16aX_684tTXpRuuK1bR37DswcJMWdSixhmq-0zxhXFp8'),
    ('', 'KPI дашборд с целями (EBITDA 25%, целевая выручка)', STATUS_DONE, P1, 'Обновлён май 2026'),
    ('', 'Дневной трекер выручки — авто из Poster (ЗБ + ОВИР)', STATUS_DONE, P1, 'Cron 23:00 ежедневно'),
    ('', 'Проверка транзакций еженедельно (check_transactions.py)', STATUS_DONE, P1, '6 правил, обе точки'),
    ('', 'Протокол проверки транзакций (Google Doc)', STATUS_DONE, P2, 'Папка 02.3_Менеджмент'),
    ('', 'Справочник категорий расходов Poster (Google Doc)', STATUS_DONE, P2, 'С реальными отклонениями'),
    ('', 'Cash Flow ежемесячный (шаблон + автозаполнение)', STATUS_WIP, P1, 'Структура есть в P&L, нужен отдельный лист'),
    ('', 'Бюджет по точкам на месяц (план vs факт)', STATUS_TODO, P1, 'Исходить из целевой выручки и ФОТ-норм'),
    ('', 'Трекер дебиторки/кредиторки (долги поставщикам)', STATUS_TODO, P2, 'Кто должен нам и мы кому'),
    ('', 'Автогенерация P&L 1-го числа каждого месяца (cron)', STATUS_TODO, P2, 'Скрипт есть, нужен cron'),
    ('', 'Финансовая модель: unit economics, break-even по точке', STATUS_TODO, P2, 'Сколько гостей нужно в день для безубыточности'),
    ('', 'Сверка Poster ↔ реальная касса (ежедневно)', STATUS_TODO, P1, 'Фиксировать расхождения'),

    # ── БЛОК 2: ОПЕРАЦИОННЫЕ СТАНДАРТЫ (SOP) ─────────────────────────────────
    ('БЛОК 2 — ОПЕРАЦИОННЫЕ СТАНДАРТЫ (SOP)', None, None, None, None),
    ('', 'SOP Управляющий V.1 (ЗБ + ОВИР)', STATUS_DONE, P1, 'Создан апрель 2026'),
    ('', 'SOP Открытие смены', STATUS_TODO, P1, 'Пошагово: касса, склад, персонал, Poster'),
    ('', 'SOP Закрытие смены', STATUS_TODO, P1, 'Инкассация, сверка, Poster, уборка'),
    ('', 'SOP Кассовая дисциплина', STATUS_TODO, P1, 'Нал, безнал, возвраты, ошибки'),
    ('', 'SOP Приём товара', STATUS_TODO, P1, 'Взвешивание, качество, оформление в Poster'),
    ('', 'SOP Onboarding нового сотрудника', STATUS_TODO, P1, '1-3-7-30 дней: что знает, что умеет'),
    ('', 'SOP Старший повар', STATUS_TODO, P1, 'Зона ответственности, контроль цеха'),
    ('', 'SOP Составление заявки с цеха', STATUS_TODO, P2, 'Когда, кому, в каком формате'),
    ('', 'SOP Работа с Poster (для персонала)', STATUS_TODO, P2, 'Как вносить расходы, комментарии, переводы'),
    ('', 'SOP Внешний вид и дресс-код', STATUS_TODO, P2, 'Стандарты для всех должностей'),
    ('', 'Чек-лист открытия смены (для управляющего)', STATUS_TODO, P1, 'Распечатать и повесить на точке'),
    ('', 'Чек-лист закрытия смены (для управляющего)', STATUS_TODO, P1, 'Распечатать и повесить на точке'),
    ('', 'Протокол ЧП и инцидентов (что делать если...)', STATUS_TODO, P2, 'Пожар, кража, конфликт, поломка оборудования'),
    ('', 'Регламент работы с жалобами гостей', STATUS_TODO, P2, 'Скрипт ответа, компенсация, эскалация'),

    # ── БЛОК 3: ПЕРСОНАЛ ──────────────────────────────────────────────────────
    ('БЛОК 3 — ПЕРСОНАЛ', None, None, None, None),
    ('', 'Ведомость на выдачу ЗП (ЗБ + ОВИР, подписи)', STATUS_DONE, P1, 'Скрипт create_vedomost.py'),
    ('', 'Анализ ФОТ: скрипт + ежемесячный отчёт', STATUS_DONE, P1, 'Флаги нарушений автоматически'),
    ('', 'Трекер контроля управляющих (4 блока)', STATUS_DONE, P1, 'ID: 1cE276utk4bGPAxlmO6TejV-GYCLNj5UI2WyjRUODC4A'),
    ('', 'База сотрудников: все точки, должности, ставки, документы', STATUS_TODO, P1, 'Google Sheets: ФИО, должность, ставка, дата найма, статус'),
    ('', 'KPI по каждой должности (измеримые показатели)', STATUS_TODO, P1, 'Управляющий, повар, кассир, уборщик'),
    ('', 'Система штрафов и бонусов — единый документ', STATUS_TODO, P1, 'Прозрачная шкала, все подписали'),
    ('', 'Программа обучения нового сотрудника', STATUS_TODO, P1, '1-3-7-30 дней: тесты, проверки'),
    ('', 'Программа обучения управляющего', STATUS_TODO, P1, 'Финансы, Poster, управление командой'),
    ('', 'Шаблон графика работы (по точкам)', STATUS_TODO, P2, 'С учётом пиков (Чт-Пт у ЗБ, Пт у ОВИР)'),
    ('', 'Трудовые договоры: актуальные, оцифрованы, в Drive', STATUS_TODO, P2, 'Проверить у всех сотрудников'),
    ('', 'Список сотрудников уволенных за последний год', STATUS_TODO, P3, 'Причины, чтобы видеть паттерны текучки'),

    # ── БЛОК 4: МЕНЮ И СЕБЕСТОИМОСТЬ ─────────────────────────────────────────
    ('БЛОК 4 — МЕНЮ И СЕБЕСТОИМОСТЬ', None, None, None, None),
    ('', 'Меню в Poster: все блюда с ценами (194 позиции, ЗБ)', STATUS_DONE, P1, 'Poster ЗБ актуален'),
    ('', 'Ингредиенты в Poster: 169 позиций с себестоимостью', STATUS_DONE, P1, 'Poster ЗБ'),
    ('', 'ТТК (техкарты) для всех блюд — формально оформлены', STATUS_TODO, P1, 'Граммовки, ингредиенты, выход, фото'),
    ('', 'Food Cost таблица: себестоимость каждого блюда', STATUS_TODO, P1, 'Обновляется при изменении цен поставщиков'),
    ('', 'Анализ меню: прибыльность × популярность (Stars/Dogs)', STATUS_TODO, P1, 'Что продвигать, что убрать, что переосмыслить'),
    ('', 'Ценообразование: пересмотр с учётом текущих цен сырья', STATUS_TODO, P1, 'Последний раз когда делалось?'),
    ('', 'Меню ОВИР: отдельная версия или унификация с ЗБ', STATUS_TODO, P2, 'Сейчас разные — нужно решение'),
    ('', 'Сезонные позиции и акции: план на полгода вперёд', STATUS_TODO, P3, 'Лето: холодные напитки, мороженое и т.д.'),

    # ── БЛОК 5: СКЛАД И ПОСТАВКИ ─────────────────────────────────────────────
    ('БЛОК 5 — СКЛАД И ПОСТАВКИ', None, None, None, None),
    ('', 'Остатки склада через Poster API (реальное время)', STATUS_DONE, P1, '221 позиция, storage.getStorageLeftovers'),
    ('', 'Минимальные остатки: настроить лимиты в Poster', STATUS_TODO, P1, 'Сейчас у всех лимит = 0, алертов нет'),
    ('', 'База поставщиков: контакты, условия, сроки оплаты', STATUS_TODO, P1, 'ЗБ: Бахори, Пакистанское мясо, Танхо, Бон Фри…'),
    ('', 'Сравнение цен поставщиков (таблица обновляемая)', STATUS_TODO, P1, 'Видеть кто дорожает, искать альтернативы'),
    ('', 'Договоры с поставщиками: оцифрованы, в Drive', STATUS_TODO, P2, 'Условия, отсрочки, ответственность'),
    ('', 'Протокол инвентаризации (как, когда, кто)', STATUS_TODO, P1, 'Частота: ежемесячно или после каждой поставки'),
    ('', 'График инвентаризаций на год', STATUS_TODO, P2, 'Фиксированные даты, ответственные'),
    ('', 'Протокол и документ по списаниям', STATUS_TODO, P1, 'Причины, кто подписывает, как в Poster'),
    ('', 'Анализ поставок: ЗБ vs ОВИР — кто дешевле закупает', STATUS_TODO, P2, 'ОВИР берёт с ЗБ — возможно невыгодно'),

    # ── БЛОК 6: АНАЛИТИКА И КОНТРОЛЬ ─────────────────────────────────────────
    ('БЛОК 6 — АНАЛИТИКА И КОНТРОЛЬ', None, None, None, None),
    ('', 'Еженедельная проверка транзакций (автоматически)', STATUS_DONE, P1, 'check_transactions.py, 6 правил'),
    ('', 'Интеграция Poster API — обе точки (ЗБ + ОВИР)', STATUS_DONE, P1, 'Транзакции, аналитика, склад, меню'),
    ('', 'Трекер управляющих: галочки, задачи, замечания', STATUS_DONE, P1, '4 блока, ЗБ + ОВИР + Свод'),
    ('', 'Еженедельный отчёт управляющего (шаблон + ритуал)', STATUS_TODO, P1, 'Каждый пн до 10:00: выручка, гости, ЧП, план'),
    ('', 'Ежемесячный разбор: формат, участники, повестка', STATUS_TODO, P1, '1-го числа: P&L, KPI, задачи на месяц'),
    ('', 'Дашборд NSM: гости в день по точкам (реальное время)', STATUS_TODO, P1, 'Looker Studio или Sheets + Poster API'),
    ('', 'Автоматический еженедельный отчёт (скрипт + Telegram)', STATUS_TODO, P2, 'Пн утром: выручка за неделю, флаги'),
    ('', 'Лог жалоб и инцидентов (фиксировать все случаи)', STATUS_TODO, P2, 'Дата, точка, суть, решение, кто ответил'),
    ('', 'Средний чек ОВИР: план роста с 79с до 100с+', STATUS_TODO, P1, 'Апрель: 79с при цели >110с — требует анализа'),

    # ── БЛОК 7: МАРКЕТИНГ ────────────────────────────────────────────────────
    ('БЛОК 7 — МАРКЕТИНГ', None, None, None, None),
    ('', 'Стратегия соцсетей: темы, частота, визуал', STATUS_TODO, P2, 'Instagram ЗБ и ОВИР + личный Азиза'),
    ('', 'Управление отзывами: 2GIS, Google Maps (ответы)', STATUS_TODO, P2, 'Отвечать на все отзывы в течение 24 ч'),
    ('', 'Программа лояльности для постоянных гостей', STATUS_TODO, P3, 'Карта, скидка, накопительная система'),
    ('', 'Календарь акций и спецпредложений на квартал', STATUS_TODO, P3, 'Привязать к пикам (Чт-Пт) и сезону'),
    ('', 'Фотосъёмка блюд (актуальные фото меню)', STATUS_TODO, P2, 'Для соцсетей и Poster'),

    # ── БЛОК 8: ЮРИДИЧЕСКОЕ И АДМИНИСТРАТИВНОЕ ───────────────────────────────
    ('БЛОК 8 — ЮРИДИЧЕСКОЕ И АДМИНИСТРАТИВНОЕ', None, None, None, None),
    ('', 'Все договоры оцифрованы и хранятся в Drive', STATUS_TODO, P1, 'Аренда, поставщики, сотрудники, сервисы'),
    ('', 'Трекер лицензий и разрешений (даты продления)', STATUS_TODO, P1, 'Когда истекает каждая лицензия/разрешение'),
    ('', 'Договоры аренды обеих точек: условия, даты, индексация', STATUS_TODO, P1, 'ЗБ и ОВИР — когда следующее повышение'),
    ('', 'Санитарные книжки сотрудников (актуальность)', STATUS_TODO, P2, 'У всех есть? Даты продления?'),
    ('', 'Пожарная безопасность: документы, инструктажи', STATUS_TODO, P2, 'Журналы, ответственный, план эвакуации'),
]

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/drive',
                       'https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)


def create_sheet(s):
    r = s.post(
        'https://www.googleapis.com/drive/v3/files?supportsAllDrives=true',
        json={'name': 'Ромашка — Систематизация To-Do',
              'mimeType': 'application/vnd.google-apps.spreadsheet',
              'parents': [FOLDER_ID]},
        timeout=30)
    data = r.json()
    if 'id' not in data:
        raise RuntimeError(f'Create failed: {data}')
    return data['id']


def fill_data(s, ss_id):
    sid_r = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}?fields=sheets.properties', timeout=20)
    sid   = sid_r.json()['sheets'][0]['properties']['sheetId']

    # Переименовать лист
    s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
           json={'requests': [{'updateSheetProperties': {
               'properties': {'sheetId': sid, 'title': 'To-Do'},
               'fields': 'title'}}]}, timeout=20)

    # Заголовок + данные
    header = [['РОМАШКА — СИСТЕМАТИЗАЦИЯ: ЧТО НУЖНО СДЕЛАТЬ', '', '', '', '']]
    subhdr = [['Блок', 'Задача', 'Статус', 'Приоритет', 'Комментарий']]
    rows   = []
    for (blok, task, status, prio, comment) in TASKS:
        if task is None:   # заголовок блока
            rows.append([blok, '', '', '', ''])
        else:
            rows.append([blok, task, status or '', prio or '', comment or ''])

    all_rows = header + subhdr + rows
    s.put(
        f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/values/To-Do!A1'
        f'?valueInputOption=USER_ENTERED',
        json={'values': all_rows}, timeout=30)

    return sid, len(all_rows)


def format_sheet(s, ss_id, sid, total_rows):
    requests = []

    # Ширина колонок
    widths = [220, 420, 130, 90, 300]
    for i, w in enumerate(widths):
        requests.append({'updateDimensionProperties': {
            'range': {'sheetId': sid, 'dimension': 'COLUMNS',
                      'startIndex': i, 'endIndex': i+1},
            'properties': {'pixelSize': w},
            'fields': 'pixelSize'}})

    # Заморозить 2 строки
    requests.append({'updateSheetProperties': {
        'properties': {'sheetId': sid, 'gridProperties': {'frozenRowCount': 2}},
        'fields': 'gridProperties.frozenRowCount'}})

    def cell_fmt(r0, r1, c0, c1, bold=False, bg=None, fg=C_WHITE, fs=11,
                 halign='LEFT', valign='MIDDLE', wrap='WRAP'):
        tf = {'fontFamily': FONT, 'fontSize': fs, 'bold': bold,
              'foregroundColor': fg}
        cf = {'textFormat': tf, 'horizontalAlignment': halign,
              'verticalAlignment': valign, 'wrapStrategy': wrap}
        if bg: cf['backgroundColor'] = bg
        return {'repeatCell': {
            'range': {'sheetId': sid, 'startRowIndex': r0, 'endRowIndex': r1,
                      'startColumnIndex': c0, 'endColumnIndex': c1},
            'cell': {'userEnteredFormat': cf},
            'fields': 'userEnteredFormat(textFormat,horizontalAlignment,verticalAlignment,wrapStrategy,backgroundColor)'}}

    # Строка-заголовок (row 0)
    requests.append(cell_fmt(0, 1, 0, 5, bold=True, bg=C_HEADER, fg=C_WHITE, fs=14, halign='CENTER'))

    # Sub-header (row 1)
    requests.append(cell_fmt(1, 2, 0, 5, bold=True, bg=rgb(50,60,80), fg=C_WHITE, fs=11, halign='CENTER'))

    # Merge заголовка
    requests.append({'mergeCells': {
        'range': {'sheetId': sid, 'startRowIndex': 0, 'endRowIndex': 1,
                  'startColumnIndex': 0, 'endColumnIndex': 5},
        'mergeType': 'MERGE_ALL'}})

    # Всё тело — базовый стиль
    requests.append(cell_fmt(2, total_rows, 0, 5, bg=C_WHITE, fg=rgb(30,30,30), fs=10))

    # Блок-цвета для заголовков блоков + строк
    BLOCK_COLORS = {
        'БЛОК 1': C_BLOCK1, 'БЛОК 2': C_BLOCK2, 'БЛОК 3': C_BLOCK3,
        'БЛОК 4': C_BLOCK4, 'БЛОК 5': C_BLOCK5, 'БЛОК 6': C_BLOCK6,
        'БЛОК 7': C_BLOCK7, 'БЛОК 8': C_BLOCK8,
    }

    row_idx = 2  # после header + subheader
    current_color = C_LGRAY
    for (blok, task, status, prio, comment) in TASKS:
        if task is None:
            # Заголовок блока
            for key, color in BLOCK_COLORS.items():
                if blok.startswith(key):
                    current_color = color
                    break
            requests.append(cell_fmt(row_idx, row_idx+1, 0, 5,
                                     bold=True, bg=current_color, fg=C_WHITE, fs=11))
            requests.append({'mergeCells': {
                'range': {'sheetId': sid, 'startRowIndex': row_idx, 'endRowIndex': row_idx+1,
                          'startColumnIndex': 0, 'endColumnIndex': 5},
                'mergeType': 'MERGE_ALL'}})
        else:
            # Цвет по статусу (колонка C = статус)
            if status == STATUS_DONE:
                bg_status = C_DONE
            elif status == STATUS_WIP:
                bg_status = C_WIP
            else:
                bg_status = C_TODO
            requests.append(cell_fmt(row_idx, row_idx+1, 2, 3,
                                     bg=bg_status, fg=rgb(30,30,30), fs=10, halign='CENTER'))

            # Приоритет — колонка D
            prio_colors = {P1: rgb(255,199,206), P2: rgb(255,242,204), P3: C_LGRAY}
            requests.append(cell_fmt(row_idx, row_idx+1, 3, 4,
                                     bg=prio_colors.get(prio, C_WHITE),
                                     fg=rgb(30,30,30), fs=10, halign='CENTER'))

        row_idx += 1

    # Высота строк
    requests.append({'updateDimensionProperties': {
        'range': {'sheetId': sid, 'dimension': 'ROWS',
                  'startIndex': 2, 'endIndex': total_rows},
        'properties': {'pixelSize': 36},
        'fields': 'pixelSize'}})

    # Высота заголовка
    requests.append({'updateDimensionProperties': {
        'range': {'sheetId': sid, 'dimension': 'ROWS',
                  'startIndex': 0, 'endIndex': 1},
        'properties': {'pixelSize': 45},
        'fields': 'pixelSize'}})

    # Границы
    requests.append({'updateBorders': {
        'range': {'sheetId': sid, 'startRowIndex': 1, 'endRowIndex': total_rows,
                  'startColumnIndex': 0, 'endColumnIndex': 5},
        'innerHorizontal': {'style': 'SOLID', 'color': rgb(200,200,200), 'width': 1},
        'innerVertical':   {'style': 'SOLID', 'color': rgb(200,200,200), 'width': 1},
        'bottom': {'style': 'SOLID', 'color': rgb(150,150,150), 'width': 1},
    }})

    r = s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate',
               json={'requests': requests}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f'Format failed: {r.status_code} {r.text[:300]}')


def main():
    s = get_session()
    print('Создаю таблицу...')
    ss_id = create_sheet(s)
    print(f'  ID: {ss_id}')
    time.sleep(1)
    print('Заполняю данные...')
    sid, total_rows = fill_data(s, ss_id)
    time.sleep(1)
    print('Применяю форматирование...')
    format_sheet(s, ss_id, sid, total_rows)
    url = f'https://docs.google.com/spreadsheets/d/{ss_id}/edit'
    print(f'\nГотово!\n{url}')
    return ss_id


if __name__ == '__main__':
    main()
