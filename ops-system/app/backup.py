#!/usr/bin/env python3
"""Резервные копии таблиц.

Все данные системы живут в Google-таблицах. Одно неверное движение —
удалённый лист, сортировка не того диапазона, случайная вставка поверх —
и восстановить нечего. История версий Google спасает от правки, но не от
удаления файла и не от того, что ошибку заметили через месяц.

Раз в сутки делаем копию каждой таблицы в отдельную папку. Копии дневные
хранятся две недели, копия первого числа остаётся навсегда — так через
полгода можно вернуться к состоянию на начало любого месяца.

ЧЕСТНОЕ ОГРАНИЧЕНИЕ: копии лежат в том же Google-аккаунте. Это защищает
от ошибок в данных, но не от потери самого аккаунта. Для второго рубежа
нужна выгрузка наружу — отдельная задача.
"""
import datetime
import os

from . import config as C
from . import storage as S

DRIVE = 'https://www.googleapis.com/drive/v3/files'
FOLDER_NAME = 'Резервные копии'
KEEP_DAYS = int(os.environ.get('BACKUP_KEEP_DAYS', '14'))

# что копируем: подпись → id таблицы. Задаётся переменной окружения,
# чтобы у другого клиента был свой список без правки кода.
def targets():
    raw = os.environ.get('BACKUP_SHEETS', '').strip()
    if raw:
        out = {}
        for part in raw.split(','):
            if '=' in part:
                name, sid = part.split('=', 1)
                out[name.strip()] = sid.strip()
        return out
    # по умолчанию — только та таблица, с которой работает система
    return {'Операционные данные': C.DATA_SHEET} if C.DATA_SHEET else {}


def _folder(parent=None):
    """Папка для копий. Создаётся один раз."""
    s = S.session()
    parent = parent or os.environ.get('BACKUP_PARENT', '').strip()
    q = (f"name = '{FOLDER_NAME}' and mimeType = "
         "'application/vnd.google-apps.folder' and trashed = false")
    if parent:
        q += f" and '{parent}' in parents"
    r = s.get(DRIVE, params={'q': q, 'fields': 'files(id)',
                             'supportsAllDrives': True,
                             'includeItemsFromAllDrives': True}, timeout=60)
    files = r.json().get('files', []) if r.ok else []
    if files:
        return files[0]['id']
    meta = {'name': FOLDER_NAME,
            'mimeType': 'application/vnd.google-apps.folder'}
    if parent:
        meta['parents'] = [parent]
    r = s.post(DRIVE, params={'supportsAllDrives': True, 'fields': 'id'},
               json=meta, timeout=60)
    r.raise_for_status()
    return r.json()['id']


def _copy(sid, name, folder):
    s = S.session()
    r = s.post(f'{DRIVE}/{sid}/copy',
               params={'supportsAllDrives': True, 'fields': 'id,name'},
               json={'name': name, 'parents': [folder]}, timeout=180)
    r.raise_for_status()
    return r.json()


def _old_copies(folder):
    """Все копии в папке: (id, имя, дата) — по имени, а не по времени файла."""
    s = S.session()
    out, page = [], None
    while True:
        params = {'q': f"'{folder}' in parents and trashed = false",
                  'fields': 'nextPageToken,files(id,name)',
                  'pageSize': 200, 'supportsAllDrives': True,
                  'includeItemsFromAllDrives': True}
        if page:
            params['pageToken'] = page
        r = s.get(DRIVE, params=params, timeout=60)
        if not r.ok:
            return out
        j = r.json()
        for f in j.get('files', []):
            # имя вида «Операционные данные — 2026-08-20»
            tail = f['name'].rsplit('—', 1)[-1].strip()
            try:
                d = datetime.date.fromisoformat(tail[:10])
            except ValueError:
                continue
            out.append((f['id'], f['name'], d))
        page = j.get('nextPageToken')
        if not page:
            return out


def cleanup(folder):
    """Дневные копии старше KEEP_DAYS удаляем. Копии первого числа — оставляем."""
    s = S.session()
    edge = C.today() - datetime.timedelta(days=KEEP_DAYS)
    killed = 0
    for fid, name, d in _old_copies(folder):
        if d >= edge or d.day == 1:
            continue
        r = s.delete(f'{DRIVE}/{fid}', params={'supportsAllDrives': True},
                     timeout=60)
        if r.ok or r.status_code == 204:
            killed += 1
    return killed


PHOTO_KEEP_DAYS = int(os.environ.get('PHOTO_KEEP_DAYS', '30'))


def photos_cleanup():
    """Селфи прихода и снимки чек-листов старше 30 дней — удаляем.

    Решение Азиза 21.08.2026. Смысл фото — подтвердить, что пришёл именно
    этот человек, и он исчерпывается за пару дней. Хранить вечно снимки
    лиц сотрудников — лишний риск и лишний повод для разговоров.
    """
    if not C.PHOTO_FOLDER:
        return 0
    s = S.session()
    edge = (C.now() - datetime.timedelta(days=PHOTO_KEEP_DAYS))
    killed, page = 0, None
    while True:
        params = {'q': f"'{C.PHOTO_FOLDER}' in parents and trashed = false "
                       f"and modifiedTime < '{edge.strftime('%Y-%m-%dT%H:%M:%S')}Z'",
                  'fields': 'nextPageToken,files(id)', 'pageSize': 200,
                  'supportsAllDrives': True, 'includeItemsFromAllDrives': True}
        if page:
            params['pageToken'] = page
        r = s.get(DRIVE, params=params, timeout=60)
        if not r.ok:
            return killed
        j = r.json()
        for f in j.get('files', []):
            d = s.delete(f'{DRIVE}/{f["id"]}',
                         params={'supportsAllDrives': True}, timeout=60)
            if d.ok or d.status_code == 204:
                killed += 1
        page = j.get('nextPageToken')
        if not page:
            return killed


def run():
    """Сделать копии и подчистить старые. → отчёт строкой."""
    tg = targets()
    if not tg:
        # Копировать нечего, но фото чистить всё равно надо: срок хранения
        # не должен зависеть от того, настроены копии или нет.
        try:
            shots = photos_cleanup()
        except Exception as e:
            return f'Резервное копирование не настроено. Чистка фото: {e}'
        return ('Резервное копирование: не задано, что копировать.'
                + (f' Удалено фото старше {PHOTO_KEEP_DAYS} дней: {shots}.'
                   if shots else ''))
    folder = _folder()
    day = C.today().isoformat()
    done, failed = [], []
    for name, sid in tg.items():
        try:
            _copy(sid, f'{name} — {day}', folder)
            done.append(name)
        except Exception as e:
            failed.append(f'{name}: {e}')
    try:
        killed = cleanup(folder)
    except Exception as e:
        killed = f'ошибка: {e}'
    L = [f'💾 <b>Резервная копия · {C.day_str()}</b>']
    if done:
        L.append('Скопировано: ' + ', '.join(done))
    if failed:
        L.append('⚠️ Не скопировалось:')
        L += ['   · ' + f for f in failed]
    L.append(f'<i>Удалено старых: {killed}. Дневные храним {KEEP_DAYS} дней, '
             f'копии первого числа — навсегда.</i>')
    try:
        shots = photos_cleanup()
        if shots:
            L.append(f'<i>Удалено фото старше {PHOTO_KEEP_DAYS} дней: {shots}.</i>')
    except Exception as e:
        L.append(f'⚠️ Чистка фото не прошла: {e}')
    return '\n'.join(L)


def folder_url():
    try:
        return f'https://drive.google.com/drive/folders/{_folder()}'
    except Exception:
        return ''
