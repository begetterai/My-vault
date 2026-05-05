#!/usr/bin/env python3
"""Создаёт Google Doc «Азиз — Цели 2026–2029» в папке Личное."""
import os, sys, json, time
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from doc_styles import DOCS_FONT, DOCS_SIZE_BODY, DOCS_SIZE_HEADING, DOCS_LINE_SPACING

CREDS     = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'romashka-drive.json')
FOLDER_ID = '1O6XiVG-P30ZFjJaOr9HcK0wvE9z33Tfs'   # Личное

CONTENT = """\
АЗИЗ — ЦЕЛИ 2026–2029. ПРАЙМ ВЕРСИЯ

ВЕКТОР 2029

Тело
Вес 90 кг, жирность 15–18%, тело пропорционально прокачено.
Зубы: импланты + брекеты — завершено.
Нос: выпрямлена перегородка, устранена асимметрия.
Уши: исправлена лопоухость.
Кожа: рубцы и постакне убраны, гладкая кожа.
ЖКТ: дисбактериоз вылечен, здоровое пищеварение.
Стиль: casual business, со вкусом.

Деньги
Доход от $20 000 в месяц.
Источники: бизнес в общепите + трейдинг + долгосрочные инвестиции.
Долгов нет. Работающий капитал.

Бизнес и статус
Ромашка автоматизирована, не требует ежедневного присутствия.
Мини-завод полуфабрикатов работает, есть внешние клиенты.
2–3 бизнес-направления, не только общепит.
Окружение — элита страны: верные партнёры, полезные связи.
Социальная узнаваемость, репутация человека которому хотят помочь.
Активные соцсети с понятным образом и аудиторией.

Жизнь
Душанбе + Казахстан/Узбекистан — живу между странами.
Постоянно в движении и росте — это главный драйвер.
Рядом девушка/жена которая понимает и соответствует.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2026 — ФУНДАМЕНТ

Цель года: убрать всё что мешает расти

Деньги
    ☐  Закрыть долг 80 000 с — до 31 декабря 2026
    ☐  Доход: выйти на 20 000 с/мес стабильно (зарплата + 10% с прибыли Ромашки)
    ☐  Не брать новых долгов

Ромашка
    ☐  Автоматизировать процессы и контроль (уже идёт)
    ☐  Настроить еженедельную отчётность от управляющих
    ☐  Закрыть все пробелы систематизации (To-Do таблица)

Здоровье
    ☐  ЖКТ: пройти обследование, вылечить дисбактериоз — до июля
    ☐  Кожа: записаться к дерматологу, начать лечение — до июня
    ☐  Зубы: импланты по плану, не откладывать
    ☐  Зал: 4 тренировки в неделю — не меньше

Трейдинг
    ☐  Выбрать одно обучение и пройти до конца — до сентября
    ☐  Изучить одну стратегию вглубь
    ☐  Торговать только на демо-счёте — до конца года

Соцсети
    ☐  Определить тему и образ — до июня
    ☐  Минимум 1 пост в неделю — с июля

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2027 — МАСШТАБ

Цель года: первые деньги вне зарплаты

Деньги
    ☐  Доход $3 000 в месяц
    ☐  Долг закрыт → начать откладывать капитал на трейдинг
    ☐  Первый реальный торговый счёт — с чёткими правилами

Бизнес
    ☐  Мини-завод полуфабрикатов: запущен, первые внешние клиенты
    ☐  Ромашка: +1 новая точка открыта
    ☐  Ромашка работает без ежедневного участия Азиза

Здоровье и внешность
    ☐  Нос или уши — одна из двух операций
    ☐  Кожа: видимый результат от лечения
    ☐  Тело: прогресс по жировой прослойке (ближе к 15–18%)

Соцсети и связи
    ☐  Понятный образ, растущая аудитория
    ☐  Первые поездки в Казахстан/Узбекистан, полезные знакомства

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2028–2029 — ПРАЙМ

Цель: всё сходится

Деньги
    ☐  Доход $10 000 → $20 000 в месяц
    ☐  Трейдинг: стабильный результат, основной источник дохода
    ☐  Работающий инвестиционный портфель

Внешность
    ☐  Все операции завершены
    ☐  Зубы: брекеты сняты, результат
    ☐  Кожа чистая

Жизнь
    ☐  Живу между странами
    ☐  Окружение и репутация сформированы
    ☐  Ромашка и цех работают без меня как операционный актив

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ПРАВИЛА

1. Долги — враг. Пока долг есть, новых не брать.
2. Трейдинг — только после обучения и только на свободные деньги.
3. Здоровье не ждёт. Каждый отложенный визит к врачу стоит дороже.
4. Фокус = 3 приоритета на квартал, не 10.
5. Окружение определяет потолок. Менять среду осознанно.
6. Я в постоянном движении — это не проблема, это топливо.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Версия 1.0  •  Азиз  •  Май 2026
"""


def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/drive',
                       'https://www.googleapis.com/auth/documents'])
    return AuthorizedSession(creds)


def create_doc(s):
    r = s.post(
        'https://www.googleapis.com/drive/v3/files?supportsAllDrives=true',
        json={'name': 'Азиз — Цели 2026–2029',
              'mimeType': 'application/vnd.google-apps.document',
              'parents': [FOLDER_ID]},
        timeout=30)
    data = r.json()
    if 'id' not in data:
        raise RuntimeError(f'Create failed: {data}')
    doc_id = data['id']
    print(f'  Создан: https://docs.google.com/document/d/{doc_id}/edit')
    return doc_id


def insert_text(s, doc_id):
    r = s.post(
        f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
        json={'requests': [{'insertText': {'location': {'index': 1}, 'text': CONTENT}}]},
        timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f'insertText: {r.status_code} {r.text[:200]}')


