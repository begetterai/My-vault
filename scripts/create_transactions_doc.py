#!/usr/bin/env python3
"""
Создаёт Google Doc «Ромашка — Протокол проверки транзакций Poster»
в папке 02.3_Менеджмент.
Описывает правила проверки скрипта check_transactions.py.
"""
import json, os, sys, time
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from doc_styles import DOCS_FONT, DOCS_SIZE_BODY, DOCS_SIZE_HEADING, DOCS_LINE_SPACING, DOCS_INDENT

CREDS     = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'romashka-drive.json')
FOLDER_ID = '1ydA0H1FVEI0mTtPo_AwYHqVknRCQedx_'   # 02.3_Менеджмент

CAT_DOC_URL = 'https://docs.google.com/document/d/1pFqgbDmThuQF2qvtG_oqMY7BrNd81rt-bKynycv7g4s/edit'

CONTENT = """\
РОМАШКА — ПРОТОКОЛ ПРОВЕРКИ ТРАНЗАКЦИЙ POSTER

ЧТО ЭТО

Еженедельный автоматический контроль транзакций в Poster для обеих точек (ЗБ и ОВИР). Скрипт check_transactions.py проверяет корректность расходных операций по 6 правилам и выводит список нарушений с подробностями.

Кто запускает: операционный директор или уполномоченный администратор.
Когда запускать: каждый понедельник за прошедшую неделю.
Кто исправляет: управляющий соответствующей точки, не позднее суток после получения отчёта.

ЗАПУСК СКРИПТА

python3 scripts/check_transactions.py --week
python3 scripts/check_transactions.py 2026-05-01 2026-05-31

Скрипт выводит отчёт в терминале. Строки с символом «→» — комментарий к конкретной транзакции.

БЛОК 1 — НЕТ КОММЕНТАРИЯ

Что нарушено: расходная транзакция внесена без текстового описания.
Правило: каждый расход должен иметь чёткое описание — что, кому и зачем.
Исключения: Переводы, Внесения в кассу, Открытие ФС — для них комментарий необязателен.
Что делать: открыть Poster → Финансы → найти транзакцию → нажать «Редактировать» → добавить описание.
Срок исправления: в тот же рабочий день.

БЛОК 2 — ПРОЧИЕ РАСХОДЫ

Что нарушено: использована категория «Прочие расходы».
Правило: данная категория — крайнее средство, только когда ни одна из 20 стандартных категорий не подходит. Использование «Прочих расходов» более 3 раз в месяц является нарушением.
Что делать: открыть транзакцию → выбрать правильную категорию по справочнику. Если описание короткое — дополнить его.
Срок исправления: в течение 24 часов.
Справочник категорий: см. документ «Ромашка — Категории расходов в Poster».

БЛОК 3 — ПЕРЕВОДЫ БЕЗ ОПИСАНИЯ

Что нарушено: внутренний перевод между счетами оформлен без указания источника и назначения.
Правило: каждый перевод должен содержать описание по формату: откуда → куда, причина.
Примеры правильных комментариев:
    ☐  «Касса ЗБ → Сейф. Инкассация за день»
    ☐  «Сейф → Касса ОВИР. Размен для смены»
    ☐  «Р/с → Алиф карта. Оплата аренды за май»
Что делать: добавить описание в поле «Комментарий» транзакции.
Срок исправления: в тот же рабочий день.

БЛОК 4 — КРУПНАЯ ТРАНЗАКЦИЯ БЕЗ ОПИСАНИЯ

Что нарушено: расход на сумму более 5 000 сомони внесён без подробного описания (менее 10 символов).
Правило: крупные расходы требуют максимальной прозрачности.
Что делать: добавить описание минимум 2–3 строки: что куплено/оплачено, кому, на основании чего (договор, счёт, устная договорённость с кем).
Срок исправления: немедленно.

БЛОК 5 — ВЕРОЯТНО НЕВЕРНАЯ КАТЕГОРИЯ

Что нарушено: ключевые слова в комментарии указывают на другую категорию, чем выбранная.
Правило: категория должна точно соответствовать характеру расхода.
Примеры флагов скрипта:
    ☐  «Доставка блендера с Китая» в категории «Расходы на заведение» → должно быть в «Расходы на логистику»
    ☐  «Вода для кулера» в «Прочие расходы» → должно быть в «Хозяйственные расходы»
    ☐  «Мясо Пакистанское» в «Расходы на заведение» → должно быть в «Поставки»
Что делать: исправить категорию. При сомнении — см. справочник категорий.
Срок исправления: в течение 24 часов.

БЛОК 6 — ВОЗМОЖНЫЙ ДУБЛЬ

Что нарушено: две транзакции с одинаковыми суммой, категорией, комментарием и датой.
Правило: дублирование расходов недопустимо — искажает финансовую отчётность.
Что делать: проверить наличие двух записей в Poster → удалить лишнюю.
Срок исправления: немедленно.

ИТОГИ И ОТЧЁТНОСТЬ

После исправления всех нарушений управляющий сообщает об этом в рабочем чате.
При систематических нарушениях (более 10 ошибок в месяц по одному типу) — депремирование по шкале ФОТ.

Количество нарушений фиксируется в трекере контроля управляющих (Блок 4 — Замечания).

СПРАВОЧНИКИ

Категории расходов Poster: %(cat_url)s

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Версия 1.0  •  Ромашка  •  Май 2026
""" % {'cat_url': CAT_DOC_URL}