def apply_styles(s, doc_id):
    r = s.get(f'https://docs.googleapis.com/v1/documents/{doc_id}', timeout=20)
    body = r.json()['body']['content']
    end  = body[-1]['endIndex'] - 1

    HEADINGS = {'АЗИЗ', 'ВЕКТОР', 'ТЕЛО', 'ДЕНЬГИ', 'БИЗНЕС', 'ЖИЗНЬ',
                'ПРАВИЛА', 'РОМАШКА', 'ЗДОРОВЬЕ', 'ТРЕЙДИНГ', 'СОЦСЕТИ'}

    requests = [
        {'updateDocumentStyle': {'documentStyle': {
            'pageSize': {'width': {'magnitude': 595.28, 'unit': 'PT'},
                         'height': {'magnitude': 841.89, 'unit': 'PT'}},
            'marginTop':    {'magnitude': 56.70, 'unit': 'PT'},
            'marginBottom': {'magnitude': 56.70, 'unit': 'PT'},
            'marginLeft':   {'magnitude': 85.05, 'unit': 'PT'},
            'marginRight':  {'magnitude': 42.52, 'unit': 'PT'},
        }, 'fields': 'pageSize,marginTop,marginBottom,marginLeft,marginRight'}},
        {'updateTextStyle': {
            'range': {'startIndex': 1, 'endIndex': end},
            'textStyle': {'weightedFontFamily': {'fontFamily': DOCS_FONT},
                          'fontSize': {'magnitude': DOCS_SIZE_BODY, 'unit': 'PT'}},
            'fields': 'weightedFontFamily,fontSize'}},
        {'updateParagraphStyle': {
            'range': {'startIndex': 1, 'endIndex': end},
            'paragraphStyle': {'lineSpacing': DOCS_LINE_SPACING,
                               'spaceAbove': {'magnitude': 3, 'unit': 'PT'}},
            'fields': 'lineSpacing,spaceAbove'}},
    ]

    YEAR_BLOCKS = {'2026', '2027', '2028'}

    for elem in body:
        if 'paragraph' not in elem:
            continue
        text = ''.join(
            e.get('textRun', {}).get('content', '')
            for e in elem['paragraph'].get('elements', [])
        ).strip()

        si, ei = elem['startIndex'], elem['endIndex']

        # Главный заголовок
        if text.startswith('АЗИЗ —'):
            requests += [
                {'updateTextStyle': {'range': {'startIndex': si, 'endIndex': ei - 1},
                                     'textStyle': {'bold': True, 'fontSize': {'magnitude': 20, 'unit': 'PT'}},
                                     'fields': 'bold,fontSize'}},
                {'updateParagraphStyle': {'range': {'startIndex': si, 'endIndex': ei},
                                          'paragraphStyle': {'alignment': 'CENTER', 'spaceAbove': {'magnitude': 0, 'unit': 'PT'}, 'spaceBelow': {'magnitude': 8, 'unit': 'PT'}},
                                          'fields': 'alignment,spaceAbove,spaceBelow'}},
            ]
        # Годовые заголовки (2026, 2027, 2028–2029)
        elif any(text.startswith(y) for y in YEAR_BLOCKS) or text.startswith('2028–'):
            requests += [
                {'updateTextStyle': {'range': {'startIndex': si, 'endIndex': ei - 1},
                                     'textStyle': {'bold': True, 'fontSize': {'magnitude': DOCS_SIZE_HEADING, 'unit': 'PT'}},
                                     'fields': 'bold,fontSize'}},
                {'updateParagraphStyle': {'range': {'startIndex': si, 'endIndex': ei},
                                          'paragraphStyle': {'alignment': 'CENTER', 'spaceAbove': {'magnitude': 14, 'unit': 'PT'}, 'spaceBelow': {'magnitude': 4, 'unit': 'PT'}},
                                          'fields': 'alignment,spaceAbove,spaceBelow'}},
            ]
        # Блок-заголовки внутри (ВЕКТОР, ДЕНЬГИ и т.д.)
        elif (text.isupper() and len(text) > 2 and not text.startswith('━')
              and any(text.startswith(h) for h in HEADINGS)):
            requests += [
                {'updateTextStyle': {'range': {'startIndex': si, 'endIndex': ei - 1},
                                     'textStyle': {'bold': True, 'fontSize': {'magnitude': 14, 'unit': 'PT'}},
                                     'fields': 'bold,fontSize'}},
                {'updateParagraphStyle': {'range': {'startIndex': si, 'endIndex': ei},
                                          'paragraphStyle': {'spaceAbove': {'magnitude': 10, 'unit': 'PT'}, 'spaceBelow': {'magnitude': 2, 'unit': 'PT'}},
                                          'fields': 'spaceAbove,spaceBelow'}},
            ]
        # Подзаголовок «Цель года»
        elif text.startswith('Цель года:') or text.startswith('Цель:'):
            requests.append(
                {'updateTextStyle': {'range': {'startIndex': si, 'endIndex': ei - 1},
                                     'textStyle': {'bold': True, 'italic': True},
                                     'fields': 'bold,italic'}})

    r2 = s.post(f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
                json={'requests': requests}, timeout=30)
    if r2.status_code != 200:
        raise RuntimeError(f'Styles: {r2.status_code} {r2.text[:200]}')


def main():
    s = get_session()
    print('Создаю документ...')
    doc_id = create_doc(s)
    time.sleep(1)
    print('Вставляю текст...')
    insert_text(s, doc_id)
    time.sleep(1)
    print('Применяю стили...')
    apply_styles(s, doc_id)
    print(f'\nГотово! https://docs.google.com/document/d/{doc_id}/edit')
    return doc_id


if __name__ == '__main__':
    main()