def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/drive',
                       'https://www.googleapis.com/auth/documents'])
    return AuthorizedSession(creds)


def create_doc(s):
    r = s.post(
        'https://www.googleapis.com/drive/v3/files?supportsAllDrives=true',
        headers={'Content-Type': 'application/json'},
        data=json.dumps({
            'name': 'Ромашка — Протокол проверки транзакций Poster (V.1)',
            'mimeType': 'application/vnd.google-apps.document',
            'parents': [FOLDER_ID],
        }), timeout=30)
    resp = r.json()
    if 'id' not in resp:
        raise RuntimeError(f'Drive create failed: {resp}')
    doc_id = resp['id']
    print(f'  Создан: https://docs.google.com/document/d/{doc_id}/edit')
    return doc_id


def insert_text(s, doc_id, text):
    r = s.post(
        f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
        json={'requests': [{'insertText': {'location': {'index': 1}, 'text': text}}]},
        timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f'insertText → {r.status_code}: {r.text[:300]}')


def apply_styles(s, doc_id):
    r = s.get(f'https://docs.googleapis.com/v1/documents/{doc_id}', timeout=20)
    doc  = r.json()
    body = doc['body']['content']
    end  = body[-1]['endIndex'] - 1

    requests = [
        {'updateDocumentStyle': {
            'documentStyle': {
                'pageSize': {
                    'width':  {'magnitude': 595.28, 'unit': 'PT'},
                    'height': {'magnitude': 841.89, 'unit': 'PT'},
                },
                'marginTop':    {'magnitude': 56.70, 'unit': 'PT'},
                'marginBottom': {'magnitude': 56.70, 'unit': 'PT'},
                'marginLeft':   {'magnitude': 85.05, 'unit': 'PT'},
                'marginRight':  {'magnitude': 42.52, 'unit': 'PT'},
            },
            'fields': 'pageSize,marginTop,marginBottom,marginLeft,marginRight'
        }},
        {'updateTextStyle': {
            'range': {'startIndex': 1, 'endIndex': end},
            'textStyle': {
                'weightedFontFamily': {'fontFamily': DOCS_FONT},
                'fontSize': {'magnitude': DOCS_SIZE_BODY, 'unit': 'PT'},
            },
            'fields': 'weightedFontFamily,fontSize'
        }},
        {'updateParagraphStyle': {
            'range': {'startIndex': 1, 'endIndex': end},
            'paragraphStyle': {
                'alignment': 'JUSTIFIED',
                'lineSpacing': DOCS_LINE_SPACING,
                'spaceAbove': {'magnitude': 4, 'unit': 'PT'},
            },
            'fields': 'alignment,lineSpacing,spaceAbove'
        }},
    ]

    BLOCK_HEADINGS = {'БЛОК', 'ЧТО ЭТО', 'ЗАПУСК', 'ИТОГИ', 'СПРАВОЧНИКИ',
                      'РОМАШКА', 'ВЕРСИЯ'}

    for elem in body:
        if 'paragraph' not in elem:
            continue
        para = elem['paragraph']
        text = ''.join(
            e.get('textRun', {}).get('content', '')
            for e in para.get('elements', [])
        ).strip()

        is_heading = (
            any(text.startswith(h) for h in BLOCK_HEADINGS) and
            text.isupper() and len(text) > 3 and not text.startswith('━')
        )
        if not is_heading:
            continue

        s_idx = elem['startIndex']
        e_idx = elem['endIndex']
        requests += [
            {'updateTextStyle': {
                'range': {'startIndex': s_idx, 'endIndex': e_idx - 1},
                'textStyle': {
                    'bold': True,
                    'fontSize': {'magnitude': DOCS_SIZE_HEADING, 'unit': 'PT'},
                },
                'fields': 'bold,fontSize'
            }},
            {'updateParagraphStyle': {
                'range': {'startIndex': s_idx, 'endIndex': e_idx},
                'paragraphStyle': {
                    'alignment': 'CENTER',
                    'spaceAbove': {'magnitude': 12, 'unit': 'PT'},
                    'spaceBelow': {'magnitude': 6, 'unit': 'PT'},
                },
                'fields': 'alignment,spaceAbove,spaceBelow'
            }},
        ]

    r2 = s.post(
        f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
        json={'requests': requests}, timeout=30)
    if r2.status_code != 200:
        raise RuntimeError(f'applyStyles → {r2.status_code}: {r2.text[:200]}')


def main():
    s = get_session()
    print('Создаю документ...')
    doc_id = create_doc(s)
    time.sleep(1)
    print('Вставляю текст...')
    insert_text(s, doc_id, CONTENT)
    time.sleep(1)
    print('Применяю стили...')
    apply_styles(s, doc_id)
    print(f'\nГотово! ID: {doc_id}')
    return doc_id


if __name__ == '__main__':
    main()
